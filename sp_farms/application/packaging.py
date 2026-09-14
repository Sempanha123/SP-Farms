"""Packaging and installation data safety rules for SP-Farms."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path, user_log_path


@dataclass(frozen=True, slots=True)
class InstallationPaths:
    """Standard runtime storage locations for SP-Farms on Windows."""

    data_dir: Path
    log_dir: Path
    database_file: Path
    backup_dir: Path
    vault_dir: Path


def resolve_installation_paths() -> InstallationPaths:
    """Return the upgrade-safe paths outside of the binary installation directory."""
    data_dir = user_data_path("SP-Farms", appauthor=False)
    log_dir = user_log_path("SP-Farms", appauthor=False)
    return InstallationPaths(
        data_dir=data_dir,
        log_dir=log_dir,
        database_file=data_dir / "sp_farms.db",
        backup_dir=data_dir / "backups",
        vault_dir=data_dir / "vault",
    )


def should_preserve_data_on_uninstall(explicit_purge_requested: bool = False) -> bool:
    """Data preservation policy: preserve user databases and backups unless explicitly requested."""
    return not explicit_purge_requested


def purge_user_data_if_requested(
    paths: InstallationPaths | None = None,
    explicit_purge_requested: bool = False,
) -> bool:
    """Purge user data directories only when explicitly requested.

    Returns True if purged, False if preserved.
    """
    if not explicit_purge_requested:
        return False

    target_paths = paths or resolve_installation_paths()
    if target_paths.data_dir.exists():
        shutil.rmtree(target_paths.data_dir, ignore_errors=True)
    if target_paths.log_dir.exists():
        shutil.rmtree(target_paths.log_dir, ignore_errors=True)
    return True
