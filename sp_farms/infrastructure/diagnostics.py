import json
import platform
import zipfile
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path

from sp_farms import __version__
from sp_farms.application.config import AppConfig
from sp_farms.application.diagnostics import RuntimeDiagnostics
from sp_farms.domain.health import HealthSummary
from sp_farms.infrastructure.logging import read_redacted_log, redact


def collect_runtime_diagnostics(
    config: AppConfig,
    provider_statuses: Mapping[str, str] | None = None,
) -> RuntimeDiagnostics:
    return RuntimeDiagnostics(
        app_version=__version__,
        python_version=platform.python_version(),
        operating_system=platform.platform(),
        database_path=config.database_path,
        log_path=config.log_path,
        providers=dict(provider_statuses or {}),
    )


def create_diagnostics_bundle(
    destination: Path,
    config: AppConfig,
    provider_statuses: Mapping[str, str] | None = None,
    health_summary: HealthSummary | None = None,
) -> Path:
    diagnostics = collect_runtime_diagnostics(config, provider_statuses)
    payload = asdict(diagnostics)
    payload["database_path"] = str(diagnostics.database_path)
    payload["log_path"] = str(diagnostics.log_path)
    serialized = redact(json.dumps(payload, indent=2, sort_keys=True))

    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("runtime.json", serialized)
        if health_summary:
            health_payload = {
                "overall_status": health_summary.overall_status.value,
                "checked_at": health_summary.checked_at.isoformat(),
                "checks": [
                    {
                        "component": c.component,
                        "status": c.status.value,
                        "message": c.message,
                        "latency_ms": round(c.latency_ms, 2),
                        "details": dict(c.details),
                    }
                    for c in health_summary.checks
                ],
            }
            bundle.writestr("health_report.json", redact(json.dumps(health_payload, indent=2)))
        log_content = read_redacted_log(config.log_path)
        if log_content:
            bundle.writestr("logs/sp_farms.log", log_content)
    return destination
