"""Crash recovery, safe mode management, and database integrity verification service."""

import json
import logging
import os
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from sp_farms.domain.health import SafeModeState

logger = logging.getLogger(__name__)


class CrashRecoveryService:
    """Manages application startup/shutdown markers, safe mode flags, and DB integrity."""

    def __init__(
        self,
        marker_path: Path,
        database_path: Path,
        consecutive_crash_threshold: int = 2,
    ) -> None:
        self.marker_path = marker_path
        self.database_path = database_path
        self.threshold = consecutive_crash_threshold
        self._safe_mode = False

    def evaluate_startup(self) -> SafeModeState:
        """Inspect existing startup marker to determine whether safe mode should be activated."""
        if not self.marker_path.exists():
            return SafeModeState(
                safe_mode_active=False,
                unclean_shutdowns_count=0,
                last_crash_at=None,
                reason=None,
            )

        try:
            data = json.loads(self.marker_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Could not read startup marker: %s", e)
            return SafeModeState(
                safe_mode_active=True,
                unclean_shutdowns_count=1,
                last_crash_at=datetime.now(UTC),
                reason="Corrupted startup marker",
            )

        cleanly_shutdown = bool(data.get("cleanly_shutdown", True))
        crashes = int(data.get("consecutive_crashes", 0))

        if not cleanly_shutdown:
            crashes += 1
            last_crash_raw = data.get("started_at")
            try:
                last_crash = (
                    datetime.fromisoformat(last_crash_raw) if last_crash_raw else datetime.now(UTC)
                )
            except Exception:
                last_crash = datetime.now(UTC)

            safe_active = crashes >= self.threshold
            reason = f"Detected {crashes} consecutive unclean shutdowns" if safe_active else None
            self._safe_mode = safe_active
            return SafeModeState(
                safe_mode_active=safe_active,
                unclean_shutdowns_count=crashes,
                last_crash_at=last_crash,
                reason=reason,
            )

        return SafeModeState(
            safe_mode_active=False,
            unclean_shutdowns_count=0,
            last_crash_at=None,
            reason=None,
        )

    def record_startup(self, pid: int | None = None) -> None:
        """Record process startup with cleanly_shutdown=False."""
        self.marker_path.parent.mkdir(parents=True, exist_ok=True)
        crashes = 0
        if self.marker_path.exists():
            try:
                prev = json.loads(self.marker_path.read_text(encoding="utf-8"))
                if not prev.get("cleanly_shutdown", True):
                    crashes = int(prev.get("consecutive_crashes", 0)) + 1
            except Exception:
                crashes = 1

        payload = {
            "pid": pid or os.getpid(),
            "started_at": datetime.now(UTC).isoformat(),
            "cleanly_shutdown": False,
            "consecutive_crashes": crashes,
        }
        self.marker_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def record_clean_shutdown(self) -> None:
        """Record clean shutdown and reset crash count."""
        if not self.marker_path.exists():
            return
        try:
            payload = {
                "stopped_at": datetime.now(UTC).isoformat(),
                "cleanly_shutdown": True,
                "consecutive_crashes": 0,
            }
            self.marker_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed writing clean shutdown marker: %s", e)

    def reset_safe_mode(self) -> None:
        """Explicitly reset safe mode state."""
        self._safe_mode = False
        self.record_clean_shutdown()

    @property
    def is_safe_mode_active(self) -> bool:
        return self._safe_mode

    def check_database_integrity(self) -> tuple[bool, list[str]]:
        """Run SQLite integrity checks against database file."""
        if not self.database_path.exists():
            return True, ["Database file does not exist yet"]

        errors: list[str] = []
        try:
            conn = sqlite3.connect(str(self.database_path), timeout=5.0)
            try:
                cursor = conn.cursor()
                # 1. Quick check
                cursor.execute("PRAGMA quick_check")
                rows = cursor.fetchall()
                for row in rows:
                    if row[0] != "ok":
                        errors.append(f"Quick check error: {row[0]}")

                # 2. Foreign key check
                cursor.execute("PRAGMA foreign_key_check")
                fk_violations = cursor.fetchall()
                if fk_violations:
                    errors.append(f"Foreign key violations found: {len(fk_violations)}")

                # 3. Full integrity check if quick check had issues
                if errors:
                    cursor.execute("PRAGMA integrity_check")
                    full_rows = cursor.fetchall()
                    errors.extend(r[0] for r in full_rows if r[0] != "ok")
            finally:
                conn.close()
        except Exception as e:
            errors.append(f"Database connection error: {e}")

        is_healthy = len(errors) == 0
        return is_healthy, errors

    def quarantine_corrupted_database(self) -> Path | None:
        """Rename corrupted database to prevent boot loops and preserve for analysis."""
        if not self.database_path.exists():
            return None

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        quarantine_target = self.database_path.with_name(
            f"{self.database_path.name}.corrupt.{timestamp}"
        )
        try:
            shutil.move(str(self.database_path), str(quarantine_target))
            # Also move WAL/SHM if they exist
            wal = self.database_path.with_name(f"{self.database_path.name}-wal")
            shm = self.database_path.with_name(f"{self.database_path.name}-shm")
            if wal.exists():
                wal_target = quarantine_target.with_name(f"{quarantine_target.name}-wal")
                shutil.move(str(wal), str(wal_target))
            if shm.exists():
                shm_target = quarantine_target.with_name(f"{quarantine_target.name}-shm")
                shutil.move(str(shm), str(shm_target))
            logger.error("Corrupted database quarantined to %s", quarantine_target)
            return quarantine_target
        except Exception as e:
            logger.error("Failed quarantining database: %s", e)
            return None
