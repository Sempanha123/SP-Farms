from collections.abc import Sequence
from typing import TYPE_CHECKING

from PySide6.QtCore import QAbstractItemModel, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.widgets import (
    CompactTable,
    MetricRow,
    Panel,
    PrimaryButton,
    StatusChip,
)
from sp_farms.domain.device_management import ManagedDevice
from sp_farms.domain.jobs import Job, JobState

if TYPE_CHECKING:
    from sp_farms.app.device_manager import DeviceManagerView
    from sp_farms.application.job_service import JobService


class DeviceRail(Panel):
    devices_route_requested = Signal()

    def __init__(
        self,
        model: QAbstractItemModel | None = None,
        controller: "DeviceManagerView | None" = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("deviceRail")
        self.setMinimumWidth(220)
        self.setMaximumWidth(270)
        self._controller = controller
        self._model = model
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)

        header = QHBoxLayout()
        title_stack = QVBoxLayout()
        title_stack.setSpacing(0)
        heading = QLabel("Device Manager")
        heading.setProperty("heading", True)
        self.online_label = QLabel("0 of 0 online")
        self.online_label.setProperty("muted", True)
        title_stack.addWidget(heading)
        title_stack.addWidget(self.online_label)
        header.addLayout(title_stack)
        header.addStretch()
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setToolTip("Refresh devices")
        self.refresh_btn.setFixedWidth(30)
        self.add_btn = PrimaryButton("+ Add Device")
        header.addWidget(self.refresh_btn)
        header.addWidget(self.add_btn)
        layout.addLayout(header)

        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        if model is not None:
            self.proxy.setSourceModel(model)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter devices...")
        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        layout.addWidget(self.search)

        options = QHBoxLayout()
        self.fleet_chip = StatusChip("No devices", "neutral")
        self.show_ip = QCheckBox("Show IP")
        options.addWidget(self.fleet_chip)
        options.addStretch()
        options.addWidget(self.show_ip)
        layout.addLayout(options)

        self.list_view = QListView()
        self.list_view.setObjectName("deviceRailList")
        self.list_view.setUniformItemSizes(True)
        self.list_view.setModel(self.proxy)
        layout.addWidget(self.list_view, stretch=1)

        preview = Panel()
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(8, 7, 8, 7)
        preview_layout.setSpacing(3)
        self.preview_name = QLabel("No device selected")
        self.preview_name.setStyleSheet("font-weight: 700;")
        self.preview_state = StatusChip("Offline", "neutral")
        self.preview_detail = QLabel("Select a device to inspect it")
        self.preview_detail.setProperty("muted", True)
        self.preview_detail.setWordWrap(True)
        preview_header = QHBoxLayout()
        preview_header.addWidget(self.preview_name)
        preview_header.addStretch()
        preview_header.addWidget(self.preview_state)
        preview_layout.addLayout(preview_header)
        preview_layout.addWidget(self.preview_detail)
        layout.addWidget(preview)

        quick_label = QLabel("Quick Actions")
        quick_label.setStyleSheet("font-weight: 700;")
        layout.addWidget(quick_label)
        quick = QHBoxLayout()
        quick.setSpacing(4)
        self.start_btn = PrimaryButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.restart_btn = QPushButton("Restart")
        quick.addWidget(self.start_btn)
        quick.addWidget(self.stop_btn)
        quick.addWidget(self.restart_btn)
        layout.addLayout(quick)
        artifacts = QHBoxLayout()
        artifacts.setSpacing(4)
        self.package_input = QLineEdit()
        self.package_input.setPlaceholderText("App package")
        self.launch_btn = QPushButton("Launch")
        self.screenshot_btn = QPushButton("Screenshot")
        artifacts.addWidget(self.package_input, stretch=1)
        artifacts.addWidget(self.launch_btn)
        artifacts.addWidget(self.screenshot_btn)
        layout.addLayout(artifacts)

        self.refresh_btn.clicked.connect(self._refresh)
        self.add_btn.clicked.connect(self.devices_route_requested.emit)
        self.list_view.selectionModel().selectionChanged.connect(self._selection_changed)
        self.show_ip.toggled.connect(self._selection_changed)
        self.package_input.textChanged.connect(self._selection_changed)
        self.start_btn.clicked.connect(lambda: self._run("start"))
        self.stop_btn.clicked.connect(lambda: self._run("stop"))
        self.restart_btn.clicked.connect(lambda: self._run("restart"))
        self.launch_btn.clicked.connect(lambda: self._run("launch_app"))
        self.screenshot_btn.clicked.connect(lambda: self._artifact("screenshot"))
        if model is not None:
            model.modelReset.connect(self._model_reset)
            model.rowsInserted.connect(self._model_reset)
            model.rowsRemoved.connect(self._model_reset)
        self._model_reset()
        self._selection_changed()

    def _selected_device(self) -> ManagedDevice | None:
        index = self.list_view.currentIndex()
        if not index.isValid():
            return None
        device = self.proxy.data(index, Qt.ItemDataRole.UserRole)
        return device if isinstance(device, ManagedDevice) else None

    def _refresh(self) -> None:
        if self._controller is not None:
            self._controller.refresh()

    def _model_reset(self) -> None:
        total = self._model.rowCount() if self._model is not None else 0
        online = 0
        if self._model is not None:
            for row in range(total):
                device = self._model.data(self._model.index(row, 0), Qt.ItemDataRole.UserRole)
                online += int(isinstance(device, ManagedDevice) and device.is_online)
        self.online_label.setText(f"{online} of {total} online")
        self.fleet_chip.update_state("success" if online else "neutral", f"{total} devices")
        self._selection_changed()

    def _selection_changed(self) -> None:
        device = self._selected_device()
        if device is None:
            self.preview_name.setText("No device selected")
            self.preview_state.update_state("neutral", "Offline")
            self.preview_detail.setText("Select a device to inspect it")
            for button in (
                self.start_btn,
                self.stop_btn,
                self.restart_btn,
                self.launch_btn,
                self.screenshot_btn,
            ):
                button.setEnabled(False)
            return
        self.preview_name.setText(device.display_name)
        self.preview_state.update_state(
            "success" if device.is_online else "error",
            "Online" if device.is_online else "Offline",
        )
        details = [device.provider.value.upper(), device.adb_serial or "No ADB serial"]
        if self.show_ip.isChecked() and device.network_state:
            details.append(device.network_state)
        self.preview_detail.setText(" • ".join(details))
        capabilities = device.capabilities
        self.start_btn.setEnabled(capabilities.can_start_stop and not device.is_online)
        self.stop_btn.setEnabled(capabilities.can_start_stop and device.is_online)
        self.restart_btn.setEnabled(capabilities.can_restart and device.is_online)
        self.launch_btn.setEnabled(
            capabilities.can_launch_apps
            and device.is_online
            and bool(self.package_input.text().strip())
        )
        self.screenshot_btn.setEnabled(capabilities.can_take_screenshot and device.is_online)

    def _run(self, action: str) -> None:
        device = self._selected_device()
        if device is not None and self._controller is not None:
            package = self.package_input.text().strip() if action == "launch_app" else None
            self._controller.run_devices(action, (device,), package)

    def _artifact(self, action: str) -> None:
        device = self._selected_device()
        if device is not None and self._controller is not None:
            self._controller.collect_device_artifacts(action, (device,))


