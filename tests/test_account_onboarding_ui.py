from collections.abc import Generator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QPushButton

from sp_farms.app.account_workspace import AccountWorkspace
from sp_farms.app.main_window import MainWindow
from sp_farms.application.account_onboarding_service import AccountOnboardingService
from sp_farms.application.account_service import AccountService
from sp_farms.application.context import ApplicationContext
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyAccountRepository,
    run_migrations,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 9, 2, tzinfo=UTC)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    return app  # type: ignore[return-value]


@pytest.fixture
def services(
    tmp_path: Path,
) -> Generator[tuple[AccountService, AccountOnboardingService, Database], None, None]:
    database = Database(tmp_path / "account-ui.db")
    run_migrations(database, MIGRATIONS)
    accounts = AccountService(
        database.unit_of_work,
        SqlAlchemyAccountRepository,
        FixedClock(),
    )
    yield accounts, AccountOnboardingService(accounts), database
    database.close()


def test_manual_onboarding_refreshes_and_masks_account_row(
    qapp: QApplication,
    services: tuple[AccountService, AccountOnboardingService, Database],
) -> None:
    accounts, onboarding, _database = services
    view = AccountWorkspace(accounts, onboarding)
    view.open_onboarding()
    panel = view.onboarding_panel
    panel.display_name_input.setText("UI Account")
    panel.platform_uid_input.setText("ui-001")
    panel.primary_email_input.setText("ui-account@example.com")
    panel.phone_input.setText("+12025550123")

    panel.submit_btn.click()

    assert view.model.rowCount() == 1
    assert view.model.item(0, 2).text() == "u***@example.com"
    assert view.model.item(0, 3).text() == "***0123"
    assert view.table.selectionModel().selectedRows()[0].row() == 0
    assert panel.pages.currentIndex() == 1
    assert not view.grab().isNull()


def test_success_actions_route_through_main_window(
    qapp: QApplication,
    services: tuple[AccountService, AccountOnboardingService, Database],
    tmp_path: Path,
) -> None:
    accounts, onboarding, _database = services
    context = ApplicationContext(
        FixedClock(),
        account_service=accounts,
        account_onboarding_service=onboarding,
    )
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window = MainWindow(context, settings)
    panel = window.account_workspace.onboarding_panel
    window.account_workspace.open_onboarding()
    panel.display_name_input.setText("Route Account")
    panel.platform_uid_input.setText("route-001")
    panel.primary_email_input.setText("route@example.com")
    panel.submit_btn.click()

    pages_button = next(
        button
        for button in panel.findChildren(QPushButton)
        if button.property("actionKey") == "pages"
    )
    pages_button.click()

    assert window.current_section == "Pages"
    window.close()


def test_local_navigation_and_action_pages_are_wired(
    qapp: QApplication,
    services: tuple[AccountService, AccountOnboardingService, Database],
) -> None:
    accounts, onboarding, _database = services
    view = AccountWorkspace(accounts, onboarding)
    routes: list[str] = []
    view.local_navigation_requested.connect(routes.append)

    view.local_nav_buttons["Pages"].click()
    assert routes == ["Pages"]
    assert view.local_nav_buttons["Accounts"].isChecked()

    view.action_nav_buttons[2].click()
    assert view.action_pages.currentIndex() == 2
    assert view.backup_btn.parentWidget() is view.action_pages.widget(2)


def test_account_filters_include_category_device_and_network(
    qapp: QApplication,
    services: tuple[AccountService, AccountOnboardingService, Database],
) -> None:
    accounts, onboarding, _database = services
    category = accounts.create_category("Primary")
    assigned = accounts.create_account("Assigned", "assigned-1", "assigned@example.com")
    accounts.save_account(replace(assigned, category_id=category.id))
    accounts.assign_device(assigned.id, "ldplayer", "device-1")
    accounts.create_account("Offline", "offline-1", "offline@example.com")
    view = AccountWorkspace(accounts, onboarding)

    assert view.category_filter.findData(category.id) >= 0
    view.category_filter.setCurrentIndex(view.category_filter.findData(category.id))
    assert view.model.rowCount() == 1
    assert view.model.item(0, 0).text() == "Assigned"
    assert view.model.item(0, 5).text() == "Primary"

    view.category_filter.setCurrentIndex(0)
    view.network_filter.setCurrentText("Offline")
    assert view.model.rowCount() == 1
    assert view.model.item(0, 0).text() == "Offline"

    view.network_filter.setCurrentText("All Networks")
    view.device_filter.setCurrentText("Assigned")
    assert view.model.rowCount() == 1
    assert view.model.item(0, 0).text() == "Assigned"
