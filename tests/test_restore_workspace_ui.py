from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from sp_farms.app.account_workspace import AccountWorkspace
from sp_farms.app.main_window import MainWindow
from sp_farms.application.account_onboarding_service import AccountOnboardingService
from sp_farms.application.account_service import AccountService
from sp_farms.application.context import ApplicationContext
from sp_farms.application.device_service import DeviceService
from sp_farms.application.restore_workspace_service import RestoreWorkspaceService
from sp_farms.domain.accounts import PreferredApp
from sp_farms.domain.providers import DeviceProviderType
from sp_farms.infrastructure.adb.fake import FakeAdbAdapter, SimulatedDevice
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyAccountRepository,
    SqlAlchemyDeviceProfileRepository,
    run_migrations,
)
from sp_farms.infrastructure.providers.ldplayer import FakeLdPlayerProvider

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 9, 2, tzinfo=UTC)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    return app  # type: ignore[return-value]


UIContext = tuple[
    AccountService,
    AccountOnboardingService,
    RestoreWorkspaceService,
    Database,
]


@pytest.fixture
def ui_context(tmp_path: Path) -> Generator[UIContext, None, None]:
    database = Database(tmp_path / "restore-ui.db")
    run_migrations(database, MIGRATIONS)
    clock = FixedClock()
    accounts = AccountService(
        database.unit_of_work,
        SqlAlchemyAccountRepository,
        clock,
    )
    onboarding = AccountOnboardingService(accounts)

    adb = FakeAdbAdapter()
    adb.add_device(
        SimulatedDevice(
            serial="emulator-5554",
            installed_packages={"com.facebook.katana", "com.android.chrome"},
        )
    )
    ldplayer = FakeLdPlayerProvider()
    device_service = DeviceService(
        (ldplayer,),
        database.unit_of_work,
        SqlAlchemyDeviceProfileRepository,
        tmp_path / "artifacts",
    )

    restore_service = RestoreWorkspaceService(
        database.unit_of_work,
        SqlAlchemyDeviceProfileRepository,
        accounts,
        device_service,
        adb,
        clock,
        providers=(ldplayer,),
    )

    yield accounts, onboarding, restore_service, database
    database.close()


def test_restore_workspace_button_enablement_and_action(
    qapp: QApplication,
    ui_context: UIContext,
) -> None:
    accounts, onboarding, restore_service, _database = ui_context
    account = accounts.create_account("Demo User", "demo-1", "demo@example.test")
    restore_service.bind_device(
        account.id,
        DeviceProviderType.LDPLAYER,
        "0",
        preferred_app=PreferredApp.FACEBOOK,
    )

    view = AccountWorkspace(accounts, onboarding, restore_service)
    assert not view.restore_btn.isEnabled()

    view.select_account(account.id)
    assert view.restore_btn.isEnabled()

    # Trigger restore synchronously or via action
    result = restore_service.restore_workspace(account.id)
    assert result.success is True

    view.status_chip.update_state("success", result.message)
    assert "Restored workspace" in view.status_chip.text()
    assert not view.grab().isNull()


def test_main_window_wires_restore_service(
    qapp: QApplication,
    ui_context: UIContext,
    tmp_path: Path,
) -> None:
    accounts, onboarding, restore_service, _database = ui_context
    clock = FixedClock()
    context = ApplicationContext(
        clock=clock,
        account_service=accounts,
        account_onboarding_service=onboarding,
        restore_workspace_service=restore_service,
    )
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window = MainWindow(context, settings)
    assert window.account_workspace._restore_service is not None
    window.close()


def test_account_workspace_multi_selection_and_inspector(
    qapp: QApplication,
    ui_context: UIContext,
) -> None:
    accounts, onboarding, restore_service, _ = ui_context
    acct1 = accounts.create_account("Alice Multi", "uid-m1", "m1@example.com")
    accounts.create_account("Bob Multi", "uid-m2", "m2@example.com")

    view = AccountWorkspace(accounts, onboarding, restore_service)
    view.refresh()

    # Select both accounts
    view.table.selectAll()
    assert len(view.selected_account_ids) == 2

    # Verify inspector populated for selected
    view.select_account(acct1.id)
    assert view.selected_account_id == acct1.id
    assert view.insp_bound_device.text() == "None"
    assert "Selected: 1" in view.bottom_strip.text()
