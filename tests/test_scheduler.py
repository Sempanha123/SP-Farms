"""Tests for Phase 34: Scheduler and Calendar."""

from collections.abc import Generator
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
import tempfile

from PySide6.QtWidgets import QApplication
import pytest

from sp_farms.app.scheduler_workspace import (
    NewScheduleDialog,
    RescheduleDialog,
    ScheduledItemTableModel,
    SchedulerWorkspace,
)
from sp_farms.application.scheduler_service import SchedulerService
from sp_farms.domain.composer import PostType, PublishDestinationType
from sp_farms.domain.scheduler import (
    PublishingWindow,
    ScheduledItem,
    ScheduledItemStatus,
    SchedulePriority,
    detect_conflicts,
)
from sp_farms.infrastructure.clock import SystemClock
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemySchedulerRepository,
    run_migrations,
)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app  # type: ignore[return-value]


@pytest.fixture
def test_db() -> Generator[Database, None, None]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_scheduler.db"
        db = Database(db_path)
        migrations_path = Path(__file__).resolve().parents[1] / "migrations"
        run_migrations(db, migrations_path)
        try:
            yield db
        finally:
            db.close()


@pytest.fixture
def scheduler_service(test_db: Database) -> SchedulerService:
    return SchedulerService(
        unit_of_work=test_db.unit_of_work,
        scheduler_repo_factory=SqlAlchemySchedulerRepository,
        clock=SystemClock(),
    )


def test_publishing_window_and_timezone_dst() -> None:
    """Test publishing window bounds, quiet hours, and next valid slot calculation."""
    # Window: 09:00 to 18:00 UTC, quiet hours 12:00-13:00, Mon-Fri (0-4)
    window = PublishingWindow(
        start_time=time(9, 0),
        end_time=time(18, 0),
        quiet_hours_start=time(12, 0),
        quiet_hours_end=time(13, 0),
        days_of_week=(0, 1, 2, 3, 4),
        timezone_name="UTC",
    )

    # Valid time: Wednesday 10:00
    valid_time = datetime(2026, 3, 4, 10, 0, tzinfo=UTC)
    assert window.is_within_window(valid_time) is True

    # Invalid time: Wednesday 08:00 (too early)
    early_time = datetime(2026, 3, 4, 8, 0, tzinfo=UTC)
    assert window.is_within_window(early_time) is False
    next_slot = window.next_valid_slot(early_time)
    assert next_slot == datetime(2026, 3, 4, 9, 0, tzinfo=UTC)

    # Invalid time: Wednesday 12:30 (quiet hours)
    quiet_time = datetime(2026, 3, 4, 12, 30, tzinfo=UTC)
    assert window.is_within_window(quiet_time) is False
    next_slot = window.next_valid_slot(quiet_time)
    assert next_slot == datetime(2026, 3, 4, 13, 0, tzinfo=UTC)

    # Invalid time: Saturday 10:00 (weekend)
    weekend_time = datetime(2026, 3, 7, 10, 0, tzinfo=UTC)
    assert window.is_within_window(weekend_time) is False
    next_slot = window.next_valid_slot(weekend_time)
    # Next Monday 09:00 (March 9, 2026)
    assert next_slot == datetime(2026, 3, 9, 9, 0, tzinfo=UTC)

    # Non-UTC timezone conversion check (America/New_York)
    ny_window = PublishingWindow(
        start_time=time(9, 0),
        end_time=time(17, 0),
        timezone_name="America/New_York",
    )
    # 14:00 UTC is 09:00 EST / 10:00 EDT -> should be inside 9-17 NY
    test_dt = datetime(2026, 3, 4, 14, 0, tzinfo=UTC)
    assert ny_window.is_within_window(test_dt) is True


def test_conflict_detection() -> None:
    """Test same-destination interval collision detection."""
    base_time = datetime(2026, 3, 4, 10, 0, tzinfo=UTC)

    item1 = ScheduledItem.create(
        title="Post 1",
        destination_type=PublishDestinationType.PAGE,
        destination_id="dest-100",
        destination_name="Brand Page",
        scheduled_at=base_time,
    )
    item2 = ScheduledItem.create(
        title="Post 2 (collision)",
        destination_type=PublishDestinationType.PAGE,
        destination_id="dest-100",
        destination_name="Brand Page",
        scheduled_at=base_time + timedelta(minutes=5),  # within 10 min window
    )
    item3 = ScheduledItem.create(
        title="Post 3 (different dest)",
        destination_type=PublishDestinationType.GROUP,
        destination_id="dest-200",
        destination_name="Community Group",
        scheduled_at=base_time + timedelta(minutes=3),  # different dest -> OK
    )
    item4 = ScheduledItem.create(
        title="Post 4 (far away)",
        destination_type=PublishDestinationType.PAGE,
        destination_id="dest-100",
        destination_name="Brand Page",
        scheduled_at=base_time + timedelta(minutes=30),  # > 10 min -> OK
    )

    conflicts = detect_conflicts([item1, item2, item3, item4], min_interval_minutes=10)
    assert len(conflicts) == 1
    assert conflicts[0].existing_item_id == item1.id
    assert conflicts[0].conflicting_item_id == item2.id
    assert conflicts[0].destination_id == "dest-100"


