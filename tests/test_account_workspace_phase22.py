import time
from collections.abc import Generator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from sp_farms.app.account_dialogs import (
    BulkCategoryDialog,
    BulkTagDialog,
    ColumnPickerDialog,
)
from sp_farms.app.account_workspace import COLUMNS, AccountWorkspace
from sp_farms.application.account_onboarding_service import AccountOnboardingService
from sp_farms.application.account_service import AccountService
from sp_farms.application.ports import Clock
from sp_farms.domain.account_onboarding import _SECRET_FIELDS
from sp_farms.domain.accounts import (
    AccountStatus,
    PermissionState,
    SecurityState,
)
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyAccountRepository,
    run_migrations,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


class FixedClock(Clock):
    def now(self) -> datetime:
        return datetime(2026, 9, 2, tzinfo=UTC)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    return app  # type: ignore[return-value]


@pytest.fixture
def account_services(
    tmp_path: Path,
) -> Generator[tuple[AccountService, AccountOnboardingService, Database], None, None]:
    database = Database(tmp_path / "phase22_test.db")
    run_migrations(database, MIGRATIONS)
    clock = FixedClock()
    accounts = AccountService(
        database.unit_of_work,
        SqlAlchemyAccountRepository,
        clock,
    )
    onboarding = AccountOnboardingService(accounts)
    yield accounts, onboarding, database
    database.close()


def test_column_picker_and_optional_columns(
    qapp: QApplication,
    account_services: tuple[AccountService, AccountOnboardingService, Database],
    tmp_path: Path,
) -> None:
    from PySide6.QtCore import QSettings

    accounts, onboarding, _ = account_services
    test_settings = QSettings(str(tmp_path / "test_settings.ini"), QSettings.Format.IniFormat)
    workspace = AccountWorkspace(accounts, onboarding, settings=test_settings)

    # 24 defined columns
    assert len(COLUMNS) == 24
    assert COLUMNS[0][0] == "account"
    assert COLUMNS[5][0] == "category"

    # Default visible columns vs optional hidden columns
    assert not workspace.table.isColumnHidden(0)  # Account visible
    assert not workspace.table.isColumnHidden(1)  # Status visible
    assert workspace.table.isColumnHidden(14)  # Birthday hidden by default
    assert workspace.table.isColumnHidden(21)  # Security State hidden by default

    # Toggle columns using ColumnPickerDialog
    visible_set = {i for i in range(len(COLUMNS)) if not workspace.table.isColumnHidden(i)}
    dialog = ColumnPickerDialog(COLUMNS, visible_set, parent=workspace)

    # Select all columns
    dialog.select_all()
    assert len(dialog.selected_column_indices) == 24

    # Deselect all (Account/col 0 stays selected)
    dialog.deselect_all()
    assert 0 in dialog.selected_column_indices
    assert len(dialog.selected_column_indices) == 1

    # Reset defaults
    dialog.reset_defaults()
    default_indices = {i for i, (_, _, d) in enumerate(COLUMNS) if d}
    assert dialog.selected_column_indices == default_indices


