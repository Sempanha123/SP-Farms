from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.analytics_workspace import AnalyticsWorkspace as PostAnalyticsView
from sp_farms.app.theme import ThemeMode
from sp_farms.app.widgets import EmptyState, MetricRow, Panel, PrimaryButton, StatusChip
from sp_farms.application.context import ApplicationContext
from sp_farms.domain.jobs import JobState


class UnavailableWorkspace(QWidget):
    route_requested = Signal(str)

    def __init__(
        self,
        title: str,
        phase: str,
        requirement: str,
        available_route: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(f"{title.casefold()}Workspace")
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        heading = QLabel(title)
        heading.setProperty("heading", True)
        root.addWidget(heading)
        status = StatusChip(f"Not installed • {phase}", "warning")
        root.addWidget(status, alignment=status.alignment())
        panel = Panel()
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(
            EmptyState(
                f"{title} is not available yet",
                f"Required first: {requirement}. No placeholder action is presented as working.",
            )
        )
        open_available = PrimaryButton(f"Open {available_route}")
        open_available.clicked.connect(
            lambda checked=False: self.route_requested.emit(available_route)
        )
        panel_layout.addWidget(open_available)
        panel_layout.addStretch()
        root.addWidget(panel, stretch=1)


class AnalyticsWorkspace(QWidget):
    def __init__(self, context: ApplicationContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("analyticsWorkspace")
        self._context = context
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self.tabs = QTabWidget()

        # Tab 1: Live Post & Engagement Insights
        if self._context.analytics_service is not None:
            self.post_analytics_view = PostAnalyticsView(self._context.analytics_service)
            self.tabs.addTab(self.post_analytics_view, "Social Post Performance")

        # Tab 2: Operational Infrastructure Metrics
        infra_tab = QWidget()
        infra_layout = QVBoxLayout(infra_tab)
        infra_layout.setContentsMargins(8, 8, 8, 8)
        infra_layout.setSpacing(8)

        header = QHBoxLayout()
        heading = QLabel("Operational Infrastructure Analytics")
        heading.setProperty("heading", True)
        header.addWidget(heading)
        header.addStretch()
        refresh = PrimaryButton("Refresh")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        infra_layout.addLayout(header)

        self.metrics = MetricRow(
            (
                ("Accounts", "0"),
                ("Active Jobs", "0"),
                ("Running", "0"),
                ("Failed", "0"),
                ("Queued", "0"),
            )
        )
        infra_layout.addWidget(self.metrics)
        infra_layout.addStretch()
        self.tabs.addTab(infra_tab, "Device & Job System Metrics")

        root.addWidget(self.tabs)
        self.refresh()

    def refresh(self) -> None:
        accounts = (
            tuple(self._context.account_service.list_accounts())
            if self._context.account_service is not None
            else ()
        )
        jobs = (
            tuple(self._context.job_service.list_jobs())
            if self._context.job_service is not None
            else ()
        )
        running = sum(job.state is JobState.RUNNING for job in jobs)
        failed = sum(job.state is JobState.FAILED for job in jobs)
        queued = sum(job.state in (JobState.PENDING, JobState.QUEUED) for job in jobs)
        for label, value in zip(
            self.metrics.value_labels,
            (len(accounts), len(jobs), running, failed, queued),
            strict=True,
        ):
            label.setText(str(value))


class SettingsWorkspace(QWidget):
    theme_requested = Signal(str)
    queue_visibility_requested = Signal(bool)

    def __init__(self, settings: QSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsWorkspace")
        self._settings = settings
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        title = QLabel("Settings")
        title.setProperty("heading", True)
        root.addWidget(title)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search settings")
        root.addWidget(self.search)

        general = Panel()
        form = QFormLayout(general)
        self.theme = QComboBox()
        self.theme.addItems(("Dark", "Light"))
        saved_theme = str(settings.value("appearance/theme", ThemeMode.DARK.value))
        self.theme.setCurrentText(saved_theme.title())
        self.queue_visible = QCheckBox("Show job queue drawer")
        self.queue_visible.setChecked(bool(settings.value("window/jobQueueVisible", False, bool)))
        form.addRow("Appearance", self.theme)
        form.addRow("Workspace", self.queue_visible)
        root.addWidget(general)

        advanced = Panel()
        advanced_layout = QVBoxLayout(advanced)
        advanced_layout.addWidget(QLabel("Configuration coverage"))
        coverage = QLabel(
            "General appearance and queue visibility are available. Meta, storage, "
            "security, scheduler, network, backup, plugin, update, and diagnostics "
            "settings require their corresponding service phases."
        )
        coverage.setProperty("muted", True)
        coverage.setWordWrap(True)
        advanced_layout.addWidget(coverage)
        root.addWidget(advanced)
        root.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        reset = QPushButton("Reset this section")
        save = PrimaryButton("Save Settings")
        buttons.addWidget(reset)
        buttons.addWidget(save)
        root.addLayout(buttons)
        save.clicked.connect(self.save)
        reset.clicked.connect(self.reset)

    def save(self) -> None:
        theme = self.theme.currentText().casefold()
        self._settings.setValue("appearance/theme", theme)
        self._settings.setValue("window/jobQueueVisible", self.queue_visible.isChecked())
        self._settings.sync()
        self.theme_requested.emit(theme)
        self.queue_visibility_requested.emit(self.queue_visible.isChecked())

    def reset(self) -> None:
        self.theme.setCurrentText("Dark")
        self.queue_visible.setChecked(False)
        self.save()
