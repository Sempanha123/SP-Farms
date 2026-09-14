from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sp_farms.application.account_exchange_service import AccountExchangeService
from sp_farms.application.account_service import AccountService
from sp_farms.application.ports import Clock
from sp_farms.application.secret_service import SecretService
from sp_farms.domain.account_exchange import (
    ConflictStrategy,
    ExportFormat,
    ExportPreset,
)
from sp_farms.domain.secrets import SecretType
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyAccountRepository,
    SqlAlchemySecretRepository,
    run_migrations,
)
from sp_farms.infrastructure.vault import KeyringVault

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


class FixedClock(Clock):
    def now(self) -> datetime:
        return datetime(2026, 9, 3, 12, 0, 0, tzinfo=UTC)


class InMemoryKeyring:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        self._data[f"{service}:{username}"] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self._data.get(f"{service}:{username}")

    def delete_password(self, service: str, username: str) -> None:
        self._data.pop(f"{service}:{username}", None)


@pytest.fixture
def exchange_service(
    tmp_path: Path,
) -> Generator[tuple[AccountExchangeService, AccountService, SecretService, Database], None, None]:
    db = Database(tmp_path / "exchange_test.db")
    run_migrations(db, MIGRATIONS)
    clock = FixedClock()
    accounts = AccountService(db.unit_of_work, SqlAlchemyAccountRepository, clock)
    keyring_backend = InMemoryKeyring()
    vault = KeyringVault(backend=keyring_backend)
    secrets = SecretService(vault)
    exchange = AccountExchangeService(
        accounts=accounts,
        unit_of_work=db.unit_of_work,
        secrets=secrets,
        secret_repository_factory=SqlAlchemySecretRepository,
    )
    yield exchange, accounts, secrets, db
    db.close()


def test_csv_export_and_import_roundtrip(
    exchange_service: tuple[AccountExchangeService, AccountService, SecretService, Database],
) -> None:
    exchange, accounts, _, _ = exchange_service
    accounts.create_account("Alpha User", "1001", "alpha@example.com")
    accounts.create_account("Beta User", "1002", "beta@example.com")

    # 1. Export to CSV
    csv_bytes = exchange.export_accounts(export_format=ExportFormat.CSV)
    assert csv_bytes.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
    csv_text = csv_bytes.decode("utf-8-sig")
    assert "Alpha User" in csv_text
    assert "Beta User" in csv_text
    assert "1001" in csv_text
    assert "1002" in csv_text

    # 2. Dry run import
    dry_run = exchange.dry_run_import(csv_bytes, file_format=ExportFormat.CSV)
    assert dry_run.total_rows == 2
    assert dry_run.valid_count == 2
    assert dry_run.duplicate_count == 2  # Already exist
    assert not dry_run.has_errors

    # 3. Import new data via CSV
    new_csv = b"Name,UID,Email\nCharlie User,1003,charlie@example.com\n"
    dry_run2 = exchange.dry_run_import(new_csv, file_format=ExportFormat.CSV)
    assert dry_run2.total_rows == 1
    assert dry_run2.valid_count == 1
    assert dry_run2.duplicate_count == 0

    res = exchange.execute_import(dry_run2, conflict_strategy=ConflictStrategy.SKIP)
    assert res.created_count == 1
    all_accts = accounts.list_accounts()
    assert len(all_accts) == 3
    assert any(a.platform_uid == "1003" for a in all_accts)


def test_xlsx_export_and_import_roundtrip(
    exchange_service: tuple[AccountExchangeService, AccountService, SecretService, Database],
) -> None:
    exchange, accounts, _, _ = exchange_service
    accounts.create_account("Delta User", "2001", "delta@example.com")

    # 1. Export to XLSX
    xlsx_bytes = exchange.export_accounts(export_format=ExportFormat.XLSX)
    assert len(xlsx_bytes) > 500

    # 2. Dry-run import XLSX
    dry_run = exchange.dry_run_import(xlsx_bytes, file_format=ExportFormat.XLSX)
    assert dry_run.total_rows == 1
    assert dry_run.valid_count == 1
    assert dry_run.duplicate_count == 1

    # 3. Create fresh DB service and import
    new_xlsx_row = b"Name,UID,Email\nEcho User,2002,echo@example.com\n"
    dry_run_csv = exchange.dry_run_import(new_xlsx_row, filename="accounts.csv")
    exec_res = exchange.execute_import(dry_run_csv)
    assert exec_res.created_count == 1

    # Export again with 2 accounts and dry-run
    xlsx_all = exchange.export_accounts(export_format=ExportFormat.XLSX)
    dry_run_all = exchange.dry_run_import(xlsx_all, filename="accounts.xlsx")
    assert dry_run_all.total_rows == 2
    assert dry_run_all.valid_count == 2
    assert dry_run_all.duplicate_count == 2


