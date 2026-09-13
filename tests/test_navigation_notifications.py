import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from sp_farms.app.command_palette import CommandPalette
from sp_farms.app.navigation import Command, NavigationService
from sp_farms.app.notifications import NotificationCenterModel, NotificationLevel, ProgressOverlay


def application() -> QApplication:
    instance = QApplication.instance()
    if isinstance(instance, QApplication):
        return instance
    return QApplication([])


def test_route_commands_execute_and_filter() -> None:
    routes: list[str] = []
    navigation = NavigationService(routes.append)
    navigation.register_routes((("Accounts", "Alt+1"), ("Devices", "Alt+2")))

    assert [command.id for command in navigation.search("device module")] == ["navigate.devices"]
    navigation.execute("navigate.accounts")
    assert routes == ["Accounts"]


def test_shortcut_collision_is_rejected() -> None:
    navigation = NavigationService(lambda _: None)
    navigation.register(Command("first", "First", "Ctrl+K", lambda: None))

    with pytest.raises(ValueError, match="Shortcut collision"):
        navigation.register(Command("second", "Second", "Ctrl+K", lambda: None))


def test_palette_filters_and_executes_current_command() -> None:
    application()
    calls: list[str] = []
    navigation = NavigationService(calls.append)
    navigation.register_routes((("Accounts", "Alt+1"), ("Devices", "Alt+2")))
    palette = CommandPalette(navigation)

    palette.search.setText("devices")
    assert palette.results.count() == 1
    palette.execute_current()
    assert calls == ["Devices"]


def test_notification_enqueue_and_dismiss() -> None:
    center = NotificationCenterModel()
    notification = center.enqueue("Completed", NotificationLevel.SUCCESS)

    assert center.rowCount() == 1
    assert center.data(center.index(0), center.MessageRole) == "Completed"
    assert center.dismiss(notification.id)
    assert center.rowCount() == 0
    assert not center.dismiss("missing")


def test_progress_overlay_is_non_modal() -> None:
    application()
    overlay = ProgressOverlay()
    overlay.start("Refreshing devices")

    assert overlay.isVisible()
    assert overlay.message.text() == "Refreshing devices"
    assert not overlay.isModal()
    overlay.finish()
    assert not overlay.isVisible()
