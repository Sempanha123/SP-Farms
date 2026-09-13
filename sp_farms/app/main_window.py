from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

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
        self._workspace = WorkspaceLayout()
        self._pages = QStackedWidget()
        self._nav_buttons: dict[str, QPushButton] = {}
        self._theme = ThemeMode.DARK
        self.setObjectName("mainWindow")
        self.setWindowTitle("SP-Farms")
        self.setMinimumSize(1024, 680)
        self.resize(1440, 900)
        self._build_shell()
        self._create_actions()
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
            else:
                placeholder = QLabel(f"{section} workspace")
                placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                placeholder.setProperty("muted", True)
                self._pages.addWidget(placeholder)
        shell_layout.addWidget(self._pages, stretch=1)
        self.setCentralWidget(shell)
        self.navigate("Accounts")

    def _create_actions(self) -> None:
        self.toggle_queue_action = QAction("Show Job Queue", self)
        self.toggle_queue_action.setCheckable(True)
        visible = bool(self._settings.value("window/jobQueueVisible", True, bool))
        self.toggle_queue_action.triggered.connect(self.set_job_queue_visible)
        self.addAction(self.toggle_queue_action)
        self.set_job_queue_visible(visible)

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
