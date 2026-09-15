"""Domain models for operator-authorized account maintenance and security automation."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import uuid4


class MaintenanceTaskType(StrEnum):
    PROFILE_AUDIT = "profile_audit"
    CACHE_PURGE = "cache_purge"
    SESSION_HEALTH_CHECK = "session_health_check"
    CREDENTIAL_SYNC = "credential_sync"
    TOTP_2FA_SETUP = "totp_2fa_setup"
    PASSWORD_ROTATION_RECORD = "password_rotation_record"


class MaintenanceStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class MaintenanceAction:
    account_id: str
    task_type: MaintenanceTaskType
    id: str = field(default_factory=lambda: str(uuid4()))
    parameters: dict[str, str] = field(default_factory=dict)
    requires_operator_approval: bool = True
    status: MaintenanceStatus = MaintenanceStatus.PENDING
    dry_run: bool = False
    created_at: datetime | None = None
    executed_at: datetime | None = None
    result_summary: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class TotpCodeInfo:
    code: str
    time_remaining_seconds: int
    account_id: str
    verified: bool = True


@dataclass(frozen=True, slots=True)
class MaintenanceExecutionResult:
    action_id: str
    task_type: MaintenanceTaskType
    success: bool
    status: MaintenanceStatus
    summary: str
    dry_run: bool = False
    details: dict[str, str] = field(default_factory=dict)
    error_message: str | None = None
