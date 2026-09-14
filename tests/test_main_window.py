import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QSplitter, QTableView

from sp_farms.app.main_window import MainWindow
from sp_farms.application.context import ApplicationContext
from sp_farms.infrastructure.clock import SystemClock


def application() -> QApplication:
    instance = QApplication.instance()
    if isinstance(instance, QApplication):
        return instance
    return QApplication([])


def settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def test_main_shell_has_reference_layout(tmp_path: Path) -> None:
    application()
    window = MainWindow(ApplicationContext(SystemClock()), settings(tmp_path))
    window.show()
    QApplication.processEvents()

    splitter = window.findChild(QSplitter, "workspaceSplitter")
    assert splitter is not None
    assert splitter.count() == 3
    first_widget = splitter.widget(0)
    assert first_widget is not None
    assert first_widget.objectName() == "deviceRail"
    assert window.current_section == "Accounts"
    assert window.minimumWidth() >= 1024
    assert not window.grab().toImage().isNull()
    window.close()


def test_navigation_changes_workspace(tmp_path: Path) -> None:
    application()
    window = MainWindow(ApplicationContext(SystemClock()), settings(tmp_path))

    window.navigate("Devices")

    assert window.current_section == "Devices"
    assert window._nav_buttons["Devices"].isChecked()
    assert window._pages.currentWidget() is window.devices_workspace
    assert window.devices_workspace.widget(0) is window.device_manager_view
    assert window.devices_workspace.widget(1) is window.qa_profile_lab
    assert window.findChild(QTableView, "deviceTable") is not None
    window.close()


def test_queue_visibility_and_geometry_persist(tmp_path: Path) -> None:
    application()
    saved_settings = settings(tmp_path)
    first_context = ApplicationContext(SystemClock())
    first = MainWindow(first_context, saved_settings)
    first.show()
    first.resize(1180, 740)
    QApplication.processEvents()
    first.set_job_queue_visible(False)
    first.closeEvent(QCloseEvent())
    saved_settings.sync()

    second = MainWindow(ApplicationContext(SystemClock()), settings(tmp_path))

    assert not second._workspace.job_queue.isVisible()
    saved_size = settings(tmp_path).value("window/size")
    assert saved_size.width() == 1180
    assert saved_size.height() == 740
    second.close()
