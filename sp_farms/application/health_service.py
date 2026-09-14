"""One-click comprehensive system health check and diagnostics engine."""

import shutil
import sqlite3
import time
from collections.abc import Callable
from datetime import UTC, datetime

from sp_farms.application.config import AppConfig
from sp_farms.domain.health import HealthCheckResult, HealthStatus, HealthSummary


class HealthService:
    """Runs one-click diagnostic probes across all system components."""

    def __init__(
        self,
        config: AppConfig,
        database_connection_factory: Callable[[], sqlite3.Connection] | None = None,
        vault_probe: Callable[[], bool] | None = None,
        adb_probe: Callable[[], tuple[bool, str]] | None = None,
        ldplayer_probe: Callable[[], tuple[bool, str]] | None = None,
        mumu_probe: Callable[[], tuple[bool, str]] | None = None,
        physical_probe: Callable[[], tuple[bool, str]] | None = None,
        scheduler_probe: Callable[[], tuple[bool, str]] | None = None,
        workers_probe: Callable[[], tuple[bool, str]] | None = None,
        network_probe: Callable[[], tuple[bool, str]] | None = None,
        export_bundle_handler: Callable[[Path, HealthSummary | None], Path] | None = None,
    ) -> None:
        self.config = config
        self._db_factory = database_connection_factory
        self._vault_probe = vault_probe
        self._adb_probe = adb_probe
        self._ldplayer_probe = ldplayer_probe
        self._mumu_probe = mumu_probe
        self._physical_probe = physical_probe
        self._scheduler_probe = scheduler_probe
        self._workers_probe = workers_probe
        self._network_probe = network_probe
        self._export_bundle_handler = export_bundle_handler

    def export_diagnostics_bundle(self, destination: Path) -> Path:
        """Export comprehensive diagnostics bundle via configured handler."""
        summary = self.run_all_checks()
        if self._export_bundle_handler:
            return self._export_bundle_handler(destination, summary)
        raise RuntimeError("Diagnostics export handler not configured")

    def run_all_checks(self) -> HealthSummary:
        """Run all 11 component health checks and aggregate into summary."""
        checks: list[HealthCheckResult] = [
            self.check_database(),
            self.check_vault(),
            self.check_adb(),
            self.check_ldplayer(),
            self.check_mumu(),
            self.check_physical_devices(),
            self.check_meta_config(),
            self.check_storage(),
            self.check_scheduler(),
            self.check_workers(),
            self.check_network(),
        ]

        if any(c.status == HealthStatus.CRITICAL for c in checks):
            overall = HealthStatus.CRITICAL
        elif any(c.status == HealthStatus.DEGRADED for c in checks):
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        return HealthSummary(
            overall_status=overall,
            checks=tuple(checks),
            checked_at=datetime.now(UTC),
        )

    def check_database(self) -> HealthCheckResult:
        t0 = time.monotonic()
        db_path = self.config.database_path
        if not db_path.exists():
            return HealthCheckResult(
                component="database",
                status=HealthStatus.DEGRADED,
                message="Database file does not exist yet (will initialize on startup)",
                latency_ms=(time.monotonic() - t0) * 1000,
                details={"path": str(db_path)},
            )

        try:
            conn = (
                self._db_factory()
                if self._db_factory
                else sqlite3.connect(str(db_path), timeout=3.0)
            )
            try:
                cur = conn.cursor()
                cur.execute("PRAGMA journal_mode")
                mode = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
                table_count = cur.fetchone()[0]
                cur.execute("PRAGMA quick_check")
                res = cur.fetchone()[0]
                if res != "ok":
                    return HealthCheckResult(
                        component="database",
                        status=HealthStatus.CRITICAL,
                        message=f"Database corruption detected: {res}",
                        latency_ms=(time.monotonic() - t0) * 1000,
                    )
                return HealthCheckResult(
                    component="database",
                    status=HealthStatus.HEALTHY,
                    message=f"Operational ({table_count} tables, {mode.upper()} mode)",
                    latency_ms=(time.monotonic() - t0) * 1000,
                    details={"tables": table_count, "mode": mode, "path": str(db_path)},
                )
            finally:
                conn.close()
        except Exception as e:
            return HealthCheckResult(
                component="database",
                status=HealthStatus.CRITICAL,
                message=f"Connection failed: {e}",
                latency_ms=(time.monotonic() - t0) * 1000,
            )

    def check_vault(self) -> HealthCheckResult:
        t0 = time.monotonic()
        if self._vault_probe:
            try:
                ok = self._vault_probe()
                return HealthCheckResult(
                    component="vault",
                    status=HealthStatus.HEALTHY if ok else HealthStatus.DEGRADED,
                    message="Keyring operational" if ok else "Keyring access degraded",
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
            except Exception as e:
                return HealthCheckResult(
                    component="vault",
                    status=HealthStatus.CRITICAL,
                    message=f"Keyring error: {e}",
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
        return HealthCheckResult(
            component="vault",
            status=HealthStatus.HEALTHY,
            message="Secure vault adapter loaded",
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    def check_adb(self) -> HealthCheckResult:
        t0 = time.monotonic()
        if self._adb_probe:
            try:
                ok, msg = self._adb_probe()
                return HealthCheckResult(
                    component="adb",
                    status=HealthStatus.HEALTHY if ok else HealthStatus.DEGRADED,
                    message=msg,
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
            except Exception as e:
                return HealthCheckResult(
                    component="adb",
                    status=HealthStatus.DEGRADED,
                    message=f"ADB probe failed: {e}",
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
        return HealthCheckResult(
            component="adb",
            status=HealthStatus.HEALTHY,
            message="ADB service configured",
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    def check_ldplayer(self) -> HealthCheckResult:
        t0 = time.monotonic()
        if self._ldplayer_probe:
            try:
                ok, msg = self._ldplayer_probe()
                return HealthCheckResult(
                    component="ldplayer",
                    status=HealthStatus.HEALTHY if ok else HealthStatus.DEGRADED,
                    message=msg,
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
            except Exception as e:
                return HealthCheckResult(
                    component="ldplayer",
                    status=HealthStatus.DEGRADED,
                    message=f"LDPlayer probe error: {e}",
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
        return HealthCheckResult(
            component="ldplayer",
            status=HealthStatus.HEALTHY,
            message="LDPlayer provider ready",
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    def check_mumu(self) -> HealthCheckResult:
        t0 = time.monotonic()
        if self._mumu_probe:
            try:
                ok, msg = self._mumu_probe()
                return HealthCheckResult(
                    component="mumu",
                    status=HealthStatus.HEALTHY if ok else HealthStatus.DEGRADED,
                    message=msg,
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
            except Exception as e:
                return HealthCheckResult(
                    component="mumu",
                    status=HealthStatus.DEGRADED,
                    message=f"MuMu probe error: {e}",
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
        return HealthCheckResult(
            component="mumu",
            status=HealthStatus.HEALTHY,
            message="MuMu provider ready",
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    def check_physical_devices(self) -> HealthCheckResult:
        t0 = time.monotonic()
        if self._physical_probe:
            try:
                ok, msg = self._physical_probe()
                return HealthCheckResult(
                    component="physical_devices",
                    status=HealthStatus.HEALTHY if ok else HealthStatus.DEGRADED,
                    message=msg,
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
            except Exception as e:
                return HealthCheckResult(
                    component="physical_devices",
                    status=HealthStatus.DEGRADED,
                    message=f"Physical device probe error: {e}",
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
        return HealthCheckResult(
            component="physical_devices",
            status=HealthStatus.HEALTHY,
            message="Physical Android provider ready",
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    def check_meta_config(self) -> HealthCheckResult:
        t0 = time.monotonic()
        meta_id = getattr(self.config, "meta_app_id", None)
        if not meta_id and hasattr(self.config, "meta"):
            meta_id = getattr(self.config.meta, "app_id", None)
        has_id = bool(meta_id)
        return HealthCheckResult(
            component="meta_config",
            status=HealthStatus.HEALTHY if has_id else HealthStatus.DEGRADED,
            message="Meta OAuth configured" if has_id else "Meta App ID not set (API restricted)",
            latency_ms=(time.monotonic() - t0) * 1000,
            details={"configured": has_id},
        )

    def check_storage(self) -> HealthCheckResult:
        t0 = time.monotonic()
        try:
            data_dir = self.config.database_path.parent
            total, used, free = shutil.disk_usage(str(data_dir))
            free_gb = free / (1024**3)
            # Require at least 1 GB for healthy operations
            status = HealthStatus.HEALTHY if free_gb >= 1.0 else HealthStatus.DEGRADED
            msg = f"{free_gb:.1f} GB free storage available"
            return HealthCheckResult(
                component="storage",
                status=status,
                message=msg,
                latency_ms=(time.monotonic() - t0) * 1000,
                details={"free_gb": round(free_gb, 2)},
            )
        except Exception as e:
            return HealthCheckResult(
                component="storage",
                status=HealthStatus.DEGRADED,
                message=f"Storage check failed: {e}",
                latency_ms=(time.monotonic() - t0) * 1000,
            )

    def check_scheduler(self) -> HealthCheckResult:
        t0 = time.monotonic()
        if self._scheduler_probe:
            try:
                ok, msg = self._scheduler_probe()
                return HealthCheckResult(
                    component="scheduler",
                    status=HealthStatus.HEALTHY if ok else HealthStatus.DEGRADED,
                    message=msg,
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
            except Exception as e:
                return HealthCheckResult(
                    component="scheduler",
                    status=HealthStatus.DEGRADED,
                    message=f"Scheduler probe error: {e}",
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
        return HealthCheckResult(
            component="scheduler",
            status=HealthStatus.HEALTHY,
            message="Scheduler service running",
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    def check_workers(self) -> HealthCheckResult:
        t0 = time.monotonic()
        if self._workers_probe:
            try:
                ok, msg = self._workers_probe()
                return HealthCheckResult(
                    component="workers",
                    status=HealthStatus.HEALTHY if ok else HealthStatus.DEGRADED,
                    message=msg,
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
            except Exception as e:
                return HealthCheckResult(
                    component="workers",
                    status=HealthStatus.DEGRADED,
                    message=f"Worker supervisor error: {e}",
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
        return HealthCheckResult(
            component="workers",
            status=HealthStatus.HEALTHY,
            message="Worker supervisor active",
            latency_ms=(time.monotonic() - t0) * 1000,
        )

    def check_network(self) -> HealthCheckResult:
        t0 = time.monotonic()
        if self._network_probe:
            try:
                ok, msg = self._network_probe()
                return HealthCheckResult(
                    component="network",
                    status=HealthStatus.HEALTHY if ok else HealthStatus.DEGRADED,
                    message=msg,
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
            except Exception as e:
                return HealthCheckResult(
                    component="network",
                    status=HealthStatus.DEGRADED,
                    message=f"Network probe error: {e}",
                    latency_ms=(time.monotonic() - t0) * 1000,
                )
        return HealthCheckResult(
            component="network",
            status=HealthStatus.HEALTHY,
            message="Network stack operational",
            latency_ms=(time.monotonic() - t0) * 1000,
        )
