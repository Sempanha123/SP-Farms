import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sp_farms.application.backup_restore_service import (
    CURRENT_APP_VERSION,
    CURRENT_BACKUP_SCHEMA_VERSION,
    BackupRestoreService,
)
from sp_farms.domain.disaster_recovery import (
    RetentionPolicy,
)


class DummyClock:
    def __init__(self, current_time: datetime) -> None:
        self._current_time = current_time

    def now(self) -> datetime:
        return self._current_time


@pytest.fixture
def test_env(tmp_path: Path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO users (name) VALUES ('Alice'), ('Bob')")
    conn.commit()
    conn.close()

    settings_path = tmp_path / "settings.json"
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump({"theme": "dark", "locale": "en_US"}, f)

    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "template.txt").write_text("Hello {name}!", encoding="utf-8")

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    clock = DummyClock(datetime(2026, 3, 29, 12, 0, 0, tzinfo=UTC))

    service = BackupRestoreService(
        database_path=db_path,
        settings_path=settings_path,
        workspace_dir=ws_dir,
        backup_dir=backup_dir,
        clock=clock,
    )

    return {
        "service": service,
        "db_path": db_path,
        "settings_path": settings_path,
        "ws_dir": ws_dir,
        "backup_dir": backup_dir,
        "clock": clock,
    }


def test_create_standard_backup_and_preview(test_env):
    service: BackupRestoreService = test_env["service"]
    archive_path = service.create_backup(description="Initial test backup")

    assert archive_path.exists()
    assert archive_path.suffix == ".spbackup"

    preview = service.preview_restore(archive_path)
    assert preview.is_valid is True
    assert preview.can_restore is True
    assert preview.requires_passphrase is False
    assert preview.manifest is not None
    assert preview.manifest.description == "Initial test backup"
    assert preview.manifest.app_version == CURRENT_APP_VERSION
    assert preview.manifest.version == CURRENT_BACKUP_SCHEMA_VERSION

    # Should include database, settings, and workspace items
    item_names = [it.name for it in preview.manifest.items]
    assert "database" in item_names
    assert "settings" in item_names
    assert "workspace/template.txt" in item_names


def test_restore_standard_backup(test_env):
    service: BackupRestoreService = test_env["service"]
    db_path: Path = test_env["db_path"]
    settings_path: Path = test_env["settings_path"]

    archive_path = service.create_backup(description="Before modification")

    # Modify database and settings
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO users (name) VALUES ('Charlie')")
    conn.commit()
    conn.close()

    settings_path.write_text(json.dumps({"theme": "light"}), encoding="utf-8")

    # Verify changes applied
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT name FROM users").fetchall()
    conn.close()
    assert len(rows) == 3

    # Restore from backup
    service.restore_backup(archive_path)

    # Verify restored state
    conn = sqlite3.connect(str(db_path))
    restored_rows = conn.execute("SELECT name FROM users").fetchall()
    conn.close()
    assert len(restored_rows) == 2
    assert [r[0] for r in restored_rows] == ["Alice", "Bob"]

    restored_settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert restored_settings["theme"] == "dark"


def test_create_encrypted_secrets_backup_and_restore(test_env):
    service: BackupRestoreService = test_env["service"]
    secrets = {"fb_token_1": "secret_abc123", "meta_app_secret": "xyz789"}

    archive_path = service.create_backup(
        description="Encrypted Secrets Backup",
        include_secrets=True,
        secrets_passphrase="SuperSecretPassword123",
        secrets_map=secrets,
    )

    preview = service.preview_restore(archive_path)
    assert preview.is_valid is True
    assert preview.requires_passphrase is True
    assert preview.manifest.includes_secrets is True

    # Attempting restore without passphrase must fail
    with pytest.raises(ValueError, match="Passphrase is required"):
        service.restore_backup(archive_path, secrets_passphrase=None)

    # Restoring with correct passphrase succeeds
    restored = service.restore_backup(archive_path, secrets_passphrase="SuperSecretPassword123")
    assert restored == secrets


def test_corrupted_backup_integrity_validation(test_env):
    import zipfile

    service: BackupRestoreService = test_env["service"]
    archive_path = service.create_backup(description="Tamper Test")

    # Tamper with the zip contents by modifying a file
    tampered_archive = test_env["backup_dir"] / "tampered.spbackup"
    with (
        zipfile.ZipFile(archive_path, "r") as zin,
        zipfile.ZipFile(tampered_archive, "w") as zout,
    ):
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "settings.json":
                data = b'{"tampered": true}'
            zout.writestr(item, data)

    preview = service.preview_restore(tampered_archive)
    assert preview.is_valid is False
    assert preview.can_restore is False
    assert any("Integrity checksum mismatch" in err for err in preview.validation_errors)

    with pytest.raises(ValueError, match="Cannot restore invalid backup archive"):
        service.restore_backup(tampered_archive)


def test_retention_policy(test_env):
    service: BackupRestoreService = test_env["service"]
    clock: DummyClock = test_env["clock"]

    # Create 5 backups spaced by days
    for i in range(5):
        clock._current_time = datetime(2026, 3, 1 + i, 12, 0, 0, tzinfo=UTC)
        service.create_backup(description=f"Backup {i}")

    all_backups = list(test_env["backup_dir"].glob("*.spbackup"))
    assert len(all_backups) == 5

    # Apply policy: max 3 backups
    clock._current_time = datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC)
    pruned = service.apply_retention(RetentionPolicy(max_backups=3, max_age_days=30))
    assert pruned == 2
    remaining = list(test_env["backup_dir"].glob("*.spbackup"))
    assert len(remaining) == 3


def test_restore_rollback_on_failure(test_env, monkeypatch):
    service: BackupRestoreService = test_env["service"]
    db_path: Path = test_env["db_path"]
    archive_path = service.create_backup(description="Safe Rollback Test")

    original_db_content = db_path.read_bytes()

    # Simulate catastrophic error during restore by patching shutil.copytree to fail
    def failing_copytree(*args, **kwargs):
        raise OSError("Disk simulated write failure")

    monkeypatch.setattr("shutil.copytree", failing_copytree)

    with pytest.raises(RuntimeError, match="Restore failed and was rolled back"):
        service.restore_backup(archive_path)

    # Database file must remain completely intact due to rollback
    assert db_path.read_bytes() == original_db_content
