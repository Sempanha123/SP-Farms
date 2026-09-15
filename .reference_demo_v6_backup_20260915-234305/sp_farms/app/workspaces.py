from collections.abc import Sequence
from typing import TYPE_CHECKING

from PySide6.QtCore import QAbstractItemModel, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
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
    SecondaryButton,
    StatusChip,
)
from sp_farms.domain.device_management import ManagedDevice
from sp_farms.domain.jobs import Job, JobState

if TYPE_CHECKING:
    from sp_farms.app.device_manager import DeviceManagerView
    from sp_farms.application.job_service import JobService


class RailFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._search = ""
        self._mode = "all"

    def set_search(self, value: str) -> None:
        self._search = value.strip().lower()
        self.invalidateFilter()

    def set_mode(self, value: str) -> None:
        self._mode = value.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:  # type: ignore[override]
        source = self.sourceModel()
        if source is None:
            return True
        index = source.index(source_row, 0, source_parent)
        device = source.data(index, Qt.ItemDataRole.UserRole)
        if not isinstance(device, ManagedDevice):
            return True

        mode = self._mode
        if mode == "online" and not device.is_online:
            return False
        if mode == "offline" and device.is_online:
            return False
        if mode in {"ldplayer", "mumu", "physical"} and device.provider.value != mode:
            return False

        haystack = " ".join(
            (
                device.display_name,
                device.provider.value,
                device.adb_serial,
                device.assigned_account or "",
                device.network_state or "",
            )
        ).lower()
        return not self._search or self._search in haystack


