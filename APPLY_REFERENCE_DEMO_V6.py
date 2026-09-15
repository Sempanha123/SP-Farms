from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
APP = ROOT / "sp_farms" / "app"

HOME_PAYLOAD = 'from __future__ import annotations\n\nfrom PySide6.QtCore import Signal\nfrom PySide6.QtWidgets import (\n    QGridLayout,\n    QHBoxLayout,\n    QLabel,\n    QListWidget,\n    QListWidgetItem,\n    QVBoxLayout,\n    QWidget,\n)\n\nfrom sp_farms.app.widgets import MetricRow, Panel, PrimaryButton, StatusChip\nfrom sp_farms.application.context import ApplicationContext\nfrom sp_farms.domain.device_management import ManagedDevice\nfrom sp_farms.domain.jobs import JobState\n\n\nclass HomeDashboard(QWidget):\n    """Compact monitoring dashboard without shortcut cards or step-flow UI."""\n\n    route_requested = Signal(str)\n\n    def __init__(\n        self,\n        context: ApplicationContext,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n        self.setObjectName("homeDashboard")\n        self._context = context\n        self._devices: tuple[ManagedDevice, ...] = ()\n        self._build_ui()\n        self.refresh()\n\n    def _build_ui(self) -> None:\n        root = QVBoxLayout(self)\n        root.setContentsMargins(10, 9, 10, 8)\n        root.setSpacing(8)\n\n        header = QHBoxLayout()\n        title_stack = QVBoxLayout()\n        title_stack.setSpacing(0)\n\n        title = QLabel("Dashboard Overview")\n        title.setProperty("heading", True)\n        title_stack.addWidget(title)\n\n        subtitle = QLabel(\n            "Accounts, device state, running work, failures, and recent activity."\n        )\n        subtitle.setProperty("muted", True)\n        title_stack.addWidget(subtitle)\n\n        header.addLayout(title_stack)\n        header.addStretch()\n\n        refresh = PrimaryButton("↻ Refresh")\n        refresh.clicked.connect(self.refresh)\n        header.addWidget(refresh)\n        root.addLayout(header)\n\n        self.metrics = MetricRow(\n            (\n                ("Total Accounts", "0"),\n                ("Devices Online", "0"),\n                ("Running Tasks", "0"),\n                ("Queue", "0"),\n                ("Success", "0"),\n                ("Failed", "0"),\n            )\n        )\n        root.addWidget(self.metrics)\n\n        body = QGridLayout()\n        body.setSpacing(8)\n\n        activities = Panel()\n        activity_layout = QVBoxLayout(activities)\n        activity_layout.setContentsMargins(10, 9, 10, 9)\n        activity_layout.setSpacing(6)\n\n        activity_title = QLabel("Recent Activities")\n        activity_title.setProperty("sectionTitle", True)\n        activity_layout.addWidget(activity_title)\n\n        self.recent_jobs = QListWidget()\n        self.recent_jobs.setObjectName("homeRecentJobs")\n        self.recent_jobs.setUniformItemSizes(True)\n        activity_layout.addWidget(self.recent_jobs, stretch=1)\n        body.addWidget(activities, 0, 0, 2, 1)\n\n        system = Panel()\n        system_layout = QVBoxLayout(system)\n        system_layout.setContentsMargins(10, 9, 10, 9)\n        system_layout.setSpacing(6)\n\n        system_title = QLabel("System Status")\n        system_title.setProperty("sectionTitle", True)\n        system_layout.addWidget(system_title)\n\n        self.device_health = StatusChip("No devices", "neutral")\n        self.job_health = StatusChip("No jobs", "neutral")\n        self.account_health = StatusChip("No accounts", "neutral")\n        self.queue_health = StatusChip("Queue clear", "success")\n\n        system_layout.addWidget(self.device_health)\n        system_layout.addWidget(self.job_health)\n        system_layout.addWidget(self.account_health)\n        system_layout.addWidget(self.queue_health)\n        system_layout.addStretch()\n        body.addWidget(system, 0, 1)\n\n        device_panel = Panel()\n        device_layout = QVBoxLayout(device_panel)\n        device_layout.setContentsMargins(10, 9, 10, 9)\n        device_layout.setSpacing(6)\n\n        device_title = QLabel("Device Status")\n        device_title.setProperty("sectionTitle", True)\n        device_layout.addWidget(device_title)\n\n        self.device_list = QListWidget()\n        self.device_list.setObjectName("homeDeviceSnapshot")\n        self.device_list.setUniformItemSizes(True)\n        device_layout.addWidget(self.device_list, stretch=1)\n        body.addWidget(device_panel, 1, 1)\n\n        body.setColumnStretch(0, 3)\n        body.setColumnStretch(1, 2)\n        body.setRowStretch(0, 1)\n        body.setRowStretch(1, 2)\n        root.addLayout(body, stretch=1)\n\n    def set_devices(self, devices: tuple[ManagedDevice, ...]) -> None:\n        self._devices = devices\n        self.refresh()\n\n    @staticmethod\n    def _state_text(state: object) -> str:\n        value = getattr(state, "value", None)\n        return str(value if value is not None else state).replace("_", " ").title()\n\n    def refresh(self) -> None:\n        accounts = (\n            tuple(self._context.account_service.list_accounts())\n            if self._context.account_service is not None\n            else ()\n        )\n        jobs = (\n            tuple(self._context.job_service.list_jobs())\n            if self._context.job_service is not None\n            else ()\n        )\n\n        online = sum(bool(device.is_online) for device in self._devices)\n        running = sum(job.state is JobState.RUNNING for job in jobs)\n        queued = sum(\n            job.state in (JobState.PENDING, JobState.QUEUED)\n            for job in jobs\n        )\n        succeeded = sum(job.state is JobState.SUCCEEDED for job in jobs)\n        failed = sum(job.state is JobState.FAILED for job in jobs)\n\n        values = (len(accounts), online, running, queued, succeeded, failed)\n        for label, value in zip(self.metrics.value_labels, values, strict=True):\n            label.setText(str(value))\n\n        self.device_health.update_state(\n            "success" if online else "neutral",\n            f"Devices: {online}/{len(self._devices)} online",\n        )\n        self.job_health.update_state(\n            "error" if failed else "active" if running else "success",\n            f"Jobs: {running} running · {failed} failed",\n        )\n        self.account_health.update_state(\n            "success" if accounts else "neutral",\n            f"Accounts: {len(accounts)} connected",\n        )\n        self.queue_health.update_state(\n            "warning" if queued else "success",\n            f"Queue: {queued} waiting" if queued else "Queue is clear",\n        )\n\n        self.recent_jobs.clear()\n        recent = list(jobs[-10:])\n        if not recent:\n            self.recent_jobs.addItem("No recent jobs.")\n        else:\n            for job in reversed(recent):\n                state = self._state_text(getattr(job, "state", "unknown"))\n                job_type = str(\n                    getattr(job, "job_type", None)\n                    or getattr(job, "type", None)\n                    or "Job"\n                ).replace("_", " ")\n                short_id = str(getattr(job, "id", ""))[:8]\n                self.recent_jobs.addItem(\n                    QListWidgetItem(\n                        f"{state:12}  {job_type}  {short_id}"\n                    )\n                )\n\n        self.device_list.clear()\n        if not self._devices:\n            self.device_list.addItem("No devices discovered.")\n        else:\n            for device in self._devices[:12]:\n                provider = getattr(\n                    getattr(device, "provider", None),\n                    "value",\n                    "device",\n                )\n                account = device.assigned_account or "Unassigned"\n                network = device.network_state or "System"\n                self.device_list.addItem(\n                    f"{\'●\' if device.is_online else \'○\'} "\n                    f"{device.display_name} · {provider} · "\n                    f"{account} · {network}"\n                )\n'
WORKSPACES_PAYLOAD = 'from collections.abc import Sequence\nfrom typing import TYPE_CHECKING\n\nfrom PySide6.QtCore import QAbstractItemModel, QSortFilterProxyModel, Qt, Signal\nfrom PySide6.QtGui import QStandardItemModel\nfrom PySide6.QtWidgets import (\n    QCheckBox,\n    QComboBox,\n    QFormLayout,\n    QHBoxLayout,\n    QHeaderView,\n    QLabel,\n    QLineEdit,\n    QListView,\n    QPushButton,\n    QSplitter,\n    QVBoxLayout,\n    QWidget,\n)\n\nfrom sp_farms.app.widgets import (\n    CompactTable,\n    MetricRow,\n    Panel,\n    PrimaryButton,\n    SecondaryButton,\n    StatusChip,\n)\nfrom sp_farms.domain.device_management import ManagedDevice\nfrom sp_farms.domain.jobs import Job, JobState\n\nif TYPE_CHECKING:\n    from sp_farms.app.device_manager import DeviceManagerView\n    from sp_farms.application.job_service import JobService\n\n\nclass RailFilterProxy(QSortFilterProxyModel):\n    def __init__(self, parent: QWidget | None = None) -> None:\n        super().__init__(parent)\n        self._search = ""\n        self._mode = "all"\n\n    def set_search(self, value: str) -> None:\n        self._search = value.strip().lower()\n        self.invalidateFilter()\n\n    def set_mode(self, value: str) -> None:\n        self._mode = value.strip().lower()\n        self.invalidateFilter()\n\n    def filterAcceptsRow(\n        self,\n        source_row: int,\n        source_parent,\n    ) -> bool:\n        source = self.sourceModel()\n        if source is None:\n            return True\n\n        index = source.index(source_row, 0, source_parent)\n        device = source.data(index, Qt.ItemDataRole.UserRole)\n        if not isinstance(device, ManagedDevice):\n            return True\n\n        mode = self._mode\n        if mode == "online" and not device.is_online:\n            return False\n        if mode == "offline" and device.is_online:\n            return False\n        if mode in {"ldplayer", "mumu", "physical"}:\n            if device.provider.value != mode:\n                return False\n\n        haystack = " ".join(\n            (\n                device.display_name,\n                device.provider.value,\n                device.adb_serial,\n                device.assigned_account or "",\n                device.network_state or "",\n            )\n        ).lower()\n        return not self._search or self._search in haystack\n\n\nclass DeviceRail(Panel):\n    devices_route_requested = Signal()\n    automation_route_requested = Signal()\n    settings_route_requested = Signal()\n\n    def __init__(\n        self,\n        model: QAbstractItemModel | None = None,\n        controller: "DeviceManagerView | None" = None,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n        self.setObjectName("deviceRail")\n        self.setMinimumWidth(245)\n        self.setMaximumWidth(300)\n        self._controller = controller\n        self._model = model\n\n        layout = QVBoxLayout(self)\n        layout.setContentsMargins(8, 8, 8, 8)\n        layout.setSpacing(6)\n\n        header = QHBoxLayout()\n        title = QLabel("Device Manager")\n        title.setProperty("heading", True)\n        header.addWidget(title)\n        header.addStretch()\n\n        self.online_chip = StatusChip("0 Online", "neutral")\n        header.addWidget(self.online_chip)\n        layout.addLayout(header)\n\n        control_row = QHBoxLayout()\n        self.refresh_btn = SecondaryButton("↻ Refresh")\n        self.add_btn = PrimaryButton("+ Add Device")\n        control_row.addWidget(self.refresh_btn)\n        control_row.addWidget(self.add_btn)\n        layout.addLayout(control_row)\n\n        self.search = QLineEdit()\n        self.search.setPlaceholderText("Search devices...")\n        layout.addWidget(self.search)\n\n        filters = QHBoxLayout()\n        self.mode_filter = QComboBox()\n        self.mode_filter.addItems(\n            (\n                "All Devices",\n                "Online",\n                "Offline",\n                "LDPlayer",\n                "MuMu",\n                "Physical",\n            )\n        )\n        self.show_ip = QCheckBox("Show IP")\n        filters.addWidget(self.mode_filter, stretch=1)\n        filters.addWidget(self.show_ip)\n        layout.addLayout(filters)\n\n        self.proxy = RailFilterProxy(self)\n        if model is not None:\n            self.proxy.setSourceModel(model)\n\n        self.list_view = QListView()\n        self.list_view.setObjectName("deviceRailList")\n        self.list_view.setUniformItemSizes(True)\n        self.list_view.setModel(self.proxy)\n        layout.addWidget(self.list_view, stretch=1)\n\n        control_title = QLabel("Device Control")\n        control_title.setProperty("sectionTitle", True)\n        layout.addWidget(control_title)\n\n        preview = Panel()\n        preview_layout = QVBoxLayout(preview)\n        preview_layout.setContentsMargins(8, 7, 8, 7)\n        preview_layout.setSpacing(5)\n\n        preview_head = QHBoxLayout()\n        self.preview_name = QLabel("No device selected")\n        self.preview_name.setProperty("sectionTitle", True)\n        preview_head.addWidget(self.preview_name)\n        preview_head.addStretch()\n\n        self.preview_state = StatusChip("Offline", "neutral")\n        preview_head.addWidget(self.preview_state)\n        preview_layout.addLayout(preview_head)\n\n        form = QFormLayout()\n        form.setContentsMargins(0, 0, 0, 0)\n        form.setHorizontalSpacing(7)\n        form.setVerticalSpacing(3)\n\n        self.preview_provider = QLabel("—")\n        self.preview_account = QLabel("—")\n        self.preview_network = QLabel("—")\n        self.preview_usage = QLabel("—")\n        self.preview_adb = QLabel("—")\n\n        for label in (\n            self.preview_provider,\n            self.preview_account,\n            self.preview_network,\n            self.preview_usage,\n            self.preview_adb,\n        ):\n            label.setProperty("muted", True)\n\n        form.addRow("Device:", self.preview_provider)\n        form.addRow("Account:", self.preview_account)\n        form.addRow("Network:", self.preview_network)\n        form.addRow("CPU / RAM:", self.preview_usage)\n        form.addRow("ADB:", self.preview_adb)\n        preview_layout.addLayout(form)\n\n        device_actions = QHBoxLayout()\n        self.start_btn = PrimaryButton("Start")\n        self.stop_btn = SecondaryButton("Stop")\n        self.restart_btn = SecondaryButton("Restart")\n        device_actions.addWidget(self.start_btn)\n        device_actions.addWidget(self.stop_btn)\n        device_actions.addWidget(self.restart_btn)\n        preview_layout.addLayout(device_actions)\n\n        artifact_row = QHBoxLayout()\n        self.package_input = QLineEdit()\n        self.package_input.setPlaceholderText("App package")\n        self.launch_btn = SecondaryButton("Launch")\n        self.screenshot_btn = SecondaryButton("Screenshot")\n        artifact_row.addWidget(self.package_input, stretch=1)\n        artifact_row.addWidget(self.launch_btn)\n        artifact_row.addWidget(self.screenshot_btn)\n        preview_layout.addLayout(artifact_row)\n\n        self.open_device_btn = PrimaryButton("Open Device")\n        self.open_device_btn.clicked.connect(\n            self.devices_route_requested.emit\n        )\n        preview_layout.addWidget(self.open_device_btn)\n\n        layout.addWidget(preview)\n\n        self.search.textChanged.connect(self.proxy.set_search)\n        self.mode_filter.currentTextChanged.connect(\n            lambda text: self.proxy.set_mode(\n                {\n                    "All Devices": "all",\n                    "Online": "online",\n                    "Offline": "offline",\n                    "LDPlayer": "ldplayer",\n                    "MuMu": "mumu",\n                    "Physical": "physical",\n                }.get(text, "all")\n            )\n        )\n        self.refresh_btn.clicked.connect(self._refresh)\n        self.add_btn.clicked.connect(self.devices_route_requested.emit)\n\n        self.list_view.selectionModel().selectionChanged.connect(\n            self._selection_changed\n        )\n        self.show_ip.toggled.connect(self._selection_changed)\n        self.package_input.textChanged.connect(self._selection_changed)\n\n        self.start_btn.clicked.connect(lambda: self._run("start"))\n        self.stop_btn.clicked.connect(lambda: self._run("stop"))\n        self.restart_btn.clicked.connect(lambda: self._run("restart"))\n        self.launch_btn.clicked.connect(lambda: self._run("launch_app"))\n        self.screenshot_btn.clicked.connect(\n            lambda: self._artifact("screenshot")\n        )\n\n        if model is not None:\n            model.modelReset.connect(self._model_reset)\n            model.rowsInserted.connect(self._model_reset)\n            model.rowsRemoved.connect(self._model_reset)\n\n        self._model_reset()\n        self._selection_changed()\n\n    def _selected_device(self) -> ManagedDevice | None:\n        index = self.list_view.currentIndex()\n        if not index.isValid():\n            return None\n\n        device = self.proxy.data(index, Qt.ItemDataRole.UserRole)\n        return device if isinstance(device, ManagedDevice) else None\n\n    def _all_devices(self) -> tuple[ManagedDevice, ...]:\n        if self._model is None:\n            return ()\n\n        devices: list[ManagedDevice] = []\n        for row in range(self._model.rowCount()):\n            device = self._model.data(\n                self._model.index(row, 0),\n                Qt.ItemDataRole.UserRole,\n            )\n            if isinstance(device, ManagedDevice):\n                devices.append(device)\n        return tuple(devices)\n\n    def _refresh(self) -> None:\n        if self._controller is not None:\n            self._controller.refresh()\n\n    def _model_reset(self) -> None:\n        devices = self._all_devices()\n        online = sum(device.is_online for device in devices)\n        self.online_chip.update_state(\n            "success" if online else "neutral",\n            f"{online} Online",\n        )\n        self._selection_changed()\n\n    def _selection_changed(self) -> None:\n        device = self._selected_device()\n\n        if device is None:\n            self.preview_name.setText("No device selected")\n            self.preview_state.update_state("neutral", "Offline")\n            self.preview_provider.setText("—")\n            self.preview_account.setText("—")\n            self.preview_network.setText("—")\n            self.preview_usage.setText("—")\n            self.preview_adb.setText("—")\n\n            for button in (\n                self.start_btn,\n                self.stop_btn,\n                self.restart_btn,\n                self.launch_btn,\n                self.screenshot_btn,\n            ):\n                button.setEnabled(False)\n            return\n\n        self.preview_name.setText(device.display_name)\n        self.preview_state.update_state(\n            "success" if device.is_online else "error",\n            "Running" if device.is_online else "Offline",\n        )\n        self.preview_provider.setText(\n            f"{device.provider.value} · "\n            f"Android {device.android_version or \'—\'}"\n        )\n        self.preview_account.setText(\n            device.assigned_account or "Unassigned"\n        )\n\n        network = device.network_state or "System"\n        if not self.show_ip.isChecked() and "ip" in network.lower():\n            network = "Connected"\n        self.preview_network.setText(network)\n\n        cpu = (\n            f"{device.cpu_usage:.0f}%"\n            if device.cpu_usage is not None\n            else "—"\n        )\n        ram = (\n            f"{device.ram_usage_mb} MB"\n            if device.ram_usage_mb is not None\n            else "—"\n        )\n        self.preview_usage.setText(f"{cpu} / {ram}")\n        self.preview_adb.setText(device.adb_serial or "No ADB serial")\n\n        capabilities = device.capabilities\n        self.start_btn.setEnabled(\n            capabilities.can_start_stop and not device.is_online\n        )\n        self.stop_btn.setEnabled(\n            capabilities.can_start_stop and device.is_online\n        )\n        self.restart_btn.setEnabled(\n            capabilities.can_restart and device.is_online\n        )\n        self.launch_btn.setEnabled(\n            capabilities.can_launch_apps\n            and device.is_online\n            and bool(self.package_input.text().strip())\n        )\n        self.screenshot_btn.setEnabled(\n            capabilities.can_take_screenshot and device.is_online\n        )\n\n    def _run(self, action: str) -> None:\n        device = self._selected_device()\n        if device is None or self._controller is None:\n            return\n\n        package = (\n            self.package_input.text().strip()\n            if action == "launch_app"\n            else None\n        )\n        self._controller.run_devices(\n            action,\n            (device,),\n            package,\n        )\n\n    def _artifact(self, action: str) -> None:\n        device = self._selected_device()\n        if device is not None and self._controller is not None:\n            self._controller.collect_device_artifacts(\n                action,\n                (device,),\n            )\n\n\nclass ManagementWorkspace(QWidget):\n    def __init__(self, parent: QWidget | None = None) -> None:\n        super().__init__(parent)\n        self.setObjectName("managementWorkspace")\n\n        layout = QVBoxLayout(self)\n        layout.setContentsMargins(0, 0, 0, 0)\n        layout.setSpacing(8)\n\n        layout.addWidget(\n            MetricRow(\n                (\n                    ("Accounts", "0"),\n                    ("Active", "0"),\n                    ("Needs attention", "0"),\n                )\n            )\n        )\n\n        toolbar = Panel()\n        toolbar_layout = QHBoxLayout(toolbar)\n        toolbar_layout.setContentsMargins(10, 7, 10, 7)\n\n        search = QLineEdit()\n        search.setPlaceholderText("Search accounts, pages, or groups")\n        toolbar_layout.addWidget(search, stretch=1)\n        toolbar_layout.addWidget(QPushButton("Filter"))\n        toolbar_layout.addWidget(PrimaryButton("Add account"))\n        layout.addWidget(toolbar)\n\n        table = CompactTable()\n        table.setObjectName("managementTable")\n\n        model = QStandardItemModel(0, 6, table)\n        model.setHorizontalHeaderLabels(\n            (\n                "Account",\n                "Status",\n                "Device",\n                "Network",\n                "Last active",\n                "Actions",\n            )\n        )\n        table.setModel(model)\n\n        header = table.horizontalHeader()\n        header.setSectionResizeMode(\n            0,\n            QHeaderView.ResizeMode.Stretch,\n        )\n        for column in range(1, 6):\n            header.setSectionResizeMode(\n                column,\n                QHeaderView.ResizeMode.ResizeToContents,\n            )\n\n        layout.addWidget(table, stretch=1)\n\n\nclass JobQueueDrawer(Panel):\n    automation_route_requested = Signal()\n\n    def __init__(\n        self,\n        service: "JobService | None" = None,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n        self.setObjectName("jobQueueDrawer")\n        self.setMinimumWidth(250)\n        self.setMaximumWidth(340)\n        self._service = service\n\n        layout = QVBoxLayout(self)\n        layout.setContentsMargins(10, 10, 10, 10)\n\n        heading = QLabel("Job Queue")\n        heading.setProperty("sectionTitle", True)\n        layout.addWidget(heading)\n\n        self.status = StatusChip("0 running", "neutral")\n        layout.addWidget(self.status)\n\n        self.summary = QLabel("Queue is clear")\n        self.summary.setProperty("muted", True)\n        self.summary.setWordWrap(True)\n        layout.addWidget(self.summary)\n\n        open_queue = PrimaryButton("Open Automation")\n        open_queue.clicked.connect(\n            self.automation_route_requested.emit\n        )\n        layout.addWidget(open_queue)\n        layout.addStretch()\n\n        self.refresh()\n\n    def refresh(self) -> tuple[Job, ...]:\n        jobs = (\n            tuple(self._service.list_jobs())\n            if self._service is not None\n            else ()\n        )\n\n        running = sum(\n            job.state is JobState.RUNNING\n            for job in jobs\n        )\n        queued = sum(\n            job.state in (JobState.PENDING, JobState.QUEUED)\n            for job in jobs\n        )\n        failed = sum(\n            job.state is JobState.FAILED\n            for job in jobs\n        )\n\n        self.status.update_state(\n            "error" if failed else "active" if running else "neutral",\n            f"{running} running",\n        )\n        self.summary.setText(\n            f"{queued} queued • {failed} failed"\n            if jobs\n            else "Queue is clear"\n        )\n        return jobs\n\n\nclass WorkspaceLayout(QWidget):\n    devices_route_requested = Signal()\n    automation_route_requested = Signal()\n    settings_route_requested = Signal()\n\n    def __init__(\n        self,\n        device_model: QAbstractItemModel | None = None,\n        content: QWidget | None = None,\n        device_controller: "DeviceManagerView | None" = None,\n        job_service: "JobService | None" = None,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n\n        root = QVBoxLayout(self)\n        root.setContentsMargins(6, 6, 6, 0)\n        root.setSpacing(5)\n\n        splitter = QSplitter(Qt.Orientation.Horizontal)\n        splitter.setObjectName("workspaceSplitter")\n        splitter.setChildrenCollapsible(False)\n\n        self.device_rail = DeviceRail(\n            device_model,\n            device_controller,\n        )\n        self.device_rail.devices_route_requested.connect(\n            self.devices_route_requested.emit\n        )\n\n        splitter.addWidget(self.device_rail)\n        splitter.addWidget(content or ManagementWorkspace())\n\n        self.job_queue = JobQueueDrawer(job_service)\n        self.job_queue.automation_route_requested.connect(\n            self.automation_route_requested.emit\n        )\n        splitter.addWidget(self.job_queue)\n\n        splitter.setStretchFactor(0, 0)\n        splitter.setStretchFactor(1, 1)\n        splitter.setStretchFactor(2, 0)\n        splitter.setSizes([265, 1120, 280])\n        root.addWidget(splitter, stretch=1)\n\n        status = QWidget()\n        status.setObjectName("statusBarContent")\n        status_layout = QHBoxLayout(status)\n        status_layout.setContentsMargins(10, 4, 10, 4)\n        status_layout.setSpacing(11)\n\n        brand = QLabel("SP-FARMS")\n        brand.setStyleSheet("font-weight: 800;")\n        status_layout.addWidget(brand)\n        status_layout.addWidget(QLabel("|"))\n\n        self.footer_labels: dict[str, QLabel] = {}\n        for key, value in (\n            ("Total", "0"),\n            ("Online", "0"),\n            ("Running", "0"),\n            ("Success", "0"),\n            ("Failed", "0"),\n            ("Queue", "0"),\n            ("CPU", "0%"),\n            ("RAM", "0 MB"),\n        ):\n            block = QHBoxLayout()\n            block.setSpacing(3)\n\n            name = QLabel(key)\n            name.setProperty("muted", True)\n\n            number = QLabel(value)\n            number.setProperty("footerValue", True)\n            self.footer_labels[key] = number\n\n            block.addWidget(name)\n            block.addWidget(number)\n            status_layout.addLayout(block)\n\n        status_layout.addStretch()\n        status_layout.addWidget(\n            QLabel("Automate Smarter • Manage Bigger")\n        )\n        root.addWidget(status)\n\n        if device_controller is not None:\n            device_controller.devices_changed.connect(\n                self._update_device_status\n            )\n\n    def refresh_jobs(self) -> None:\n        jobs = self.job_queue.refresh()\n        self._update_job_status(jobs)\n\n    def _update_job_status(self, jobs: Sequence[Job]) -> None:\n        self.footer_labels["Success"].setText(\n            str(\n                sum(\n                    job.state is JobState.SUCCEEDED\n                    for job in jobs\n                )\n            )\n        )\n        self.footer_labels["Failed"].setText(\n            str(\n                sum(\n                    job.state is JobState.FAILED\n                    for job in jobs\n                )\n            )\n        )\n        self.footer_labels["Queue"].setText(\n            str(\n                sum(\n                    job.state in (JobState.PENDING, JobState.QUEUED)\n                    for job in jobs\n                )\n            )\n        )\n\n    def _update_device_status(self, devices: object) -> None:\n        if not isinstance(devices, tuple):\n            return\n\n        managed = tuple(\n            device\n            for device in devices\n            if isinstance(device, ManagedDevice)\n        )\n        online = tuple(\n            device\n            for device in managed\n            if device.is_online\n        )\n\n        self.footer_labels["Total"].setText(\n            str(len(managed))\n        )\n        self.footer_labels["Online"].setText(\n            str(len(online))\n        )\n        self.footer_labels["Running"].setText(\n            str(len(online))\n        )\n\n        cpu = [\n            device.cpu_usage\n            for device in managed\n            if device.cpu_usage is not None\n        ]\n        ram = [\n            device.ram_usage_mb\n            for device in managed\n            if device.ram_usage_mb is not None\n        ]\n\n        self.footer_labels["CPU"].setText(\n            f"{sum(cpu) / len(cpu):.0f}%"\n            if cpu\n            else "0%"\n        )\n        self.footer_labels["RAM"].setText(\n            f"{sum(ram)} MB"\n            if ram\n            else "0 MB"\n        )\n'
QUICK_PAYLOAD = 'from __future__ import annotations\n\nfrom PySide6.QtCore import Signal\nfrom PySide6.QtWidgets import (\n    QCheckBox,\n    QComboBox,\n    QFormLayout,\n    QHBoxLayout,\n    QLabel,\n    QLineEdit,\n    QListWidget,\n    QMessageBox,\n    QPushButton,\n    QVBoxLayout,\n    QWidget,\n)\n\nfrom sp_farms.app.automation_builder_workspace import DryRunDialog\nfrom sp_farms.app.widgets import (\n    Panel,\n    PrimaryButton,\n    SecondaryButton,\n    StatusChip,\n)\nfrom sp_farms.application.automation_builder import AutomationBuilderService\nfrom sp_farms.domain.automation_builder import AutomationPreset\n\n\nclass QuickAutomationWorkspace(QWidget):\n    """Compact preset launcher without step-flow cards."""\n\n    advanced_requested = Signal()\n    action_list_requested = Signal()\n\n    def __init__(\n        self,\n        service: AutomationBuilderService,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n        self._service = service\n        self.setObjectName("quickAutomationWorkspace")\n        self._build_ui()\n        self.refresh_presets()\n\n    def _build_ui(self) -> None:\n        root = QVBoxLayout(self)\n        root.setContentsMargins(10, 9, 10, 9)\n        root.setSpacing(8)\n\n        header = QHBoxLayout()\n\n        title_stack = QVBoxLayout()\n        title_stack.setSpacing(0)\n\n        title = QLabel("Preset Launcher")\n        title.setProperty("heading", True)\n        title_stack.addWidget(title)\n\n        subtitle = QLabel(\n            "Choose a saved workflow, review targets, dry-run, then start."\n        )\n        subtitle.setProperty("muted", True)\n        title_stack.addWidget(subtitle)\n\n        header.addLayout(title_stack)\n        header.addStretch()\n\n        action_list = SecondaryButton("Action List")\n        action_list.clicked.connect(\n            self.action_list_requested.emit\n        )\n        header.addWidget(action_list)\n\n        advanced = SecondaryButton("Task Builder")\n        advanced.clicked.connect(\n            self.advanced_requested.emit\n        )\n        header.addWidget(advanced)\n\n        root.addLayout(header)\n\n        body = QHBoxLayout()\n        body.setSpacing(8)\n\n        setup = Panel()\n        setup_layout = QVBoxLayout(setup)\n        setup_layout.setContentsMargins(11, 10, 11, 10)\n        setup_layout.setSpacing(8)\n\n        form = QFormLayout()\n        form.setHorizontalSpacing(12)\n        form.setVerticalSpacing(7)\n\n        self.preset_combo = QComboBox()\n        self.preset_combo.currentIndexChanged.connect(\n            self._refresh_summary\n        )\n        form.addRow("Workflow:", self.preset_combo)\n\n        self.use_preset_targets = QCheckBox(\n            "Use targets saved in preset"\n        )\n        self.use_preset_targets.setChecked(True)\n        self.use_preset_targets.toggled.connect(\n            self._target_mode_changed\n        )\n        form.addRow("Targets:", self.use_preset_targets)\n\n        self.account_ids = QLineEdit()\n        self.account_ids.setPlaceholderText(\n            "account-id-1, account-id-2"\n        )\n        self.account_ids.setEnabled(False)\n        form.addRow("Accounts:", self.account_ids)\n\n        self.destination_ids = QLineEdit()\n        self.destination_ids.setPlaceholderText(\n            "page-id-1, destination-id-2"\n        )\n        self.destination_ids.setEnabled(False)\n        form.addRow("Destinations:", self.destination_ids)\n\n        setup_layout.addLayout(form)\n\n        self.status = StatusChip("Ready", "success")\n        setup_layout.addWidget(self.status)\n\n        buttons = QHBoxLayout()\n\n        refresh = QPushButton("↻ Refresh")\n        refresh.clicked.connect(self.refresh_presets)\n        buttons.addWidget(refresh)\n\n        buttons.addStretch()\n\n        dry_run = SecondaryButton("Dry Run")\n        dry_run.setProperty("infoAction", True)\n        dry_run.clicked.connect(self._dry_run)\n        buttons.addWidget(dry_run)\n\n        start = PrimaryButton("▶ Start")\n        start.setProperty("successAction", True)\n        start.clicked.connect(self._run)\n        buttons.addWidget(start)\n\n        setup_layout.addLayout(buttons)\n        body.addWidget(setup, stretch=3)\n\n        preview = Panel()\n        preview_layout = QVBoxLayout(preview)\n        preview_layout.setContentsMargins(10, 9, 10, 9)\n        preview_layout.setSpacing(6)\n\n        preview_title = QLabel("Selected Actions")\n        preview_title.setProperty("sectionTitle", True)\n        preview_layout.addWidget(preview_title)\n\n        self.summary = QLabel("Select a preset.")\n        self.summary.setProperty("muted", True)\n        self.summary.setWordWrap(True)\n        preview_layout.addWidget(self.summary)\n\n        self.steps = QListWidget()\n        self.steps.setObjectName("quickAutomationSteps")\n        preview_layout.addWidget(self.steps, stretch=1)\n\n        body.addWidget(preview, stretch=2)\n        root.addLayout(body, stretch=1)\n\n    def refresh_presets(self) -> None:\n        current_id = self.preset_combo.currentData()\n\n        self.preset_combo.blockSignals(True)\n        self.preset_combo.clear()\n\n        for preset in self._service.list_presets():\n            suffix = " · Built-in" if preset.is_built_in else ""\n            self.preset_combo.addItem(\n                f"{preset.name}{suffix}",\n                preset.id,\n            )\n\n        if current_id:\n            for index in range(self.preset_combo.count()):\n                if self.preset_combo.itemData(index) == current_id:\n                    self.preset_combo.setCurrentIndex(index)\n                    break\n\n        self.preset_combo.blockSignals(False)\n        self._refresh_summary()\n\n    def _selected_preset(self) -> AutomationPreset | None:\n        preset_id = self.preset_combo.currentData()\n        if not preset_id:\n            return None\n        return self._service.get_preset(str(preset_id))\n\n    @staticmethod\n    def _parse_ids(text: str) -> list[str]:\n        return [\n            value.strip()\n            for value in text.replace("\\n", ",").split(",")\n            if value.strip()\n        ]\n\n    def _targets(\n        self,\n    ) -> tuple[list[str] | None, list[str] | None]:\n        if self.use_preset_targets.isChecked():\n            return None, None\n\n        return (\n            self._parse_ids(self.account_ids.text()),\n            self._parse_ids(self.destination_ids.text()),\n        )\n\n    def _target_mode_changed(self, checked: bool) -> None:\n        self.account_ids.setEnabled(not checked)\n        self.destination_ids.setEnabled(not checked)\n\n    def _refresh_summary(self) -> None:\n        preset = self._selected_preset()\n        self.steps.clear()\n\n        if preset is None:\n            self.summary.setText("No presets are available.")\n            self.status.update_state(\n                "warning",\n                "No preset",\n            )\n            return\n\n        enabled = sorted(\n            (\n                step\n                for step in preset.steps\n                if step.enabled\n            ),\n            key=lambda step: step.order,\n        )\n        approvals = sum(\n            step.requires_approval\n            for step in enabled\n        )\n\n        self.summary.setText(\n            f"{preset.description}\\n\\n"\n            f"{len(enabled)} enabled actions · "\n            f"{approvals} approval-gated."\n        )\n\n        for step in enabled:\n            title = step.step_type.value.replace(\n                "_",\n                " ",\n            ).title()\n            suffix = (\n                " · approval"\n                if step.requires_approval\n                else ""\n            )\n            self.steps.addItem(\n                f"{step.order:02d}. {title}{suffix}"\n            )\n\n        errors = self._service.validate_preset(preset)\n        self.status.update_state(\n            "warning" if errors else "success",\n            (\n                f"{len(errors)} validation issue(s)"\n                if errors\n                else "Preset ready"\n            ),\n        )\n\n    def _dry_run(self) -> None:\n        preset = self._selected_preset()\n        if preset is None:\n            QMessageBox.warning(\n                self,\n                "Preset Launcher",\n                "Select a preset first.",\n            )\n            return\n\n        accounts, destinations = self._targets()\n        if (\n            not self.use_preset_targets.isChecked()\n            and not accounts\n        ):\n            QMessageBox.warning(\n                self,\n                "Preset Launcher",\n                "Enter at least one authorized account "\n                "or use preset targets.",\n            )\n            return\n\n        report = self._service.generate_dry_run_report(\n            preset,\n            target_accounts=accounts,\n            target_destinations=destinations,\n        )\n        DryRunDialog(report, self).exec()\n\n    def _run(self) -> None:\n        preset = self._selected_preset()\n        if preset is None:\n            QMessageBox.warning(\n                self,\n                "Preset Launcher",\n                "Select a preset first.",\n            )\n            return\n\n        accounts, destinations = self._targets()\n        if (\n            not self.use_preset_targets.isChecked()\n            and not accounts\n        ):\n            QMessageBox.warning(\n                self,\n                "Preset Launcher",\n                "Enter at least one authorized account "\n                "or use preset targets.",\n            )\n            return\n\n        answer = QMessageBox.question(\n            self,\n            "Start workflow?",\n            f"Start \'{preset.name}\' now?",\n            (\n                QMessageBox.StandardButton.Yes\n                | QMessageBox.StandardButton.No\n            ),\n            QMessageBox.StandardButton.No,\n        )\n        if answer != QMessageBox.StandardButton.Yes:\n            return\n\n        success, message, job_ids = (\n            self._service.execute_preset(\n                preset,\n                target_accounts=accounts,\n                target_destinations=destinations,\n                initiator="operator_preset_launcher",\n            )\n        )\n\n        if success:\n            self.status.update_state(\n                "active",\n                f"Started · {len(job_ids)} job(s)",\n            )\n            QMessageBox.information(\n                self,\n                "Workflow started",\n                f"{message}\\n\\nCreated jobs: {len(job_ids)}",\n            )\n        else:\n            self.status.update_state(\n                "error",\n                "Could not start",\n            )\n            QMessageBox.warning(\n                self,\n                "Workflow not started",\n                message,\n            )\n'


