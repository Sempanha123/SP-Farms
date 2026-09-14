from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any


class AssetPermission(StrEnum):
    MANAGE = "MANAGE"
    CREATE_CONTENT = "CREATE_CONTENT"
    MODERATE = "MODERATE"
    MESSAGING = "MESSAGING"
    ANALYZE = "ANALYZE"
    ADVERTISE = "ADVERTISE"
    ADMIN = "ADMIN"
    MODERATOR = "MODERATOR"
    MEMBER = "MEMBER"


class AssetHealthState(StrEnum):
    HEALTHY = "healthy"
    NEEDS_ATTENTION = "needs_attention"
    RESTRICTED = "restricted"
    STALE = "stale"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class Page:
    id: str
    account_id: str
    page_id: str
    name: str
    category: str | None = None
    tasks: tuple[str, ...] = field(default_factory=tuple)
    access_token_ref: str | None = None
    can_publish: bool = True
    followers_count: int = 0
    likes_count: int = 0
    link: str | None = None
    health: AssetHealthState = AssetHealthState.HEALTHY
    last_synced_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def has_task(self, task: str | AssetPermission) -> bool:
        task_str = task.value if isinstance(task, AssetPermission) else task
        return task_str.upper() in (t.upper() for t in self.tasks)

    def is_publishing_eligible(self) -> bool:
        if self.health != AssetHealthState.HEALTHY:
            return False
        if not self.can_publish:
            return False
        # Manage or Create Content grants publishing eligibility
        return self.has_task(AssetPermission.MANAGE) or self.has_task(
            AssetPermission.CREATE_CONTENT
        )

    def is_stale(self, threshold_hours: int = 24) -> bool:
        if self.last_synced_at is None:
            return True
        cutoff = datetime.now(UTC) - timedelta(hours=threshold_hours)
        return self.last_synced_at < cutoff

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "account_id": self.account_id,
            "page_id": self.page_id,
            "name": self.name,
            "category": self.category,
            "tasks": list(self.tasks),
            "access_token_ref": self.access_token_ref,
            "can_publish": self.can_publish,
            "followers_count": self.followers_count,
            "likes_count": self.likes_count,
            "link": self.link,
            "health": self.health.value,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class Group:
    id: str
    account_id: str
    group_id: str
    name: str
    privacy: str = "PUBLIC"  # PUBLIC, CLOSED, SECRET
    role: str = "MEMBER"  # ADMIN, MODERATOR, MEMBER
    member_count: int = 0
    can_post: bool = True
    health: AssetHealthState = AssetHealthState.HEALTHY
    last_synced_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_admin(self) -> bool:
        return self.role.upper() == AssetPermission.ADMIN.value

    def is_moderator(self) -> bool:
        return self.role.upper() in (
            AssetPermission.ADMIN.value,
            AssetPermission.MODERATOR.value,
        )

    def is_posting_eligible(self) -> bool:
        if self.health != AssetHealthState.HEALTHY:
            return False
        return self.can_post

    def is_stale(self, threshold_hours: int = 24) -> bool:
        if self.last_synced_at is None:
            return True
        cutoff = datetime.now(UTC) - timedelta(hours=threshold_hours)
        return self.last_synced_at < cutoff

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "account_id": self.account_id,
            "group_id": self.group_id,
            "name": self.name,
            "privacy": self.privacy,
            "role": self.role,
            "member_count": self.member_count,
            "can_post": self.can_post,
            "health": self.health.value,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class SyncResult:
    account_id: str
    synced_pages_count: int = 0
    synced_groups_count: int = 0
    stale_pages_count: int = 0
    stale_groups_count: int = 0
    errors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_successful(self) -> bool:
        return len(self.errors) == 0

    @property
    def has_partial_failure(self) -> bool:
        return len(self.errors) > 0 and (
            self.synced_pages_count > 0 or self.synced_groups_count > 0
        )
