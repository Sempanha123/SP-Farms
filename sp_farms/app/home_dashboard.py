from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.widgets import MetricRow, Panel, PrimaryButton, StatusChip
from sp_farms.application.context import ApplicationContext
from sp_farms.domain.device_management import ManagedDevice
from sp_farms.domain.jobs import JobState


class HomeDashboard(QWidget):
    """Direct monitoring dashboard: no quick-action cards or step-flow strip."""

    route_requested = Signal(str)

    def __init__(
        self,
        context: ApplicationContext,
        parent: QWidget | None = None,
    ) -> None:
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

        title = QLabel("Dashboard")
        title.setProperty("heading", True)
        title_stack.addWidget(title)

        subtitle = QLabel(
            "Current accounts, devices, queue state, failures, and recent activity."
        )
        subtitle.setProperty("muted", True)
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
                ("Online Devices", "0"),
                ("Running", "0"),
                ("Queued", "0"),
                ("Success", "0"),
                ("Failed", "0"),
            )
        )
        root.addWidget(self.metrics)

        body = QGridLayout()
        body.setSpacing(8)

        activity = Panel()
        activity_layout = QVBoxLayout(activity)
        activity_layout.setContentsMargins(10, 9, 10, 9)
        activity_layout.setSpacing(6)

        activity_title = QLabel("Recent Activity")
        activity_title.setProperty("sectionTitle", True)
        activity_layout.addWidget(activity_title)

        self.recent_jobs = QListWidget()
        self.recent_jobs.setObjectName("homeRecentJobs")
        self.recent_jobs.setUniformItemSizes(True)
        activity_layout.addWidget(self.recent_jobs, stretch=1)

        body.addWidget(activity, 0, 0, 2, 1)

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

        body.addWidget(health, 0, 1)

        devices = Panel()
        device_layout = QVBoxLayout(devices)
        device_layout.setContentsMargins(10, 9, 10, 9)
        device_layout.setSpacing(6)

        device_title = QLabel("Device Status")
        device_title.setProperty("sectionTitle", True)
        device_layout.addWidget(device_title)

        self.device_list = QListWidget()
        self.device_list.setObjectName("homeDeviceSnapshot")
        self.device_list.setUniformItemSizes(True)
        device_layout.addWidget(self.device_list, stretch=1)

        body.addWidget(devices, 1, 1)

        body.setColumnStretch(0, 3)
        body.setColumnStretch(1, 2)
        body.setRowStretch(0, 1)
        body.setRowStretch(1, 2)

        root.addLayout(body, stretch=1)

    def set_devices(
        self,
        devices: tuple[ManagedDevice, ...],
    ) -> None:
        self._devices = devices
        self.refresh()

    @staticmethod
    def _state_text(state: object) -> str:
        value = getattr(state, "value", None)
        return str(
            value if value is not None else state
        ).replace("_", " ").title()

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

        online = sum(
            bool(device.is_online)
            for device in self._devices
        )
        running = sum(
            job.state is JobState.RUNNING
            for job in jobs
        )
        queued = sum(
            job.state in (JobState.PENDING, JobState.QUEUED)
            for job in jobs
        )
        succeeded = sum(
            job.state is JobState.SUCCEEDED
            for job in jobs
        )
        failed = sum(
            job.state is JobState.FAILED
            for job in jobs
        )

        values = (
            len(accounts),
            online,
            running,
            queued,
            succeeded,
            failed,
        )
        for label, value in zip(
            self.metrics.value_labels,
            values,
            strict=True,
        ):
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
            f"Queue: {queued} waiting"
            if queued
            else "Queue is clear",
        )

        self.recent_jobs.clear()
        recent = list(jobs[-12:])

        if not recent:
            self.recent_jobs.addItem("No recent jobs.")
        else:
            for job in reversed(recent):
                state = self._state_text(
                    getattr(job, "state", "unknown")
                )
                job_type = str(
                    getattr(job, "job_type", None)
                    or getattr(job, "type", None)
                    or "Job"
                ).replace("_", " ")
                short_id = str(
                    getattr(job, "id", "")
                )[:8]

                self.recent_jobs.addItem(
                    QListWidgetItem(
                        f"{state:12}  {job_type}  {short_id}"
                    )
                )

        self.device_list.clear()

        if not self._devices:
            self.device_list.addItem("No devices discovered.")
            return

        for device in self._devices[:14]:
            provider = getattr(
                getattr(device, "provider", None),
                "value",
                "device",
            )
            account = device.assigned_account or "Unassigned"
            network = device.network_state or "System"

            self.device_list.addItem(
                f"{'●' if device.is_online else '○'} "
                f"{device.display_name} · {provider} · "
                f"{account} · {network}"
            )
