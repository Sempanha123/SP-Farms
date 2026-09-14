from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from sp_farms.app.widgets import EmptyState, MetricRow, Panel, PrimaryButton, StatusChip
from sp_farms.application.context import ApplicationContext
from sp_farms.domain.device_management import ManagedDevice
from sp_farms.domain.jobs import JobState


class HomeDashboard(QWidget):
    route_requested = Signal(str)

    def __init__(self, context: ApplicationContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("homeDashboard")
        self._context = context
        self._devices: tuple[ManagedDevice, ...] = ()

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 8)
        root.setSpacing(8)

        header = QHBoxLayout()
        title_stack = QVBoxLayout()
        title_stack.setSpacing(0)
        title = QLabel("Operations Dashboard")
        title.setProperty("heading", True)
        subtitle = QLabel("System health, active work, and quick access")
        subtitle.setProperty("muted", True)
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        header.addLayout(title_stack)
        header.addStretch()
        refresh = PrimaryButton("Refresh")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        root.addLayout(header)

        self.metrics = MetricRow(
            (
                ("Accounts", "0"),
                ("Pages", "Not configured"),
                ("Groups", "Not configured"),
                ("Online Devices", "0"),
                ("Running Jobs", "0"),
                ("Failed Jobs", "0"),
            )
        )
        root.addWidget(self.metrics)

        body = QGridLayout()
        body.setSpacing(8)
        health = Panel()
        health_layout = QVBoxLayout(health)
        health_layout.setContentsMargins(10, 9, 10, 9)
        health_layout.addWidget(QLabel("System Health"))
        self.device_health = StatusChip("No devices", "neutral")
        self.job_health = StatusChip("Job service unavailable", "neutral")
        self.account_health = StatusChip("Account service unavailable", "neutral")
        health_layout.addWidget(self.device_health)
        health_layout.addWidget(self.job_health)
        health_layout.addWidget(self.account_health)
        health_layout.addStretch()
        body.addWidget(health, 0, 0)

        quick = Panel()
        quick_layout = QVBoxLayout(quick)
        quick_layout.setContentsMargins(10, 9, 10, 9)
        quick_layout.addWidget(QLabel("Quick Actions"))
        for label, route in (
            ("Manage Accounts", "Accounts"),
            ("Manage Devices", "Devices"),
            ("Open Automation Queue", "Automation"),
            ("Open Settings", "Settings"),
        ):
            button = QPushButton(label)
            button.clicked.connect(
                lambda checked=False, destination=route: self.route_requested.emit(destination)
            )
            quick_layout.addWidget(button)
        quick_layout.addStretch()
        body.addWidget(quick, 0, 1)

        unavailable = Panel()
        unavailable_layout = QVBoxLayout(unavailable)
        unavailable_layout.setContentsMargins(10, 9, 10, 9)
        unavailable_layout.addWidget(
            EmptyState(
                "Publishing services not configured",
                "Pages, Groups, Content, Analytics, and provider health become available "
                "after their service modules are installed and configured.",
            )
        )
        body.addWidget(unavailable, 1, 0, 1, 2)
        body.setColumnStretch(0, 1)
        body.setColumnStretch(1, 1)
        body.setRowStretch(1, 1)
        root.addLayout(body, stretch=1)
        self.refresh()

    def set_devices(self, devices: tuple[ManagedDevice, ...]) -> None:
        self._devices = devices
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
        online = sum(device.is_online for device in self._devices)
        running = sum(job.state is JobState.RUNNING for job in jobs)
        failed = sum(job.state is JobState.FAILED for job in jobs)
        for label, value in zip(
            self.metrics.value_labels,
            (len(accounts), "Not configured", "Not configured", online, running, failed),
            strict=True,
        ):
            label.setText(str(value))
        self.device_health.update_state(
            "success" if online else "neutral",
            f"Devices: {online} of {len(self._devices)} online",
        )
        self.job_health.update_state(
            "error" if failed else "success" if self._context.job_service else "neutral",
            f"Jobs: {running} running, {failed} failed"
            if self._context.job_service
            else "Job service unavailable",
        )
        self.account_health.update_state(
            "success" if self._context.account_service else "neutral",
            f"Accounts: {len(accounts)} connected"
            if self._context.account_service
            else "Account service unavailable",
        )
