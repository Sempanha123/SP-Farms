"""Tests for Phase 49: Health Checks, Crash-Safe Startup, Safe Mode, DB Integrity, and Updates."""

import sqlite3
import zipfile
from pathlib import Path

from sp_farms.application.config import AppConfig
from sp_farms.application.crash_recovery_service import CrashRecoveryService
from sp_farms.application.health_service import HealthService
from sp_farms.application.update_service import (
    FakeUpdateAdapter,
    UpdateService,
    compare_versions,
    is_newer_version,
    parse_semver,
)
from sp_farms.domain.health import HealthStatus
from sp_farms.infrastructure.diagnostics import create_diagnostics_bundle


def test_crash_recovery_clean_shutdown(tmp_path: Path) -> None:
    marker_file = tmp_path / ".startup_marker.json"
    db_file = tmp_path / "test.db"
    recovery = CrashRecoveryService(marker_path=marker_file, database_path=db_file)

    state = recovery.evaluate_startup()
    assert not state.safe_mode_active
    assert state.unclean_shutdowns_count == 0

    recovery.record_startup(pid=12345)
    assert marker_file.exists()

    recovery.record_clean_shutdown()
    state_after = recovery.evaluate_startup()
    assert not state_after.safe_mode_active
    assert state_after.unclean_shutdowns_count == 0


def test_crash_recovery_triggers_safe_mode_after_consecutive_crashes(tmp_path: Path) -> None:
    marker_file = tmp_path / ".startup_marker.json"
    db_file = tmp_path / "test.db"
    recovery = CrashRecoveryService(
        marker_path=marker_file,
        database_path=db_file,
        consecutive_crash_threshold=2,
    )

    # First run: start without clean shutdown (simulated crash)
    recovery.record_startup(pid=1001)

    # Second startup: unclean shutdown detected (crash count 1)
    state1 = recovery.evaluate_startup()
    assert not state1.safe_mode_active
    assert state1.unclean_shutdowns_count == 1

    # Second run: start again without clean shutdown
    recovery.record_startup(pid=1002)

    # Third startup: 2 consecutive crashes -> triggers safe mode
    state2 = recovery.evaluate_startup()
    assert state2.safe_mode_active
    assert state2.unclean_shutdowns_count == 2
    assert state2.reason is not None and "2 consecutive unclean shutdowns" in state2.reason

    # Reset safe mode
    recovery.reset_safe_mode()
    state_reset = recovery.evaluate_startup()
    assert not state_reset.safe_mode_active
    assert state_reset.unclean_shutdowns_count == 0


def test_database_integrity_and_quarantine(tmp_path: Path) -> None:
    db_file = tmp_path / "test_integrity.db"
    marker_file = tmp_path / ".startup_marker.json"
    recovery = CrashRecoveryService(marker_path=marker_file, database_path=db_file)

    # 1. Valid database
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO users VALUES (1, 'Alice')")
    conn.commit()
    conn.close()

    ok, errors = recovery.check_database_integrity()
    assert ok
    assert len(errors) == 0

    # 2. Corrupt database by overwriting header with random bytes
    db_file.write_bytes(b"CORRUPTED_GARBAGE_HEADER_DATA_NOT_SQLITE3")
    ok_corrupt, errors_corrupt = recovery.check_database_integrity()
    assert not ok_corrupt
    assert len(errors_corrupt) > 0

    # 3. Quarantine
    quarantined = recovery.quarantine_corrupted_database()
    assert quarantined is not None
    assert quarantined.exists()
    assert not db_file.exists()
    assert ".corrupt." in quarantined.name