def fail(message: str) -> None:
    print(f"[ERROR] {message}")
    raise SystemExit(1)


def backup_files(names: tuple[str, ...]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = ROOT / f".reference_demo_v6_backup_{stamp}"

    for name in names:
        source = APP / name
        if not source.exists():
            continue

        target = backup / "sp_farms" / "app" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    return backup


def remove_block(
    text: str,
    start_token: str,
    end_token: str,
    label: str,
) -> str:
    start = text.find(start_token)
    if start == -1:
        print(f"[SKIP] {label}: not present")
        return text

    line_start = text.rfind("\n", 0, start) + 1

    # Include a directly preceding comment when it describes the removed flow UI.
    previous_line_end = max(0, line_start - 1)
    previous_line_start = text.rfind("\n", 0, previous_line_end) + 1
    previous_line = text[previous_line_start:previous_line_end].lower()
    if "flow" in previous_line and previous_line.strip().startswith("#"):
        line_start = previous_line_start

    end = text.find(end_token, start)
    if end == -1:
        print(f"[WARN] {label}: start found but end not found")
        return text

    end += len(end_token)
    if end < len(text) and text[end] == "\n":
        end += 1

    print(f"[REMOVE] {label}")
    return text[:line_start] + text[end:]


def remove_indented_block(
    text: str,
    marker: str,
    base_indent: int,
    label: str,
) -> str:
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    skipping = False
    removed = False

    for line in lines:
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)

        if not skipping and marker in line:
            skipping = True
            removed = True
            continue

        if skipping:
            if stripped.strip() == "":
                continue
            if indent > base_indent:
                continue

            skipping = False

        output.append(line)

    if removed:
        print(f"[REMOVE] {label}")
    else:
        print(f"[SKIP] {label}: not present")

    return "".join(output)


