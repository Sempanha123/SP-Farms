from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.widgets import (
    FlowStepButton,
    MetricRow,
    Panel,
    PrimaryButton,
    QuickActionButton,
    StatusChip,
)
from sp_farms.application.context import ApplicationContext
from sp_farms.domain.device_management import ManagedDevice
from sp_farms.domain.jobs import JobState


class HomeDashboard(QWidget):
    """Reference-inspired operator dashboard with an obvious end-to-end flow."""

    route_requested = Signal(str)

    def __init__(self, context: ApplicationContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("homeDashboard")
        self._context = context
        self._devices: tuple[ManagedDevice, ...] = ()
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 9, 10, 8)
        root.setSpacing(8)

        header = QHBoxLayout()
        title_stack = QVBoxLayout()
        title_stack.setSpacing(0)
        title = QLabel("Dashboard Overview")
        title.setProperty("heading", True)
        title_stack.addWidget(title)
        subtitle = QLabel("System health, active work, recent activity, and quick actions")
        subtitle.setProperty("muted", True)
        title_stack.addWidget(subtitle)
        header.addLayout(title_stack)
        header.addStretch()
        refresh = PrimaryButton("↻ Refresh")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        root.addLayout(header)

        self.metrics = MetricRow(
            (
                ("Total Accounts", "0"),
                ("Online Devices", "0"),
                ("Running Tasks", "0"),
                ("Queue", "0"),
                ("Success", "0"),
                ("Failed", "0"),
            )
        )
        root.addWidget(self.metrics)

        flow_panel = Panel()
        flow_panel.setProperty("flowPanel", True)
        flow = QHBoxLayout(flow_panel)
        flow.setContentsMargins(9, 7, 9, 7)
        flow.setSpacing(5)
        flow_title = QLabel("QUICK FLOW")
        flow_title.setProperty("sectionTitle", True)
        flow.addWidget(flow_title)

        flow_defs = (
            ("Account", "Select / health", "Accounts"),
            ("Device + Network", "Resolve binding", "Devices"),
            ("Restore", "Workspace + app", "Accounts"),
            ("Action", "Post / Reel / task", "Content"),
            ("Monitor", "Queue + results", "Automation"),
        )
        self.flow_buttons: list[FlowStepButton] = []
        for index, (name, detail, route) in enumerate(flow_defs, start=1):
            button = FlowStepButton(index, name, detail)
            button.clicked.connect(
                lambda checked=False, target=route: self.route_requested.emit(target)
            )
            self.flow_buttons.append(button)
            flow.addWidget(button, stretch=1)
            if index < len(flow_defs):
                arrow = QLabel("→")
                arrow.setProperty("flowArrow", True)
                flow.addWidget(arrow)
        root.addWidget(flow_panel)

        body = QGridLayout()
        body.setSpacing(8)

        quick = Panel()
        quick_layout = QVBoxLayout(quick)
        quick_layout.setContentsMargins(10, 9, 10, 9)
        quick_layout.setSpacing(6)
        quick_title = QLabel("Quick Actions")
        quick_title.setProperty("sectionTitle", True)
        quick_layout.addWidget(quick_title)

        quick_grid = QGridLayout()
        quick_grid.setSpacing(6)
        actions = (
            ("Accounts", "Manage & restore", "👤", "Accounts"),
            ("Compose", "Post / Reel / Story", "✦", "Content"),
            ("Automation", "Quick presets", "⚡", "Automation"),
            ("Devices", "LDPlayer / MuMu / Android", "▣", "Devices"),
            ("Analytics", "Performance & reliability", "▥", "Analytics"),
            ("Security", "Auth / 2FA / sessions", "🛡", "Security"),
            ("Errors", "Failures & audit trail", "!", "Error Center"),
            ("Settings", "App & integrations", "⚙", "Settings"),
        )
        for i, (title, subtitle, icon, route) in enumerate(actions):
            button = QuickActionButton(title, subtitle, icon)
            button.clicked.connect(
                lambda checked=False, target=route: self.route_requested.emit(target)
            )
            quick_grid.addWidget(button, i // 2, i % 2)
        quick_layout.addLayout(quick_grid)
        quick_layout.addStretch()
        body.addWidget(quick, 0, 0)

        health = Panel()
        health_layout = QVBoxLayout(health)
        health_layout.setContentsMargins(10, 9, 10, 9)
        health_layout.setSpacing(6)
        health_title = QLabel("System Status")
        health_title.setProperty("sectionTitle", True)
        health_layout.addWidget(health_title)

        self.device_health = StatusChip("No devices", "neutral")
        self.job_health = StatusChip("No jobs", "neutral")
        self.account_health = StatusChip("No accounts", "neutral")
        self.queue_health = StatusChip("Queue clear", "success")
        health_layout.addWidget(self.device_health)
        health_layout.addWidget(self.job_health)
        health_layout.addWidget(self.account_health)
        health_layout.addWidget(self.queue_health)
        health_layout.addStretch()

        open_devices = QPushButton("Open Device Manager")
        open_devices.clicked.connect(lambda: self.route_requested.emit("Devices"))
        health_layout.addWidget(open_devices)
        open_auto = QPushButton("Open Automation")
        open_auto.clicked.connect(lambda: self.route_requested.emit("Automation"))
        health_layout.addWidget(open_auto)
        body.addWidget(health, 0, 1)

        jobs = Panel()
        jobs_layout = QVBoxLayout(jobs)
        jobs_layout.setContentsMargins(10, 9, 10, 9)
        jobs_layout.setSpacing(6)
        jobs_header = QHBoxLayout()
        jobs_title = QLabel("Recent Activities")
        jobs_title.setProperty("sectionTitle", True)
        jobs_header.addWidget(jobs_title)
        jobs_header.addStretch()
        jobs_open = QPushButton("View Queue")
        jobs_open.clicked.connect(lambda: self.route_requested.emit("Automation"))
        jobs_header.addWidget(jobs_open)
        jobs_layout.addLayout(jobs_header)

        self.recent_jobs = QListWidget()
        self.recent_jobs.setObjectName("homeRecentJobs")
        self.recent_jobs.setUniformItemSizes(True)
        jobs_layout.addWidget(self.recent_jobs, stretch=1)
        body.addWidget(jobs, 1, 0)

        devices = Panel()
        device_layout = QVBoxLayout(devices)
        device_layout.setContentsMargins(10, 9, 10, 9)
        device_layout.setSpacing(6)
        device_head = QHBoxLayout()
        device_title = QLabel("Device Snapshot")
        device_title.setProperty("sectionTitle", True)
        device_head.addWidget(device_title)
        device_head.addStretch()
        manage = QPushButton("Manage")
        manage.clicked.connect(lambda: self.route_requested.emit("Devices"))
        device_head.addWidget(manage)
        device_layout.addLayout(device_head)

        self.device_list = QListWidget()
        self.device_list.setObjectName("homeDeviceSnapshot")
        self.device_list.setUniformItemSizes(True)
        device_layout.addWidget(self.device_list, stretch=1)
        body.addWidget(devices, 1, 1)

        body.setColumnStretch(0, 3)
        body.setColumnStretch(1, 2)
        body.setRowStretch(1, 1)
        root.addLayout(body, stretch=1)

    def set_devices(self, devices: tuple[ManagedDevice, ...]) -> None:
        self._devices = devices
        self.refresh()

    @staticmethod
    def _state_text(state: object) -> str:
        value = getattr(state, "value", None)
        return str(value if value is not None else state).replace("_", " ").title()

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
        online = sum(bool(device.is_online) for device in self._devices)
        running = sum(job.state is JobState.RUNNING for job in jobs)
        queued = sum(job.state in (JobState.PENDING, JobState.QUEUED) for job in jobs)
        succeeded = sum(job.state is JobState.SUCCEEDED for job in jobs)
        failed = sum(job.state is JobState.FAILED for job in jobs)

        values = (len(accounts), online, running, queued, succeeded, failed)
        for label, value in zip(self.metrics.value_labels, values, strict=True):
            label.setText(str(value))

        self.device_health.update_state(
            "success" if online else "neutral",
            f"Devices: {online}/{len(self._devices)} online",
        )
        self.job_health.update_state(
            "error" if failed else "active" if running else "success",
            f"Jobs: {running} running · {failed} failed",
        )
        self.account_health.update_state(
            "success" if accounts else "neutral",
            f"Accounts: {len(accounts)} connected",
        )
        self.queue_health.update_state(
            "warning" if queued else "success",
            f"Queue: {queued} waiting" if queued else "Queue is clear",
        )

        flow_states = (
            "done" if accounts else "next",
            "done" if online else ("next" if accounts else ""),
            "done" if running or succeeded else ("next" if online else ""),
            "done" if running else ("next" if online else ""),
            "done" if succeeded or failed else ("next" if running else ""),
        )
        for button, state in zip(self.flow_buttons, flow_states, strict=True):
            button.set_flow_state(state)

        self.recent_jobs.clear()
        recent = list(jobs[-8:])
        if not recent:
            self.recent_jobs.addItem("No recent jobs · use Quick Automation when ready.")
        else:
            for job in reversed(recent):
                state = self._state_text(getattr(job, "state", "unknown"))
                job_type = str(
                    getattr(job, "job_type", None)
                    or getattr(job, "type", None)
                    or "Job"
                ).replace("_", " ")
                short_id = str(getattr(job, "id", ""))[:8]
                self.recent_jobs.addItem(
                    QListWidgetItem(f"{state:12}  {job_type}  {short_id}")
                )

        self.device_list.clear()
        if not self._devices:
            self.device_list.addItem("No devices discovered · open Device Manager.")
        else:
            for device in self._devices[:8]:
                provider = getattr(getattr(device, "provider", None), "value", "device")
                account = device.assigned_account or "Unassigned"
                net = device.network_state or "System"
                self.device_list.addItem(
                    f"{'●' if device.is_online else '○'} {device.display_name} "
                    f"· {provider} · {account} · {net}"
                )
