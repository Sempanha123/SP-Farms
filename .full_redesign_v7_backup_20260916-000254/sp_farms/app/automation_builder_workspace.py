"""Automation Builder workspace: per-function setup, presets, target selection,
and capability-aware workflows.
"""

from __future__ import annotations

import uuid

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sp_farms.application.automation_builder import AutomationBuilderService
from sp_farms.domain.automation_builder import (
    CAPABILITY_MATRIX,
    AutomationPreset,
    AutomationPresetStep,
    AutomationStepType,
    CapabilitySupport,
    DryRunReport,
    TargetSelectionRules,
)


class DryRunDialog(QDialog):
    """Modal dialog displaying pre-flight Dry Run analysis with zero side effects."""

    def __init__(self, report: DryRunReport, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pre-Flight Dry Run Inspection — SP-Farms")
        self.resize(850, 600)
        self._build_ui(report)

    def _build_ui(self, report: DryRunReport) -> None:
        layout = QVBoxLayout(self)

        # Header summary banner
        header = QFrame()
        header.setStyleSheet("background-color: #1e293b; border-radius: 8px; padding: 12px;")
        h_layout = QVBoxLayout(header)

        title = QLabel(f"Simulation Plan for Preset: <b>{report.preset_name}</b>")
        title.setStyleSheet("font-size: 16px; color: #38bdf8;")
        h_layout.addWidget(title)

        stats_row = QHBoxLayout()
        stats_row.addWidget(QLabel(f"Target Accounts: <b>{report.target_accounts_count}</b>"))
        stats_row.addWidget(
            QLabel(f"Target Destinations: <b>{report.target_destinations_count}</b>")
        )
        stats_row.addWidget(QLabel(f"Devices Expected: <b>{report.expected_devices_count}</b>"))
        stats_row.addWidget(QLabel(f"Estimated Jobs: <b>{report.estimated_jobs_count}</b>"))
        h_layout.addLayout(stats_row)

        safe_chip = QLabel("ZERO SIDE EFFECTS GUARANTEE: Read-only simulation pass.")
        safe_chip.setStyleSheet("color: #4ade80; font-weight: bold;")
        h_layout.addWidget(safe_chip)

        layout.addWidget(header)

        if report.warnings:
            warn_box = QFrame()
            warn_box.setStyleSheet("background-color: #451a03; border-radius: 6px; padding: 8px;")
            w_layout = QVBoxLayout(warn_box)
            w_title = QLabel("Pre-Flight Warnings / Capability Notes:")
            w_title.setStyleSheet("color: #fbbf24; font-weight: bold;")
            w_layout.addWidget(w_title)
            for w in report.warnings:
                w_lbl = QLabel(f"• {w}")
                w_lbl.setStyleSheet("color: #fef08a;")
                w_layout.addWidget(w_lbl)
            layout.addWidget(warn_box)

        # Plan table
        table = QTableWidget(len(report.items), 6)
        table.setHorizontalHeaderLabels(
            [
                "Step",
                "Function",
                "Account",
                "Destination",
                "Device",
                "Capability Tier",
            ]
        )
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        for i, item in enumerate(report.items):
            table.setItem(i, 0, QTableWidgetItem(str(item.step_order)))
            table.setItem(i, 1, QTableWidgetItem(item.title))
            table.setItem(i, 2, QTableWidgetItem(item.target_account))
            table.setItem(i, 3, QTableWidgetItem(item.target_destination))
            table.setItem(i, 4, QTableWidgetItem(item.expected_device))
            table.setItem(i, 5, QTableWidgetItem(item.capability_tier.value))

        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class AutomationBuilderWorkspace(QWidget):
    """Full-featured Automation Builder with target selection, function matrix, and presets."""

    run_requested = Signal(str)  # preset_id

    def __init__(
        self,
        builder_service: AutomationBuilderService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = builder_service
        self._current_preset: AutomationPreset | None = None
        self._active_step_type: AutomationStepType = AutomationStepType.PUBLISH_TEXT
        self._config_editors: dict[AutomationStepType, QWidget] = {}
        self._init_ui()
        self._load_presets()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 1. Top Action & Preset Selection Bar
        top_bar = QFrame()
        top_bar.setProperty("panel", True)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(8, 4, 8, 4)

        top_layout.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        self._preset_combo.setMinimumWidth(240)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        top_layout.addWidget(self._preset_combo)

        btn_new = QPushButton("New Preset")
        btn_new.clicked.connect(self._on_new_preset)
        top_layout.addWidget(btn_new)

        btn_save = QPushButton("Save")
        btn_save.clicked.connect(self._on_save_preset)
        top_layout.addWidget(btn_save)

        btn_duplicate = QPushButton("Duplicate")
        btn_duplicate.clicked.connect(self._on_duplicate_preset)
        top_layout.addWidget(btn_duplicate)

        btn_import = QPushButton("Import...")
        btn_import.clicked.connect(self._on_import_preset)
        top_layout.addWidget(btn_import)

        btn_export = QPushButton("Export...")
        btn_export.clicked.connect(self._on_export_preset)
        top_layout.addWidget(btn_export)

        top_layout.addStretch()

        btn_validate = QPushButton("Validate")
        btn_validate.clicked.connect(self._on_validate_preset)
        top_layout.addWidget(btn_validate)

        btn_dry_run = QPushButton("Dry Run (Simulate)")
        btn_dry_run.setProperty("infoAction", True)
        btn_dry_run.clicked.connect(self._on_dry_run)
        top_layout.addWidget(btn_dry_run)

        btn_run = QPushButton("Run Workflow")
        btn_run.setProperty("successAction", True)
        btn_run.clicked.connect(self._on_run_workflow)
        top_layout.addWidget(btn_run)

        main_layout.addWidget(top_bar)

        # 2. Main 3-Column Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # LEFT: Target Selection Rules
        left_panel = self._create_targets_panel()
        splitter.addWidget(left_panel)

        # CENTER: Function Checklist & Reordering
        center_panel = self._create_functions_panel()
        splitter.addWidget(center_panel)

        # RIGHT: Dynamic Function Setup View
        right_panel = self._create_setup_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([260, 380, 480])
        main_layout.addWidget(splitter, stretch=1)

        # 3. Bottom Summary Status Bar
        bottom_bar = QFrame()
        bottom_bar.setProperty("softPanel", True)
        bot_layout = QHBoxLayout(bottom_bar)
        self._lbl_status = QLabel("Ready. Select or build a workflow preset.")
        self._lbl_status.setProperty("muted", True)
        bot_layout.addWidget(self._lbl_status)
        bot_layout.addStretch()

        self._lbl_metrics = QLabel(
            "Accounts: 0 | Devices: 0 | Destinations: 0 | Enabled Functions: 0"
        )
        self._lbl_metrics.setStyleSheet("color: #38bdf8; font-weight: bold;")
        bot_layout.addWidget(self._lbl_metrics)

        main_layout.addWidget(bottom_bar)

    def _create_targets_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        c_layout = QVBoxLayout(content)

        # Account targets
        acc_grp = QGroupBox("Target Accounts")
        acc_lay = QVBoxLayout(acc_grp)
        self._chk_healthy_only = QCheckBox("Only Healthy Accounts (Score > 70)")
        self._chk_healthy_only.setChecked(True)
        acc_lay.addWidget(self._chk_healthy_only)

        self._chk_device_bound_only = QCheckBox("Only Accounts With Assigned Device")
        acc_lay.addWidget(self._chk_device_bound_only)

        self._chk_valid_auth_only = QCheckBox("Only Valid Auth State (No Expirations)")
        self._chk_valid_auth_only.setChecked(True)
        acc_lay.addWidget(self._chk_valid_auth_only)

        acc_lay.addWidget(QLabel("Account Category:"))
        self._txt_acc_category = QLineEdit()
        self._txt_acc_category.setPlaceholderText("All categories")
        acc_lay.addWidget(self._txt_acc_category)
        c_layout.addWidget(acc_grp)

        # Device allocation
        dev_grp = QGroupBox("Device Allocation Policy")
        dev_lay = QVBoxLayout(dev_grp)
        dev_lay.addWidget(QLabel("Device Policy:"))
        self._cmb_device_policy = QComboBox()
        self._cmb_device_policy.addItems(
            [
                "Bound Device First",
                "Any Available Device",
                "Least Recently Used",
                "Preferred Provider Order",
            ]
        )
        dev_lay.addWidget(self._cmb_device_policy)

        dev_lay.addWidget(QLabel("Provider Order:"))
        self._cmb_provider = QComboBox()
        self._cmb_provider.addItems(
            [
                "LDPlayer -> MuMu -> Physical",
                "Physical -> LDPlayer -> MuMu",
                "LDPlayer Only",
                "MuMu Only",
                "Physical Only",
            ]
        )
        dev_lay.addWidget(self._cmb_provider)

        dev_lay.addWidget(QLabel("Max Concurrent Devices:"))
        self._spn_concurrent_dev = QSpinBox()
        self._spn_concurrent_dev.setRange(1, 32)
        self._spn_concurrent_dev.setValue(4)
        dev_lay.addWidget(self._spn_concurrent_dev)

        self._chk_stop_device = QCheckBox("Stop Device After Workflow Release")
        dev_lay.addWidget(self._chk_stop_device)
        c_layout.addWidget(dev_grp)

        # Destinations
        dest_grp = QGroupBox("Target Destinations")
        dest_lay = QVBoxLayout(dest_grp)
        self._chk_dest_pages = QCheckBox("Authorized Facebook Pages")
        self._chk_dest_pages.setChecked(True)
        dest_lay.addWidget(self._chk_dest_pages)

        self._chk_dest_groups = QCheckBox("Authorized Facebook Groups")
        dest_lay.addWidget(self._chk_dest_groups)

        self._chk_dest_permissions = QCheckBox("Require Full Post Publishing Permissions")
        self._chk_dest_permissions.setChecked(True)
        dest_lay.addWidget(self._chk_dest_permissions)
        c_layout.addWidget(dest_grp)

        c_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        return container

    def _create_functions_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)

        header = QLabel("Workflow Functions (Check to Enable, Configure on Right)")
        header.setProperty("sectionTitle", True)
        layout.addWidget(header)

        self._functions_list = QListWidget()
        self._functions_list.currentItemChanged.connect(self._on_function_selected)
        layout.addWidget(self._functions_list, stretch=1)

        # Populate all 24 functions from CAPABILITY_MATRIX
        self._step_checkboxes: dict[AutomationStepType, QCheckBox] = {}
        for st, cap in CAPABILITY_MATRIX.items():
            item = QListWidgetItem()
            widget = QWidget()
            w_lay = QHBoxLayout(widget)
            w_lay.setContentsMargins(4, 2, 4, 2)

            chk = QCheckBox(cap.title)
            chk.setChecked(False)
            chk.toggled.connect(self._update_metrics)
            self._step_checkboxes[st] = chk
            w_lay.addWidget(chk, stretch=1)

            # Capability badge
            badge = QLabel(cap.support_tier.value)
            badge.setStyleSheet(self._get_badge_style(cap.support_tier))
            w_lay.addWidget(badge)

            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, st)
            self._functions_list.addItem(item)
            self._functions_list.setItemWidget(item, widget)

        return container

    def _get_badge_style(self, tier: CapabilitySupport) -> str:
        if tier == CapabilitySupport.OFFICIALLY_SUPPORTED:
            return (
                "background-color: #064e3b; color: #6ee7b7; border-radius: 4px; "
                "padding: 2px 6px; font-size: 10px;"
            )
        if tier == CapabilitySupport.REQUIRES_OPERATOR_APPROVAL:
            return (
                "background-color: #713f12; color: #fde047; border-radius: 4px; "
                "padding: 2px 6px; font-size: 10px;"
            )
        if tier == CapabilitySupport.READ_ONLY_ANALYTICS:
            return (
                "background-color: #1e3a8a; color: #93c5fd; border-radius: 4px; "
                "padding: 2px 6px; font-size: 10px;"
            )
        return (
            "background-color: #4c1d95; color: #d8b4fe; border-radius: 4px; "
            "padding: 2px 6px; font-size: 10px;"
        )

    def _create_setup_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)

        self._setup_title = QLabel("Function Configuration")
        self._setup_title.setProperty("sectionTitle", True)
        layout.addWidget(self._setup_title)

        self._setup_stack = QStackedWidget()

        # Build individual configuration editors
        for st in CAPABILITY_MATRIX:
            editor = self._build_config_editor_for_step(st)
            self._config_editors[st] = editor
            self._setup_stack.addWidget(editor)

        layout.addWidget(self._setup_stack, stretch=1)
        return container

    def _build_config_editor_for_step(self, step_type: AutomationStepType) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        form.setContentsMargins(8, 8, 8, 8)

        cap = CAPABILITY_MATRIX[step_type]
        desc_lbl = QLabel(f"<b>Overview:</b> {cap.description}")
        desc_lbl.setWordWrap(True)
        form.addRow(desc_lbl)

        # Specific custom configuration widgets
        if step_type == AutomationStepType.PUBLISH_TEXT:
            txt_caption = QTextEdit()
            txt_caption.setPlaceholderText("Enter caption text...")
            form.addRow("Caption Text:", txt_caption)
            chk_approval = QCheckBox("Require Operator Approval Before Publishing")
            chk_approval.setChecked(True)
            form.addRow("Approval:", chk_approval)

        elif step_type in (
            AutomationStepType.PUBLISH_IMAGE,
            AutomationStepType.PUBLISH_MULTI_IMAGE,
        ):
            txt_pool = QLineEdit()
            txt_pool.setPlaceholderText("Media tag pool (e.g. approved_morning_posts)")
            form.addRow("Media Pool Tag:", txt_pool)
            txt_img_caption = QTextEdit()
            txt_img_caption.setPlaceholderText("Caption or template...")
            form.addRow("Caption:", txt_img_caption)
            chk_approval = QCheckBox("Require Approval")
            chk_approval.setChecked(True)
            form.addRow("Approval:", chk_approval)

        elif step_type in (AutomationStepType.PUBLISH_VIDEO, AutomationStepType.PUBLISH_REEL):
            txt_video = QLineEdit()
            txt_video.setPlaceholderText("Select video file or tag...")
            form.addRow("Video Source:", txt_video)
            txt_v_caption = QTextEdit()
            form.addRow("Caption:", txt_v_caption)
            if step_type == AutomationStepType.PUBLISH_REEL:
                aspect_lbl = QLabel("Aspect ratio: 9:16 vertical (enforced for Reels)")
                aspect_lbl.setStyleSheet("color: #38bdf8;")
                form.addRow("Format:", aspect_lbl)

        elif step_type == AutomationStepType.PUBLISH_STORY:
            note = QLabel(
                "NOTE: Ephemeral stories are capability-gated. "
                "Only available on Pages with official Meta Graph API Story publishing enabled."
            )
            note.setStyleSheet("color: #fbbf24; font-weight: bold;")
            note.setWordWrap(True)
            form.addRow("Capability Gate:", note)

        elif step_type in (
            AutomationStepType.READ_COMMENTS,
            AutomationStepType.REPLY_COMMENTS,
            AutomationStepType.MODERATE_COMMENTS,
        ):
            spn_limit = QSpinBox()
            spn_limit.setRange(5, 50)
            spn_limit.setValue(10)
            form.addRow("Max Comments to Process:", spn_limit)
            if step_type == AutomationStepType.REPLY_COMMENTS:
                txt_reply = QTextEdit()
                txt_reply.setPlaceholderText("Canned reply or AI prompt template...")
                form.addRow("Reply Template:", txt_reply)
                chk_reply_app = QCheckBox("Require Human Approval for each reply")
                chk_reply_app.setChecked(True)
                form.addRow("Policy:", chk_reply_app)

        elif step_type in (AutomationStepType.READ_INBOX, AutomationStepType.REPLY_INBOX):
            spn_inbox = QSpinBox()
            spn_inbox.setRange(1, 20)
            spn_inbox.setValue(5)
            form.addRow("Max Inquiries per run:", spn_inbox)
            if step_type == AutomationStepType.REPLY_INBOX:
                txt_saved = QTextEdit()
                txt_saved.setPlaceholderText("Saved canned reply text...")
                form.addRow("Saved Reply:", txt_saved)

        elif step_type == AutomationStepType.COLLECT_REACTION_ANALYTICS:
            lbl_analytics_only = QLabel(
                "READ-ONLY REACTION ANALYTICS:\n"
                "Collects breakdown of Like, Love, Care, Haha, Wow, Sad, and Angry reactions.\n"
                "Zero automated engagement or reaction generation is permitted."
            )
            lbl_analytics_only.setStyleSheet("color: #38bdf8; font-weight: bold;")
            lbl_analytics_only.setWordWrap(True)
            form.addRow("Safety Boundary:", lbl_analytics_only)

        elif step_type == AutomationStepType.COLLECT_FOLLOWER_ANALYTICS:
            lbl_follower = QLabel(
                "READ-ONLY FOLLOWER METRICS:\n"
                "Fetches organic follower growth curves and Page likes.\n"
                "Automated mass following/unfollowing is strictly prohibited."
            )
            lbl_follower.setStyleSheet("color: #38bdf8; font-weight: bold;")
            lbl_follower.setWordWrap(True)
            form.addRow("Safety Boundary:", lbl_follower)

        return widget

    def _on_function_selected(
        self, current: QListWidgetItem, previous: QListWidgetItem | None
    ) -> None:
        if not current:
            return
        st: AutomationStepType = current.data(Qt.ItemDataRole.UserRole)
        self._active_step_type = st
        cap = CAPABILITY_MATRIX[st]
        self._setup_title.setText(f"Setup: {cap.title}")
        editor = self._config_editors.get(st)
        if editor:
            self._setup_stack.setCurrentWidget(editor)

    def _load_presets(self) -> None:
        self._preset_combo.blockSignals(True)
        self._preset_combo.clear()
        presets = self._service.list_presets()
        for p in presets:
            prefix = "[Built-in] " if p.is_built_in else ""
            self._preset_combo.addItem(f"{prefix}{p.name}", p.id)
        self._preset_combo.blockSignals(False)

        if presets:
            self._preset_combo.setCurrentIndex(0)
            self._apply_preset(presets[0])

    def _on_preset_selected(self, index: int) -> None:
        preset_id = self._preset_combo.currentData()
        if not preset_id:
            return
        preset = self._service.get_preset(preset_id)
        if preset:
            self._apply_preset(preset)

    def _apply_preset(self, preset: AutomationPreset) -> None:
        self._current_preset = preset

        # Apply target rules
        r = preset.target_rules
        self._chk_healthy_only.setChecked(r.only_healthy_accounts)
        self._chk_device_bound_only.setChecked(r.only_accounts_with_device)
        self._chk_valid_auth_only.setChecked(r.only_valid_auth)
        self._txt_acc_category.setText(r.account_category or "")
        self._spn_concurrent_dev.setValue(r.max_concurrent_devices)
        self._chk_stop_device.setChecked(r.stop_device_after_release)

        # Reset all checkboxes
        for chk in self._step_checkboxes.values():
            chk.setChecked(False)

        # Enable steps in preset
        for s in preset.steps:
            if s.enabled and s.step_type in self._step_checkboxes:
                self._step_checkboxes[s.step_type].setChecked(True)

        self._lbl_status.setText(
            f"Loaded preset '{preset.name}' ({len(preset.steps)} configured steps)."
        )
        self._update_metrics()

    def _update_metrics(self) -> None:
        enabled_count = sum(1 for chk in self._step_checkboxes.values() if chk.isChecked())
        self._lbl_metrics.setText(
            f"Target Mode: Filtered | Concurrent Devices: {self._spn_concurrent_dev.value()} | "
            f"Enabled Functions: {enabled_count} of 24"
        )

    def _on_new_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "New Preset", "Enter preset name:")
        if not ok or not name:
            return
        new_p = self._service.create_preset(name=name, description="Custom automation workflow")
        self._load_presets()
        for idx in range(self._preset_combo.count()):
            if self._preset_combo.itemData(idx) == new_p.id:
                self._preset_combo.setCurrentIndex(idx)
                break

    def _on_save_preset(self) -> None:
        if not self._current_preset:
            return
        if self._current_preset.is_built_in:
            QMessageBox.information(
                self,
                "Built-in Preset",
                "Built-in presets are protected templates. "
                "Use 'Duplicate' to save customized modifications.",
            )
            return

        # Collect enabled steps
        steps: list[AutomationPresetStep] = []
        order = 1
        for st, chk in self._step_checkboxes.items():
            if chk.isChecked():
                steps.append(
                    AutomationPresetStep(
                        id=str(uuid.uuid4()),
                        preset_id=self._current_preset.id,
                        step_type=st,
                        enabled=True,
                        order=order,
                        configuration={},
                    )
                )
                order += 1

        updated = AutomationPreset(
            id=self._current_preset.id,
            name=self._current_preset.name,
            description=self._current_preset.description,
            target_rules=TargetSelectionRules(
                only_healthy_accounts=self._chk_healthy_only.isChecked(),
                only_accounts_with_device=self._chk_device_bound_only.isChecked(),
                only_valid_auth=self._chk_valid_auth_only.isChecked(),
                account_category=self._txt_acc_category.text() or None,
                max_concurrent_devices=self._spn_concurrent_dev.value(),
                stop_device_after_release=self._chk_stop_device.isChecked(),
            ),
            steps=tuple(steps),
            tags=self._current_preset.tags,
            is_built_in=False,
            version=self._current_preset.version + 1,
        )
        self._service.update_preset(updated)
        self._current_preset = updated
        self._lbl_status.setText(f"Saved preset '{updated.name}' successfully.")

    def _on_duplicate_preset(self) -> None:
        if not self._current_preset:
            return
        new_name = f"{self._current_preset.name} (Copy)"
        dup = self._service.duplicate_preset(self._current_preset.id, new_name)
        if dup:
            self._load_presets()
            for idx in range(self._preset_combo.count()):
                if self._preset_combo.itemData(idx) == dup.id:
                    self._preset_combo.setCurrentIndex(idx)
                    break

    def _on_import_preset(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Preset", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
            imported = self._service.import_preset_json(content)
            self._load_presets()
            QMessageBox.information(
                self, "Preset Imported", f"Preset '{imported.name}' imported successfully."
            )
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"Failed to import preset: {e}")

    def _on_export_preset(self) -> None:
        if not self._current_preset:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Preset",
            f"{self._current_preset.name.lower().replace(' ', '_')}.json",
            "JSON Files (*.json)",
        )
        if not path:
            return
        try:
            doc = self._service.export_preset_json(self._current_preset.id)
            with open(path, "w", encoding="utf-8") as f:
                f.write(doc)
            QMessageBox.information(self, "Preset Exported", f"Preset exported to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export preset: {e}")

    def _on_validate_preset(self) -> None:
        if not self._current_preset:
            return
        errors = self._service.validate_preset(self._current_preset)
        if errors:
            QMessageBox.warning(self, "Preset Validation", "\n".join(errors))
        else:
            QMessageBox.information(
                self, "Preset Validation", "Preset passed all safety and capability validations!"
            )

    def _on_dry_run(self) -> None:
        if not self._current_preset:
            return
        report = self._service.generate_dry_run_report(self._current_preset)
        dialog = DryRunDialog(report, self)
        dialog.exec()

    def _on_run_workflow(self) -> None:
        if not self._current_preset:
            return
        confirm = QMessageBox.question(
            self,
            "Run Workflow",
            f"Execute workflow '{self._current_preset.name}' now?\n"
            "Tasks will be queued in the execution engine.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            success, msg, _ = self._service.execute_preset(self._current_preset)
            if success:
                self._lbl_status.setText(msg)
                self.run_requested.emit(self._current_preset.id)
            else:
                QMessageBox.warning(self, "Execution Blocked", msg)