def remove_account_flow_references(text: str) -> str:
    text = remove_indented_block(
        text,
        'if hasattr(self, "account_flow_buttons"):',
        8,
        "Account flow state block",
    )

    lines = text.splitlines(keepends=True)
    output: list[str] = []
    skip_multiline = False
    balance = 0

    for line in lines:
        if skip_multiline:
            balance += line.count("(") - line.count(")")
            if balance <= 0:
                skip_multiline = False
            continue

        if "self.account_flow_" in line:
            balance = line.count("(") - line.count(")")
            if balance > 0:
                skip_multiline = True
            continue

        output.append(line)

    return "".join(output)


def patch_main_window() -> None:
    path = APP / "main_window.py"
    text = path.read_text(encoding="utf-8")

    quick_tab = (
        "                if self.quick_automation_workspace is not None:\n"
        '                    automation_tabs.addTab(self.quick_automation_workspace, "Quick Mode")\n'
    )
    if quick_tab in text:
        text = text.replace(quick_tab, "", 1)
        print("[REMOVE] Automation Quick Mode tab")
    else:
        print("[SKIP] Automation Quick Mode tab: not present")

    action_connection = (
        "                if self.quick_automation_workspace is not None:\n"
        "                    self.quick_automation_workspace.action_list_requested.connect(\n"
        "                        lambda tabs=automation_tabs: tabs.setCurrentWidget(\n"
        "                            self.action_list_workspace\n"
        "                        )\n"
        "                        if self.action_list_workspace is not None\n"
        "                        else None\n"
        "                    )\n"
    )
    if action_connection in text:
        text = text.replace(action_connection, "", 1)
        print("[REMOVE] Quick Mode → Action List connection")

    advanced_connection = (
        "                if self.quick_automation_workspace is not None:\n"
        "                    self.quick_automation_workspace.advanced_requested.connect(\n"
        "                        lambda tabs=automation_tabs: tabs.setCurrentWidget(\n"
        "                            self.automation_builder_workspace\n"
        "                        )\n"
        "                        if self.automation_builder_workspace is not None\n"
        "                        else None\n"
        "                    )\n"
    )
    if advanced_connection in text:
        text = text.replace(advanced_connection, "", 1)
        print("[REMOVE] Quick Mode → Task Builder connection")

    # Also support the pre-Ruff lambda form created by V4/V5.
    old_action_connection = (
        "                if self.quick_automation_workspace is not None:\n"
        "                    self.quick_automation_workspace.action_list_requested.connect(\n"
        "                        lambda: automation_tabs.setCurrentWidget(\n"
        "                            self.action_list_workspace\n"
        "                        )\n"
        "                        if self.action_list_workspace is not None\n"
        "                        else None\n"
        "                    )\n"
    )
    text = text.replace(old_action_connection, "", 1)

    old_advanced_connection = (
        "                if self.quick_automation_workspace is not None:\n"
        "                    self.quick_automation_workspace.advanced_requested.connect(\n"
        "                        lambda: automation_tabs.setCurrentWidget(\n"
        "                            self.automation_builder_workspace\n"
        "                        )\n"
        "                        if self.automation_builder_workspace is not None\n"
        "                        else None\n"
        "                    )\n"
    )
    text = text.replace(old_advanced_connection, "", 1)

    text = text.replace(
        'automation_tabs.addTab(self.automation_builder_workspace, "Advanced Builder")',
        'automation_tabs.addTab(self.automation_builder_workspace, "Task Builder")',
    )
    text = text.replace(
        'automation_tabs.addTab(self.automation_builder_workspace, "Automation Builder")',
        'automation_tabs.addTab(self.automation_builder_workspace, "Task Builder")',
    )

    path.write_text(text, encoding="utf-8")
    print("[PATCH] Main window reference-demo tabs")