def test_smart_filters_and_text_search(
    qapp: QApplication,
    account_services: tuple[AccountService, AccountOnboardingService, Database],
) -> None:
    accounts, onboarding, _ = account_services
    clock = FixedClock()
    now = clock.now()

    # 1. Normal active account with device
    a1 = accounts.create_account("Alice Normal", "uid-001", "alice@example.com")
    accounts.assign_device(a1.id, "ldplayer", "emulator-5554")

    # 2. No device account
    accounts.create_account("Bob Unassigned", "uid-002", "bob@example.com")

    # 3. Expiring session account (> 30 days since last login)
    a3 = accounts.create_account("Charlie Expiring", "uid-003", "charlie@example.com")
    accounts.save_account(replace(a3, last_login_at=now - timedelta(days=45)))

    # 4. Permission issue account
    a4 = accounts.create_account("Dave Revoked", "uid-004", "dave@example.com")
    accounts.save_account(replace(a4, permission_state=PermissionState.REVOKED))

    # 5. Needs review account (Attention status)
    a5 = accounts.create_account("Eve Attention", "uid-005", "eve@example.com")
    accounts.save_account(
        replace(
            a5,
            status=AccountStatus.ATTENTION,
            security_state=SecurityState.REVIEW_REQUIRED,
        )
    )

    workspace = AccountWorkspace(accounts, onboarding)
    workspace.refresh()
    assert workspace.model.rowCount() == 5

    # Text search
    workspace.search_input.setText("alice")
    assert workspace.model.rowCount() == 1
    assert workspace.model.item(0, 0).text() == "Alice Normal"

    workspace.search_input.clear()
    assert workspace.model.rowCount() == 5

    # Smart filter: No Device
    workspace.smart_filter.setCurrentText("No Device")
    names = [workspace.model.item(r, 0).text() for r in range(workspace.model.rowCount())]
    assert "Alice Normal" not in names
    assert "Bob Unassigned" in names

    # Smart filter: Expiring Session
    workspace.smart_filter.setCurrentText("Expiring Session")
    names = [workspace.model.item(r, 0).text() for r in range(workspace.model.rowCount())]
    assert "Charlie Expiring" in names

    # Smart filter: Permission Issue
    workspace.smart_filter.setCurrentText("Permission Issue")
    names = [workspace.model.item(r, 0).text() for r in range(workspace.model.rowCount())]
    assert "Dave Revoked" in names

    # Smart filter: Needs Review
    workspace.smart_filter.setCurrentText("Needs Review")
    names = [workspace.model.item(r, 0).text() for r in range(workspace.model.rowCount())]
    assert "Eve Attention" in names

    workspace.smart_filter.setCurrentText("All Smart Filters")
    assert workspace.model.rowCount() == 5


def test_table_sorting(
    qapp: QApplication,
    account_services: tuple[AccountService, AccountOnboardingService, Database],
) -> None:
    accounts, onboarding, _ = account_services
    a1 = accounts.create_account("Zeta Account", "uid-z", "zeta@example.com")
    a2 = accounts.create_account("Alpha Account", "uid-a", "alpha@example.com")
    accounts.save_account(replace(a1, page_count=10))
    accounts.save_account(replace(a2, page_count=2))

    workspace = AccountWorkspace(accounts, onboarding)
    workspace.refresh()

    # Sort ascending by Account Name (Col 0)
    workspace.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
    assert workspace.model.item(0, 0).text() == "Alpha Account"
    assert workspace.model.item(1, 0).text() == "Zeta Account"

    # Sort descending by Account Name (Col 0)
    workspace.table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
    assert workspace.model.item(0, 0).text() == "Zeta Account"
    assert workspace.model.item(1, 0).text() == "Alpha Account"

    # Sort ascending by Pages (Col 9) - numeric check
    workspace.table.sortByColumn(9, Qt.SortOrder.AscendingOrder)
    assert workspace.model.item(0, 0).text() == "Alpha Account"  # 2 pages
    assert workspace.model.item(1, 0).text() == "Zeta Account"  # 10 pages


def test_bulk_actions_and_context_menu(
    qapp: QApplication,
    account_services: tuple[AccountService, AccountOnboardingService, Database],
) -> None:
    accounts, onboarding, _ = account_services
    cat1 = accounts.create_category("VIP Category")
    tag1 = accounts.create_tag("Priority Tag")

    accounts.create_account("User One", "uid-01", "one@example.com")
    accounts.create_account("User Two", "uid-02", "two@example.com")

    workspace = AccountWorkspace(accounts, onboarding)
    workspace.refresh()

    # Select both rows
    workspace.table.selectAll()
    selected = workspace.selected_account_ids
    assert len(selected) == 2

    # Bulk assign category
    accounts.bulk_assign_category(selected, cat1.id)
    workspace.refresh()
    assert workspace.model.item(0, 5).text() == "VIP Category"
    assert workspace.model.item(1, 5).text() == "VIP Category"

    # Bulk set tags
    accounts.bulk_set_tags(selected, (tag1.id,))
    workspace.refresh()
    workspace.table.selectRow(0)
    assert tag1.name in workspace.insp_tags.text()

    # Bulk dialogs
    cat_dlg = BulkCategoryDialog(((cat1.id, cat1.name),), 2, parent=workspace)
    cat_dlg.category_combo.setCurrentIndex(1)
    assert cat_dlg.selected_category_id == cat1.id

    tag_dlg = BulkTagDialog(((tag1.id, tag1.name),), 2, parent=workspace)
    tag_dlg._tag_checkboxes[0].setChecked(True)
    assert tag_dlg.selected_tag_ids == (tag1.id,)

    # Bulk archive
    accounts.bulk_archive(selected)
    workspace.refresh()
    assert workspace.model.rowCount() == 0  # archived accounts excluded from list


