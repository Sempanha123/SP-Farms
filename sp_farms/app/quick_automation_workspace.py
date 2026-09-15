from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.automation_builder_workspace import DryRunDialog
from sp_farms.app.widgets import Panel, PrimaryButton, SecondaryButton, StatusChip
from sp_farms.application.automation_builder import AutomationBuilderService
from sp_farms.domain.automation_builder import AutomationPreset


class QuickAutomationWorkspace(QWidget):
    """Simple operator workflow backed by the existing AutomationBuilderService."""

    advanced_requested = Signal()

    def __init__(
        self,
        service: AutomationBuilderService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self.setObjectName("quickAutomationWorkspace")
        self._build_ui()
        self.refresh_presets()

    def _flow_step(self, number: str, title: str, detail: str) -> QPushButton:
        button = QPushButton(f"{number}  {title}\n    {detail}")
        button.setProperty("flowStep", True)
        return button

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 9, 10, 9)
        root.setSpacing(8)

        header = QHBoxLayout()
        title_stack = QVBoxLayout()
        title_stack.setSpacing(0)

        title = QLabel("Quick Automation")
        title.setProperty("heading", True)
        title_stack.addWidget(title)

        subtitle = QLabel(
            "Fast mode for normal use. Advanced Builder remains available for complex presets."
        )
        subtitle.setProperty("muted", True)
        title_stack.addWidget(subtitle)

        header.addLayout(title_stack)
        header.addStretch()

        advanced = SecondaryButton("Advanced Builder")
        advanced.clicked.connect(self.advanced_requested.emit)
        header.addWidget(advanced)
        root.addLayout(header)

        flow = Panel()
        flow.setProperty("flowPanel", True)
        flow_layout = QHBoxLayout(flow)
        flow_layout.setContentsMargins(8, 7, 8, 7)
        flow_layout.setSpacing(5)

        self.step_preset = self._flow_step("1", "Preset", "Choose workflow")
        self.step_targets = self._flow_step("2", "Targets", "Accounts / assets")
        self.step_preview = self._flow_step("3", "Dry Run", "Zero side effects")
        self.step_start = self._flow_step("4", "Start", "Create jobs")
        self.step_monitor = self._flow_step("5", "Monitor", "Job Queue")

        for index, button in enumerate(
            (
                self.step_preset,
                self.step_targets,
                self.step_preview,
                self.step_start,
                self.step_monitor,
            )
        ):
            flow_layout.addWidget(button, stretch=1)
            if index < 4:
                arrow = QLabel("→")
                arrow.setProperty("flowArrow", True)
                flow_layout.addWidget(arrow)

        root.addWidget(flow)

        setup = QHBoxLayout()
        setup.setSpacing(8)

        left = Panel()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(11, 10, 11, 10)
        left_layout.setSpacing(8)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(7)

        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(300)
        self.preset_combo.currentIndexChanged.connect(self._refresh_summary)
        form.addRow("Workflow:", self.preset_combo)

        self.use_preset_targets = QCheckBox("Use targets saved in the preset")
        self.use_preset_targets.setChecked(True)
        self.use_preset_targets.toggled.connect(self._target_mode_changed)
        form.addRow("Targets:", self.use_preset_targets)

        self.account_ids = QLineEdit()
        self.account_ids.setPlaceholderText("account-id-1, account-id-2")
        self.account_ids.setEnabled(False)
        self.account_ids.textChanged.connect(self._refresh_flow_state)
        form.addRow("Account IDs:", self.account_ids)

        self.destination_ids = QLineEdit()
        self.destination_ids.setPlaceholderText("page-id-1, destination-id-2")
        self.destination_ids.setEnabled(False)
        self.destination_ids.textChanged.connect(self._refresh_flow_state)
        form.addRow("Destinations:", self.destination_ids)

        left_layout.addLayout(form)

        self.status = StatusChip("Preset ready", "success")
        left_layout.addWidget(self.status)

        button_row = QHBoxLayout()
        refresh = QPushButton("↻ Refresh")
        refresh.clicked.connect(self.refresh_presets)
        button_row.addWidget(refresh)
        button_row.addStretch()

        self.dry_run_btn = SecondaryButton("3  Dry Run")
        self.dry_run_btn.setProperty("infoAction", True)
        self.dry_run_btn.clicked.connect(self._dry_run)
        button_row.addWidget(self.dry_run_btn)

        self.run_btn = PrimaryButton("4  ▶ Start Workflow")
        self.run_btn.setProperty("successAction", True)
        self.run_btn.clicked.connect(self._run)
        button_row.addWidget(self.run_btn)
        left_layout.addLayout(button_row)
        setup.addWidget(left, stretch=3)

        right = Panel()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(10, 9, 10, 9)
        right_layout.setSpacing(6)

        summary_title = QLabel("Workflow Preview")
        summary_title.setProperty("sectionTitle", True)
        right_layout.addWidget(summary_title)

        self.summary = QLabel("Select a preset.")
        self.summary.setWordWrap(True)
        self.summary.setProperty("muted", True)
        right_layout.addWidget(self.summary)

        self.steps = QListWidget()
        self.steps.setObjectName("quickAutomationSteps")
        right_layout.addWidget(self.steps, stretch=1)
        setup.addWidget(right, stretch=2)

        root.addLayout(setup, stretch=1)
        self._refresh_flow_state()

    def refresh_presets(self) -> None:
        current_id = self.preset_combo.currentData()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()

        for preset in self._service.list_presets():
            suffix = " · Built-in" if preset.is_built_in else ""
            self.preset_combo.addItem(f"{preset.name}{suffix}", preset.id)

        if current_id:
            for index in range(self.preset_combo.count()):
                if self.preset_combo.itemData(index) == current_id:
                    self.preset_combo.setCurrentIndex(index)
                    break

        self.preset_combo.blockSignals(False)
        self._refresh_summary()

    def _selected_preset(self) -> AutomationPreset | None:
        preset_id = self.preset_combo.currentData()
        if not preset_id:
            return None
        return self._service.get_preset(str(preset_id))

    def _target_mode_changed(self, checked: bool) -> None:
        self.account_ids.setEnabled(not checked)
        self.destination_ids.setEnabled(not checked)
        self._refresh_flow_state()

    @staticmethod
    def _parse_ids(text: str) -> list[str]:
        return [
            value.strip()
            for value in text.replace("\n", ",").split(",")
            if value.strip()
        ]

    def _targets(self) -> tuple[list[str] | None, list[str] | None]:
        if self.use_preset_targets.isChecked():
            return None, None
        return (
            self._parse_ids(self.account_ids.text()),
            self._parse_ids(self.destination_ids.text()),
        )

    def _refresh_flow_state(self) -> None:
        preset_ready = self._selected_preset() is not None
        target_ready = self.use_preset_targets.isChecked() or bool(
            self._parse_ids(self.account_ids.text())
        )

        states = (
            "done" if preset_ready else "next",
            "done" if target_ready else ("next" if preset_ready else ""),
            "next" if preset_ready and target_ready else "",
            "",
            "",
        )
        for button, state in zip(
            (
                self.step_preset,
                self.step_targets,
                self.step_preview,
                self.step_start,
                self.step_monitor,
            ),
            states,
            strict=True,
        ):
            button.setProperty("flowState", state)
            button.style().unpolish(button)
            button.style().polish(button)

    def _refresh_summary(self) -> None:
        preset = self._selected_preset()
        self.steps.clear()

        if preset is None:
            self.summary.setText("No presets are available.")
            self.status.update_state("warning", "No preset")
            self._refresh_flow_state()
            return

        enabled = sorted(
            (step for step in preset.steps if step.enabled),
            key=lambda step: step.order,
        )
        approvals = sum(step.requires_approval for step in enabled)
        self.summary.setText(
            f"{preset.description}\n\n"
            f"{len(enabled)} enabled steps · {approvals} approval-gated · "
            f"max {preset.target_rules.max_concurrent_devices} devices."
        )

        for step in enabled:
            title = step.step_type.value.replace("_", " ").title()
            approval = " · approval" if step.requires_approval else ""
            self.steps.addItem(f"{step.order:02d}. {title}{approval}")

        errors = self._service.validate_preset(preset)
        self.status.update_state(
            "warning" if errors else "success",
            f"{len(errors)} validation issue(s)" if errors else "Preset ready",
        )
        self._refresh_flow_state()

    def _dry_run(self) -> None:
        preset = self._selected_preset()
        if preset is None:
            QMessageBox.warning(self, "Quick Automation", "Select a preset first.")
            return

        accounts, destinations = self._targets()
        if not self.use_preset_targets.isChecked() and not accounts:
            QMessageBox.warning(
                self,
                "Quick Automation",
                "Enter at least one authorized account ID or use preset targets.",
            )
            return

        report = self._service.generate_dry_run_report(
            preset,
            target_accounts=accounts,
            target_destinations=destinations,
        )
        self.step_preview.setProperty("flowState", "done")
        self.step_start.setProperty("flowState", "next")
        for widget in (self.step_preview, self.step_start):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        DryRunDialog(report, self).exec()

    def _run(self) -> None:
        preset = self._selected_preset()
        if preset is None:
            QMessageBox.warning(self, "Quick Automation", "Select a preset first.")
            return

        accounts, destinations = self._targets()
        if not self.use_preset_targets.isChecked() and not accounts:
            QMessageBox.warning(
                self,
                "Quick Automation",
                "Enter at least one authorized account ID or use preset targets.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Start workflow?",
            f"Start '{preset.name}' now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        success, message, job_ids = self._service.execute_preset(
            preset,
            target_accounts=accounts,
            target_destinations=destinations,
            initiator="operator_quick_mode",
        )

        if success:
            self.status.update_state("active", f"Started · {len(job_ids)} job(s)")
            self.step_start.setProperty("flowState", "done")
            self.step_monitor.setProperty("flowState", "next")
            for widget in (self.step_start, self.step_monitor):
                widget.style().unpolish(widget)
                widget.style().polish(widget)
            QMessageBox.information(
                self,
                "Workflow started",
                f"{message}\n\nCreated jobs: {len(job_ids)}",
            )
        else:
            self.status.update_state("error", "Could not start")
            QMessageBox.warning(self, "Workflow not started", message)