def test_json_export_and_import_roundtrip(
    exchange_service: tuple[AccountExchangeService, AccountService, SecretService, Database],
) -> None:
    exchange, accounts, _, _ = exchange_service
    accounts.create_account("Foxtrot User", "3001", "foxtrot@example.com")

    json_bytes = exchange.export_accounts(export_format=ExportFormat.JSON)
    json_text = json_bytes.decode("utf-8")
    assert "schema_version" in json_text
    assert "Foxtrot User" in json_text

    dry_run = exchange.dry_run_import(json_bytes, file_format=ExportFormat.JSON)
    assert dry_run.total_rows == 1
    assert dry_run.valid_count == 1


def test_export_presets(
    exchange_service: tuple[AccountExchangeService, AccountService, SecretService, Database],
) -> None:
    exchange, accounts, _, _ = exchange_service
    accounts.create_account("Golf User", "4001", "golf@example.com")

    basic_csv = exchange.export_accounts(
        export_format=ExportFormat.CSV, preset=ExportPreset.BASIC
    ).decode("utf-8-sig")
    header_line = basic_csv.splitlines()[0]
    assert "Platform UID" in header_line
    assert "Name" in header_line
    assert "Primary Email" in header_line
    assert "Pages" not in header_line
    assert "Security State" not in header_line

    sec_csv = exchange.export_accounts(
        export_format=ExportFormat.CSV, preset=ExportPreset.SECURITY_AUDIT
    ).decode("utf-8-sig")
    sec_header = sec_csv.splitlines()[0]
    assert "Security State" in sec_header
    assert "2FA Enabled" in sec_header

    ops_csv = exchange.export_accounts(
        export_format=ExportFormat.CSV, preset=ExportPreset.OPERATIONS
    ).decode("utf-8-sig")
    ops_header = ops_csv.splitlines()[0]
    assert "Device" in ops_header
    assert "Provider" in ops_header


def test_strict_secret_exclusion_in_export_and_import(
    exchange_service: tuple[AccountExchangeService, AccountService, SecretService, Database],
) -> None:
    exchange, accounts, _, _ = exchange_service
    accounts.create_account("Hotel User", "5001", "hotel@example.com")

    # Verify normal export never has secrets
    for fmt in (ExportFormat.CSV, ExportFormat.XLSX, ExportFormat.JSON):
        data = exchange.export_accounts(export_format=fmt)
        if fmt != ExportFormat.XLSX:
            text = data.decode("utf-8", errors="ignore")
            assert "password" not in text.casefold()
            assert "access_token" not in text.casefold()
            assert "cookie" not in text.casefold()

    # Verify import rejects forbidden secret fields
    malicious_json = (
        b'{"name": "Evil", "uid": "666", "email": "evil@example.com", "password": "plaintext-pw"}'
    )
    dry_run = exchange.dry_run_import(malicious_json, file_format=ExportFormat.JSON)
    assert dry_run.has_errors
    assert any("forbidden secret" in err for err in dry_run.rows[0].errors)


def test_duplicate_detection_and_conflict_strategies(
    exchange_service: tuple[AccountExchangeService, AccountService, SecretService, Database],
) -> None:
    exchange, accounts, _, _ = exchange_service
    orig = accounts.create_account("Original Name", "6001", "orig@example.com")

    import_data = b"Name,UID,Email,Notes\nUpdated Name,6001,updated@example.com,New note\n"

    # 1. SKIP strategy
    dry_run = exchange.dry_run_import(import_data, file_format=ExportFormat.CSV)
    assert dry_run.duplicate_count == 1
    res_skip = exchange.execute_import(dry_run, conflict_strategy=ConflictStrategy.SKIP)
    assert res_skip.skipped_count == 1
    assert res_skip.created_count == 0
    assert res_skip.updated_count == 0
    unchanged = accounts.get_account(orig.id)
    assert unchanged.display_name == "Original Name"

    # 2. OVERWRITE strategy
    res_overwrite = exchange.execute_import(dry_run, conflict_strategy=ConflictStrategy.OVERWRITE)
    assert res_overwrite.updated_count == 1
    updated = accounts.get_account(orig.id)
    assert updated.display_name == "Updated Name"
    assert updated.notes == "New note"

    # 3. ERROR strategy
    with pytest.raises(ValueError, match="duplicates detected"):
        exchange.execute_import(dry_run, conflict_strategy=ConflictStrategy.ERROR)


