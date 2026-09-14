from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any


class SchedulingPolicy(StrEnum):
    BOUND_DEVICE_FIRST = "bound_device_first"
    ANY_AVAILABLE = "any_available"
    LEAST_RECENTLY_USED = "least_recently_used"
    ROUND_ROBIN = "round_robin"
    PREFERRED_PROVIDER = "preferred_provider"


class DeviceReservationState(StrEnum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    RESTORING = "restoring"
    IN_USE = "in_use"
    ERROR = "error"


class DevicePoolState(StrEnum):
    OFFLINE = "offline"
    STARTING = "starting"
    AVAILABLE = "available"
    RESERVED = "reserved"
    RESTORING = "restoring"
    IN_USE = "in_use"
    RELEASING = "releasing"
    ERROR = "error"
    MAINTENANCE = "maintenance"


@dataclass(slots=True)
class PoolDevice:
    device_key: str
    provider: str
    external_id: str
    display_name: str
    state: DevicePoolState = DevicePoolState.OFFLINE
    is_online: bool = False
    adb_ready: bool = False
    in_maintenance: bool = False
    last_available_at: datetime | None = None
    current_account_id: str | None = None
    reservation_job_id: str | None = None
    reservation_expires_at: datetime | None = None



@dataclass(slots=True)
class AccountWorkspaceLock:
    account_id: str
    device_key: str  # Format: "provider:external_id"
    job_id: str | None
    acquired_at: datetime
    expires_at: datetime
    heartbeat: datetime

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def refresh(self, now: datetime, ttl_seconds: int = 300) -> None:
        self.heartbeat = now
        self.expires_at = now + timedelta(seconds=ttl_seconds)


@dataclass(frozen=True, slots=True)
class SnapshotMetadataRecord:
    id: str
    account_id: str
    path: str
    size_bytes: int
    schema_version: str
    checksum: str
    device_profile_id: str | None
    preferred_app: str
    notes: str
    created_at: datetime
    last_restored_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AccountWorkspaceSnapshot:
    id: str
    account_id: str
    display_name: str
    platform_uid: str
    primary_email_masked: str
    phone_masked: str
    preferred_app: str
    locale: str
    timezone: str
    schema_version: str
    created_at: datetime
    device_profile_id: str | None = None
    device_preferences: dict[str, Any] = field(default_factory=dict)
    qa_profile_ref: str | None = None
    vault_secret_refs: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    checksum: str = ""
    size_bytes: int = 0


@dataclass(slots=True)
class QueuedRestoreItem:
    account_id: str
    requested_device_id: str | None
    scheduling_policy: SchedulingPolicy
    preferred_app: str
    priority: int
    enqueued_at: datetime
    status: str = "queued"  # "queued", "restoring", "completed", "failed", "cancelled"
    assigned_device_key: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class DevicePoolPolicy:
    id: str
    name: str
    policy: SchedulingPolicy
    preferred_provider_order: tuple[str, ...] = ("ldplayer", "mumu", "physical")
    allow_fallback: bool = True
    max_concurrent_restores: int = 2
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

