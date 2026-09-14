"""Domain models for publishing campaigns and multi-destination targeting."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from sp_farms.domain.composer import PostType, PublishDestinationType


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    WAITING_APPROVAL = "waiting_approval"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class TargetStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class SchedulePolicyType(StrEnum):
    IMMEDIATE = "immediate"
    SCHEDULED_ONCE = "scheduled_once"
    STAGGERED = "staggered"


class ApprovalPolicy(StrEnum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


@dataclass(frozen=True, slots=True)
class SchedulePolicy:
    policy_type: SchedulePolicyType = SchedulePolicyType.IMMEDIATE
    scheduled_at: datetime | None = None
    stagger_interval_seconds: int = 0  # Interval between targets if STAGGERED


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: int = 60
    allow_retry_on_network_error: bool = True


@dataclass(frozen=True, slots=True)
class CampaignTarget:
    """Individual destination target within a campaign."""

    id: str
    campaign_id: str
    destination_type: PublishDestinationType
    destination_id: str
    destination_name: str
    status: TargetStatus = TargetStatus.PENDING
    attempt_count: int = 0
    published_post_id: str | None = None
    error_message: str | None = None
    executed_at: datetime | None = None
    scheduled_at: datetime | None = None

    @classmethod
    def create(
        cls,
        campaign_id: str,
        destination_type: PublishDestinationType,
        destination_id: str,
        destination_name: str,
        scheduled_at: datetime | None = None,
    ) -> "CampaignTarget":
        return cls(
            id=str(uuid.uuid4()),
            campaign_id=campaign_id,
            destination_type=destination_type,
            destination_id=destination_id,
            destination_name=destination_name,
            status=TargetStatus.PENDING,
            attempt_count=0,
            published_post_id=None,
            error_message=None,
            executed_at=None,
            scheduled_at=scheduled_at,
        )


@dataclass(frozen=True, slots=True)
class CampaignReportSummary:
    """Aggregated execution summary for a campaign."""

    total_targets: int
    pending_targets: int
    running_targets: int
    successful_targets: int
    failed_targets: int
    skipped_targets: int
    completion_percentage: float


@dataclass(frozen=True, slots=True)
class Campaign:
    """Multi-destination publishing campaign entity."""

    id: str
    title: str
    content_item_id: str | None
    post_type: PostType
    caption: str
    media_asset_ids: tuple[str, ...]
    status: CampaignStatus
    schedule_policy: SchedulePolicy
    approval_policy: ApprovalPolicy
    retry_policy: RetryPolicy
    created_at: datetime
    updated_at: datetime
    targets: tuple[CampaignTarget, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""
    archived_at: datetime | None = None

    @classmethod
    def create(
        cls,
        title: str,
        post_type: PostType = PostType.FEED,
        caption: str = "",
        content_item_id: str | None = None,
        media_asset_ids: Sequence[str] = (),
        schedule_policy: SchedulePolicy | None = None,
        approval_policy: ApprovalPolicy = ApprovalPolicy.MANUAL,
        retry_policy: RetryPolicy | None = None,
        tags: Sequence[str] = (),
        notes: str = "",
        targets: Sequence[CampaignTarget] = (),
        created_at: datetime | None = None,
    ) -> "Campaign":
        now = created_at or datetime.now()
        return cls(
            id=str(uuid.uuid4()),
            title=title.strip(),
            content_item_id=content_item_id,
            post_type=post_type,
            caption=caption,
            media_asset_ids=tuple(media_asset_ids),
            status=CampaignStatus.DRAFT,
            schedule_policy=schedule_policy or SchedulePolicy(),
            approval_policy=approval_policy,
            retry_policy=retry_policy or RetryPolicy(),
            created_at=now,
            updated_at=now,
            targets=tuple(targets),
            tags=tuple(tags),
            notes=notes,
            archived_at=None,
        )

    def generate_summary(self) -> CampaignReportSummary:
        total = len(self.targets)
        if total == 0:
            return CampaignReportSummary(0, 0, 0, 0, 0, 0, 0.0)

        pending = sum(1 for t in self.targets if t.status == TargetStatus.PENDING)
        running = sum(1 for t in self.targets if t.status == TargetStatus.RUNNING)
        success = sum(1 for t in self.targets if t.status == TargetStatus.SUCCESS)
        failed = sum(1 for t in self.targets if t.status == TargetStatus.FAILED)
        skipped = sum(1 for t in self.targets if t.status == TargetStatus.SKIPPED)

        completed_count = success + failed + skipped
        pct = (completed_count / total) * 100.0

        return CampaignReportSummary(
            total_targets=total,
            pending_targets=pending,
            running_targets=running,
            successful_targets=success,
            failed_targets=failed,
            skipped_targets=skipped,
            completion_percentage=round(pct, 1),
        )

    def evaluate_status_transition(self) -> CampaignStatus:
        """Evaluate and return appropriate campaign status based on current state and targets."""
        if self.status in (
            CampaignStatus.DRAFT,
            CampaignStatus.PAUSED,
            CampaignStatus.ARCHIVED,
        ):
            return self.status

        summary = self.generate_summary()
        if summary.total_targets == 0:
            return self.status

        if summary.running_targets > 0:
            return CampaignStatus.RUNNING

        if summary.pending_targets == summary.total_targets:
            if self.approval_policy == ApprovalPolicy.MANUAL and self.status in (
                CampaignStatus.DRAFT,
                CampaignStatus.WAITING_APPROVAL,
            ):
                return CampaignStatus.WAITING_APPROVAL
            if self.schedule_policy.policy_type != SchedulePolicyType.IMMEDIATE:
                return CampaignStatus.SCHEDULED
            return CampaignStatus.READY

        if summary.pending_targets > 0:
            return CampaignStatus.RUNNING

        # All targets processed (success / failed / skipped)
        if summary.successful_targets == summary.total_targets:
            return CampaignStatus.COMPLETED
        elif summary.successful_targets > 0:
            return CampaignStatus.PARTIALLY_COMPLETED
        elif summary.failed_targets > 0 or summary.skipped_targets > 0:
            return CampaignStatus.FAILED

        return self.status