def test_invalid_import_rows_reporting(
    exchange_service: tuple[AccountExchangeService, AccountService, SecretService, Database],
) -> None:
    exchange, _, _, _ = exchange_service
    bad_csv = (
        b"Name,UID,Email\n"
        b",7001,good@example.com\n"  # Missing name
        b"Valid Name,,good2@example.com\n"  # Missing UID
        b"Valid Name 2,7003,not-an-email\n"  # Invalid email
    )

    dry_run = exchange.dry_run_import(bad_csv, file_format=ExportFormat.CSV)
    assert dry_run.total_rows == 3
    assert dry_run.valid_count == 0
    assert dry_run.error_count == 3
    assert "Missing required field: display_name" in dry_run.rows[0].errors[0]
    assert "Missing required field: platform_uid" in dry_run.rows[1].errors[0]
    assert "Missing or invalid primary email" in dry_run.rows[2].errors[0]


def test_encrypted_vault_backup_and_restore_roundtrip(
    exchange_service: tuple[AccountExchangeService, AccountService, SecretService, Database],
) -> None:
    exchange, accounts, secrets, _ = exchange_service
    acct = accounts.create_account("Vault Account", "8001", "vault@example.com")

    # Store a password in the vault for this account
    pw_ref = secrets.create_reference(SecretType.PASSWORD, acct.id, "super-secret-password-123")
    totp_ref = secrets.create_reference(SecretType.RECOVERY_SECRET, acct.id, "JBSWY3DPEHPK3PXP")
    with exchange_service[3].unit_of_work() as uow:
        repo = SqlAlchemySecretRepository(uow)
        repo.save(pw_ref)
        repo.save(totp_ref)
        uow.commit()

    passphrase = "CorrectHorseBatteryStaple123!"

    # 1. Export vault archive
    archive_bytes = exchange.export_vault_archive(passphrase)
    assert b"super-secret-password-123" not in archive_bytes  # Strongly encrypted
    assert b"ciphertext" in archive_bytes

    # 2. Delete secret from keyring to simulate restore
    secrets.delete(pw_ref)
    assert secrets.reveal(pw_ref) is None

    # 3. Restore with correct passphrase
    restored = exchange.import_vault_archive(archive_bytes, passphrase)
    assert restored >= 1

    # 4. Wrong passphrase fails
    with pytest.raises(ValueError, match="Invalid passphrase"):
        exchange.import_vault_archive(archive_bytes, "WrongPassphrase123!")


def test_workspace_exchange_dialog_wiring(
    exchange_service: tuple[AccountExchangeService, AccountService, SecretService, Database],
) -> None:
    from PySide6.QtWidgets import QApplication

    from sp_farms.app.account_exchange_dialogs import AccountExportDialog, AccountImportDialog
    from sp_farms.app.account_workspace import AccountWorkspace
    from sp_farms.application.account_onboarding_service import AccountOnboardingService

    app = QApplication.instance() or QApplication([])
    assert app is not None

    exchange, accounts, _, _ = exchange_service
    onboarding = AccountOnboardingService(accounts)
    workspace = AccountWorkspace(
        accounts=accounts,
        onboarding=onboarding,
        exchange_service=exchange,
    )
    assert workspace._exchange_service is exchange

    # Verify dialogs instantiate cleanly with the service
    export_dlg = AccountExportDialog(exchange, parent=workspace)
    assert export_dlg.windowTitle() == "Export Accounts Metadata"

    import_dlg = AccountImportDialog(exchange, parent=workspace)
    assert import_dlg.windowTitle() == "Import Accounts Metadata"
