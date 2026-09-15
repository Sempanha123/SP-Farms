from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sp_farms.application.account_service import AccountService
from sp_farms.application.snapshot_service import SnapshotService
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyAccountRepository,
    SqlAlchemyDevicePoolRepository,
    SqlAlchemyDeviceProfileRepository,
    run_migrations,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


BackupEnv = tuple[
    SnapshotService,
    AccountService,
    Database,
    Path,
]


@pytest.fixture
def backup_env(tmp_path: Path) -> Generator[BackupEnv, None, None]:
    database = Database(tmp_path / "backup_test.db")
    run_migrations(database, MIGRATIONS)
    clock = FixedClock()
    account_service = AccountService(
        database.unit_of_work,
        SqlAlchemyAccountRepository,
        clock,
    )
    storage_dir = tmp_path / "backups"
    snapshot_service = SnapshotService(
        database.unit_of_work,
        SqlAlchemyDevicePoolRepository,
        SqlAlchemyAccountRepository,
        SqlAlchemyDeviceProfileRepository,
        storage_dir=storage_dir,
        clock=clock,
        max_size_bytes=100 * 1024,  # 100 KB max for test
    )

    yield snapshot_service, account_service, database, storage_dir
    database.close()


def test_create_and_verify_lightweight_snapshot(backup_env: BackupEnv) -> None:
    snapshot_service, accounts, _, storage_dir = backup_env
    acct = accounts.create_account(
        "John Doe",
        "10008899",
        "johndoe@example.com",
    )

    record = snapshot_service.create_snapshot(acct.id, notes="First backup")
    assert record.id is not None
    assert record.account_id == acct.id
    assert Path(record.path).exists()
    assert record.size_bytes > 0
    # Lightweight backup must be compact (under 50KB)
    assert record.size_bytes < 50 * 1024

    # Verify checksum
    assert snapshot_service.verify_snapshot(record.id) is True

    # Read payload
    payload = snapshot_service.read_snapshot_payload(record.id)
    assert payload["display_name"] == "John Doe"
    # Ensure sensitive data like full email / raw password are NOT stored raw
    assert "password" not in payload
    assert "cookies" not in payload
    assert payload["primary_email_masked"].startswith("jo")
    assert "johndoe@example.com" not in payload.values()


def test_snapshot_tamper_detection(backup_env: BackupEnv) -> None:
    snapshot_service, accounts, _, _ = backup_env
    acct = accounts.create_account("Alice Smith", "uid-alice", "alice@example.com")
    record = snapshot_service.create_snapshot(acct.id)

    # Tamper with the file contents
    path = Path(record.path)
    path.write_bytes(b"tampered data corrupted archive")

    # Verify must fail
    assert snapshot_service.verify_snapshot(record.id) is False


def test_export_and_import_snapshot(backup_env: BackupEnv, tmp_path: Path) -> None:
    snapshot_service, accounts, _, _ = backup_env
    acct = accounts.create_account("Export User", "uid-export", "export@example.com")
    record = snapshot_service.create_snapshot(acct.id, notes="To be exported")

    export_path = tmp_path / "exported.spws"
    res = snapshot_service.export_snapshot(record.id, export_path)
    assert res.exists()
    assert res.stat().st_size == record.size_bytes

    # Import into another account
    acct2 = accounts.create_account("Import Target", "uid-target", "target@example.com")
    imported_record = snapshot_service.import_snapshot(export_path, account_id=acct2.id)
    assert imported_record.account_id == acct2.id
    assert snapshot_service.verify_snapshot(imported_record.id) is True


def test_snapshot_size_cap_enforcement(tmp_path: Path) -> None:
    database = Database(tmp_path / "cap_test.db")
    run_migrations(database, MIGRATIONS)
    clock = FixedClock()
    account_service = AccountService(
        database.unit_of_work,
        SqlAlchemyAccountRepository,
        clock,
    )
    # Set cap to tiny 10 bytes to trigger size cap error
    tiny_snapshot_service = SnapshotService(
        database.unit_of_work,
        SqlAlchemyDevicePoolRepository,
        SqlAlchemyAccountRepository,
        SqlAlchemyDeviceProfileRepository,
        storage_dir=tmp_path / "backups",
        clock=clock,
        max_size_bytes=10,
    )
    acct = account_service.create_account("Cap Test User", "uid-cap", "cap@example.com")

    with pytest.raises(ValueError, match="exceeds configured maximum"):
        tiny_snapshot_service.create_snapshot(acct.id)

    database.close()
