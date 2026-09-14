from collections.abc import Callable, Sequence
from dataclasses import replace

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.widgets import Panel, PrimaryButton, SecondaryButton, StatusChip
from sp_farms.application.qa_profile_service import QAProfileService
from sp_farms.domain.device_management import ManagedDevice
from sp_farms.domain.qa_profiles import QABridgeStatus, QAProfile
from sp_farms.domain.result import Result


class _WorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)


class _Worker(QRunnable):
    def __init__(self, operation: Callable[[], object]) -> None:
        super().__init__()
        self.operation = operation
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            self.signals.succeeded.emit(self.operation())
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class QAProfileLab(QWidget):
    def __init__(
        self,
        service: QAProfileService | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("qaProfileLab")
        self._service = service
        self._devices: tuple[ManagedDevice, ...] = ()
        self._profiles: tuple[QAProfile, ...] = ()
        self._workers: set[_Worker] = set()
        self._pool = QThreadPool.globalInstance()
        self._build_ui()
        self._connect()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 8)
        root.setSpacing(7)
        notice = QLabel(
            "Authorized QA only: synthetic test data remains separate from actual device inventory."
        )
        notice.setProperty("muted", True)
        root.addWidget(notice)

        actions = QHBoxLayout()
        self.new_btn = PrimaryButton("New")
        self.clone_btn = SecondaryButton("Clone")
        self.randomize_btn = SecondaryButton("Randomize")
        self.save_btn = PrimaryButton("Save")
        self.delete_btn = SecondaryButton("Delete")
        self.push_btn = SecondaryButton("Push")
        self.reload_btn = PrimaryButton("Push + Reload")
        self.verify_btn = SecondaryButton("Verify")
        self.restore_btn = SecondaryButton("Restore Default")
        for button in (
            self.new_btn,
            self.clone_btn,
            self.randomize_btn,
            self.save_btn,
            self.delete_btn,
            self.push_btn,
            self.reload_btn,
            self.verify_btn,
            self.restore_btn,
        ):
            actions.addWidget(button)
        actions.addStretch()
        root.addLayout(actions)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        devices = Panel()
        devices_layout = QVBoxLayout(devices)
        devices_layout.addWidget(QLabel("Devices"))
        self.device_list = QListWidget()
        self.device_list.setObjectName("qaDeviceList")
        devices_layout.addWidget(self.device_list)
        splitter.addWidget(devices)

        center = Panel()
        center_layout = QVBoxLayout(center)
        center_layout.addWidget(QLabel("QA Profiles"))
        self.profile_table = QTableWidget(0, 4)
        self.profile_table.setObjectName("qaProfileTable")
        self.profile_table.setHorizontalHeaderLabels(
            ("Profile", "Manufacturer", "Model", "Timezone")
        )
        self.profile_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        center_layout.addWidget(self.profile_table)
        editor = QFormLayout()
        self.name_input = QLineEdit()
        self.manufacturer_input = QLineEdit()
        self.model_input = QLineEdit()
        self.product_input = QLineEdit()
        self.timezone_input = QLineEdit("UTC")
        self.test_data_input = QPlainTextEdit()
        self.test_data_input.setPlaceholderText(
            "Optional authorized test fixture JSON: test_android_id, test_serial_number, ..."
        )
        self.test_data_input.setMaximumHeight(90)
        editor.addRow("Profile name", self.name_input)
        editor.addRow("Manufacturer", self.manufacturer_input)
        editor.addRow("Model", self.model_input)
        editor.addRow("Product", self.product_input)
        editor.addRow("Timezone", self.timezone_input)
        editor.addRow("Test fields", self.test_data_input)
        center_layout.addLayout(editor)
        splitter.addWidget(center)

        target = Panel()
        target_layout = QVBoxLayout(target)
        target_layout.addWidget(QLabel("Authorized Target Package"))
        target_form = QFormLayout()
        self.package_input = QLineEdit()
        self.package_input.setPlaceholderText("com.example.ownedapp")
        self.package_name_input = QLineEdit()
        self.ownership_input = QLineEdit()
        self.ownership_input.setPlaceholderText("Ownership/authorization evidence")
        target_form.addRow("Package ID", self.package_input)
        target_form.addRow("Display name", self.package_name_input)
        target_form.addRow("Authorization", self.ownership_input)
        target_layout.addLayout(target_form)
        self.allow_target_btn = PrimaryButton("Add to Allowlist")
        target_layout.addWidget(self.allow_target_btn)
        target_layout.addWidget(QLabel("Bridge Status"))
        self.bridge_status = StatusChip("Not verified", "neutral")
        target_layout.addWidget(self.bridge_status)
        self.active_profile = QLabel("Active profile: —")
        self.active_profile.setWordWrap(True)
        target_layout.addWidget(self.active_profile)
        target_layout.addStretch()
        splitter.addWidget(target)
        splitter.setSizes((250, 620, 330))
        root.addWidget(splitter, stretch=1)

        self.summary = StatusChip("0 selected · 0 pushed · 0 reloaded · 0 verified · 0 failed")
        root.addWidget(self.summary)

    def _connect(self) -> None:
        self.new_btn.clicked.connect(self._new_profile)
        self.clone_btn.clicked.connect(self._clone_profile)
        self.randomize_btn.clicked.connect(self._randomize)
        self.save_btn.clicked.connect(self._save)
        self.delete_btn.clicked.connect(self._delete)
        self.allow_target_btn.clicked.connect(self._allow_target)
        self.push_btn.clicked.connect(lambda: self._push(False))
        self.reload_btn.clicked.connect(lambda: self._push(True))
        self.verify_btn.clicked.connect(self._verify)
        self.restore_btn.clicked.connect(self._restore)
        self.profile_table.itemSelectionChanged.connect(self._load_selected_profile)

    def set_devices(self, devices: Sequence[ManagedDevice]) -> None:
        self._devices = tuple(devices)
        self.device_list.clear()
        if self._service is None:
            return
        for index, device in enumerate(self._devices):
            assignment = self._service.get_assignment(device.provider.value, device.external_id)
            profile = self._profile(assignment.profile_id) if assignment else None
            label = profile.profile_name if profile else "Unassigned"
            item = QListWidgetItem(
                f"{device.display_name}\n{device.provider.value} · {device.state.value} · {label}"
            )
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.device_list.addItem(item)

    def refresh(self) -> None:
        if self._service is None:
            return
        self._profiles = tuple(self._service.list_profiles())
        self.profile_table.setRowCount(len(self._profiles))
        for row, profile in enumerate(self._profiles):
            values = (profile.profile_name, profile.manufacturer, profile.model, profile.timezone)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, profile.id)
                self.profile_table.setItem(row, column, item)
        self.profile_table.resizeColumnsToContents()
        self.set_devices(self._devices)

    def _selected_profile(self) -> QAProfile | None:
        row = self.profile_table.currentRow()
        return self._profiles[row] if 0 <= row < len(self._profiles) else None

    def _selected_device(self) -> ManagedDevice | None:
        item = self.device_list.currentItem()
        if item is None:
            return None
        index = int(item.data(Qt.ItemDataRole.UserRole))
        return self._devices[index]

    def _profile(self, profile_id: str) -> QAProfile | None:
        return next((profile for profile in self._profiles if profile.id == profile_id), None)

    def _new_profile(self) -> None:
        self.profile_table.clearSelection()
        self.name_input.setText("New QA Profile")
        for field in (
            self.manufacturer_input,
            self.model_input,
            self.product_input,
            self.test_data_input,
        ):
            field.clear()
        self.timezone_input.setText("UTC")

    def _load_selected_profile(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return
        self.name_input.setText(profile.profile_name)
        self.manufacturer_input.setText(profile.manufacturer)
        self.model_input.setText(profile.model)
        self.product_input.setText(profile.product)
        self.timezone_input.setText(profile.timezone)
        serialized = profile.to_dict()["profile"]
        if not isinstance(serialized, dict):
            return
        test_values = {
            key: value
            for key, value in serialized.items()
            if key.startswith("test_") and value
        }
        from json import dumps

        self.test_data_input.setPlainText(dumps(test_values, indent=2, sort_keys=True))

    def _editor_profile(self) -> QAProfile:
        from json import loads

        selected = self._selected_profile()
        if self._service is None:
            raise RuntimeError("QA profile storage is unavailable")
        profile = selected or self._service.new_profile(self.name_input.text())
        raw = self.test_data_input.toPlainText().strip()
        test_values = loads(raw) if raw else {}
        if not isinstance(test_values, dict) or any(
            not key.startswith("test_") for key in test_values
        ):
            raise ValueError("Only test_* fields are accepted in test fixture JSON")
        unknown = set(test_values) - set(QAProfile.__dataclass_fields__)
        if unknown:
            raise ValueError(f"Unknown test fields: {', '.join(sorted(unknown))}")
        return replace(
            profile,
            profile_name=self.name_input.text().strip(),
            manufacturer=self.manufacturer_input.text().strip(),
            model=self.model_input.text().strip(),
            product=self.product_input.text().strip(),
            timezone=self.timezone_input.text().strip() or "UTC",
            **test_values,
        )

    def _save(self) -> None:
        if self._service is None:
            return
        try:
            profile = self._service.save_profile(self._editor_profile())
            device = self._selected_device()
            if device is not None:
                self._service.assign(device.provider.value, device.external_id, profile.id)
            self.refresh()
            self._status("success", "Profile saved")
        except Exception as exc:
            self._status("error", str(exc))

    def _clone_profile(self) -> None:
        profile = self._selected_profile()
        if self._service is None or profile is None:
            return
        try:
            self._service.clone_profile(profile.id, f"{profile.profile_name} Copy")
            self.refresh()
        except Exception as exc:
            self._status("error", str(exc))

    def _randomize(self) -> None:
        profile = self._selected_profile()
        if self._service is None or profile is None:
            return
        try:
            self._service.randomize_compatibility_fields(profile.id)
            self.refresh()
        except Exception as exc:
            self._status("error", str(exc))

    def _delete(self) -> None:
        profile = self._selected_profile()
        if self._service is None or profile is None:
            return
        try:
            self._service.delete_profile(profile.id)
            self.refresh()
        except Exception as exc:
            self._status("error", str(exc))

    def _allow_target(self) -> None:
        if self._service is None:
            return
        try:
            profile = self._selected_profile()
            self._service.allow_target(
                self.package_input.text(),
                self.package_name_input.text(),
                self.ownership_input.text(),
                profile.id if profile else None,
            )
            self._status("success", "Target allowlisted")
        except Exception as exc:
            self._status("error", str(exc))

    def _push(self, reload_profile: bool) -> None:
        profile = self._selected_profile()
        device = self._selected_device()
        if self._service is None or profile is None or device is None:
            return
        service = self._service
        self._submit(
            lambda: service.push(
                device.adb_serial,
                device.provider.value,
                device.external_id,
                profile.id,
                self.package_input.text(),
                reload_profile,
            ),
            self._bridge_complete,
        )

    def _verify(self) -> None:
        device = self._selected_device()
        if self._service is None or device is None:
            return
        service = self._service
        self._submit(
            lambda: service.verify(
                device.adb_serial,
                device.provider.value,
                device.external_id,
                self.package_input.text(),
            ),
            self._bridge_complete,
        )

    def _restore(self) -> None:
        device = self._selected_device()
        if self._service is None or device is None:
            return
        service = self._service
        self._submit(
            lambda: service.restore(
                device.adb_serial,
                device.provider.value,
                device.external_id,
                self.package_input.text(),
            ),
            self._bridge_complete,
        )

    def _submit(
        self,
        operation: Callable[[], object],
        success: Callable[[object], None],
    ) -> None:
        worker = _Worker(operation)
        self._workers.add(worker)
        worker.signals.succeeded.connect(success)
        worker.signals.succeeded.connect(lambda _value, item=worker: self._workers.discard(item))
        worker.signals.failed.connect(lambda error: self._status("error", error))
        worker.signals.failed.connect(lambda _error, item=worker: self._workers.discard(item))
        self._pool.start(worker)

    def _bridge_complete(self, value: object) -> None:
        if not isinstance(value, Result):
            self._status("error", "Unexpected bridge response")
            return
        if not value.is_success:
            self._status("error", value.error.message)
            return
        status = value.value
        if not isinstance(status, QABridgeStatus):
            self._status("error", "Unexpected bridge status")
            return
        state = "success" if status.loaded else "active"
        self.bridge_status.update_state(state, status.message)
        self.active_profile.setText(f"Active profile: {status.profile_id or 'default'}")
        self.summary.update_state("success", "1 selected · operation completed · 0 failed")

    def _status(self, state: str, message: str) -> None:
        self.bridge_status.update_state(state, message)
        if state == "error":
            self.summary.update_state("error", "1 failed")
