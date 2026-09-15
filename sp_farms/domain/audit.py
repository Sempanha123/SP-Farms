from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from sp_farms.domain.redaction import redact_data, redact_text


class AuditResult(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    WARNING = "warning"
    CANCELLED = "cancelled"


class AuditTargetType(StrEnum):
    ACCOUNT = "account"
    DEVICE = "device"
    JOB = "job"
    PAGE = "page"
    GROUP = "group"
    VAULT = "vault"
    SYSTEM = "system"


class AuditAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    IMPORT = "import"
    EXPORT = "export"
    RESTORE = "restore"
    SYNC = "sync"
    BACKUP = "backup"
    REAUTH = "reauth"
    ASSIGN = "assign"
    EXECUTE = "execute"
    CANCEL = "cancel"
    RETRY = "retry"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: str
    initiator: str  # "operator", "worker", "scheduler", "system"
    action: str  # e.g. "account.create", "job.retry", "asset.sync"
    target_type: str  # e.g. "account", "device", "job"
    target_id: str
    timestamp: datetime
    result: AuditResult
    error_code: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    job_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        id: str,
        initiator: str,
        action: str,
        target_type: str,
        target_id: str,
        timestamp: datetime,
        result: AuditResult,
        error_code: str | None = None,
        error_message: str | None = None,
        retry_count: int = 0,
        job_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> "AuditEvent":
        """Create an AuditEvent with automatic secret redaction applied."""
        clean_msg = redact_text(error_message) if error_message else None
        clean_details = redact_data(details or {}) if details else {}
        return cls(
            id=id,
            initiator=initiator,
            action=action,
            target_type=target_type,
            target_id=target_id,
            timestamp=timestamp,
            result=result,
            error_code=error_code,
            error_message=clean_msg,
            retry_count=retry_count,
            job_id=job_id,
            details=clean_details,
        )


@dataclass(frozen=True, slots=True)
class ErrorDiagnosticEntry:
    id: str
    title: str
    error_code: str
    friendly_summary: str
    technical_details: str
    safe_recovery_suggestion: str
    timestamp: datetime
    target_type: str
    target_id: str
    initiator: str
    retry_count: int = 0
    job_id: str | None = None
    is_retryable: bool = True
    context_data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_audit(cls, audit: AuditEvent) -> "ErrorDiagnosticEntry":
        technical = audit.error_message or "No technical stacktrace or message provided."
        summary, suggestion, retryable = _diagnose_error(audit.error_code, technical)

        return cls(
            id=audit.id,
            title=f"Error {audit.error_code or 'UNKNOWN'}: {audit.action}",
            error_code=audit.error_code or "UNKNOWN_ERROR",
            friendly_summary=summary,
            technical_details=redact_text(technical),
            safe_recovery_suggestion=suggestion,
            timestamp=audit.timestamp,
            target_type=audit.target_type,
            target_id=audit.target_id,
            initiator=audit.initiator,
            retry_count=audit.retry_count,
            job_id=audit.job_id,
            is_retryable=retryable,
            context_data=audit.details,
        )


def _diagnose_error(error_code: str | None, details: str) -> tuple[str, str, bool]:
    """Provide user-friendly summaries, recovery suggestions, and retryable checks for errors."""
    code = (error_code or "").upper()
    det = details.lower()

    if "AUTH_EXPIRED" in code or "190" in code or "expired" in det:
        return (
            "The authorization session or Meta access token has expired.",
            "Generate a new authorization session via the Security Center or Accounts workspace.",
            False,
        )
    if "RATE_LIMIT" in code or "4" in code or "17" in code or "rate limit" in det:
        return (
            "Meta Graph API or system rate limit exceeded.",
            "Pause publishing and wait for cool-down window to elapse before retrying.",
            True,
        )
    if "DEVICE_OFFLINE" in code or "offline" in det or "adb connection" in det:
        return (
            "The target Android emulator or physical device is disconnected.",
            "Verify USB connection, emulator state, and ADB connectivity in Device Manager.",
            True,
        )
    if "CHALLENGE_REQUIRED" in code or "checkpoint" in det or "captcha" in det:
        return (
            "Security challenge or device checkpoint triggered on the account.",
            "DO NOT bypass. Open device emulator to resolve the challenge manually.",
            False,
        )
    if "VAULT_ERROR" in code or "keyring" in det:
        return (
            "Unable to access credentials in OS Keyring / Windows Credential Manager.",
            "Verify Windows user permissions and ensure the secure vault is unlocked.",
            True,
        )

    # Generic fallback
    return (
        "An unexpected operation failure occurred.",
        "Inspect the technical details and diagnostics. If transient, trigger a safe retry.",
        True,
    )
