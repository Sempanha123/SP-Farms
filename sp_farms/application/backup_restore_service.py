import hashlib
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import zipfile
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sp_farms.application.ports import Clock
from sp_farms.domain.disaster_recovery import (
    BackupItem,
    BackupManifest,
    RestorePreview,
    RetentionPolicy,
)
from sp_farms.infrastructure.vault import (
    KeyringVault,
    decrypt_secret,
    encrypt_secret,
)

logger = logging.getLogger(__name__)

CURRENT_BACKUP_SCHEMA_VERSION = "1.0.0"
CURRENT_APP_VERSION = "1.0.0"


def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class BackupRestoreService:
    """Orchestrates safe, transactional disaster recovery backups and restorations."""

    def __init__(
        self,
        database_path: Path,
        settings_path: Path | None = None,
        workspace_dir: Path | None = None,
        backup_dir: Path | None = None,
        vault: KeyringVault | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.database_path = database_path
        self.settings_path = settings_path
        self.workspace_dir = workspace_dir
        self.backup_dir = backup_dir or (database_path.parent / "backups")
        self.vault = vault
        self.clock = clock
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _now(self) -> datetime:
        if self.clock:
            return self.clock.now()
        return datetime.now(UTC)

    def create_backup(
        self,
        destination_dir: Path | None = None,
        description: str = "Standard System Backup",
        include_secrets: bool = False,
        secrets_passphrase: str | None = None,
        retention_policy: RetentionPolicy | None = None,
        secrets_map: dict[str, str] | None = None,
    ) -> Path:
        """Create a complete, verified system backup archive."""
        dest_dir = destination_dir or self.backup_dir
        dest_dir.mkdir(parents=True, exist_ok=True)

        now = self._now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        backup_id = f"backup_{timestamp_str}"
        archive_name = f"{backup_id}.spbackup"
        archive_path = dest_dir / archive_name

        if include_secrets:
            if not secrets_passphrase or len(secrets_passphrase) < 6:
                raise ValueError("Explicit secrets backup requires a passphrase of at least 6 characters")

        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp)
            items: list[BackupItem] = []

            # 1. Database backup using SQLite online backup API
            if self.database_path.exists():
                db_target = staging / "sp_farms.db"
                # Safe live SQLite backup
                src_conn = sqlite3.connect(str(self.database_path))
                dst_conn = sqlite3.connect(str(db_target))
                try:
                    src_conn.backup(dst_conn)
                finally:
                    dst_conn.close()
                    src_conn.close()

                items.append(
                    BackupItem(
                        name="database",
                        relative_path="sp_farms.db",
                        size_bytes=db_target.stat().st_size,
                        sha256=compute_sha256(db_target),
                    )
                )

            # 2. Settings backup
            if self.settings_path and self.settings_path.exists():
                settings_target = staging / "settings.json"
                shutil.copy2(self.settings_path, settings_target)
                items.append(
                    BackupItem(
                        name="settings",
                        relative_path="settings.json",
                        size_bytes=settings_target.stat().st_size,
                        sha256=compute_sha256(settings_target),
                    )
                )

            # 3. Workspace state and templates
            if self.workspace_dir and self.workspace_dir.exists():
                workspace_target = staging / "workspace"
                shutil.copytree(self.workspace_dir, workspace_target, dirs_exist_ok=True)
                for root, _, files in os.walk(workspace_target):
                    for file in files:
                        p = Path(root) / file
                        rel = p.relative_to(staging).as_posix()
                        items.append(
                            BackupItem(
                                name=f"workspace/{file}",
                                relative_path=rel,
                                size_bytes=p.stat().st_size,
                                sha256=compute_sha256(p),
                            )
                        )

            # 4. Optional Encrypted Secrets Vault Backup
            if include_secrets:
                raw_secrets = secrets_map or {}
                enc_archive = encrypt_secret(json.dumps(raw_secrets), secrets_passphrase)  # type: ignore[arg-type]
                sec_file = staging / "secrets.enc"
                with open(sec_file, "w", encoding="utf-8") as f:
                    f.write(enc_archive.to_json())

                items.append(
                    BackupItem(
                        name="secrets_vault",
                        relative_path="secrets.enc",
                        size_bytes=sec_file.stat().st_size,
                        sha256=compute_sha256(sec_file),
                    )
                )

            # 5. Build Manifest
            combined_hash = hashlib.sha256()
            for it in sorted(items, key=lambda x: x.relative_path):
                combined_hash.update(f"{it.relative_path}:{it.sha256}".encode("utf-8"))

            manifest = BackupManifest(
                backup_id=backup_id,
                version=CURRENT_BACKUP_SCHEMA_VERSION,
                app_version=CURRENT_APP_VERSION,
                created_at=now,
                description=description,
                includes_secrets=include_secrets,
                items=tuple(items),
                checksum=combined_hash.hexdigest(),
            )

            manifest_file = staging / "manifest.json"
            with open(manifest_file, "w", encoding="utf-8") as f:
                json.dump(manifest.to_dict(), f, indent=2)

            # 6. Package into ZIP
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.write(manifest_file, arcname="manifest.json")
                for it in items:
                    file_to_pack = staging / it.relative_path
                    if file_to_pack.exists():
                        zf.write(file_to_pack, arcname=it.relative_path)

        # 7. Apply Retention Rules
        if retention_policy is not None:
            self.apply_retention(retention_policy=retention_policy)

        return archive_path

    def preview_restore(self, archive_path: Path) -> RestorePreview:
        """Inspect and validate a backup archive without modifying current state."""
        if not archive_path.exists():
            return RestorePreview(
                manifest=None,
                is_valid=False,
                validation_errors=[f"Backup file not found: {archive_path}"],
            )

        if not zipfile.is_zipfile(archive_path):
            return RestorePreview(
                manifest=None,
                is_valid=False,
                validation_errors=["File is not a valid zip archive or is corrupted"],
            )

        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                if "manifest.json" not in zf.namelist():
                    return RestorePreview(
                        manifest=None,
                        is_valid=False,
                        validation_errors=["Corrupted backup: missing manifest.json"],
                    )

                manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
                manifest = BackupManifest.from_dict(manifest_data)

                errors: list[str] = []
                warnings: list[str] = []

                # Version check
                major_backup_ver = manifest.version.split(".")[0]
                major_curr_ver = CURRENT_BACKUP_SCHEMA_VERSION.split(".")[0]
                if major_backup_ver > major_curr_ver:
                    errors.append(
                        f"Incompatible backup schema version: {manifest.version} (supported: {CURRENT_BACKUP_SCHEMA_VERSION})"
                    )

                # Integrity verification of every item
                for item in manifest.items:
                    if item.relative_path not in zf.namelist():
                        errors.append(f"Missing file in archive: {item.relative_path}")
                        continue

                    data = zf.read(item.relative_path)
                    actual_sha = hashlib.sha256(data).hexdigest()
                    if actual_sha != item.sha256:
                        errors.append(
                            f"Integrity checksum mismatch for {item.relative_path}: expected {item.sha256}, got {actual_sha}"
                        )

                is_valid = len(errors) == 0
                can_restore = is_valid

                return RestorePreview(
                    manifest=manifest,
                    is_valid=is_valid,
                    validation_errors=tuple(errors),
                    warnings=tuple(warnings),
                    can_restore=can_restore,
                    requires_passphrase=manifest.includes_secrets,
                )

        except Exception as e:
            return RestorePreview(
                manifest=None,
                is_valid=False,
                validation_errors=[f"Failed to read backup archive: {e}"],
            )

    def restore_backup(
        self,
        archive_path: Path,
        secrets_passphrase: str | None = None,
        allow_rollback: bool = True,
    ) -> dict[str, str]:
        """Restore database, settings, and workspace state with automated rollback protection."""
        preview = self.preview_restore(archive_path)
        if not preview.is_valid or not preview.manifest:
            raise ValueError(f"Cannot restore invalid backup archive: {preview.validation_errors}")

        manifest = preview.manifest

        if manifest.includes_secrets and not secrets_passphrase:
            raise ValueError("Passphrase is required to restore secrets from this encrypted backup")

        restored_secrets: dict[str, str] = {}

        # Rollback snapshot directory
        rollback_dir: Path | None = None
        if allow_rollback:
            rollback_dir = Path(tempfile.mkdtemp(prefix="sp_farms_rollback_"))
            if self.database_path.exists():
                shutil.copy2(self.database_path, rollback_dir / self.database_path.name)
            if self.settings_path and self.settings_path.exists():
                shutil.copy2(self.settings_path, rollback_dir / self.settings_path.name)

        try:
            with tempfile.TemporaryDirectory() as tmp:
                extract_dir = Path(tmp)
                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extractall(extract_dir)

                # 1. Restore database
                db_extracted = extract_dir / "sp_farms.db"
                if db_extracted.exists():
                    self.database_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(db_extracted, self.database_path)

                # 2. Restore settings
                if self.settings_path:
                    settings_extracted = extract_dir / "settings.json"
                    if settings_extracted.exists():
                        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(settings_extracted, self.settings_path)

                # 3. Restore workspace
                if self.workspace_dir:
                    ws_extracted = extract_dir / "workspace"
                    if ws_extracted.exists():
                        self.workspace_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copytree(ws_extracted, self.workspace_dir, dirs_exist_ok=True)

                # 4. Restore secrets if present
                sec_extracted = extract_dir / "secrets.enc"
                if sec_extracted.exists() and secrets_passphrase:
                    from sp_farms.infrastructure.vault import EncryptedSecretArchive

                    with open(sec_extracted, encoding="utf-8") as f:
                        enc_archive = EncryptedSecretArchive.from_json(f.read())
                    decrypted_raw = decrypt_secret(enc_archive, secrets_passphrase)
                    restored_secrets = json.loads(decrypted_raw)

                    # Persist to vault if available
                    if self.vault and isinstance(restored_secrets, dict):
                        for k, v in restored_secrets.items():
                            self.vault.store(k, v)

        except Exception as err:
            logger.exception("Restore failed, initiating rollback: %s", err)
            if rollback_dir and rollback_dir.exists():
                rb_db = rollback_dir / self.database_path.name
                if rb_db.exists():
                    shutil.copy2(rb_db, self.database_path)
                if self.settings_path:
                    rb_settings = rollback_dir / self.settings_path.name
                    if rb_settings.exists():
                        shutil.copy2(rb_settings, self.settings_path)
            raise RuntimeError(f"Restore failed and was rolled back: {err}") from err
        finally:
            if rollback_dir and rollback_dir.exists():
                shutil.rmtree(rollback_dir, ignore_errors=True)

        return restored_secrets

    def list_backups(self) -> Sequence[BackupManifest]:
        """Scan backup directory and return list of valid backup manifests."""
        manifests: list[BackupManifest] = []
        if not self.backup_dir.exists():
            return manifests

        for archive in self.backup_dir.glob("*.spbackup"):
            preview = self.preview_restore(archive)
            if preview.manifest:
                manifests.append(preview.manifest)

        manifests.sort(key=lambda m: m.created_at, reverse=True)
        return manifests

    def apply_retention(
        self,
        retention_policy: RetentionPolicy | None = None,
    ) -> int:
        """Prune older backups according to retention policy."""
        policy = retention_policy or RetentionPolicy()
        if not self.backup_dir.exists():
            return 0

        archives = sorted(
            self.backup_dir.glob("*.spbackup"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        cutoff_date = self._now() - timedelta(days=policy.max_age_days)
        pruned = 0

        for idx, archive in enumerate(archives):
            # Check count
            if idx >= policy.max_backups:
                archive.unlink(missing_ok=True)
                pruned += 1
                continue

            # Check age
            mtime = datetime.fromtimestamp(archive.stat().st_mtime, tz=UTC)
            if mtime < cutoff_date:
                archive.unlink(missing_ok=True)
                pruned += 1

        return pruned
