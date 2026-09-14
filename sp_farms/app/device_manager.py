from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QRunnable,
    QSettings,
    QSortFilterProxyModel,
    Qt,
    QThreadPool,
    Signal,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QSplitter,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.widgets import (
    CompactTable,
    Panel,
    PrimaryButton,
    SecondaryButton,
    StatusChip,
)
from sp_farms.application.device_service import DeviceService
from sp_farms.domain.device_management import ManagedDevice

COLUMNS = (
    "Provider",
    "Device",
    "ADB Serial",
    "ADB Status",
    "Android",
    "Assigned Account",
    "App Version",
    "CPU / RAM",
    "Network",
    "Resolution",
    "Heartbeat",
    "Appium Status",
    "Appium Session",
    "Active Job",
)
_ROOT_INDEX = QModelIndex()


def _format_heartbeat(value: datetime | None) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S") if value else "—"


class DeviceTableModel(QAbstractTableModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._devices: list[ManagedDevice] = []

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = _ROOT_INDEX) -> int:
        return 0 if parent.isValid() else len(self._devices)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = _ROOT_INDEX) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            orientation is Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(COLUMNS)
        ):
            return COLUMNS[section]
        return None

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        device = self.get_device(index.row()) if index.isValid() else None
        if device is None:
            return None
        if role == Qt.ItemDataRole.UserRole:
            return device
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        cpu_ram = "—"
        if device.cpu_usage is not None or device.ram_usage_mb is not None:
            cpu = f"{device.cpu_usage:.0f}%" if device.cpu_usage is not None else "—"
            ram = f"{device.ram_usage_mb} MB" if device.ram_usage_mb is not None else "—"
            cpu_ram = f"{cpu} / {ram}"
        adb_status = "Connected" if device.is_online else "Disconnected"
        appium_status = getattr(device, "appium_status", "Ready")
        appium_session = getattr(device, "appium_session_state", "Idle")
        active_job = getattr(device, "current_job_id", "—") or "—"

        values = (
            device.provider.value,
            device.display_name,
            device.adb_serial,
            adb_status,
            device.android_version or "—",
            device.assigned_account or "Unassigned",
            device.app_version or "—",
            cpu_ram,
            device.network_state or "—",
            f"{device.resolution[0]}x{device.resolution[1]}" if device.resolution else "—",
            _format_heartbeat(device.last_heartbeat),
            appium_status,
            appium_session,
            active_job,
        )
        return values[index.column()] if 0 <= index.column() < len(values) else None

    def set_devices(self, devices: Sequence[ManagedDevice]) -> None:
        self.beginResetModel()
        self._devices = list(devices)
        self.endResetModel()

    def get_device(self, row: int) -> ManagedDevice | None:
        return self._devices[row] if 0 <= row < len(self._devices) else None

    def counts(self) -> tuple[int, int]:
        return len(self._devices), sum(device.is_online for device in self._devices)


class DeviceFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._search = ""
        self._state = "all"
        self._provider = "all"

    def set_search(self, value: str) -> None:
        self._search = value.strip().lower()
        self.beginFilterChange()
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def set_state_filter(self, value: str) -> None:
        self._state = value.lower()
        self.beginFilterChange()
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def set_provider_filter(self, value: str) -> None:
        self._provider = value.lower()
        self.beginFilterChange()
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def filterAcceptsRow(
        self,
        source_row: int,
        source_parent: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        model = self.sourceModel()
        if not isinstance(model, DeviceTableModel):
            return True
        device = model.get_device(source_row)
        if device is None:
            return False
        if self._provider != "all" and device.provider.value != self._provider:
            return False
        if self._state == "online" and not device.is_online:
            return False
        if self._state == "offline" and device.is_online:
            return False
        searchable = " ".join(
            (
                device.provider.value,
                device.name,
                device.alias,
                device.adb_serial,
                device.assigned_account or "",
                device.notes,
            )
        ).lower()
        return not self._search or self._search in searchable


class DeviceRailModel(QAbstractListModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._devices: list[ManagedDevice] = []

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = _ROOT_INDEX) -> int:
        return 0 if parent.isValid() else len(self._devices)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._devices):
            return None
        device = self._devices[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            marker = "●" if device.is_online else "○"
            details = f"{device.provider.value} · {device.adb_serial}"
            return f"{marker} {device.display_name}\n   {details}"
        if role == Qt.ItemDataRole.UserRole:
            return device
        return None

    def set_devices(self, devices: Sequence[ManagedDevice]) -> None:
        self.beginResetModel()
        self._devices = list(devices)
        self.endResetModel()


class _WorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)


