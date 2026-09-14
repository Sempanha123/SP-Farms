from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from sp_farms.domain.device_pool import PoolDevice, SchedulingPolicy


class BatchRestoreDialog(QDialog):
    def __init__(
        self,
        selected_accounts_count: int,
        available_devices: Sequence[PoolDevice],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Restore Selected on Available Devices")
        self.resize(440, 360)
        self.setObjectName("batchRestoreDialog")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.accounts_count_label = QLabel(str(selected_accounts_count))
        form.addRow("Selected Accounts:", self.accounts_count_label)

        self.devices_count_label = QLabel(str(len(available_devices)))
        form.addRow("Eligible Devices:", self.devices_count_label)

        # Provider filter
        self.provider_combo = QComboBox()
        self.provider_combo.addItem("All Providers", userData="all")
        self.provider_combo.addItem("LDPlayer Only", userData="ldplayer")
        self.provider_combo.addItem("MuMu Only", userData="mumu")
        self.provider_combo.addItem("Physical Only", userData="physical")
        form.addRow("Device Provider:", self.provider_combo)

        # Policy
        self.policy_combo = QComboBox()
        self.policy_combo.addItem(
            "Bound Device First", userData=SchedulingPolicy.BOUND_DEVICE_FIRST
        )
        self.policy_combo.addItem("Any Available Device", userData=SchedulingPolicy.ANY_AVAILABLE)
        self.policy_combo.addItem(
            "Least Recently Used", userData=SchedulingPolicy.LEAST_RECENTLY_USED
        )
        self.policy_combo.addItem("Round Robin", userData=SchedulingPolicy.ROUND_ROBIN)
        self.policy_combo.addItem(
            "Preferred Provider", userData=SchedulingPolicy.PREFERRED_PROVIDER
        )
        form.addRow("Scheduling Policy:", self.policy_combo)

        # Preserves
        self.preserve_binding_check = QCheckBox("Preserve existing device binding")
        self.preserve_binding_check.setChecked(True)
        form.addRow("", self.preserve_binding_check)

        self.allow_fallback_check = QCheckBox("Allow fallback device")
        self.allow_fallback_check.setChecked(True)
        form.addRow("", self.allow_fallback_check)

        # Max concurrent
        self.max_concurrent_spin = QSpinBox()
        self.max_concurrent_spin.setRange(1, 16)
        self.max_concurrent_spin.setValue(2)
        form.addRow("Max Concurrent:", self.max_concurrent_spin)

        # Priority
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(0, 100)
        self.priority_spin.setValue(0)
        form.addRow("Queue Priority:", self.priority_spin)

        # Stop on error
        self.stop_on_error_check = QCheckBox("Stop queue on error")
        self.stop_on_error_check.setChecked(False)
        form.addRow("", self.stop_on_error_check)

        layout.addLayout(form)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    @property
    def selected_policy(self) -> SchedulingPolicy:
        return SchedulingPolicy(self.policy_combo.currentData())

    @property
    def provider_filter(self) -> str:
        return str(self.provider_combo.currentData())

    @property
    def allow_fallback(self) -> bool:
        return self.allow_fallback_check.isChecked()

    @property
    def max_concurrent(self) -> int:
        return self.max_concurrent_spin.value()

    @property
    def priority(self) -> int:
        return self.priority_spin.value()

    @property
    def stop_on_error(self) -> bool:
        return self.stop_on_error_check.isChecked()
