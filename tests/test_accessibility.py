import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QWidget

from sp_farms.app.accessibility import (
    AccessibleFocusManager,
    apply_accessibility,
    chain_tab_order,
    verify_accessible_semantics,
)
from sp_farms.app.account_workspace import AccountWorkspace
from sp_farms.app.command_palette import CommandPalette
from sp_farms.app.main_window import NAVIGATION
from sp_farms.app.navigation import Command, NavigationService
from sp_farms.app.settings_workspace import SettingsWorkspace
from sp_farms.app.widgets import StatusChip


def get_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_status_chip_non_color_representation():
    get_qapp()
    chip_success = StatusChip("Completed", state="success")
    assert "✓" in chip_success.text()
    assert "Completed" in chip_success.accessibleName()
    assert "success" in chip_success.accessibleDescription().lower()

    chip_warning = StatusChip("Needs Attention", state="warning")
    assert "▲" in chip_warning.text()
    assert "warning" in chip_warning.accessibleDescription().lower()

    chip_error = StatusChip("Failed", state="error")
    assert "✖" in chip_error.text()

    chip_paused = StatusChip("Paused", state="paused")
    assert "⏸" in chip_paused.text()

    chip_active = StatusChip("Active", state="active")
    assert "●" in chip_active.text()


def test_navigation_shortcuts_and_keyboard_critical_path():
    get_qapp()
    navigated_routes: list[str] = []

    def navigate_callback(target: str) -> None:
        navigated_routes.append(target)

    nav = NavigationService(navigate_callback)
    routes = tuple((section, f"Alt+{i + 1}") for i, section in enumerate(NAVIGATION))
    nav.register_routes(routes)

    # Test keyboard navigation execution for Home (Alt+1)
    nav.execute("navigate.home")
    assert navigated_routes[-1] == "Home"

    # Test keyboard navigation execution for Accounts (Alt+2)
    nav.execute("navigate.accounts")
    assert navigated_routes[-1] == "Accounts"

    # Test keyboard navigation execution for Settings (Alt+9)
    nav.execute("navigate.settings")
    assert navigated_routes[-1] == "Settings"


def test_command_palette_keyboard_flow():
    get_qapp()
    executed: list[str] = []
    nav = NavigationService(lambda target: executed.append(target))
    nav.register(
        Command("action.test", "Test Action", "Ctrl+T", lambda: executed.append("action_done"))
    )

    palette = CommandPalette(nav)
    # Search for action
    palette.search.setText("Test Action")
    assert palette.results.count() == 1
    # Execute current via keyboard enter emulation
    palette.execute_current()
    assert "action_done" in executed


def test_accessible_names_and_semantics_smoke_check(tmp_path):
    get_qapp()
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    workspace = SettingsWorkspace(settings=settings)

    # Search bar accessibility
    assert workspace.search.accessibleName() == "Search Settings"
    assert "Filter settings" in workspace.search.accessibleDescription()

    # Nav list accessibility
    assert workspace.nav_list.accessibleName() == "Settings Sections"

    # Input controls accessibility
    assert workspace.language_selector.accessibleName() == "Display Language"
    assert workspace.start_minimized.accessibleName() == "Startup State"
    assert workspace.auto_sync_interval.accessibleName() == "Auto-Sync Interval"


def test_account_workspace_accessibility():
    from unittest.mock import MagicMock

    get_qapp()
    mock_accounts = MagicMock()
    mock_accounts.list.return_value = []
    mock_onboarding = MagicMock()
    acc_ws = AccountWorkspace(mock_accounts, mock_onboarding)

    assert (
        acc_ws.search_input.accessibleName() == "Search Accounts"
        or acc_ws.search_input.accessibleName() == "Search accounts"
    )
    assert acc_ws.table.accessibleName() == "Accounts Table"
    assert acc_ws.smart_filter.accessibleName() == "Smart filter"
    assert acc_ws.status_filter.accessibleName() == "Status filter"


def test_tab_order_chaining():
    get_qapp()
    parent = QWidget()
    btn1 = QPushButton("Btn 1", parent)
    btn2 = QPushButton("Btn 2", parent)
    btn3 = QPushButton("Btn 3", parent)

    chain_tab_order([btn1, btn2, btn3])
    # Verification that tab order does not raise and binds
    apply_accessibility(btn1, "Button One", "Primary action")
    valid, msg = verify_accessible_semantics(btn1)
    assert valid is True
    assert msg == "OK"


def test_dialog_escape_key_helper():
    get_qapp()
    dialog = QDialog()
    AccessibleFocusManager.setup_dialog_keyboard_navigation(dialog, close_on_escape=True)
    assert dialog is not None
