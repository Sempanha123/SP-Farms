import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QLineEdit

from sp_farms.app.settings_workspace import SettingsWorkspace


def get_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def get_settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def test_settings_workspace_sections_and_layout(tmp_path: Path):
    get_qapp()
    settings = get_settings(tmp_path)
    workspace = SettingsWorkspace(settings=settings)

    assert workspace.nav_list.count() == 14
    expected_sections = [
        "General",
        "Appearance",
        "Accounts",
        "Devices",
        "Meta Integration",
        "Storage",
        "Security",
        "Scheduler",
        "Network",
        "Notifications",
        "Backup",
        "Plugins",
        "Updates",
        "Diagnostics",
    ]
    actual_sections = [workspace.nav_list.item(i).text() for i in range(14)]
    assert actual_sections == expected_sections
    assert workspace.stack.count() == 14


def test_settings_persistence(tmp_path: Path):
    get_qapp()
    settings = get_settings(tmp_path)
    workspace = SettingsWorkspace(settings=settings)

    # Modify some settings
    workspace.theme.setCurrentText("Light")
    workspace.queue_visible.setChecked(True)
    workspace.auto_sync_interval.setValue(45)
    workspace.max_active_accounts.setValue(12)
    workspace.meta_app_id.setText("123456789012345")
    workspace.meta_api_version.setCurrentText("v20.0")
    workspace.log_level.setCurrentText("DEBUG")

    saved = workspace.save_all()
    assert saved is True

    # Reload into a new instance with the same QSettings file
    reloaded_settings = get_settings(tmp_path)
    workspace2 = SettingsWorkspace(settings=reloaded_settings)

    assert workspace2.theme.currentText() == "Light"
    assert workspace2.queue_visible.isChecked() is True
    assert workspace2.auto_sync_interval.value() == 45
    assert workspace2.max_active_accounts.value() == 12
    assert workspace2.meta_app_id.text() == "123456789012345"
    assert workspace2.meta_api_version.currentText() == "v20.0"
    assert workspace2.log_level.currentText() == "DEBUG"


def test_settings_validation_failure(tmp_path: Path):
    get_qapp()
    settings = get_settings(tmp_path)
    workspace = SettingsWorkspace(settings=settings)

    # Invalid Meta App ID (non-digit)
    workspace.meta_app_id.setText("NOT_A_DIGIT_123")
    is_valid, errors = workspace.validate_settings()
    assert is_valid is False
    assert any("Meta App ID" in e for e in errors)
    assert workspace.save_all() is False

    # Fix App ID, test invalid redirect uri
    workspace.meta_app_id.setText("123456789")
    workspace.meta_redirect_uri.setText("ftp://invalid-scheme")
    is_valid, errors = workspace.validate_settings()
    assert is_valid is False
    assert any("Meta OAuth Redirect URI" in e for e in errors)

    # Test invalid proxy
    workspace.meta_redirect_uri.setText("https://localhost/callback")
    workspace.proxy_url.setText("ftp://bad-proxy")
    is_valid, errors = workspace.validate_settings()
    assert is_valid is False
    assert any("Network Proxy" in e for e in errors)


def test_reset_section_defaults(tmp_path: Path):
    get_qapp()
    settings = get_settings(tmp_path)
    workspace = SettingsWorkspace(settings=settings)

    # Select Meta section
    workspace.nav_list.setCurrentRow(4)  # "Meta Integration"
    workspace.meta_app_id.setText("999999999")
    workspace.meta_api_version.setCurrentText("v19.0")

    # Reset
    workspace.reset_current_section()

    assert workspace.meta_app_id.text() == ""
    assert workspace.meta_api_version.currentText() == "v21.0"
    assert workspace.meta_redirect_uri.text() == "https://localhost/oauth/callback"


def test_search_filtering(tmp_path: Path):
    get_qapp()
    settings = get_settings(tmp_path)
    workspace = SettingsWorkspace(settings=settings)

    # Search for "proxy"
    workspace._filter_settings("proxy")

    # Only "Network" should remain visible
    network_item = None
    for i in range(workspace.nav_list.count()):
        item = workspace.nav_list.item(i)
        if item.text() == "Network":
            assert not item.isHidden()
            network_item = item
        else:
            assert item.isHidden()
    assert network_item is not None

    # Clear search
    workspace._filter_settings("")
    for i in range(workspace.nav_list.count()):
        assert not workspace.nav_list.item(i).isHidden()


def test_secrets_masked(tmp_path: Path):
    get_qapp()
    settings = get_settings(tmp_path)
    workspace = SettingsWorkspace(settings=settings)

    # Secret input must be in Password echo mode
    assert workspace.meta_app_secret_masked.echoMode() == QLineEdit.EchoMode.Password