def test_scheduler_service_lifecycle_and_reschedule(
    scheduler_service: SchedulerService,
) -> None:
    """Test creating, rescheduling, canceling, and querying scheduled posts."""
    now = datetime.now(UTC)

    # 1. Schedule a post
    res = scheduler_service.schedule_post(
        title="Launch Product Video",
        destination_type=PublishDestinationType.PAGE,
        destination_id="page-abc",
        destination_name="Tech News",
        scheduled_at=now + timedelta(hours=2),
        post_type=PostType.REEL,
        priority=SchedulePriority.HIGH,
    )
    assert res.is_success
    item = res.value
    assert item.title == "Launch Product Video"
    assert item.status == ScheduledItemStatus.QUEUED
    assert item.priority == SchedulePriority.HIGH

    # 2. Reschedule the post
    new_time = now + timedelta(days=1)
    resched_res = scheduler_service.reschedule_item(item.id, new_time)
    assert resched_res.is_success
    assert resched_res.value.scheduled_at == new_time

    # 3. Pause all
    scheduler_service.pause_all()
    assert scheduler_service.is_paused is True
    scheduler_service.resume_all()
    assert scheduler_service.is_paused is False

    # 4. Cancel item
    cancel_res = scheduler_service.cancel_item(item.id)
    assert cancel_res.is_success
    assert cancel_res.value.status == ScheduledItemStatus.CANCELLED


def test_missed_task_recovery(scheduler_service: SchedulerService) -> None:
    """Test detecting and recovering missed publishing tasks."""
    past_time = datetime.now(UTC) - timedelta(hours=2)

    # Schedule a task in the past
    res = scheduler_service.schedule_post(
        title="Overdue Campaign Post",
        destination_type=PublishDestinationType.ACCOUNT_PROFILE,
        destination_id="prof-1",
        destination_name="John Doe",
        scheduled_at=past_time,
        auto_adjust_to_window=False,
    )
    assert res.is_success
    item = res.value

    # Recover missed task
    recovered = scheduler_service.recover_missed_tasks(
        grace_period_minutes=10, action="requeue_now"
    )
    assert len(recovered) == 1
    assert recovered[0].id == item.id
    assert recovered[0].priority == SchedulePriority.HIGH
    assert recovered[0].status == ScheduledItemStatus.QUEUED


def test_scheduler_workspace_ui(
    qapp: QApplication, scheduler_service: SchedulerService
) -> None:
    """Test PySide6 SchedulerWorkspace initialization, model updates, and dialogs."""
    now = datetime.now(UTC)
    scheduler_service.schedule_post(
        title="Scheduled Morning Post",
        destination_type=PublishDestinationType.PAGE,
        destination_id="dest-1",
        destination_name="Page 1",
        scheduled_at=now + timedelta(hours=3),
    )

    workspace = SchedulerWorkspace(scheduler_service)
    assert workspace.table_model.rowCount() >= 1

    # Check metric labels
    assert workspace.metrics.value_labels[0].text() != "0"

    # View switching
    workspace.day_btn.setChecked(True)
    assert workspace._view_mode == "day"

    workspace.agenda_btn.setChecked(True)
    assert workspace._view_mode == "agenda"

    # Test Table Model directly
    model = ScheduledItemTableModel()
    item = ScheduledItem.create(
        title="Test Item",
        destination_type=PublishDestinationType.GROUP,
        destination_id="grp-1",
        destination_name="Group 1",
        scheduled_at=now,
    )
    model.set_items([item])
    assert model.rowCount() == 1
    assert model.columnCount() == 7
    assert model.get_item(0) == item

    # Test dialogs instantiate cleanly
    resched_dlg = RescheduleDialog(item)
    assert resched_dlg.get_datetime() is not None

    new_dlg = NewScheduleDialog()
    assert new_dlg.get_datetime() is not None
