"""Domain models for scheduling, calendar views, and publishing time windows."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta, tzinfo
from enum import StrEnum
from uuid import uuid4
from zoneinfo import ZoneInfo

from sp_farms.domain.composer import PostType, PublishDestinationType


class ScheduledItemStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    MISSED = "missed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class SchedulePriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class PublishingWindow:
    """Time window and quiet hours configuration for a destination or global schedule."""

    start_time: time = time(8, 0)  # 08:00
    end_time: time = time(22, 0)  # 22:00
    timezone_name: str = "UTC"
    quiet_hours_start: time = time(22, 0)
    quiet_hours_end: time = time(8, 0)
    days_of_week: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6)  # Monday=0, Sunday=6

    def is_within_window(self, dt: datetime) -> bool:
        """Check if datetime falls within allowed publishing window and outside quiet hours."""
        tz: tzinfo = UTC
        if self.timezone_name not in ("UTC", "Etc/UTC", "Z", ""):
            try:
                tz = ZoneInfo(self.timezone_name)
            except Exception:
                tz = UTC

        local_dt = dt.astimezone(tz)
        if local_dt.weekday() not in self.days_of_week:
            return False

        t = local_dt.time()
        # Check window
        if self.start_time <= self.end_time:
            if not (self.start_time <= t <= self.end_time):
                return False
        else:  # Overnight window
            if not (t >= self.start_time or t <= self.end_time):
                return False

        # Check quiet hours
        if self.quiet_hours_start < self.quiet_hours_end:
            if self.quiet_hours_start <= t < self.quiet_hours_end:
                return False
        else:  # Overnight quiet hours
            if t >= self.quiet_hours_start or t < self.quiet_hours_end:
                return False

        return True

    def next_valid_slot(self, from_dt: datetime, step_minutes: int = 15) -> datetime:
        """Find the earliest valid datetime in or after from_dt within publishing window."""
        candidate = from_dt
        # Search up to 14 days ahead in step_minutes intervals
        max_steps = (14 * 24 * 60) // step_minutes
        for _ in range(max_steps):
            if self.is_within_window(candidate):
                return candidate
            candidate += timedelta(minutes=step_minutes)
        return from_dt


@dataclass(frozen=True, slots=True)
class ScheduleConflict:
    """Represents a scheduling conflict between two items."""

    existing_item_id: str
    conflicting_item_id: str
    destination_id: str
    scheduled_time: datetime
    reason: str


@dataclass(frozen=True, slots=True)
class ScheduledItem:
    """A distinct publishing task scheduled for a specific destination and time."""

    id: str
    title: str
    campaign_id: str | None
    content_item_id: str | None
    destination_type: PublishDestinationType
    destination_id: str
    destination_name: str
    scheduled_at: datetime
    post_type: PostType = PostType.FEED
    caption: str = ""
    media_asset_ids: tuple[str, ...] = ()
    status: ScheduledItemStatus = ScheduledItemStatus.QUEUED
    priority: SchedulePriority = SchedulePriority.NORMAL
    timezone_name: str = "UTC"
    retry_count: int = 0
    max_retries: int = 3
    error_message: str | None = None
    executed_at: datetime | None = None
    tags: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        title: str,
        destination_type: PublishDestinationType,
        destination_id: str,
        destination_name: str,
        scheduled_at: datetime,
        campaign_id: str | None = None,
        content_item_id: str | None = None,
        post_type: PostType = PostType.FEED,
        caption: str = "",
        media_asset_ids: Sequence[str] = (),
        priority: SchedulePriority = SchedulePriority.NORMAL,
        timezone_name: str = "UTC",
        max_retries: int = 3,
        tags: Sequence[str] = (),
    ) -> "ScheduledItem":
        now = datetime.now(UTC)
        # Ensure scheduled_at is UTC
        if scheduled_at.tzinfo is None:
            utc_scheduled = scheduled_at.replace(tzinfo=UTC)
        else:
            utc_scheduled = scheduled_at.astimezone(UTC)

        return cls(
            id=str(uuid4()),
            title=title,
            campaign_id=campaign_id,
            content_item_id=content_item_id,
            destination_type=destination_type,
            destination_id=destination_id,
            destination_name=destination_name,
            scheduled_at=utc_scheduled,
            post_type=post_type,
            caption=caption,
            media_asset_ids=tuple(media_asset_ids),
            priority=priority,
            timezone_name=timezone_name,
            max_retries=max_retries,
            tags=tuple(tags),
            created_at=now,
            updated_at=now,
        )

    def is_missed(self, current_time: datetime, grace_period_minutes: int = 15) -> bool:
        """Returns True if the item was due before current_time - grace_period and hasn't run."""
        if self.status != ScheduledItemStatus.QUEUED:
            return False
        cutoff = current_time - timedelta(minutes=grace_period_minutes)
        return self.scheduled_at < cutoff


def detect_conflicts(
    items: Sequence[ScheduledItem],
    min_interval_minutes: int = 10,
) -> Sequence[ScheduleConflict]:
    """Detect collisions where multiple items target same destination within min interval."""
    conflicts: list[ScheduleConflict] = []
    # Group active items by destination
    by_dest: dict[str, list[ScheduledItem]] = {}
    for item in items:
        if item.status in (ScheduledItemStatus.QUEUED, ScheduledItemStatus.PAUSED):
            by_dest.setdefault(item.destination_id, []).append(item)

    min_delta = timedelta(minutes=min_interval_minutes)

    for dest_id, dest_items in by_dest.items():
        sorted_items = sorted(dest_items, key=lambda x: x.scheduled_at)
        for i in range(len(sorted_items) - 1):
            curr = sorted_items[i]
            next_item = sorted_items[i + 1]
            diff = next_item.scheduled_at - curr.scheduled_at
            if diff < min_delta:
                spacing_min = int(diff.total_seconds() // 60)
                conflicts.append(
                    ScheduleConflict(
                        existing_item_id=curr.id,
                        conflicting_item_id=next_item.id,
                        destination_id=dest_id,
                        scheduled_time=next_item.scheduled_at,
                        reason=(
                            f"Spacing between '{curr.title}' and '{next_item.title}' is "
                            f"{spacing_min}m (minimum required: {min_interval_minutes}m)"
                        ),
                    )
                )

    return tuple(conflicts)