def test_safe_metadata_export(
    qapp: QApplication,
    account_services: tuple[AccountService, AccountOnboardingService, Database],
    tmp_path: Path,
) -> None:
    accounts, onboarding, _ = account_services
    cat = accounts.create_category("Export Category")
    tag = accounts.create_tag("Export Tag")
    acct = accounts.create_account("Export Target", "uid-exp", "secret_user@example.com")
    accounts.save_account(replace(acct, category_id=cat.id, notes="Important account notes"))
    accounts.set_tags(acct.id, (tag.id,))

    workspace = AccountWorkspace(accounts, onboarding)
    workspace.refresh()

    # JSON export
    json_path = tmp_path / "accounts_export.json"
    records = workspace.export_metadata([acct.id], destination_path=json_path, export_format="json")

    assert len(records) == 1
    rec = records[0]
    assert rec["display_name"] == "Export Target"
    assert rec["platform_uid"] == "uid-exp"
    assert rec["notes"] == "Important account notes"
    # Email must be masked
    assert "@" in rec["primary_email"]
    assert "secret_user" not in rec["primary_email"]

    # Invariant: NO secret fields exported
    for secret in _SECRET_FIELDS:
        assert secret not in rec

    assert json_path.exists()

    # CSV export
    csv_path = tmp_path / "accounts_export.csv"
    csv_records = workspace.export_metadata(
        [acct.id], destination_path=csv_path, export_format="csv"
    )
    assert len(csv_records) == 1
    assert csv_path.exists()
    csv_content = csv_path.read_text(encoding="utf-8")
    assert "Export Target" in csv_content
    assert "Important account notes" in csv_content


def test_large_dataset_performance(
    qapp: QApplication,
    account_services: tuple[AccountService, AccountOnboardingService, Database],
) -> None:
    accounts, onboarding, _ = account_services

    # Create 250 accounts in batch
    for i in range(250):
        accounts.create_account(
            f"Bulk Account {i:03d}",
            f"uid-{i:04d}",
            f"user_{i}@example.com",
        )

    workspace = AccountWorkspace(accounts, onboarding)

    # Time populate
    t0 = time.perf_counter()
    workspace.refresh()
    populate_duration = time.perf_counter() - t0

    assert workspace.model.rowCount() == 250
    # Must populate 250 accounts into table in less than 0.5s
    assert populate_duration < 0.5

    # Time search filter
    t1 = time.perf_counter()
    workspace.search_input.setText("123")
    filter_duration = time.perf_counter() - t1

    assert workspace.model.rowCount() == 1
    assert workspace.model.item(0, 0).text() == "Bulk Account 123"
    # Must filter in less than 1.0s
    assert filter_duration < 1.0


def test_account_workspace_context_menu(
    qapp: QApplication,
    account_services: tuple[AccountService, AccountOnboardingService, Database],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PySide6.QtWidgets import QMenu

    accounts, onboarding, _ = account_services
    accounts.create_account("Menu Test Account", "uid-menu", "menu@example.com")
    workspace = AccountWorkspace(accounts, onboarding)
    workspace.refresh()

    workspace.table.selectRow(0)
    index = workspace.table.model().index(0, 0)

    exec_called: list[bool] = []

    class NonModalMenu(QMenu):
        def exec(self, *args, **kwargs):
            exec_called.append(True)
            return None

    monkeypatch.setattr("sp_farms.app.account_workspace.QMenu", NonModalMenu)

    workspace._show_context_menu(workspace.table.visualRect(index).center())
    assert len(exec_called) == 1