class ManagementWorkspace(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("managementWorkspace")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(MetricRow((("Accounts", "0"), ("Active", "0"), ("Needs attention", "0"))))

        toolbar = Panel()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 7, 10, 7)
        toolbar_layout.addWidget(QLineEdit("Search accounts, pages, or groups"), stretch=1)
        toolbar_layout.addWidget(QPushButton("Filter"))
        toolbar_layout.addWidget(PrimaryButton("Add account"))
        layout.addWidget(toolbar)

        table = CompactTable()
        table.setObjectName("managementTable")
        model = QStandardItemModel(0, 6, table)
        model.setHorizontalHeaderLabels(
            ("Account", "Status", "Device", "Network", "Last active", "Actions")
        )
        table.setModel(model)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(table, stretch=1)


class JobQueueDrawer(Panel):
    automation_route_requested = Signal()

    def __init__(
        self,
        service: "JobService | None" = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("jobQueueDrawer")
        self.setMinimumWidth(250)
        self.setMaximumWidth(340)
        self._service = service
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        heading = QLabel("Job Queue")
        heading.setStyleSheet("font-weight: 650;")
        layout.addWidget(heading)
        self.status = StatusChip("0 running", "neutral")
        layout.addWidget(self.status)
        self.summary = QLabel("Queue is clear")
        self.summary.setProperty("muted", True)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        open_queue = PrimaryButton("Open Automation")
        open_queue.clicked.connect(self.automation_route_requested.emit)
        layout.addWidget(open_queue)
        layout.addStretch()
        self.refresh()

    def refresh(self) -> tuple[Job, ...]:
        jobs = tuple(self._service.list_jobs()) if self._service is not None else ()
        running = sum(job.state is JobState.RUNNING for job in jobs)
        queued = sum(job.state in (JobState.PENDING, JobState.QUEUED) for job in jobs)
        failed = sum(job.state is JobState.FAILED for job in jobs)
        self.status.update_state(
            "error" if failed else "active" if running else "neutral",
            f"{running} running",
        )
        self.summary.setText(f"{queued} queued • {failed} failed" if jobs else "Queue is clear")
        return jobs


class WorkspaceLayout(QWidget):
    devices_route_requested = Signal()
    automation_route_requested = Signal()

    def __init__(
        self,
        device_model: QAbstractItemModel | None = None,
        content: QWidget | None = None,
        device_controller: "DeviceManagerView | None" = None,
        job_service: "JobService | None" = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(7, 7, 7, 0)
        root.setSpacing(5)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("workspaceSplitter")
        splitter.setChildrenCollapsible(False)
        self.device_rail = DeviceRail(device_model, device_controller)
        self.device_rail.devices_route_requested.connect(self.devices_route_requested.emit)
        splitter.addWidget(self.device_rail)
        splitter.addWidget(content or ManagementWorkspace())
        self.job_queue = JobQueueDrawer(job_service)
        self.job_queue.automation_route_requested.connect(self.automation_route_requested.emit)
        splitter.addWidget(self.job_queue)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([255, 1100, 280])
        root.addWidget(splitter, stretch=1)

        status = QWidget()
        status.setObjectName("statusBarContent")
        status_layout = QHBoxLayout(status)
        status_layout.setContentsMargins(10, 4, 10, 4)
        status_layout.setSpacing(11)
        brand = QLabel("SP-FARMS")
        brand.setStyleSheet("font-weight: 800;")
        status_layout.addWidget(brand)
        self.footer_labels: dict[str, QLabel] = {}
        for key, value in (
            ("Total", "0"),
            ("Online", "0"),
            ("Running", "0"),
            ("Success", "0"),
            ("Failed", "0"),
            ("Queue", "0"),
            ("CPU", "0%"),
            ("RAM", "0 MB"),
        ):
            block = QHBoxLayout()
            block.setSpacing(4)
            name = QLabel(key)
            name.setProperty("muted", True)
            number = QLabel(value)
            number.setProperty("footerValue", True)
            self.footer_labels[key] = number
            block.addWidget(name)
            block.addWidget(number)
            status_layout.addLayout(block)
        status_layout.addStretch()
        status_layout.addWidget(QLabel("Automate Smarter • Manage Bigger"))
        root.addWidget(status)

        if device_controller is not None:
            device_controller.devices_changed.connect(self._update_device_status)

    def refresh_jobs(self) -> None:
        jobs = self.job_queue.refresh()
        self._update_job_status(jobs)

    def _update_job_status(self, jobs: Sequence[Job]) -> None:
        self.footer_labels["Success"].setText(
            str(sum(job.state is JobState.SUCCEEDED for job in jobs))
        )
        self.footer_labels["Failed"].setText(str(sum(job.state is JobState.FAILED for job in jobs)))
        self.footer_labels["Queue"].setText(
            str(sum(job.state in (JobState.PENDING, JobState.QUEUED) for job in jobs))
        )

    def _update_device_status(self, devices: object) -> None:
        if not isinstance(devices, tuple):
            return
        managed = tuple(device for device in devices if isinstance(device, ManagedDevice))
        online = tuple(device for device in managed if device.is_online)
        self.footer_labels["Total"].setText(str(len(managed)))
        self.footer_labels["Online"].setText(str(len(online)))
        self.footer_labels["Running"].setText(str(len(online)))
        cpu = [device.cpu_usage for device in managed if device.cpu_usage is not None]
        ram = [device.ram_usage_mb for device in managed if device.ram_usage_mb is not None]
        self.footer_labels["CPU"].setText(f"{sum(cpu) / len(cpu):.0f}%" if cpu else "0%")
        self.footer_labels["RAM"].setText(f"{sum(ram)} MB" if ram else "0 MB")
