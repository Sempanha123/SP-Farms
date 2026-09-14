import os
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from platformdirs import user_data_path, user_log_path

from sp_farms.application.config import AppConfig

_ENVIRONMENT_KEYS = {
    "SP_FARMS_ENV": "environment",
    "SP_FARMS_LOG_LEVEL": "log_level",
    "SP_FARMS_DATABASE_PATH": "database_path",
    "SP_FARMS_LOG_PATH": "log_path",
    "SP_FARMS_LOG_MAX_BYTES": "log_max_bytes",
    "SP_FARMS_LOG_BACKUP_COUNT": "log_backup_count",
    "SP_FARMS_ADB_PATH": "adb_path",
}
_ALLOWED_FILE_KEYS = frozenset(_ENVIRONMENT_KEYS.values())
_SECRET_MARKERS = ("authorization", "cookie", "password", "secret", "token")


def load_config(
    config_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> AppConfig:
    environment = os.environ if environ is None else environ
    data_dir = user_data_path("SP-Farms", appauthor=False)
    values: dict[str, Any] = {
        "environment": "production",
        "log_level": "INFO",
        "database_path": data_dir / "sp_farms.db",
        "log_path": user_log_path("SP-Farms", appauthor=False) / "sp_farms.log",
        "log_max_bytes": 5_000_000,
        "log_backup_count": 5,
    }

    selected_path = config_path
    if selected_path is None and environment.get("SP_FARMS_CONFIG"):
        selected_path = Path(environment["SP_FARMS_CONFIG"])
    if selected_path is not None and selected_path.exists():
        file_values = _read_local_config(selected_path)
        values.update(file_values)

    for variable, key in _ENVIRONMENT_KEYS.items():
        if variable in environment:
            values[key] = environment[variable]

    values["log_level"] = str(values["log_level"]).upper()
    values["database_path"] = Path(values["database_path"])
    values["log_path"] = Path(values["log_path"])
    values["log_max_bytes"] = int(values["log_max_bytes"])
    values["log_backup_count"] = int(values["log_backup_count"])
    if "adb_path" in values and values["adb_path"] is not None:
        values["adb_path"] = Path(values["adb_path"])
    else:
        values["adb_path"] = None
    return AppConfig(**values)


def _read_local_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        document = tomllib.load(stream)
    values = document.get("sp_farms", {})
    if not isinstance(values, dict):
        raise ValueError("[sp_farms] must be a table")
    unknown = set(values) - _ALLOWED_FILE_KEYS
    if unknown:
        raise ValueError(f"Unsupported config keys: {', '.join(sorted(unknown))}")
    if any(marker in key.lower() for key in values for marker in _SECRET_MARKERS):
        raise ValueError("Secrets are not allowed in the local config file")
    return values