def patch_account_workspace() -> None:
    path = APP / "account_workspace.py"
    text = path.read_text(encoding="utf-8")

    text = remove_block(
        text,
        "        account_flow = Panel()\n",
        "        listing_layout.addWidget(account_flow)\n",
        "Accounts FLOW strip",
    )
    text = remove_account_flow_references(text)

    text = text.replace(
        'SecondaryButton("Action List...")',
        'SecondaryButton("Action List")',
    )
    text = text.replace(
        'PrimaryButton("Actions...")',
        'PrimaryButton("Account Actions")',
    )

    path.write_text(text, encoding="utf-8")
    print("[PATCH] Accounts now follows table + Action List / Account Actions")


def patch_content_workspace() -> None:
    path = APP / "content_workspace.py"
    text = path.read_text(encoding="utf-8")

    text = remove_block(
        text,
        "        content_flow = Panel()\n",
        "        layout.addWidget(content_flow)\n",
        "Content FLOW strip",
    )

    path.write_text(text, encoding="utf-8")
    print("[PATCH] Content flow strip removed")


def patch_action_list() -> None:
    path = APP / "farm_reel_action_list.py"
    if not path.exists():
        print("[SKIP] farm_reel_action_list.py not installed")
        return

    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'SecondaryButton("Common Flow")',
        'SecondaryButton("Common Actions")',
    )
    path.write_text(text, encoding="utf-8")
    print("[PATCH] Action List wording aligned with demo")