class _Worker(QRunnable):
    def __init__(self, operation: Callable[[], object]) -> None:
        super().__init__()
        self._operation = operation
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            result = self._operation()
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        else:
            self.signals.succeeded.emit(result)


class DeviceManagerView(QWidget):
    devices_changed = Signal(object)

    def __init__(
        self,
        service: DeviceService | None,
        settings: QSettings | None = None,
        rail_model: DeviceRailModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("deviceManagerView")
        self._service = service
        self._settings = settings or QSettings("SP-Farms", "SP-Farms")
        self._pool = QThreadPool.globalInstance()
        self._workers: set[_Worker] = set()
        self.model = DeviceTableModel(self)
        self.proxy_model = DeviceFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.rail_model = rail_model or DeviceRailModel(self)
        self._build_ui()
        self._connect_signals()
        self._load_presets()
        self._update_action_states()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 8)
        root.setSpacing(7)
        toolbar = Panel()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 6, 8, 6)
        toolbar_layout.setSpacing(6)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search devices...")
        self.search_input.setMaximumWidth(240)
        self.provider_filter = QComboBox()
        self.provider_filter.addItems(("All providers", "LDPlayer", "MuMu", "Physical"))
        self.state_filter = QComboBox()
        self.state_filter.addItems(("All states", "Online", "Offline"))
        self.preset_combo = QComboBox()
        self.preset_combo.setEditable(True)
        self.preset_combo.setPlaceholderText("Saved filter")
        self.save_preset_btn = SecondaryButton("Save Filter")
        self.refresh_btn = PrimaryButton("Refresh")
        for widget in (
            self.search_input,
            self.provider_filter,
            self.state_filter,
            self.preset_combo,
            self.save_preset_btn,
            self.refresh_btn,
        ):
            toolbar_layout.addWidget(widget)
        toolbar_layout.addStretch()
        root.addWidget(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.rail = QListView()
        self.rail.setObjectName("deviceRail")
        self.rail.setModel(self.rail_model)
        self.rail.setMinimumWidth(210)
        self.rail.setMaximumWidth(290)
        self.rail.setUniformItemSizes(True)
        splitter.addWidget(self.rail)

        self.table = CompactTable()
        self.table.setObjectName("deviceTable")
        self.table.setModel(self.proxy_model)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        splitter.addWidget(self.table)

        inspector = Panel()
        inspector.setMinimumWidth(250)
        inspector.setMaximumWidth(330)
        inspector_layout = QVBoxLayout(inspector)
        inspector_layout.setContentsMargins(10, 10, 10, 10)
        inspector_layout.addWidget(QLabel("Device Details"))
        form = QFormLayout()
        self.alias_input = QLineEdit()
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(100)
        self.package_input = QLineEdit("com.facebook.katana")
        self.appium_status_lbl = QLabel("Appium: Ready")
        self.session_state_lbl = QLabel("Session: Idle")
        self.active_job_lbl = QLabel("Job: None")
        form.addRow("Alias", self.alias_input)
        form.addRow("Notes", self.notes_input)
        form.addRow("Package", self.package_input)
        form.addRow("Appium State", self.appium_status_lbl)
        form.addRow("Session State", self.session_state_lbl)
        form.addRow("Active Job", self.active_job_lbl)
        inspector_layout.addLayout(form)
        self.save_profile_btn = PrimaryButton("Save Alias & Notes")
        inspector_layout.addWidget(self.save_profile_btn)
        inspector_layout.addStretch()
        splitter.addWidget(inspector)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes((230, 900, 280))
        root.addWidget(splitter, stretch=1)

        actions = Panel()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(8, 5, 8, 5)
        self.select_all_btn = SecondaryButton("Select All")
        self.start_btn = PrimaryButton("Start")
        self.stop_btn = SecondaryButton("Stop")
        self.restart_btn = SecondaryButton("Restart")
        self.launch_btn = SecondaryButton("Launch App")
        self.screenshot_btn = SecondaryButton("Screenshot")
        self.logs_btn = SecondaryButton("Logs")
        self.arrange_btn = SecondaryButton("Arrange Windows")
        self.arrange_btn.setEnabled(False)
        for button in (
            self.select_all_btn,
            self.start_btn,
            self.stop_btn,
            self.restart_btn,
            self.launch_btn,
            self.screenshot_btn,
            self.logs_btn,
            self.arrange_btn,
        ):
            actions_layout.addWidget(button)
        actions_layout.addStretch()
        self.status_chip = StatusChip("0 devices", "neutral")
        actions_layout.addWidget(self.status_chip)
        root.addWidget(actions)

    def _connect_signals(self) -> None:
        self.search_input.textChanged.connect(self.proxy_model.set_search)
        self.provider_filter.currentTextChanged.connect(self._apply_filters)
        self.state_filter.currentTextChanged.connect(self._apply_filters)
        self.preset_combo.activated.connect(self._apply_preset)
        self.save_preset_btn.clicked.connect(self._save_preset)
        self.refresh_btn.clicked.connect(self.refresh)
        self.select_all_btn.clicked.connect(self.table.selectAll)
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)
        self.save_profile_btn.clicked.connect(self._save_profile)
        self.start_btn.clicked.connect(lambda: self._run_action("start"))
        self.stop_btn.clicked.connect(lambda: self._run_action("stop"))
        self.restart_btn.clicked.connect(lambda: self._run_action("restart"))
        self.launch_btn.clicked.connect(lambda: self._run_action("launch_app"))
        self.screenshot_btn.clicked.connect(lambda: self._run_artifact_action("screenshot"))
        self.logs_btn.clicked.connect(lambda: self._run_artifact_action("logs"))

    def set_devices(self, devices: Sequence[ManagedDevice]) -> None:
        current = tuple(devices)
        self.model.set_devices(current)
        self.rail_model.set_devices(current)
        total, online = self.model.counts()
        self.status_chip.update_state(
            "success" if online else "neutral", f"{online}/{total} online"
        )
        self.devices_changed.emit(current)
        self._update_action_states()

    def refresh(self) -> None:
        if self._service is None:
            self.set_devices(())
            return
        self.refresh_btn.setEnabled(False)
        self.status_chip.update_state("active", "Discovering...")
        self._submit(self._service.discover, self._discovery_complete)

    def _submit(self, operation: Callable[[], object], success: Callable[[object], None]) -> None:
        worker = _Worker(operation)
        self._workers.add(worker)
        worker.signals.succeeded.connect(success)
        worker.signals.succeeded.connect(lambda _result, item=worker: self._workers.discard(item))
        worker.signals.failed.connect(self._operation_failed)
        worker.signals.failed.connect(lambda _error, item=worker: self._workers.discard(item))
        self._pool.start(worker)

    def _discovery_complete(self, result: object) -> None:
        if isinstance(result, tuple) and all(isinstance(item, ManagedDevice) for item in result):
            self.set_devices(result)
        self.refresh_btn.setEnabled(True)

    def _operation_failed(self, message: str) -> None:
        self.refresh_btn.setEnabled(True)
        self.status_chip.update_state("error", message or "Operation failed")

    def _selected_devices(self) -> list[ManagedDevice]:
        selection = self.table.selectionModel()
        if selection is None:
            return []
        devices: list[ManagedDevice] = []
        for proxy_index in selection.selectedRows():
            device = self.model.get_device(self.proxy_model.mapToSource(proxy_index).row())
            if device is not None:
                devices.append(device)
        return devices

    def _selection_changed(self) -> None:
        selected = self._selected_devices()
        if len(selected) == 1:
            dev = selected[0]
            self.alias_input.setText(dev.alias)
            self.notes_input.setPlainText(dev.notes)
            appium_st = getattr(dev, "appium_status", "Ready")
            session_st = getattr(dev, "appium_session_state", "Idle")
            cur_job = getattr(dev, "current_job_id", "None") or "None"
            self.appium_status_lbl.setText(f"Appium: {appium_st}")
            self.session_state_lbl.setText(f"Session: {session_st}")
            self.active_job_lbl.setText(f"Job: {cur_job}")
        else:
            self.alias_input.clear()
            self.notes_input.clear()
            self.appium_status_lbl.setText("Appium: Ready")
            self.session_state_lbl.setText("Session: Idle")
            self.active_job_lbl.setText("Job: None")
        self._update_action_states()

    def _update_action_states(self) -> None:
        selected = self._selected_devices()
        self.start_btn.setEnabled(
            bool(selected)
            and all(
                device.capabilities.can_start_stop and not device.is_online for device in selected
            )
        )
        self.stop_btn.setEnabled(
            bool(selected)
            and all(device.capabilities.can_start_stop and device.is_online for device in selected)
        )
        self.restart_btn.setEnabled(
            bool(selected)
            and all(device.capabilities.can_restart and device.is_online for device in selected)
        )
        ready = bool(selected) and all(device.is_online for device in selected)
        self.launch_btn.setEnabled(ready and all(d.capabilities.can_launch_apps for d in selected))
        self.screenshot_btn.setEnabled(
            ready and all(device.capabilities.can_take_screenshot for device in selected)
        )
        self.logs_btn.setEnabled(
            ready and all(device.capabilities.can_collect_logs for device in selected)
        )
        self.save_profile_btn.setEnabled(len(selected) == 1 and self._service is not None)

    def run_devices(
        self,
        action: str,
        devices: Sequence[ManagedDevice],
        package_name: str | None = None,
    ) -> None:
        if self._service is None or not devices:
            return
        selected = tuple(devices)
        service = self._service
        package = package_name if package_name is not None else self.package_input.text()
        operations: dict[str, Callable[[], object]] = {
            "start": lambda: service.start(selected),
            "stop": lambda: service.stop(selected),
            "restart": lambda: service.restart(selected),
            "launch_app": lambda: service.launch_app(selected, package),
        }
        self._submit(operations[action], lambda _result: self.refresh())

    def collect_device_artifacts(self, action: str, devices: Sequence[ManagedDevice]) -> None:
        if self._service is None or not devices:
            return
        selected = tuple(devices)
        service = self._service

        def operation() -> object:
            if action == "screenshot":
                return tuple(service.take_screenshot(device) for device in selected)
            return tuple(service.collect_logs(device) for device in selected)

        self._submit(operation, lambda result: self._artifact_complete(action, result))

    def _run_action(self, action: str) -> None:
        self.run_devices(action, self._selected_devices())

    def _run_artifact_action(self, action: str) -> None:
        self.collect_device_artifacts(action, self._selected_devices())

    def _artifact_complete(self, action: str, result: object) -> None:
        count = len(result) if isinstance(result, tuple) else 0
        label = "screenshots" if action == "screenshot" else "logs"
        self.status_chip.update_state("success", f"Saved {count} {label}")

    def _save_profile(self) -> None:
        if self._service is None:
            return
        selected = self._selected_devices()
        if len(selected) != 1:
            return
        service = self._service
        self._submit(
            lambda: service.save_profile(
                selected[0], self.alias_input.text(), self.notes_input.toPlainText()
            ),
            lambda _result: self.refresh(),
        )

    def _apply_filters(self) -> None:
        provider_labels = {
            "All providers": "all",
            "LDPlayer": "ldplayer",
            "MuMu": "mumu",
            "Physical": "physical",
        }
        state_labels = {"All states": "all", "Online": "online", "Offline": "offline"}
        self.proxy_model.set_provider_filter(provider_labels[self.provider_filter.currentText()])
        self.proxy_model.set_state_filter(state_labels[self.state_filter.currentText()])

    def _load_presets(self) -> None:
        self.preset_combo.clear()
        self._settings.beginGroup("devices/filters")
        self.preset_combo.addItems(sorted(self._settings.childKeys()))
        self._settings.endGroup()

    def _save_preset(self) -> None:
        name = self.preset_combo.currentText().strip()
        if not name:
            return
        value = "\x1f".join(
            (
                self.search_input.text(),
                self.provider_filter.currentText(),
                self.state_filter.currentText(),
            )
        )
        self._settings.setValue(f"devices/filters/{name}", value)
        self._settings.sync()
        self._load_presets()
        self.preset_combo.setCurrentText(name)

    def _apply_preset(self, index: int) -> None:
        name = self.preset_combo.itemText(index)
        value = str(self._settings.value(f"devices/filters/{name}", "", str))
        parts = value.split("\x1f")
        if len(parts) != 3:
            return
        self.search_input.setText(parts[0])
        self.provider_filter.setCurrentText(parts[1])
        self.state_filter.setCurrentText(parts[2])
