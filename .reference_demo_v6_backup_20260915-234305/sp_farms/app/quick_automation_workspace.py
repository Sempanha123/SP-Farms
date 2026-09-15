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
from sp_farms.app.widgets import FlowStepButton, Panel, PrimaryButton, SecondaryButton, StatusChip
from sp_farms.application.automation_builder import AutomationBuilderService
from sp_farms.domain.automation_builder import AutomationPreset


class QuickAutomationWorkspace(QWidget):
    """Farm-Reel-simple front end on the existing real automation service."""

    advanced_requested = Signal()
    action_list_requested = Signal()

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

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 9, 10, 9)
        root.setSpacing(8)

        header = QHBoxLayout()
        stack = QVBoxLayout()
        stack.setSpacing(0)
        title = QLabel("Quick Automation")
        title.setProperty("heading", True)
        stack.addWidget(title)
        subtitle = QLabel("Preset → targets → dry run → start → monitor")
        subtitle.setProperty("muted", True)
        stack.addWidget(subtitle)
        header.addLayout(stack)
        header.addStretch()
        action_list = SecondaryButton("Action List")
        action_list.clicked.connect(self.action_list_requested.emit)
        header.addWidget(action_list)

        advanced = SecondaryButton("Advanced Builder")
        advanced.clicked.connect(self.advanced_requested.emit)
        header.addWidget(advanced)
        root.addLayout(header)

        flow_panel = Panel()
        flow_panel.setProperty("flowPanel", True)
        flow = QHBoxLayout(flow_panel)
        flow.setContentsMargins(8, 7, 8, 7)
        flow.setSpacing(5)
        self.flow_buttons = [
            FlowStepButton(1, "Preset", "Choose workflow"),
            FlowStepButton(2, "Targets", "Accounts / assets"),
            FlowStepButton(3, "Dry Run", "Zero side effects"),
            FlowStepButton(4, "Start", "Create jobs"),
            FlowStepButton(5, "Monitor", "Job Queue"),
        ]
        for index, button in enumerate(self.flow_buttons):
            flow.addWidget(button, stretch=1)
            if index < len(self.flow_buttons) - 1:
                arrow = QLabel("→")
                arrow.setProperty("flowArrow", True)
                flow.addWidget(arrow)
        root.addWidget(flow_panel)

        body = QHBoxLayout()
        body.setSpacing(8)

        settings = Panel()
        settings_layout = QVBoxLayout(settings)
        settings_layout.setContentsMargins(11, 10, 11, 10)
        settings_layout.setSpacing(8)
        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(7)

        self.preset_combo = QComboBox()
        self.preset_combo.currentIndexChanged.connect(self._refresh_summary)
        form.addRow("Workflow:", self.preset_combo)

        self.use_preset_targets = QCheckBox("Use targets saved in preset")
        self.use_preset_targets.setChecked(True)
        self.use_preset_targets.toggled.connect(self._target_mode_changed)
        form.addRow("Targets:", self.use_preset_targets)

        self.account_ids = QLineEdit()
        self.account_ids.setPlaceholderText("account-id-1, account-id-2")
        self.account_ids.setEnabled(False)
        self.account_ids.textChanged.connect(self._refresh_flow)
        form.addRow("Accounts:", self.account_ids)

        self.destination_ids = QLineEdit()
        self.destination_ids.setPlaceholderText("page-id-1, destination-id-2")
        self.destination_ids.setEnabled(False)
        self.destination_ids.textChanged.connect(self._refresh_flow)
        form.addRow("Destinations:", self.destination_ids)

        settings_layout.addLayout(form)
        self.status = StatusChip("Ready", "success")
        settings_layout.addWidget(self.status)

        actions = QHBoxLayout()
        refresh = QPushButton("↻ Refresh")
        refresh.clicked.connect(self.refresh_presets)
        actions.addWidget(refresh)
        actions.addStretch()

        dry_run = SecondaryButton("Dry Run")
        dry_run.setProperty("infoAction", True)
        dry_run.clicked.connect(self._dry_run)
        actions.addWidget(dry_run)

        run = PrimaryButton("▶ Start Workflow")
        run.setProperty("successAction", True)
        run.clicked.connect(self._run)
        actions.addWidget(run)
        settings_layout.addLayout(actions)
        body.addWidget(settings, stretch=3)

        preview = Panel()
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(10, 9, 10, 9)
        preview_layout.setSpacing(6)
        preview_title = QLabel("Selected Actions")
        preview_title.setProperty("sectionTitle", True)
        preview_layout.addWidget(preview_title)
        self.summary = QLabel("Select a preset.")
        self.summary.setProperty("muted", True)
        self.summary.setWordWrap(True)
        preview_layout.addWidget(self.summary)
        self.steps = QListWidget()
        self.steps.setObjectName("quickAutomationSteps")
        preview_layout.addWidget(self.steps, stretch=1)
        body.addWidget(preview, stretch=2)

        root.addLayout(body, stretch=1)
        self._refresh_flow()

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
        return self._service.get_preset(str(preset_id)) if preset_id else None

    @staticmethod
    def _parse_ids(text: str) -> list[str]:
        return [value.strip() for value in text.replace("\n", ",").split(",") if value.strip()]

    def _targets(self) -> tuple[list[str] | None, list[str] | None]:
        if self.use_preset_targets.isChecked():
            return None, None
        return self._parse_ids(self.account_ids.text()), self._parse_ids(
            self.destination_ids.text()
        )

    def _target_mode_changed(self, checked: bool) -> None:
        self.account_ids.setEnabled(not checked)
        self.destination_ids.setEnabled(not checked)
        self._refresh_flow()

    def _refresh_flow(self) -> None:
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
        for button, state in zip(self.flow_buttons, states, strict=True):
            button.set_flow_state(state)

    def _refresh_summary(self) -> None:
        preset = self._selected_preset()
        self.steps.clear()
        if preset is None:
            self.summary.setText("No presets are available.")
            self.status.update_state("warning", "No preset")
            self._refresh_flow()
            return

        enabled = sorted(
            (step for step in preset.steps if step.enabled),
            key=lambda step: step.order,
        )
        approvals = sum(step.requires_approval for step in enabled)
        self.summary.setText(
            f"{preset.description}\n\n{len(enabled)} enabled steps · "
            f"{approvals} approval-gated · max "
            f"{preset.target_rules.max_concurrent_devices} devices."
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
        self._refresh_flow()

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
        self.flow_buttons[2].set_flow_state("done")
        self.flow_buttons[3].set_flow_state("next")
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
            self.flow_buttons[3].set_flow_state("done")
            self.flow_buttons[4].set_flow_state("next")
            QMessageBox.information(
                self,
                "Workflow started",
                f"{message}\n\nCreated jobs: {len(job_ids)}",
            )
        else:
            self.status.update_state("error", "Could not start")
            QMessageBox.warning(self, "Workflow not started", message)