class DeviceRail(Panel):
    devices_route_requested = Signal()
    automation_route_requested = Signal()
    settings_route_requested = Signal()

    def __init__(
        self,
        model: QAbstractItemModel | None = None,
        controller: "DeviceManagerView | None" = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("deviceRail")
        self.setMinimumWidth(245)
        self.setMaximumWidth(300)
        self._controller = controller
        self._model = model

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("Device Manager")
        title.setProperty("heading", True)
        header.addWidget(title)
        header.addStretch()
        self.online_chip = StatusChip("0 Online", "neutral")
        header.addWidget(self.online_chip)
        layout.addLayout(header)

        control_row = QHBoxLayout()
        self.refresh_btn = SecondaryButton("↻ Refresh")
        self.add_btn = PrimaryButton("+ Add Device")
        control_row.addWidget(self.refresh_btn)
        control_row.addWidget(self.add_btn)
        layout.addLayout(control_row)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search devices...")
        layout.addWidget(self.search)

        filters = QHBoxLayout()
        self.mode_filter = QComboBox()
        self.mode_filter.addItems(
            ("All Devices", "Online", "Offline", "LDPlayer", "MuMu", "Physical")
        )
        self.show_ip = QCheckBox("Show IP")
        filters.addWidget(self.mode_filter, stretch=1)
        filters.addWidget(self.show_ip)
        layout.addLayout(filters)

        self.proxy = RailFilterProxy(self)
        if model is not None:
            self.proxy.setSourceModel(model)
        self.list_view = QListView()
        self.list_view.setObjectName("deviceRailList")
        self.list_view.setUniformItemSizes(True)
        self.list_view.setModel(self.proxy)
        layout.addWidget(self.list_view, stretch=1)

        preview = Panel()
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(8, 7, 8, 7)
        preview_layout.setSpacing(5)

        preview_head = QHBoxLayout()
        self.preview_name = QLabel("No device selected")
        self.preview_name.setProperty("sectionTitle", True)
        preview_head.addWidget(self.preview_name)
        preview_head.addStretch()
        self.preview_state = StatusChip("Offline", "neutral")
        preview_head.addWidget(self.preview_state)
        preview_layout.addLayout(preview_head)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(7)
        form.setVerticalSpacing(3)
        self.preview_provider = QLabel("—")
        self.preview_account = QLabel("—")
        self.preview_network = QLabel("—")
        self.preview_usage = QLabel("—")
        self.preview_adb = QLabel("—")
        for label in (
            self.preview_provider,
            self.preview_account,
            self.preview_network,
            self.preview_usage,
            self.preview_adb,
        ):
            label.setProperty("muted", True)
        form.addRow("Device:", self.preview_provider)
        form.addRow("Account:", self.preview_account)
        form.addRow("Network:", self.preview_network)
        form.addRow("CPU / RAM:", self.preview_usage)
        form.addRow("ADB:", self.preview_adb)
        preview_layout.addLayout(form)

        self.open_device_btn = PrimaryButton("▣ Open Device Manager")
        self.open_device_btn.clicked.connect(self.devices_route_requested.emit)
        preview_layout.addWidget(self.open_device_btn)

        local_actions = QHBoxLayout()
        self.start_btn = PrimaryButton("Start")
        self.stop_btn = SecondaryButton("Stop")
        self.restart_btn = SecondaryButton("Restart")
        local_actions.addWidget(self.start_btn)
        local_actions.addWidget(self.stop_btn)
        local_actions.addWidget(self.restart_btn)
        preview_layout.addLayout(local_actions)

        artifact_row = QHBoxLayout()
        self.package_input = QLineEdit()
        self.package_input.setPlaceholderText("App package")
        self.launch_btn = SecondaryButton("Launch")
        self.screenshot_btn = SecondaryButton("Shot")
        artifact_row.addWidget(self.package_input, stretch=1)
        artifact_row.addWidget(self.launch_btn)
        artifact_row.addWidget(self.screenshot_btn)
        preview_layout.addLayout(artifact_row)
        layout.addWidget(preview)

        quick_title = QLabel("Quick Actions")
        quick_title.setProperty("sectionTitle", True)
        layout.addWidget(quick_title)

        self.start_all_btn = QPushButton("▶  Start All Devices")
        self.stop_all_btn = QPushButton("■  Stop All Devices")
        self.devices_btn = QPushButton("▣  Full Device Manager")
        self.automation_btn = QPushButton("⚡  Automation Builder")
        self.network_btn = QPushButton("⌁  Network Settings")
        for button in (
            self.start_all_btn,
            self.stop_all_btn,
            self.devices_btn,
            self.automation_btn,
            self.network_btn,
        ):
            button.setProperty("quickAction", True)
            layout.addWidget(button)

        self.search.textChanged.connect(self.proxy.set_search)
        self.mode_filter.currentTextChanged.connect(
            lambda text: self.proxy.set_mode(
                {
                    "All Devices": "all",
                    "Online": "online",
                    "Offline": "offline",
                    "LDPlayer": "ldplayer",
                    "MuMu": "mumu",
                    "Physical": "physical",
                }.get(text, "all")
            )
        )
        self.refresh_btn.clicked.connect(self._refresh)
        self.add_btn.clicked.connect(self.devices_route_requested.emit)
        self.devices_btn.clicked.connect(self.devices_route_requested.emit)
        self.automation_btn.clicked.connect(self.automation_route_requested.emit)
        self.network_btn.clicked.connect(self.settings_route_requested.emit)
        self.list_view.selectionModel().selectionChanged.connect(self._selection_changed)
        self.show_ip.toggled.connect(self._selection_changed)
        self.package_input.textChanged.connect(self._selection_changed)
        self.start_btn.clicked.connect(lambda: self._run("start"))
        self.stop_btn.clicked.connect(lambda: self._run("stop"))
        self.restart_btn.clicked.connect(lambda: self._run("restart"))
        self.launch_btn.clicked.connect(lambda: self._run("launch_app"))
        self.screenshot_btn.clicked.connect(lambda: self._artifact("screenshot"))
        self.start_all_btn.clicked.connect(lambda: self._run_all("start"))
        self.stop_all_btn.clicked.connect(lambda: self._run_all("stop"))

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

    def _all_devices(self) -> tuple[ManagedDevice, ...]:
        devices: list[ManagedDevice] = []
        if self._model is None:
            return ()
        for row in range(self._model.rowCount()):
            device = self._model.data(self._model.index(row, 0), Qt.ItemDataRole.UserRole)
            if isinstance(device, ManagedDevice):
                devices.append(device)
        return tuple(devices)

    def _refresh(self) -> None:
        if self._controller is not None:
            self._controller.refresh()

    def _model_reset(self) -> None:
        devices = self._all_devices()
        online = sum(device.is_online for device in devices)
        self.online_chip.update_state(
            "success" if online else "neutral",
            f"{online} Online",
        )
        self.start_all_btn.setEnabled(
            bool(devices)
            and any(
                device.capabilities.can_start_stop and not device.is_online
                for device in devices
            )
        )
        self.stop_all_btn.setEnabled(
            any(device.capabilities.can_start_stop and device.is_online for device in devices)
        )
        self._selection_changed()

    def _selection_changed(self) -> None:
        device = self._selected_device()
        if device is None:
            self.preview_name.setText("No device selected")
            self.preview_state.update_state("neutral", "Offline")
            self.preview_provider.setText("—")
            self.preview_account.setText("—")
            self.preview_network.setText("—")
            self.preview_usage.setText("—")
            self.preview_adb.setText("—")
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
            "Running" if device.is_online else "Offline",
        )
        self.preview_provider.setText(
            f"{device.provider.value} · Android {device.android_version or '—'}"
        )
        self.preview_account.setText(device.assigned_account or "Unassigned")
        network = device.network_state or "System"
        if not self.show_ip.isChecked() and "ip" in network.lower():
            network = "Connected"
        self.preview_network.setText(network)
        cpu = f"{device.cpu_usage:.0f}%" if device.cpu_usage is not None else "—"
        ram = f"{device.ram_usage_mb} MB" if device.ram_usage_mb is not None else "—"
        self.preview_usage.setText(f"{cpu} / {ram}")
        self.preview_adb.setText(device.adb_serial or "No ADB serial")

        caps = device.capabilities
        self.start_btn.setEnabled(caps.can_start_stop and not device.is_online)
        self.stop_btn.setEnabled(caps.can_start_stop and device.is_online)
        self.restart_btn.setEnabled(caps.can_restart and device.is_online)
        self.launch_btn.setEnabled(
            caps.can_launch_apps and device.is_online and bool(self.package_input.text().strip())
        )
        self.screenshot_btn.setEnabled(caps.can_take_screenshot and device.is_online)

    def _run(self, action: str) -> None:
        device = self._selected_device()
        if device is not None and self._controller is not None:
            package = self.package_input.text().strip() if action == "launch_app" else None
            self._controller.run_devices(action, (device,), package)

    def _run_all(self, action: str) -> None:
        if self._controller is None:
            return
        devices = tuple(
            device
            for device in self._all_devices()
            if device.capabilities.can_start_stop
            and (
                (action == "start" and not device.is_online)
                or (action == "stop" and device.is_online)
            )
        )
        if devices:
            self._controller.run_devices(action, devices)

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
        layout.addWidget(
            MetricRow((("Accounts", "0"), ("Active", "0"), ("Needs attention", "0")))
        )

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
        heading.setProperty("sectionTitle", True)
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
    settings_route_requested = Signal()

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
        root.setContentsMargins(6, 6, 6, 0)
        root.setSpacing(5)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("workspaceSplitter")
        splitter.setChildrenCollapsible(False)

        self.device_rail = DeviceRail(device_model, device_controller)
        self.device_rail.devices_route_requested.connect(self.devices_route_requested.emit)
        self.device_rail.automation_route_requested.connect(self.automation_route_requested.emit)
        self.device_rail.settings_route_requested.connect(self.settings_route_requested.emit)
        splitter.addWidget(self.device_rail)
        splitter.addWidget(content or ManagementWorkspace())

        self.job_queue = JobQueueDrawer(job_service)
        self.job_queue.automation_route_requested.connect(self.automation_route_requested.emit)
        splitter.addWidget(self.job_queue)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([265, 1120, 280])
        root.addWidget(splitter, stretch=1)

        status = QWidget()
        status.setObjectName("statusBarContent")
        status_layout = QHBoxLayout(status)
        status_layout.setContentsMargins(10, 4, 10, 4)
        status_layout.setSpacing(11)

        brand = QLabel("SP-FARMS")
        brand.setStyleSheet("font-weight: 800;")
        status_layout.addWidget(brand)
        status_layout.addWidget(QLabel("|"))

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
            block.setSpacing(3)
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
        self.footer_labels["Failed"].setText(
            str(sum(job.state is JobState.FAILED for job in jobs))
        )
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
