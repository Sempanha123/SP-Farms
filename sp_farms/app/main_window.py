from PySide6.QtCore import QByteArray, QSettings, Qt, QThreadPool
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
from sp_farms.app.approval_workspace import ApprovalWorkspace
from sp_farms.app.asset_workspace import PagesGroupsWorkspace
from sp_farms.app.automation_builder_workspace import AutomationBuilderWorkspace
from sp_farms.app.campaign_workspace import CampaignWorkspace
from sp_farms.app.command_palette import CommandPalette
from sp_farms.app.content_workspace import ContentWorkspace
from sp_farms.app.device_manager import DeviceManagerView
from sp_farms.app.error_center import ErrorCenterWorkspace
from sp_farms.app.home_dashboard import HomeDashboard
from sp_farms.app.job_queue import JobQueueView
from sp_farms.app.navigation import Command, NavigationService
from sp_farms.app.notifications import NotificationCenterModel
from sp_farms.app.operational_workspaces import (
    AnalyticsWorkspace,
    SettingsWorkspace,
    UnavailableWorkspace,
)
from sp_farms.app.qa_profile_lab import QAProfileLab
from sp_farms.app.quick_automation_workspace import QuickAutomationWorkspace
from sp_farms.app.scheduler_workspace import SchedulerWorkspace
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
            selection_context_service=self._context.selection_context_service,
            app_context=self._context,
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
            self._context.restore_workspace_service,
            self._context.device_pool_service,
            self._context.snapshot_service,
            self._context.account_exchange_service,
            self._context.security_service,
            selection_context_service=self._context.selection_context_service,
            app_context=self._context,
        )
        self._workspace = WorkspaceLayout(
            self.device_manager_view.rail_model,
            self.account_workspace,
            self.device_manager_view,
            self._context.job_service,
        )
        self.home_dashboard = HomeDashboard(self._context)
        self.device_manager_view.devices_changed.connect(self.home_dashboard.set_devices)
        self.home_workspace = WorkspaceLayout(
            self.device_manager_view.rail_model,
            self.home_dashboard,
            self.device_manager_view,
            self._context.job_service,
        )
        self.home_dashboard.route_requested.connect(self.navigate)
        self.home_workspace.devices_route_requested.connect(lambda: self.navigate("Devices"))
        self.home_workspace.automation_route_requested.connect(lambda: self.navigate("Automation"))
        self._workspace.devices_route_requested.connect(lambda: self.navigate("Devices"))
        self._workspace.automation_route_requested.connect(lambda: self.navigate("Automation"))
        self.account_workspace.success_action_requested.connect(self._route_account_action)
        self.account_workspace.local_navigation_requested.connect(self.navigate)
        self.pages_workspace = PagesGroupsWorkspace(
            self._context.asset_sync_service,
            self._context.account_service,
            selection_context_service=self._context.selection_context_service,
            app_context=self._context,
        )
        self.pages_workspace.set_tab("Pages")
        self.pages_workspace.route_requested.connect(self.navigate)
        self.groups_workspace = PagesGroupsWorkspace(
            self._context.asset_sync_service,
            self._context.account_service,
            selection_context_service=self._context.selection_context_service,
            app_context=self._context,
        )
        self.groups_workspace.set_tab("Groups")
        self.groups_workspace.route_requested.connect(self.navigate)
        self.content_workspace: ContentWorkspace | None = (
            ContentWorkspace(
                self._context.content_service,
                composer_service=self._context.composer_service,
                caption_ai_service=self._context.caption_ai_service,
            )
            if self._context.content_service
            else None
        )
        self.error_center_workspace: ErrorCenterWorkspace | None = (
            ErrorCenterWorkspace(self._context.audit_service)
            if self._context.audit_service
            else None
        )
        self.campaign_workspace: CampaignWorkspace | None = (
            CampaignWorkspace(self._context.campaign_service)
            if self._context.campaign_service
            else None
        )
        self.scheduler_workspace: SchedulerWorkspace | None = (
            SchedulerWorkspace(self._context.scheduler_service)
            if self._context.scheduler_service
            else None
        )
        self.approval_workspace: ApprovalWorkspace | None = (
            ApprovalWorkspace(self._context.approval_service)
            if self._context.approval_service
            else None
        )
        self.automation_builder_workspace: AutomationBuilderWorkspace | None = (
            AutomationBuilderWorkspace(self._context.automation_builder_service)
            if self._context.automation_builder_service
            else None
        )
        self.quick_automation_workspace: QuickAutomationWorkspace | None = (
            QuickAutomationWorkspace(self._context.automation_builder_service)
            if self._context.automation_builder_service
            else None
        )
        if self.error_center_workspace:
            self.error_center_workspace.route_requested.connect(self.navigate)
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
        if section in ("Security", "Security Center"):
            self.navigate("Accounts")
            self.account_workspace.show_security_center()
            return
        if section in ("Error Center", "Errors", "Audit", "Audit Trail"):
            if self.error_center_workspace is not None:
                self._pages.setCurrentWidget(self.error_center_workspace)
                for button in self._nav_buttons.values():
                    button.setChecked(False)
                if section in ("Audit", "Audit Trail"):
                    self.error_center_workspace.tabs.setCurrentIndex(1)
                else:
                    self.error_center_workspace.tabs.setCurrentIndex(0)
                self.error_center_workspace.refresh()
            return
        index = NAVIGATION.index(section)
        self._pages.setCurrentIndex(index)
        for name, button in self._nav_buttons.items():
            button.setChecked(name == section)
        if section == "Home":
            self.home_dashboard.refresh()
            self.home_workspace.refresh_jobs()
        elif section == "Accounts":
            self.account_workspace.refresh()
            self._workspace.refresh_jobs()
        elif section == "Pages":
            self.pages_workspace.set_tab("Pages")
            self.pages_workspace.refresh()
        elif section == "Groups":
            self.groups_workspace.set_tab("Groups")
            self.groups_workspace.refresh()
        elif section == "Automation":
            self.job_queue_view.refresh()
            if self.quick_automation_workspace is not None:
                self.quick_automation_workspace.refresh_presets()
        elif section == "Devices" and self.device_manager_view.model.rowCount() == 0:
            self.device_manager_view.refresh()
        elif section == "Analytics":
            self.analytics_workspace.refresh()

    def set_theme(self, mode: ThemeMode) -> None:
        self._theme = mode
        self.setStyleSheet(style_sheet(mode))
        self._settings.setValue("appearance/theme", mode.value)

    def _apply_locale(self, locale_code: str) -> None:
        if not self._context or not self._context.i18n_service:
            return
        self._context.i18n_service.set_locale(locale_code)
        if hasattr(self, "brand_subtitle"):
            self.brand_subtitle.setText(self._context.i18n_service.t("app.subtitle"))
        for section, btn in self._nav_buttons.items():
            translated = self._context.i18n_service.t(f"nav.{section.casefold()}", default=section)
            btn.setText(translated)

    def set_job_queue_visible(self, visible: bool) -> None:
        self._workspace.job_queue.setVisible(visible)
        self.home_workspace.job_queue.setVisible(visible)
        self.toggle_queue_action.setChecked(visible)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._settings.setValue("window/geometry", self.saveGeometry())
        self._settings.setValue("window/size", self.size())
        self._settings.setValue("window/jobQueueVisible", self._workspace.job_queue.isVisible())
        QThreadPool.globalInstance().waitForDone()
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
        navigation_layout.setContentsMargins(10, 7, 12, 7)
        navigation_layout.setSpacing(4)

        brand_block = QWidget()
        brand_block.setObjectName("brandBlock")
        brand_layout = QHBoxLayout(brand_block)
        brand_layout.setContentsMargins(0, 0, 10, 0)
        brand_layout.setSpacing(7)
        mark = QLabel("♣")
        mark.setObjectName("brandMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(38, 38)
        brand_layout.addWidget(mark)
        brand_text = QVBoxLayout()
        brand_text.setContentsMargins(0, 0, 0, 0)
        brand_text.setSpacing(0)
        product_row = QHBoxLayout()
        product_row.setSpacing(5)
        brand = QLabel("SP-FARMS")
        brand.setObjectName("brand")
        version = QLabel("v1.0.0")
        version.setObjectName("brandVersion")
        product_row.addWidget(brand)
        product_row.addWidget(version, alignment=Qt.AlignmentFlag.AlignBottom)
        brand_text.addLayout(product_row)
        self.brand_subtitle = QLabel("Automate Smarter • Manage Bigger")
        self.brand_subtitle.setObjectName("brandSubtitle")
        brand_text.addWidget(self.brand_subtitle)
        brand_layout.addLayout(brand_text)
        navigation_layout.addWidget(brand_block)
        navigation_layout.addSpacing(4)
        nav_button_list = []
        for index, section in enumerate(NAVIGATION):
            button = QPushButton(section)
            button.setProperty("nav", True)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            shortcut_hint = f"Alt+{index + 1}"
            button.setToolTip(f"Switch to {section} ({shortcut_hint})")
            button.setAccessibleName(f"Navigate to {section}")
            button.setAccessibleDescription(
                f"Switch to {section} workspace using shortcut {shortcut_hint}"
            )
            button.clicked.connect(lambda checked=False, name=section: self.navigate(name))
            self._nav_buttons[section] = button
            nav_button_list.append(button)
            navigation_layout.addWidget(button)

        for i in range(len(nav_button_list) - 1):
            QWidget.setTabOrder(nav_button_list[i], nav_button_list[i + 1])

        navigation_layout.addStretch()
        shell_layout.addWidget(navigation)

        for section in NAVIGATION:
            if section == "Home":
                self._pages.addWidget(self.home_workspace)
            elif section == "Accounts":
                self._pages.addWidget(self._workspace)
            elif section == "Automation":
                self.automation_tabs = QTabWidget()
                automation_tabs = self.automation_tabs
                if self.quick_automation_workspace is not None:
                    automation_tabs.addTab(self.quick_automation_workspace, "Quick Mode")
                if self.automation_builder_workspace is not None:
                    automation_tabs.addTab(self.automation_builder_workspace, "Advanced Builder")
                if self.campaign_workspace is not None:
                    automation_tabs.addTab(self.campaign_workspace, "Campaigns")
                if self.scheduler_workspace is not None:
                    automation_tabs.addTab(self.scheduler_workspace, "Scheduler & Calendar")
                if self.approval_workspace is not None:
                    automation_tabs.addTab(self.approval_workspace, "Approval Queue")
                self.job_queue_view = JobQueueView(self._context.job_service)
                automation_tabs.addTab(self.job_queue_view, "Job Execution Queue")
                if self.quick_automation_workspace is not None:
                    self.quick_automation_workspace.advanced_requested.connect(
                        lambda: automation_tabs.setCurrentWidget(
                            self.automation_builder_workspace
                        )
                        if self.automation_builder_workspace is not None
                        else None
                    )
                self._pages.addWidget(automation_tabs)
            elif section == "Devices":
                self._pages.addWidget(self.devices_workspace)
            elif section == "Pages":
                self._pages.addWidget(self.pages_workspace)
            elif section == "Groups":
                self._pages.addWidget(self.groups_workspace)
            elif section == "Content":
                if self.content_workspace is not None:
                    self._pages.addWidget(self.content_workspace)
                else:
                    workspace = UnavailableWorkspace(
                        "Content",
                        "Phases 29–38",
                        "content library, composer, campaigns, and publishing services",
                        "Automation",
                    )
                    workspace.route_requested.connect(self.navigate)
                    self._pages.addWidget(workspace)
            elif section == "Analytics":
                self.analytics_workspace = AnalyticsWorkspace(self._context)
                self._pages.addWidget(self.analytics_workspace)
            elif section == "Settings":
                self.settings_workspace = SettingsWorkspace(self._settings)
                self.settings_workspace.theme_requested.connect(
                    lambda value: self.set_theme(ThemeMode(value))
                )
                self.settings_workspace.queue_visibility_requested.connect(
                    self.set_job_queue_visible
                )
                self.settings_workspace.locale_requested.connect(self._apply_locale)
                self._pages.addWidget(self.settings_workspace)
        if self.error_center_workspace is not None:
            self._pages.addWidget(self.error_center_workspace)
        shell_layout.addWidget(self._pages, stretch=1)
        self.setCentralWidget(shell)
        self._apply_locale(str(self._settings.value("general/locale", "en_US")))
        self.navigate("Home")

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
        self.navigation.register(
            Command(
                "security.open",
                "Open Security Center",
                "Ctrl+Alt+S",
                self._open_security_center,
                keywords=("security", "audit", "2fa", "token", "credentials"),
            )
        )
        self.navigation.register(
            Command(
                "errors.open",
                "Open Error Center & Audit Trail",
                "Ctrl+Alt+E",
                lambda: self.navigate("Error Center"),
                keywords=("error", "errors", "diagnostic", "audit", "retries", "failure"),
            )
        )
        for command in self.navigation.commands:
            action = QAction(command.title, self)
            action.setShortcut(command.shortcut)
            action.triggered.connect(command.handler)
            self.addAction(action)

        self.toggle_queue_action = QAction("Show Job Queue", self)
        self.toggle_queue_action.setCheckable(True)
        visible = bool(self._settings.value("window/jobQueueVisible", False, bool))
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

    def _open_security_center(self) -> None:
        self.navigate("Security")

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
