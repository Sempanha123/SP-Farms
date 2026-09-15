"""Domain models for approval requests, review policies, and human-in-the-loop decisions."""

import fnmatch
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalActionType(StrEnum):
    PUBLISH_POST = "publish_post"
    CAMPAIGN_EXECUTION = "campaign_execution"
    DELETE_ASSET = "delete_asset"
    CREDENTIAL_ROTATION = "credential_rotation"
    DEVICE_WIPE = "device_wipe"
    BULK_ACTION = "bulk_action"


@dataclass(frozen=True, slots=True)
class ApprovalPolicyRule:
    """Rule defining whether a specific action requires human sign-off."""

    id: str
    action_type: ApprovalActionType
    target_pattern: str = "*"  # e.g., destination ID, campaign ID, or "*"
    require_reason: bool = False
    max_pending_hours: int = 48
    enabled: bool = True

    def matches(self, action_type: ApprovalActionType, target_id: str) -> bool:
        if not self.enabled:
            return False
        if self.action_type != action_type:
            return False
        if self.target_pattern in ("*", ""):
            return True
        return fnmatch.fnmatch(target_id, self.target_pattern)


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """Persistent request for operator authorization before executing sensitive operations."""

    id: str
    action_type: ApprovalActionType
    target_id: str
    target_name: str
    summary: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    campaign_id: str | None = None
    job_id: str | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_by: str = "system"
    reviewed_by: str | None = None
    review_notes: str | None = None
    expires_at: datetime | None = None
    decided_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        action_type: ApprovalActionType,
        target_id: str,
        target_name: str,
        summary: str,
        payload: Mapping[str, Any] | None = None,
        campaign_id: str | None = None,
        job_id: str | None = None,
        requested_by: str = "system",
        expires_in_hours: int = 48,
    ) -> "ApprovalRequest":
        now = datetime.now(UTC)
        return cls(
            id=str(uuid4()),
            action_type=action_type,
            target_id=target_id,
            target_name=target_name,
            summary=summary,
            payload=dict(payload or {}),
            campaign_id=campaign_id,
            job_id=job_id,
            status=ApprovalStatus.PENDING,
            requested_by=requested_by,
            expires_at=now + timedelta(hours=expires_in_hours) if expires_in_hours > 0 else None,
            created_at=now,
            updated_at=now,
        )

    def is_stale(self, current_time: datetime) -> bool:
        if self.status != ApprovalStatus.PENDING:
            return False
        if self.expires_at is None:
            return False
        return current_time > self.expires_at

    def approve(self, reviewer: str, notes: str = "") -> "ApprovalRequest":
        if self.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot approve request with status '{self.status}'")
        now = datetime.now(UTC)
        return ApprovalRequest(
            id=self.id,
            action_type=self.action_type,
            target_id=self.target_id,
            target_name=self.target_name,
            summary=self.summary,
            payload=self.payload,
            campaign_id=self.campaign_id,
            job_id=self.job_id,
            status=ApprovalStatus.APPROVED,
            requested_by=self.requested_by,
            reviewed_by=reviewer,
            review_notes=notes,
            expires_at=self.expires_at,
            decided_at=now,
            created_at=self.created_at,
            updated_at=now,
        )

    def reject(self, reviewer: str, notes: str = "") -> "ApprovalRequest":
        if self.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot reject request with status '{self.status}'")
        now = datetime.now(UTC)
        return ApprovalRequest(
            id=self.id,
            action_type=self.action_type,
            target_id=self.target_id,
            target_name=self.target_name,
            summary=self.summary,
            payload=self.payload,
            campaign_id=self.campaign_id,
            job_id=self.job_id,
            status=ApprovalStatus.REJECTED,
            requested_by=self.requested_by,
            reviewed_by=reviewer,
            review_notes=notes,
            expires_at=self.expires_at,
            decided_at=now,
            created_at=self.created_at,
            updated_at=now,
        )

    def expire(self) -> "ApprovalRequest":
        if self.status != ApprovalStatus.PENDING:
            return self
        now = datetime.now(UTC)
        return ApprovalRequest(
            id=self.id,
            action_type=self.action_type,
            target_id=self.target_id,
            target_name=self.target_name,
            summary=self.summary,
            payload=self.payload,
            campaign_id=self.campaign_id,
            job_id=self.job_id,
            status=ApprovalStatus.EXPIRED,
            requested_by=self.requested_by,
            reviewed_by="system",
            review_notes="Approval request expired automatically",
            expires_at=self.expires_at,
            decided_at=now,
            created_at=self.created_at,
            updated_at=now,
        )
