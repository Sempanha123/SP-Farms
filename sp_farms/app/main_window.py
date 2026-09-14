from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.account_workspace import AccountWorkspace
from sp_farms.app.command_palette import CommandPalette
from sp_farms.app.device_manager import DeviceManagerView
from sp_farms.app.job_queue import JobQueueView
from sp_farms.app.navigation import Command, NavigationService
from sp_farms.app.notifications import NotificationCenterModel
from sp_farms.app.qa_profile_lab import QAProfileLab
from sp_farms.app.shortcut_help import ShortcutHelpDialog
from sp_farms.app.theme import ThemeMode, style_sheet
from sp_farms.app.workspaces import WorkspaceLayout
from sp_farms.application.context import ApplicationContext

NAVIGATION = (
    "Home",
    "Accounts",
    "Pages",
    "Groups",
    "Content",
    "Automation",
    "Devices",
    "Analytics",
    "Settings",
)


class MainWindow(QMainWindow):
    def __init__(
        self,
        context: ApplicationContext,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__()
        self._context = context
        self._settings = settings or QSettings("SP-Farms", "SP-Farms")
        self._pages = QStackedWidget()
        self._nav_buttons: dict[str, QPushButton] = {}
        self._theme = ThemeMode.DARK
        self.navigation = NavigationService(self.navigate)
        self.notifications = NotificationCenterModel()
        self.device_manager_view = DeviceManagerView(
            self._context.device_service,
            self._settings,
        )
        self.qa_profile_lab = QAProfileLab(self._context.qa_profile_service)
        self.device_manager_view.devices_changed.connect(self.qa_profile_lab.set_devices)
        self.devices_workspace = QTabWidget()
        self.devices_workspace.setObjectName("devicesWorkspace")
        self.devices_workspace.addTab(self.device_manager_view, "Device Manager")
        self.devices_workspace.addTab(self.qa_profile_lab, "QA Profile Lab")
        self.account_workspace = AccountWorkspace(
            self._context.account_service,
            self._context.account_onboarding_service,
        )
        self._workspace = WorkspaceLayout(
            self.device_manager_view.rail_model,
            self.account_workspace,
        )
        self.account_workspace.success_action_requested.connect(self._route_account_action)
        self.setObjectName("mainWindow")
        self.setWindowTitle("SP-Farms")
        self.setMinimumSize(1024, 680)
        self.resize(1440, 900)
        self._build_shell()
        self._create_actions()
        self.command_palette = CommandPalette(self.navigation, self)
        self.shortcut_help = ShortcutHelpDialog(self.navigation, self)
        self.set_theme(self._load_theme())
        self._restore_geometry()

    @property
    def current_section(self) -> str:
        return NAVIGATION[self._pages.currentIndex()]

    def navigate(self, section: str) -> None:
        index = NAVIGATION.index(section)
        self._pages.setCurrentIndex(index)
        for name, button in self._nav_buttons.items():
            button.setChecked(name == section)
        if section == "Devices" and self.device_manager_view.model.rowCount() == 0:
            self.device_manager_view.refresh()

    def set_theme(self, mode: ThemeMode) -> None:
        self._theme = mode
        self.setStyleSheet(style_sheet(mode))
        self._settings.setValue("appearance/theme", mode.value)

    def set_job_queue_visible(self, visible: bool) -> None:
        self._workspace.job_queue.setVisible(visible)
        self.toggle_queue_action.setChecked(visible)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._settings.setValue("window/geometry", self.saveGeometry())
        self._settings.setValue("window/size", self.size())
        self._settings.setValue("window/jobQueueVisible", self._workspace.job_queue.isVisible())
        self._context.close()
        event.accept()

    def _build_shell(self) -> None:
        shell = QWidget()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        navigation = QWidget()
        navigation.setObjectName("topNavigation")
        navigation_layout = QHBoxLayout(navigation)
        navigation_layout.setContentsMargins(12, 8, 12, 8)
        navigation_layout.setSpacing(4)
        brand = QLabel("SP-FARMS")
        brand.setObjectName("brand")
        brand.setStyleSheet("font-size: 15px; font-weight: 750;")
        navigation_layout.addWidget(brand)
        navigation_layout.addSpacing(12)
        for section in NAVIGATION:
            button = QPushButton(section)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.clicked.connect(lambda checked=False, name=section: self.navigate(name))
            self._nav_buttons[section] = button
            navigation_layout.addWidget(button)
        navigation_layout.addStretch()
        shell_layout.addWidget(navigation)

        for section in NAVIGATION:
            if section == "Accounts":
                self._pages.addWidget(self._workspace)
            elif section == "Automation":
                self.job_queue_view = JobQueueView(self._context.job_service)
                self._pages.addWidget(self.job_queue_view)
            elif section == "Devices":
                self._pages.addWidget(self.devices_workspace)
            else:
                placeholder = QLabel(f"{section} workspace")
                placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                placeholder.setProperty("muted", True)
                self._pages.addWidget(placeholder)
        shell_layout.addWidget(self._pages, stretch=1)
        self.setCentralWidget(shell)
        self.navigate("Accounts")

    def _create_actions(self) -> None:
        route_shortcuts = tuple(
            (section, f"Alt+{index + 1}") for index, section in enumerate(NAVIGATION)
        )
        self.navigation.register_routes(route_shortcuts)
        self.navigation.register(
            Command("palette.open", "Open command palette", "Ctrl+K", self._open_palette)
        )
        self.navigation.register(
            Command("shortcuts.open", "Show keyboard shortcuts", "Ctrl+/", self._open_shortcuts)
        )
        for command in self.navigation.commands:
            action = QAction(command.title, self)
            action.setShortcut(command.shortcut)
            action.triggered.connect(command.handler)
            self.addAction(action)

        self.toggle_queue_action = QAction("Show Job Queue", self)
        self.toggle_queue_action.setCheckable(True)
        visible = bool(self._settings.value("window/jobQueueVisible", True, bool))
        self.toggle_queue_action.triggered.connect(self.set_job_queue_visible)
        self.addAction(self.toggle_queue_action)
        self.set_job_queue_visible(visible)

    def _route_account_action(self, account_id: str, action: str) -> None:
        routes = {
            "open_account": "Accounts",
            "assign_device": "Devices",
            "add_category": "Accounts",
            "security_center": "Settings",
            "pages": "Pages",
            "content": "Content",
            "scheduler": "Automation",
        }
        section = routes.get(action)
        if section is not None:
            self.navigate(section)
        if action in {"open_account", "add_category"}:
            self.account_workspace.select_account(account_id)

    def _open_palette(self) -> None:
        self.command_palette.open()

    def _open_shortcuts(self) -> None:
        self.shortcut_help.open()

    def _load_theme(self) -> ThemeMode:
        stored = str(self._settings.value("appearance/theme", ThemeMode.DARK.value, str))
        try:
            return ThemeMode(stored)
        except ValueError:
            return ThemeMode.DARK

    def _restore_geometry(self) -> None:
        geometry = self._settings.value("window/geometry")
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
            return
        size = self._settings.value("window/size")
        if size is not None:
            self.resize(size)
