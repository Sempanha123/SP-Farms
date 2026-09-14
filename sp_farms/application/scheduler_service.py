"""Scheduler service for time-based publishing, conflict detection, and queue execution."""

import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

from sp_farms.application.ports import Clock
from sp_farms.application.scheduler_repository import ScheduledItemRepositoryPort
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.composer import PostType, PublishDestinationType
from sp_farms.domain.result import AppError, Result
from sp_farms.domain.scheduler import (
    PublishingWindow,
    ScheduleConflict,
    ScheduledItem,
    ScheduledItemStatus,
    SchedulePriority,
    detect_conflicts,
)

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(
        self,
        unit_of_work: Callable[[], UnitOfWork],
        scheduler_repo_factory: Callable[[UnitOfWork], ScheduledItemRepositoryPort],
        clock: Clock,
        default_window: PublishingWindow | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._repo_factory = scheduler_repo_factory
        self._clock = clock
        self._default_window = default_window or PublishingWindow()
        self._paused: bool = False

    @property
    def is_paused(self) -> bool:
        return self._paused

    def pause_all(self) -> None:
        """Pause all scheduled execution."""
        self._paused = True
        logger.info("Scheduler paused: all automatic dispatch stopped.")

    def resume_all(self) -> None:
        """Resume scheduled execution."""
        self._paused = False
        logger.info("Scheduler resumed.")

    def schedule_post(
        self,
        title: str,
        destination_type: PublishDestinationType,
        destination_id: str,
        destination_name: str,
        scheduled_at: datetime,
        post_type: PostType = PostType.FEED,
        caption: str = "",
        media_asset_ids: Sequence[str] = (),
        campaign_id: str | None = None,
        content_item_id: str | None = None,
        priority: SchedulePriority = SchedulePriority.NORMAL,
        timezone_name: str = "UTC",
        max_retries: int = 3,
        tags: Sequence[str] = (),
        window: PublishingWindow | None = None,
        auto_adjust_to_window: bool = True,
    ) -> Result[ScheduledItem]:
        if not title.strip():
            return Result.failure(
                AppError(code="INVALID_ARGUMENT", message="Scheduled item title cannot be empty")
            )

        win = window or self._default_window
        target_time = scheduled_at
        if auto_adjust_to_window and not win.is_within_window(target_time):
            target_time = win.next_valid_slot(target_time)

        item = ScheduledItem.create(
            title=title,
            destination_type=destination_type,
            destination_id=destination_id,
            destination_name=destination_name,
            scheduled_at=target_time,
            campaign_id=campaign_id,
            content_item_id=content_item_id,
            post_type=post_type,
            caption=caption,
            media_asset_ids=media_asset_ids,
            priority=priority,
            timezone_name=timezone_name,
            max_retries=max_retries,
            tags=tags,
        )

        with self._uow() as uow:
            repo = self._repo_factory(uow)
            saved = repo.save_item(item)
            uow.commit()

        return Result.success(saved)

    def reschedule_item(
        self,
        item_id: str,
        new_scheduled_at: datetime,
        check_conflicts: bool = True,
    ) -> Result[ScheduledItem]:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            item = repo.get_item(item_id)
            if item is None:
                return Result.failure(
                    AppError(code="NOT_FOUND", message=f"Scheduled item {item_id} not found")
                )

            utc_time = (
                new_scheduled_at
                if new_scheduled_at.tzinfo is not None
                else new_scheduled_at.replace(tzinfo=UTC)
            )

            updated = ScheduledItem(
                id=item.id,
                title=item.title,
                campaign_id=item.campaign_id,
                content_item_id=item.content_item_id,
                destination_type=item.destination_type,
                destination_id=item.destination_id,
                destination_name=item.destination_name,
                scheduled_at=utc_time.astimezone(UTC),
                post_type=item.post_type,
                caption=item.caption,
                media_asset_ids=item.media_asset_ids,
                status=item.status
                if item.status != ScheduledItemStatus.MISSED
                else ScheduledItemStatus.QUEUED,
                priority=item.priority,
                timezone_name=item.timezone_name,
                retry_count=item.retry_count,
                max_retries=item.max_retries,
                error_message=item.error_message,
                executed_at=item.executed_at,
                tags=item.tags,
                created_at=item.created_at,
                updated_at=self._clock.now(),
            )
            saved = repo.save_item(updated)
            uow.commit()
            return Result.success(saved)

    def get_conflicts(
        self,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        min_interval_minutes: int = 10,
    ) -> Sequence[ScheduleConflict]:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            items = repo.list_items(
                from_time=from_time,
                to_time=to_time,
                status=ScheduledItemStatus.QUEUED,
            )
            return detect_conflicts(items, min_interval_minutes=min_interval_minutes)

    def list_calendar_items(
        self,
        view_mode: str = "month",  # "day", "week", "month", "agenda"
        reference_date: datetime | None = None,
        destination_id: str | None = None,
    ) -> Sequence[ScheduledItem]:
        ref = reference_date or self._clock.now()

        if view_mode == "day":
            from_time = ref.replace(hour=0, minute=0, second=0, microsecond=0)
            to_time = from_time + timedelta(days=1)
        elif view_mode == "week":
            # Start of current week (Monday)
            from_time = (ref - timedelta(days=ref.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            to_time = from_time + timedelta(days=7)
        elif view_mode == "month":
            from_time = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Roughly full month + padding
            to_time = (from_time + timedelta(days=32)).replace(day=1)
        else:  # agenda
            from_time = ref.replace(hour=0, minute=0, second=0, microsecond=0)
            to_time = from_time + timedelta(days=30)

        with self._uow() as uow:
            repo = self._repo_factory(uow)
            return repo.list_items(
                from_time=from_time,
                to_time=to_time,
                destination_id=destination_id,
            )

    def recover_missed_tasks(
        self,
        grace_period_minutes: int = 15,
        action: str = "requeue_now",  # "requeue_now", "mark_missed", "reschedule_next_window"
    ) -> Sequence[ScheduledItem]:
        """Detect tasks that missed their scheduled time and apply recovery strategy."""
        now = self._clock.now()
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            missed = repo.list_missed_items(now, grace_period_minutes=grace_period_minutes)
            recovered: list[ScheduledItem] = []

            for item in missed:
                if action == "mark_missed":
                    updated = ScheduledItem(
                        id=item.id,
                        title=item.title,
                        campaign_id=item.campaign_id,
                        content_item_id=item.content_item_id,
                        destination_type=item.destination_type,
                        destination_id=item.destination_id,
                        destination_name=item.destination_name,
                        scheduled_at=item.scheduled_at,
                        post_type=item.post_type,
                        caption=item.caption,
                        media_asset_ids=item.media_asset_ids,
                        status=ScheduledItemStatus.MISSED,
                        priority=item.priority,
                        timezone_name=item.timezone_name,
                        retry_count=item.retry_count,
                        max_retries=item.max_retries,
                        error_message="Missed scheduled publishing slot",
                        executed_at=item.executed_at,
                        tags=item.tags,
                        created_at=item.created_at,
                        updated_at=now,
                    )
                elif action == "reschedule_next_window":
                    next_slot = self._default_window.next_valid_slot(now + timedelta(minutes=5))
                    updated = ScheduledItem(
                        id=item.id,
                        title=item.title,
                        campaign_id=item.campaign_id,
                        content_item_id=item.content_item_id,
                        destination_type=item.destination_type,
                        destination_id=item.destination_id,
                        destination_name=item.destination_name,
                        scheduled_at=next_slot,
                        post_type=item.post_type,
                        caption=item.caption,
                        media_asset_ids=item.media_asset_ids,
                        status=ScheduledItemStatus.QUEUED,
                        priority=item.priority,
                        timezone_name=item.timezone_name,
                        retry_count=item.retry_count,
                        max_retries=item.max_retries,
                        error_message="Rescheduled after missed window",
                        executed_at=item.executed_at,
                        tags=item.tags,
                        created_at=item.created_at,
                        updated_at=now,
                    )
                else:  # requeue_now
                    updated = ScheduledItem(
                        id=item.id,
                        title=item.title,
                        campaign_id=item.campaign_id,
                        content_item_id=item.content_item_id,
                        destination_type=item.destination_type,
                        destination_id=item.destination_id,
                        destination_name=item.destination_name,
                        scheduled_at=now,
                        post_type=item.post_type,
                        caption=item.caption,
                        media_asset_ids=item.media_asset_ids,
                        status=ScheduledItemStatus.QUEUED,
                        priority=SchedulePriority.HIGH,  # bump priority
                        timezone_name=item.timezone_name,
                        retry_count=item.retry_count,
                        max_retries=item.max_retries,
                        error_message=item.error_message,
                        executed_at=item.executed_at,
                        tags=item.tags,
                        created_at=item.created_at,
                        updated_at=now,
                    )
                saved = repo.save_item(updated)
                recovered.append(saved)

            uow.commit()
            return tuple(recovered)

    def cancel_item(self, item_id: str) -> Result[ScheduledItem]:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            item = repo.get_item(item_id)
            if item is None:
                return Result.failure(
                    AppError(code="NOT_FOUND", message=f"Scheduled item {item_id} not found")
                )

            updated = ScheduledItem(
                id=item.id,
                title=item.title,
                campaign_id=item.campaign_id,
                content_item_id=item.content_item_id,
                destination_type=item.destination_type,
                destination_id=item.destination_id,
                destination_name=item.destination_name,
                scheduled_at=item.scheduled_at,
                post_type=item.post_type,
                caption=item.caption,
                media_asset_ids=item.media_asset_ids,
                status=ScheduledItemStatus.CANCELLED,
                priority=item.priority,
                timezone_name=item.timezone_name,
                retry_count=item.retry_count,
                max_retries=item.max_retries,
                error_message=item.error_message,
                executed_at=item.executed_at,
                tags=item.tags,
                created_at=item.created_at,
                updated_at=self._clock.now(),
            )
            saved = repo.save_item(updated)
            uow.commit()
            return Result.success(saved)

    def get_next_run(self) -> ScheduledItem | None:
        """Get the earliest queued item scheduled to run."""
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            items = repo.list_items(status=ScheduledItemStatus.QUEUED, limit=1)
            return items[0] if items else None
