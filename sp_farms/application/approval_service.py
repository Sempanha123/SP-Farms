"""Approval service orchestrating human-in-the-loop review, policy matching, and job transitions."""

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from sp_farms.application.approval_repository import ApprovalRepositoryPort
from sp_farms.application.audit_service import AuditService
from sp_farms.application.job_service import JobService
from sp_farms.application.ports import Clock
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.approvals import (
    ApprovalActionType,
    ApprovalPolicyRule,
    ApprovalRequest,
    ApprovalStatus,
)
from sp_farms.domain.audit import AuditResult
from sp_farms.domain.jobs import JobState
from sp_farms.domain.result import AppError, Result

logger = logging.getLogger(__name__)


class ApprovalService:
    def __init__(
        self,
        unit_of_work: Callable[[], UnitOfWork],
        approval_repo_factory: Callable[[UnitOfWork], ApprovalRepositoryPort],
        clock: Clock,
        audit_service: AuditService | None = None,
        job_service: JobService | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._repo_factory = approval_repo_factory
        self._clock = clock
        self._audit = audit_service
        self._jobs = job_service

    def requires_approval(self, action_type: ApprovalActionType, target_id: str = "*") -> bool:
        """Evaluate active policy rules to determine if action requires human sign-off."""
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            rules = repo.list_policy_rules()
            return any(r.matches(action_type, target_id) for r in rules)

    def request_approval(
        self,
        action_type: ApprovalActionType,
        target_id: str,
        target_name: str,
        summary: str,
        payload: Mapping[str, Any] | None = None,
        campaign_id: str | None = None,
        job_id: str | None = None,
        requested_by: str = "system",
        expires_in_hours: int = 48,
    ) -> Result[ApprovalRequest]:
        if not summary.strip():
            return Result.failure(
                AppError(code="INVALID_ARGUMENT", message="Approval summary cannot be empty")
            )

        req = ApprovalRequest.create(
            action_type=action_type,
            target_id=target_id,
            target_name=target_name,
            summary=summary,
            payload=payload,
            campaign_id=campaign_id,
            job_id=job_id,
            requested_by=requested_by,
            expires_in_hours=expires_in_hours,
        )

        with self._uow() as uow:
            repo = self._repo_factory(uow)
            saved = repo.save_request(req)
            uow.commit()

        if self._audit:
            self._audit.record_event(
                action="approval.requested",
                initiator=requested_by,
                target_type=action_type.value,
                target_id=target_id,
                result=AuditResult.SUCCESS,
                details={
                    "request_id": saved.id,
                    "summary": summary,
                    "campaign_id": campaign_id,
                    "job_id": job_id,
                },
            )

        return Result.success(saved)

    def approve_request(
        self,
        request_id: str,
        reviewer: str,
        notes: str = "",
    ) -> Result[ApprovalRequest]:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            req = repo.get_request(request_id)
            if req is None:
                return Result.failure(
                    AppError(code="NOT_FOUND", message=f"Approval request {request_id} not found")
                )
            if req.status != ApprovalStatus.PENDING:
                return Result.failure(
                    AppError(
                        code="INVALID_STATE",
                        message=f"Request is in {req.status} state, cannot approve",
                    )
                )

            approved = req.approve(reviewer=reviewer, notes=notes)
            saved = repo.save_request(approved)
            uow.commit()

        # Emit audit event
        if self._audit:
            self._audit.record_event(
                action="approval.approved",
                initiator=reviewer,
                target_type=saved.action_type.value,
                target_id=saved.target_id,
                result=AuditResult.SUCCESS,
                details={
                    "request_id": saved.id,
                    "notes": notes,
                    "job_id": saved.job_id,
                    "campaign_id": saved.campaign_id,
                },
            )

        # Resume / unblock linked job if present
        if saved.job_id and self._jobs:
            try:
                job = self._jobs.get_job(saved.job_id)
                if job and job.state == JobState.WAITING_APPROVAL:
                    self._jobs.transition_job(
                        job_id=saved.job_id,
                        new_state=JobState.RUNNING,
                        message="Approved by operator",
                    )
            except Exception as e:
                logger.warning(f"Could not automatically resume job {saved.job_id}: {e}")

        return Result.success(saved)

    def reject_request(
        self,
        request_id: str,
        reviewer: str,
        notes: str = "",
        cancel_job: bool = True,
    ) -> Result[ApprovalRequest]:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            req = repo.get_request(request_id)
            if req is None:
                return Result.failure(
                    AppError(code="NOT_FOUND", message=f"Approval request {request_id} not found")
                )
            if req.status != ApprovalStatus.PENDING:
                return Result.failure(
                    AppError(
                        code="INVALID_STATE",
                        message=f"Request is in {req.status} state, cannot reject",
                    )
                )

            rejected = req.reject(reviewer=reviewer, notes=notes)
            saved = repo.save_request(rejected)
            uow.commit()

        # Emit audit event
        if self._audit:
            self._audit.record_event(
                action="approval.rejected",
                initiator=reviewer,
                target_type=saved.action_type.value,
                target_id=saved.target_id,
                result=AuditResult.SUCCESS,
                details={
                    "request_id": saved.id,
                    "notes": notes,
                    "job_id": saved.job_id,
                    "campaign_id": saved.campaign_id,
                },
            )

        # Cancel linked job if requested
        if saved.job_id and cancel_job and self._jobs:
            try:
                self._jobs.cancel_job(saved.job_id)
            except Exception as e:
                logger.warning(f"Could not automatically cancel job {saved.job_id}: {e}")

        return Result.success(saved)

    def expire_stale_requests(self) -> Sequence[ApprovalRequest]:
        now = self._clock.now()
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            pending = repo.list_requests(status=ApprovalStatus.PENDING)
            expired_list: list[ApprovalRequest] = []

            for req in pending:
                if req.is_stale(now):
                    expired = req.expire()
                    saved = repo.save_request(expired)
                    expired_list.append(saved)

            uow.commit()
            return tuple(expired_list)

    def list_inbox(
        self,
        status: ApprovalStatus | None = ApprovalStatus.PENDING,
        action_type: ApprovalActionType | None = None,
        limit: int = 100,
    ) -> Sequence[ApprovalRequest]:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            return repo.list_requests(status=status, action_type=action_type, limit=limit)

    def add_policy_rule(
        self,
        rule_id: str,
        action_type: ApprovalActionType,
        target_pattern: str = "*",
        require_reason: bool = False,
        max_pending_hours: int = 48,
    ) -> ApprovalPolicyRule:
        rule = ApprovalPolicyRule(
            id=rule_id,
            action_type=action_type,
            target_pattern=target_pattern,
            require_reason=require_reason,
            max_pending_hours=max_pending_hours,
            enabled=True,
        )
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            saved = repo.save_policy_rule(rule)
            uow.commit()
            return saved

    def list_policy_rules(self) -> Sequence[ApprovalPolicyRule]:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            return repo.list_policy_rules()