def test_semver_comparison_and_update_service() -> None:
    assert parse_semver("1.2.3") == (1, 2, 3, "")
    assert parse_semver("v2.0.1") == (2, 0, 1, "")
    assert parse_semver("1.0.0-beta.1") == (1, 0, 0, "beta.1")

    assert compare_versions("1.0.1", "1.0.0") == 1
    assert compare_versions("1.0.0", "1.0.1") == -1
    assert compare_versions("1.0.0", "1.0.0") == 0
    assert compare_versions("2.0.0", "1.9.9") == 1
    assert compare_versions("1.0.0", "1.0.0-beta.1") == 1
    assert compare_versions("1.0.0-beta.1", "1.0.0") == -1

    assert is_newer_version("1.1.0", "1.0.0")
    assert not is_newer_version("1.0.0", "1.1.0")

    fake_adapter = FakeUpdateAdapter(
        latest_version="1.2.0",
        release_notes="Added Phase 49 features",
        download_url="https://github.com/Sempanha123/SP-Farms/releases/tag/v1.2.0",
    )
    svc = UpdateService(current_version="1.1.0", update_port=fake_adapter)
    info = svc.check_for_updates()
    assert info.is_update_available
    assert info.current_version == "1.1.0"
    assert info.latest_version == "1.2.0"
    assert "Phase 49" in info.release_notes

    # Same version -> no update available
    svc_same = UpdateService(current_version="1.2.0", update_port=fake_adapter)
    info_same = svc_same.check_for_updates()
    assert not info_same.is_update_available


def test_health_service_aggregation(tmp_path: Path) -> None:
    db_file = tmp_path / "health_test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("CREATE TABLE dummy (id INT)")
    conn.commit()
    conn.close()

    cfg = AppConfig(
        environment="test",
        log_level="INFO",
        database_path=db_file,
        log_path=tmp_path / "test.log",
        adb_path=tmp_path / "adb",
        ldplayer_path=tmp_path / "ldplayer",
        mumu_path=tmp_path / "mumu",
        meta_app_id="1234567890",
    )

    health_svc = HealthService(
        config=cfg,
        vault_probe=lambda: True,
        adb_probe=lambda: (True, "ADB operational"),
        ldplayer_probe=lambda: (True, "LDPlayer ready"),
        mumu_probe=lambda: (True, "MuMu ready"),
        physical_probe=lambda: (True, "1 device connected"),
        scheduler_probe=lambda: (True, "Scheduler active"),
        workers_probe=lambda: (True, "Workers active"),
        network_probe=lambda: (True, "Online"),
    )

    summary = health_svc.run_all_checks()
    assert summary.overall_status == HealthStatus.HEALTHY
    assert summary.is_fully_healthy
    assert summary.healthy_count == 11
    assert summary.degraded_count == 0
    assert summary.critical_count == 0

    # Simulate a degraded component
    health_svc_degraded = HealthService(
        config=cfg,
        vault_probe=lambda: False,  # degraded
        adb_probe=lambda: (True, "ADB operational"),
    )
    deg_summary = health_svc_degraded.run_all_checks()
    assert deg_summary.overall_status == HealthStatus.DEGRADED
    assert deg_summary.degraded_count >= 1


def test_diagnostics_bundle_includes_health_report(tmp_path: Path) -> None:
    db_file = tmp_path / "bundle_test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE t (id INT)")
    conn.commit()
    conn.close()

    log_file = tmp_path / "sp_farms.log"
    log_file.write_text("INFO: Application booted successfully\n", encoding="utf-8")

    cfg = AppConfig(
        environment="test",
        log_level="INFO",
        database_path=db_file,
        log_path=log_file,
        adb_path=tmp_path / "adb",
        ldplayer_path=tmp_path / "ldplayer",
        mumu_path=tmp_path / "mumu",
    )
    health_svc = HealthService(config=cfg)
    summary = health_svc.run_all_checks()

    zip_dest = tmp_path / "diagnostics_bundle.zip"
    created = create_diagnostics_bundle(
        destination=zip_dest,
        config=cfg,
        health_summary=summary,
    )
    assert created.exists()

    with zipfile.ZipFile(created, "r") as zf:
        names = zf.namelist()
        assert "runtime.json" in names
        assert "health_report.json" in names
        assert "logs/sp_farms.log" in names
        report_content = zf.read("health_report.json").decode("utf-8")
        assert "overall_status" in report_content
        assert "database" in report_content
