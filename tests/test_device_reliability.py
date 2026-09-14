"""Tests for Phase 41: Device Reliability Analytics."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from PySide6.QtWidgets import QApplication

from sp_farms.app.analytics_workspace import (
    AnalyticsWorkspace,
)
from sp_farms.application.device_analytics_service import DeviceAnalyticsService
from sp_farms.domain.device_analytics import (
    DeviceOperationalEvent,
    DeviceReliabilityRating,
    OperationalEventType,
)
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyDeviceAnalyticsRepository,
    run_migrations,
)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app  # type: ignore[return-value]


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_reliability.db"
    database = Database(db_path)
    from pathlib import Path

    migrations_path = Path(__file__).resolve().parents[1] / "migrations"
    run_migrations(database, migrations_path)
    yield database
    database.close()


def test_device_reliability_domain_rating():
    assert DeviceReliabilityRating.from_score(95.0) == DeviceReliabilityRating.EXCELLENT
    assert DeviceReliabilityRating.from_score(80.0) == DeviceReliabilityRating.GOOD
    assert DeviceReliabilityRating.from_score(65.0) == DeviceReliabilityRating.FAIR
    assert DeviceReliabilityRating.from_score(50.0) == DeviceReliabilityRating.POOR
    assert DeviceReliabilityRating.from_score(20.0) == DeviceReliabilityRating.CRITICAL


def test_device_analytics_service_in_memory_metrics():
    service = DeviceAnalyticsService()

    # Device 1: clean run
    service.record_job_completion(
        device_key="ldplayer:emulator-5554",
        provider="ldplayer",
        success=True,
        duration_seconds=10.0,
    )
    service.record_job_completion(
        device_key="ldplayer:emulator-5554",
        provider="ldplayer",
        success=True,
        duration_seconds=20.0,
    )

    # Device 2: flaky run with disconnects and retries
    service.record_job_completion(
        device_key="mumu:127.0.0.1:16384",
        provider="mumu",
        success=False,
        duration_seconds=5.0,
        retried=True,
        error_code="TIMEOUT",
    )
    service.record_disconnect(
        device_key="mumu:127.0.0.1:16384",
        provider="mumu",
        reason="ADB pipe closed",
    )
    service.record_provider_error(
        device_key="mumu:127.0.0.1:16384",
        provider="mumu",
        error_code="PROVIDER_CRASH",
    )

    stats1 = service.get_device_reliability("ldplayer:emulator-5554")
    assert stats1.total_jobs == 2
    assert stats1.successful_jobs == 2
    assert stats1.failed_jobs == 0
    assert stats1.average_job_duration_seconds == 15.0
    assert stats1.disconnect_count == 0
    assert stats1.reliability_score == 100.0
    assert stats1.rating == DeviceReliabilityRating.EXCELLENT

    stats2 = service.get_device_reliability("mumu:127.0.0.1:16384")
    assert stats2.total_jobs == 1
    assert stats2.failed_jobs == 1
    assert stats2.retried_jobs == 1
    assert stats2.disconnect_count == 1
    assert stats2.provider_error_rate > 0.0
    assert stats2.reliability_score < 75.0


def test_device_analytics_repository_persistence(db):
    service = DeviceAnalyticsService(
        unit_of_work=db.unit_of_work,
        repo_factory=SqlAlchemyDeviceAnalyticsRepository,
    )

    service.record_event(
        device_key="physical:R58M12345",
        provider="physical",
        event_type=OperationalEventType.CONNECT,
        metadata={"battery": 95},
    )

    service.record_job_completion(
        device_key="physical:R58M12345",
        provider="physical",
        success=True,
        duration_seconds=42.5,
    )

    # Query back via repository
    with db.unit_of_work() as uow:
        repo = SqlAlchemyDeviceAnalyticsRepository(uow)
        events = repo.list_events(device_key="physical:R58M12345")
        assert len(events) == 2
        assert events[0].provider == "physical"

    stats = service.get_device_reliability("physical:R58M12345")
    assert stats.total_jobs == 1
    assert stats.successful_jobs == 1
    assert stats.average_job_duration_seconds == 42.5
    assert stats.reliability_score == 100.0


def test_device_analytics_time_window_filtering():
    service = DeviceAnalyticsService()
    now = datetime.now(UTC)

    # Event in the past (3 days ago)
    old_event = DeviceOperationalEvent(
        id="old-1",
        device_key="ldplayer:emulator-5556",
        provider="ldplayer",
        event_type=OperationalEventType.JOB_FAILURE,
        duration_seconds=12.0,
        created_at=now - timedelta(days=3),
    )
    service._in_memory_events.append(old_event)

    # Event today
    recent_event = DeviceOperationalEvent(
        id="recent-1",
        device_key="ldplayer:emulator-5556",
        provider="ldplayer",
        event_type=OperationalEventType.JOB_SUCCESS,
        duration_seconds=8.0,
        created_at=now - timedelta(hours=2),
    )
    service._in_memory_events.append(recent_event)

    # Filter by last 24h: only recent event should be included
    since_24h = now - timedelta(hours=24)
    stats_recent = service.get_device_reliability("ldplayer:emulator-5556", since=since_24h)
    assert stats_recent.total_jobs == 1
    assert stats_recent.successful_jobs == 1
    assert stats_recent.failed_jobs == 0

    # Filter all time: both events included
    stats_all = service.get_device_reliability("ldplayer:emulator-5556")
    assert stats_all.total_jobs == 2
    assert stats_all.successful_jobs == 1
    assert stats_all.failed_jobs == 1


def test_device_analytics_missing_data_handling():
    service = DeviceAnalyticsService()

    # Query device with zero events/missing telemetry
    stats = service.get_device_reliability("physical:unknown_serial")
    assert stats.total_jobs == 0
    assert stats.successful_jobs == 0
    assert stats.failed_jobs == 0
    assert stats.retried_jobs == 0
    assert stats.disconnect_count == 0
    assert stats.job_success_rate == 100.0
    assert stats.average_job_duration_seconds == 0.0
    assert stats.reliability_score == 100.0
    assert stats.rating == DeviceReliabilityRating.EXCELLENT
    assert stats.last_seen is None

    # Empty fleet report
    report = service.generate_fleet_report()
    assert len(report.device_stats) == 0
    assert len(report.provider_stats) == 0
    assert report.overall_score == 100.0
    assert len(report.unreliable_devices) == 0


def test_fleet_report_and_diagnostics_export():
    service = DeviceAnalyticsService()

    service.record_job_completion("ldplayer:5554", "ldplayer", True, 10.0)
    service.record_disconnect("ldplayer:5554", "ldplayer", "Test disconnect")
    service.record_disconnect("ldplayer:5554", "ldplayer", "Test disconnect 2")
    service.record_disconnect("ldplayer:5554", "ldplayer", "Test disconnect 3")

    service.record_job_completion("mumu:16384", "mumu", True, 25.0)

    report = service.generate_fleet_report()
    assert len(report.device_stats) == 2
    assert len(report.provider_stats) == 2
    assert "ldplayer:5554" in report.unreliable_devices

    json_diag = service.export_diagnostics_json()
    parsed = json.loads(json_diag)
    assert "overall_score" in parsed
    assert len(parsed["devices"]) == 2
    assert len(parsed["providers"]) == 2

    csv_diag = service.export_diagnostics_csv()
    assert "device_key,serial,provider,reliability_score" in csv_diag
    assert "ldplayer:5554" in csv_diag
    assert "mumu:16384" in csv_diag


def test_analytics_workspace_ui_smoke(qapp):
    device_service = DeviceAnalyticsService()
    device_service.record_job_completion("ldplayer:5554", "ldplayer", True, 15.0)
    device_service.record_disconnect("ldplayer:5554", "ldplayer")

    class MockContext:
        analytics_service = None
        device_analytics_service = device_service

    ctx = MockContext()
    workspace = AnalyticsWorkspace(ctx)

    assert workspace.tabs.count() == 2
    assert workspace.tabs.tabText(0) == "Social Post Performance"
    assert workspace.tabs.tabText(1) == "Device & Provider Reliability"

    # Switch to Device Reliability tab
    workspace.tabs.setCurrentIndex(1)
    assert workspace.device_table_model.rowCount() == 1

    # Select first row in device table
    workspace.device_table_view.selectRow(0)
    workspace._on_device_row_selected()
    assert "Device: ldplayer:5554" in workspace.lbl_device_insp_title.text()
    assert "Uptime Percentage:" in workspace.lbl_device_insp_details.text()
