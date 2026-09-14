import json
import platform
import sys
from collections.abc import Callable, Sequence
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sp_farms.application.audit_repository import AuditRepository
from sp_farms.application.ports import Clock
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.audit import (
    AuditAction,
    AuditEvent,
    AuditResult,
    AuditTargetType,
    ErrorDiagnosticEntry,
)
from sp_farms.domain.redaction import redact_data, safe_json_dumps
from sp_farms.domain.security import SecurityEvent

if TYPE_CHECKING:
    from sp_farms.application.job_service import JobService


class AuditService:
    """Coordinates audit logging, security event tracking, error diagnostics, and safe retries."""

    def __init__(
        self,
        unit_of_work: Callable[[], UnitOfWork],
        audit_repository_factory: Callable[[UnitOfWork], AuditRepository],
        clock: Clock,
        job_service: "JobService | None" = None,
    ) -> None:
        self._uow = unit_of_work
        self._repo_factory = audit_repository_factory
        self._clock = clock
        self._job_service = job_service

    def record_event(
        self,
        initiator: str,
        action: str,
        target_type: str,
        target_id: str,
        result: AuditResult,
        error_code: str | None = None,
        error_message: str | None = None,
        retry_count: int = 0,
        job_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Record an audit event with guaranteed secret redaction."""
        now = self._clock.now()
        event = AuditEvent.create(
            id=str(uuid4()),
            initiator=initiator,
            action=action,
            target_type=target_type,
            target_id=target_id,
            timestamp=now,
            result=result,
            error_code=error_code,
            error_message=error_message,
            retry_count=retry_count,
            job_id=job_id,
            details=details,
        )

        with self._uow() as uow:
            repo = self._repo_factory(uow)
            repo.add(event)
            uow.commit()

        return event

    def record_error(
        self,
        initiator: str,
        action: str,
        target_type: str,
        target_id: str,
        error_code: str,
        error_message: str,
        retry_count: int = 0,
        job_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Convenience helper to record an error or operation failure."""
        return self.record_event(
            initiator=initiator,
            action=action,
            target_type=target_type,
            target_id=target_id,
            result=AuditResult.FAILURE,
            error_code=error_code,
            error_message=error_message,
            retry_count=retry_count,
            job_id=job_id,
            details=details,
        )

    def record_security_event(self, sec_event: SecurityEvent) -> AuditEvent:
        """Transform and store a domain SecurityEvent as an AuditEvent."""
        is_warn = sec_event.severity.value in ("medium", "high", "critical")
        return self.record_event(
            initiator="security_center",
            action=f"security.{sec_event.category.value}",
            target_type=AuditTargetType.ACCOUNT if sec_event.account_id else AuditTargetType.SYSTEM,
            target_id=sec_event.account_id or "system",
            result=AuditResult.WARNING if is_warn else AuditResult.SUCCESS,
            error_code=f"SEC_{sec_event.severity.value.upper()}",
            error_message=sec_event.description,
            details={
                "title": sec_event.title,
                "remediation": sec_event.remediation,
                "resolved": sec_event.resolved,
            },
        )

    def get_event(self, event_id: str) -> AuditEvent | None:
        """Retrieve single audit event."""
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            return repo.get(event_id)

    def list_events(
        self,
        limit: int = 100,
        offset: int = 0,
        result: AuditResult | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        action: str | None = None,
    ) -> Sequence[AuditEvent]:
        """List audit events."""
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            return repo.list_events(
                limit=limit,
                offset=offset,
                result=result,
                target_type=target_type,
                target_id=target_id,
                action=action,
            )

    def list_error_diagnostics(
        self,
        limit: int = 100,
        offset: int = 0,
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> list[ErrorDiagnosticEntry]:
        """List error diagnostic entries."""
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            errors = repo.list_errors(
                limit=limit,
                offset=offset,
                target_type=target_type,
                target_id=target_id,
            )
        return [ErrorDiagnosticEntry.from_audit(err) for err in errors]

    def retry_job(self, job_id: str) -> bool:
        """Safe retry route: if job service is available, clone and re-enqueue the job."""
        if not self._job_service:
            return False

        original_job = self._job_service.get_job(job_id)
        if not original_job:
            return False

        # Create new retry job with incremented attempt
        job_result = self._job_service.create_job(
            job_type=original_job.job_type,
            target_type=original_job.target_type,
            target_id=original_job.target_id,
            max_attempts=original_job.max_attempts,
            idempotency_key=f"retry-{original_job.id}-{uuid4().hex[:6]}",
        )
        new_job = job_result[0] if isinstance(job_result, tuple) else job_result

        # Record audit trail for retry action
        self.record_event(
            initiator="operator",
            action=f"{original_job.job_type}.{AuditAction.RETRY.value}",
            target_type=original_job.target_type,
            target_id=original_job.target_id,
            result=AuditResult.SUCCESS,
            retry_count=original_job.attempt_count + 1,
            job_id=new_job.id,
            details={"original_job_id": original_job.id, "new_job_id": new_job.id},
        )
        return True

    def generate_diagnostics_bundle(self, error_id: str) -> str:
        """Produce a clean, redacted JSON diagnostics bundle suitable for troubleshooting."""
        event = self.get_event(error_id)
        if not event:
            return json.dumps({"error": f"Event {error_id} not found"})

        diag_entry = ErrorDiagnosticEntry.from_audit(event)

        bundle = {
            "sp_farms_version": "1.0.0",
            "environment": {
                "os": platform.platform(),
                "python_version": sys.version.split()[0],
                "system_time": self._clock.now().isoformat(),
            },
            "error": {
                "id": diag_entry.id,
                "code": diag_entry.error_code,
                "action": event.action,
                "friendly_summary": diag_entry.friendly_summary,
                "recovery_suggestion": diag_entry.safe_recovery_suggestion,
                "technical_details": diag_entry.technical_details,
                "target": {
                    "type": diag_entry.target_type,
                    "id": diag_entry.target_id,
                },
                "initiator": diag_entry.initiator,
                "timestamp": diag_entry.timestamp.isoformat(),
                "job_id": diag_entry.job_id,
                "retry_count": diag_entry.retry_count,
            },
            "context_details": redact_data(event.details),
        }

        return safe_json_dumps(bundle, indent=2)

    def prune_audit_logs(self, retention_days: int = 30) -> int:
        """Enforce retention policy: remove events older than retention_days."""
        cutoff = self._clock.now() - timedelta(days=retention_days)
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            pruned_count = repo.prune(cutoff)
            uow.commit()

        if pruned_count > 0:
            # Record audit of retention maintenance
            self.record_event(
                initiator="system",
                action="audit.prune_retention",
                target_type=AuditTargetType.SYSTEM,
                target_id="audit_logs",
                result=AuditResult.SUCCESS,
                details={"retention_days": retention_days, "pruned_count": pruned_count},
            )

        return pruned_count