def main() -> None:
    if not (APP / "main_window.py").exists():
        fail(
            "Run APPLY_REFERENCE_DEMO_V6.py from the SP-Farms repository root."
        )

    touched = (
        "home_dashboard.py",
        "workspaces.py",
        "quick_automation_workspace.py",
        "main_window.py",
        "account_workspace.py",
        "content_workspace.py",
        "farm_reel_action_list.py",
    )
    backup = backup_files(touched)
    print(f"[OK] Backup created: {backup}")

    (APP / "home_dashboard.py").write_text(
        HOME_PAYLOAD,
        encoding="utf-8",
    )
    (APP / "workspaces.py").write_text(
        WORKSPACES_PAYLOAD,
        encoding="utf-8",
    )
    (APP / "quick_automation_workspace.py").write_text(
        QUICK_PAYLOAD,
        encoding="utf-8",
    )
    print("[COPY] Home + Device rail + Preset Launcher")

    patch_main_window()
    patch_account_workspace()
    patch_content_workspace()
    patch_action_list()

    print()
    print("SP-Farms Reference Demo V6 applied.")
    print("Removed from the visible UX:")
    print("  - Home Quick Actions")
    print("  - Home QUICK FLOW")
    print("  - Accounts ACCOUNT FLOW")
    print("  - Content CONTENT FLOW")
    print("  - Automation Quick Mode tab")
    print("  - Device rail Quick Actions section")
    print()
    print("Kept:")
    print("  - dense account/page/group tables")
    print("  - Device Manager controls")
    print("  - Account Actions")
    print("  - Farm-Reel-style Action List")
    print("  - Task Builder / job queue")
    print("  - real existing services and job engine")
    print()
    print("Validate:")
    print(
        r"  .\.venv\Scripts\python.exe -m ruff check "
        r"sp_farms tests/test_farm_reel_action_list.py"
    )
    print(
        r"  .\.venv\Scripts\python.exe -m pytest "
        r"tests/test_design_system.py tests/test_main_window.py "
        r"tests/test_farm_reel_action_list.py -q"
    )
    print(r"  .\.venv\Scripts\python.exe -m sp_farms.app.main")
    print()
    print(f"Rollback backup: {backup}")


if __name__ == "__main__":
    main()
