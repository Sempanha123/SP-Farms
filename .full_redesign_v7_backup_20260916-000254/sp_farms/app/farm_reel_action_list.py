from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.automation_builder_workspace import DryRunDialog
from sp_farms.app.widgets import Panel, PrimaryButton, SecondaryButton, StatusChip
from sp_farms.application.automation_builder import AutomationBuilderService
from sp_farms.domain.automation_builder import (
    CAPABILITY_MATRIX,
    AutomationPreset,
    AutomationPresetStep,
    AutomationStepType,
    CapabilitySupport,
    TargetSelectionRules,
)

# Farm-Reel-like grouping, backed only by SP-Farms' existing authorized step types.
ACTION_GROUPS: tuple[tuple[str, tuple[AutomationStepType, ...]], ...] = (
    (
        "Workspace",
        (
            AutomationStepType.RESTORE_WORKSPACE,
            AutomationStepType.OPEN_PREFERRED_APP,
            AutomationStepType.HEALTH_CHECK,
            AutomationStepType.REFRESH_ASSETS,
        ),
    ),
    (
        "Content",
        (
            AutomationStepType.PUBLISH_TEXT,
            AutomationStepType.PUBLISH_IMAGE,
            AutomationStepType.PUBLISH_MULTI_IMAGE,
            AutomationStepType.PUBLISH_VIDEO,
            AutomationStepType.PUBLISH_REEL,
            AutomationStepType.PUBLISH_STORY,
            AutomationStepType.PUBLISH_LINK,
            AutomationStepType.SCHEDULE_CONTENT,
        ),
    ),
    (
        "Comments & Inbox",
        (
            AutomationStepType.READ_COMMENTS,
            AutomationStepType.REPLY_COMMENTS,
            AutomationStepType.MODERATE_COMMENTS,
            AutomationStepType.READ_INBOX,
            AutomationStepType.REPLY_INBOX,
            AutomationStepType.ASSIGN_INBOX,
            AutomationStepType.ADD_INTERNAL_NOTE,
            AutomationStepType.MARK_RESOLVED,
        ),
    ),
    (
        "Analytics",
        (
            AutomationStepType.COLLECT_POST_ANALYTICS,
            AutomationStepType.COLLECT_REACTION_ANALYTICS,
            AutomationStepType.COLLECT_SHARE_VIEW_ANALYTICS,
            AutomationStepType.COLLECT_FOLLOWER_ANALYTICS,
        ),
    ),
    (
        "Device Queue",
        (
            AutomationStepType.BACKUP_WORKSPACE,
            AutomationStepType.RELEASE_DEVICE,
            AutomationStepType.START_NEXT_ACCOUNT,
        ),
    ),
)


class ActionConfigEditor(Panel):
    """Configuration editor for one real AutomationStepType."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._step_type: AutomationStepType | None = None
        self._configs: dict[AutomationStepType, dict[str, Any]] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 9, 10, 9)
        root.setSpacing(7)

        self.title = QLabel("Select an action")
        self.title.setProperty("heading", True)
        root.addWidget(self.title)

        self.description = QLabel(
            "Select a checked action to configure its content, approval, retry, and timeout."
        )
        self.description.setProperty("muted", True)
        self.description.setWordWrap(True)
        root.addWidget(self.description)

        self.capability = StatusChip("No action", "neutral")
        root.addWidget(self.capability)

        self.dynamic = QStackedWidget()
        root.addWidget(self.dynamic, stretch=1)

        self.empty_page = QWidget()
        empty_layout = QVBoxLayout(self.empty_page)
        empty_layout.addStretch()
        empty = QLabel("Action settings appear here.")
        empty.setProperty("muted", True)
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty)
        empty_layout.addStretch()
        self.dynamic.addWidget(self.empty_page)

        self.form_page = QWidget()
        self.form_layout = QFormLayout(self.form_page)
        self.form_layout.setContentsMargins(0, 4, 0, 4)
        self.form_layout.setHorizontalSpacing(10)
        self.form_layout.setVerticalSpacing(7)
        self.dynamic.addWidget(self.form_page)

        self._field_widgets: dict[str, QWidget] = {}

        common = Panel()
        common_layout = QFormLayout(common)
        common_layout.setContentsMargins(8, 7, 8, 7)
        common_layout.setVerticalSpacing(6)

        self.approval = QCheckBox("Require operator approval before execution")
        self.approval.toggled.connect(self.changed.emit)
        common_layout.addRow("Approval:", self.approval)

        self.retry = QComboBox()
        self.retry.addItem("No retry", "no_retry")
        self.retry.addItem("Retry once", "once")
        self.retry.addItem("Retry up to 3", "up_to_3")
        self.retry.currentIndexChanged.connect(self.changed.emit)
        common_layout.addRow("Retry:", self.retry)

        self.timeout = QSpinBox()
        self.timeout.setRange(10, 3600)
        self.timeout.setValue(120)
        self.timeout.setSuffix(" sec")
        self.timeout.valueChanged.connect(self.changed.emit)
        common_layout.addRow("Timeout:", self.timeout)

        self.delay = QSpinBox()
        self.delay.setRange(0, 3600)
        self.delay.setValue(0)
        self.delay.setSuffix(" sec")
        self.delay.setToolTip(
            "Stored in the step configuration and applied by workers that "
            "support delayed execution."
        )
        self.delay.valueChanged.connect(self.changed.emit)
        common_layout.addRow("Delay:", self.delay)

        self.continue_on_error = QCheckBox("Continue workflow if this step fails")
        self.continue_on_error.toggled.connect(self.changed.emit)
        common_layout.addRow("On failure:", self.continue_on_error)

        root.addWidget(common)

    def _clear_form(self) -> None:
        while self.form_layout.rowCount():
            self.form_layout.removeRow(0)
        self._field_widgets.clear()

    def _add_line(
        self,
        key: str,
        label: str,
        placeholder: str = "",
        value: str = "",
    ) -> QLineEdit:
        widget = QLineEdit(value)
        widget.setPlaceholderText(placeholder)
        widget.textChanged.connect(self._save_current)
        self.form_layout.addRow(label, widget)
        self._field_widgets[key] = widget
        return widget

    def _add_text(
        self,
        key: str,
        label: str,
        placeholder: str = "",
        value: str = "",
        height: int = 100,
    ) -> QTextEdit:
        widget = QTextEdit()
        widget.setPlaceholderText(placeholder)
        widget.setPlainText(value)
        widget.setMinimumHeight(height)
        widget.textChanged.connect(self._save_current)
        self.form_layout.addRow(label, widget)
        self._field_widgets[key] = widget
        return widget

    def _add_check(self, key: str, label: str, checked: bool = False) -> QCheckBox:
        widget = QCheckBox()
        widget.setChecked(checked)
        widget.toggled.connect(self._save_current)
        self.form_layout.addRow(label, widget)
        self._field_widgets[key] = widget
        return widget

    def _add_spin(
        self,
        key: str,
        label: str,
        value: int,
        minimum: int,
        maximum: int,
    ) -> QSpinBox:
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        widget.setValue(value)
        widget.valueChanged.connect(self._save_current)
        self.form_layout.addRow(label, widget)
        self._field_widgets[key] = widget
        return widget

    def _value(self, key: str, default: Any = None) -> Any:
        return self._configs.get(self._step_type, {}).get(key, default)

    def set_step(self, step_type: AutomationStepType | None) -> None:
        self._save_current()
        self._step_type = step_type
        self._clear_form()

        if step_type is None:
            self.title.setText("Select an action")
            self.description.setText(
                "Select a checked action to configure its content, approval, retry, and timeout."
            )
            self.capability.update_state("neutral", "No action")
            self.dynamic.setCurrentWidget(self.empty_page)
            return

        info = CAPABILITY_MATRIX[step_type]
        self.title.setText(info.title)
        self.description.setText(info.description)

        if info.support_tier is CapabilitySupport.OFFICIALLY_SUPPORTED:
            tone, label = "success", "Supported"
        elif info.support_tier is CapabilitySupport.REQUIRES_OPERATOR_APPROVAL:
            tone, label = "warning", "Approval required"
        elif info.support_tier is CapabilitySupport.READ_ONLY_ANALYTICS:
            tone, label = "active", "Read-only"
        else:
            tone, label = "warning", "Capability gated"
        self.capability.update_state(tone, label)

        cfg = self._configs.setdefault(step_type, {})
        self.dynamic.setCurrentWidget(self.form_page)

        if step_type is AutomationStepType.RESTORE_WORKSPACE:
            self._add_check(
                "launch_app",
                "Launch preferred app:",
                bool(cfg.get("launch_app", True)),
            )
            self._add_check(
                "allow_fallback_device",
                "Allow fallback device:",
                bool(cfg.get("allow_fallback_device", True)),
            )
            self._add_check(
                "require_network",
                "Require stored network:",
                bool(cfg.get("require_network", True)),
            )

        elif step_type is AutomationStepType.OPEN_PREFERRED_APP:
            self._add_line(
                "preferred_app",
                "Preferred app:",
                "facebook / facebook_lite / business_suite / browser",
                str(cfg.get("preferred_app", "")),
            )

        elif step_type is AutomationStepType.PUBLISH_TEXT:
            self._add_text(
                "text",
                "Post text:",
                "Write the authorized Page/Group post text...",
                str(cfg.get("text", "")),
                130,
            )
            self._add_line(
                "caption_template_id",
                "Template ID:",
                "Optional saved caption template ID",
                str(cfg.get("caption_template_id", "")),
            )

        elif step_type in (
            AutomationStepType.PUBLISH_IMAGE,
            AutomationStepType.PUBLISH_MULTI_IMAGE,
        ):
            self._add_text(
                "media_paths",
                "Media paths:",
                "One local path per line",
                "\n".join(cfg.get("media_paths", [])),
                90,
            )
            self._add_line(
                "media_pool_tag",
                "Media pool tag:",
                "Optional content-library tag",
                str(cfg.get("media_pool_tag", "")),
            )
            self._add_text(
                "caption",
                "Caption:",
                "Post caption...",
                str(cfg.get("caption", "")),
                90,
            )

        elif step_type in (
            AutomationStepType.PUBLISH_VIDEO,
            AutomationStepType.PUBLISH_REEL,
        ):
            self._add_line(
                "video_path",
                "Video:",
                "Local .mp4 path",
                str(cfg.get("video_path", "")),
            )
            self._add_line(
                "media_pool_tag",
                "Media pool tag:",
                "Optional content-library tag",
                str(cfg.get("media_pool_tag", "")),
            )
            self._add_text(
                "caption",
                "Caption:",
                "Video/Reel caption...",
                str(cfg.get("caption", "")),
                90,
            )
            if step_type is AutomationStepType.PUBLISH_REEL:
                self._add_line(
                    "aspect_ratio",
                    "Aspect ratio:",
                    "9:16",
                    str(cfg.get("aspect_ratio", "9:16")),
                )

        elif step_type is AutomationStepType.PUBLISH_STORY:
            self._add_line(
                "media_path",
                "Story media:",
                "Image or video path",
                str(cfg.get("media_path", "")),
            )
            self._add_text(
                "caption",
                "Caption:",
                "Optional story caption",
                str(cfg.get("caption", "")),
                70,
            )

        elif step_type is AutomationStepType.PUBLISH_LINK:
            self._add_line(
                "url",
                "Link:",
                "https://...",
                str(cfg.get("url", "")),
            )
            self._add_text(
                "text",
                "Caption:",
                "Link post text...",
                str(cfg.get("text", "")),
                80,
            )

        elif step_type is AutomationStepType.SCHEDULE_CONTENT:
            self._add_line(
                "schedule_at",
                "Schedule at:",
                "YYYY-MM-DD HH:MM",
                str(cfg.get("schedule_at", "")),
            )
            self._add_line(
                "timezone",
                "Timezone:",
                "e.g. Asia/Phnom_Penh",
                str(cfg.get("timezone", "")),
            )

        elif step_type is AutomationStepType.REPLY_COMMENTS:
            self._add_text(
                "reply_template",
                "Reply template:",
                "Operator-approved reply template...",
                str(cfg.get("reply_template", "")),
                90,
            )
            self._add_check(
                "use_ai_suggestion",
                "AI suggestion:",
                bool(cfg.get("use_ai_suggestion", False)),
            )
            self._add_spin(
                "max_replies_per_run",
                "Max selected replies:",
                int(cfg.get("max_replies_per_run", 5)),
                1,
                50,
            )

        elif step_type is AutomationStepType.MODERATE_COMMENTS:
            self._add_line(
                "rule",
                "Moderation rule:",
                "spam / profanity / configured rule",
                str(cfg.get("rule", "spam")),
            )

        elif step_type is AutomationStepType.REPLY_INBOX:
            self._add_text(
                "saved_reply",
                "Saved reply:",
                "Operator-approved customer reply...",
                str(cfg.get("saved_reply", "")),
                90,
            )
            self._add_check(
                "use_ai_suggestion",
                "AI suggestion:",
                bool(cfg.get("use_ai_suggestion", False)),
            )
            self._add_spin(
                "max_replies_per_run",
                "Max selected replies:",
                int(cfg.get("max_replies_per_run", 5)),
                1,
                25,
            )

        elif step_type is AutomationStepType.ASSIGN_INBOX:
            self._add_line(
                "assignee",
                "Assign to:",
                "Operator / queue",
                str(cfg.get("assignee", "")),
            )

        elif step_type is AutomationStepType.ADD_INTERNAL_NOTE:
            self._add_text(
                "note",
                "Internal note:",
                "Internal-only note...",
                str(cfg.get("note", "")),
                80,
            )

        elif step_type is AutomationStepType.MARK_RESOLVED:
            self._add_line(
                "resolution_note",
                "Resolution note:",
                "Optional internal note",
                str(cfg.get("resolution_note", "")),
            )

        elif step_type in (
            AutomationStepType.COLLECT_POST_ANALYTICS,
            AutomationStepType.COLLECT_REACTION_ANALYTICS,
            AutomationStepType.COLLECT_SHARE_VIEW_ANALYTICS,
            AutomationStepType.COLLECT_FOLLOWER_ANALYTICS,
        ):
            self._add_spin(
                "range_days",
                "Date range:",
                int(cfg.get("range_days", 7)),
                1,
                90,
            )

        elif step_type is AutomationStepType.BACKUP_WORKSPACE:
            self._add_line(
                "notes",
                "Snapshot notes:",
                "Optional backup label / note",
                str(cfg.get("notes", "")),
            )

        elif step_type is AutomationStepType.HEALTH_CHECK:
            self._add_check(
                "include_device",
                "Include device:",
                bool(cfg.get("include_device", True)),
            )
            self._add_check(
                "include_auth",
                "Include auth:",
                bool(cfg.get("include_auth", True)),
            )

        elif step_type is AutomationStepType.REFRESH_ASSETS:
            self._add_check("pages", "Refresh Pages:", bool(cfg.get("pages", True)))
            self._add_check(
                "groups",
                "Refresh authorized Groups:",
                bool(cfg.get("groups", True)),
            )

        else:
            note = QLabel("This action uses its existing service defaults.")
            note.setProperty("muted", True)
            note.setWordWrap(True)
            self.form_layout.addRow("", note)

        self.approval.setChecked(bool(cfg.get("_requires_approval", False)))
        self.retry.setCurrentIndex(
            max(
                0,
                self.retry.findData(str(cfg.get("_retry_policy", "no_retry"))),
            )
        )
        self.timeout.setValue(int(cfg.get("_timeout_seconds", 120)))
        self.delay.setValue(int(cfg.get("delay_seconds", 0)))
        self.continue_on_error.setChecked(bool(cfg.get("_continue_on_error", False)))

    def _save_current(self) -> None:
        step_type = self._step_type
        if step_type is None:
            return
        cfg = self._configs.setdefault(step_type, {})

        for key, widget in self._field_widgets.items():
            if isinstance(widget, QLineEdit):
                value: Any = widget.text().strip()
                if key == "media_paths":
                    value = [p.strip() for p in widget.text().splitlines() if p.strip()]
            elif isinstance(widget, QTextEdit):
                if key == "media_paths":
                    value = [p.strip() for p in widget.toPlainText().splitlines() if p.strip()]
                else:
                    value = widget.toPlainText().strip()
            elif isinstance(widget, QCheckBox):
                value = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                value = widget.value()
            else:
                continue
            cfg[key] = value

        cfg["_requires_approval"] = self.approval.isChecked()
        cfg["_retry_policy"] = self.retry.currentData()
        cfg["_timeout_seconds"] = self.timeout.value()
        cfg["delay_seconds"] = self.delay.value()
        cfg["_continue_on_error"] = self.continue_on_error.isChecked()
        self.changed.emit()

    def step_config(self, step_type: AutomationStepType) -> dict[str, Any]:
        if self._step_type is step_type:
            self._save_current()
        return dict(self._configs.get(step_type, {}))

    def common_settings(self, step_type: AutomationStepType) -> tuple[bool, str, int, bool]:
        cfg = self.step_config(step_type)
        info = CAPABILITY_MATRIX[step_type]
        requires_approval = bool(cfg.pop("_requires_approval", False))
        if info.support_tier is CapabilitySupport.REQUIRES_OPERATOR_APPROVAL:
            requires_approval = True
        return (
            requires_approval,
            str(cfg.pop("_retry_policy", "no_retry")),
            int(cfg.pop("_timeout_seconds", 120)),
            bool(cfg.pop("_continue_on_error", False)),
        )


class FarmReelActionListWorkspace(QWidget):
    """Farm-Reel-style action selection backed by the existing AutomationBuilderService."""

    queue_requested = Signal()
    accounts_requested = Signal()

    def __init__(
        self,
        service: AutomationBuilderService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._selected_steps: list[AutomationStepType] = []
        self._tree_items: dict[AutomationStepType, QTreeWidgetItem] = {}
        self._building_tree = False
        self.setObjectName("farmReelActionListWorkspace")
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(9, 8, 9, 8)
        root.setSpacing(7)

        header = QHBoxLayout()
        title_stack = QVBoxLayout()
        title_stack.setSpacing(0)
        title = QLabel("Action List")
        title.setProperty("heading", True)
        title_stack.addWidget(title)
        subtitle = QLabel(
            "Farm-Reel-style selection, using SP-Farms' existing authorized workflow engine."
        )
        subtitle.setProperty("muted", True)
        title_stack.addWidget(subtitle)
        header.addLayout(title_stack)
        header.addStretch()
        self.status = StatusChip("0 actions selected", "neutral")
        header.addWidget(self.status)
        root.addLayout(header)

        target_panel = Panel()
        target_layout = QGridLayout(target_panel)
        target_layout.setContentsMargins(9, 7, 9, 7)
        target_layout.setHorizontalSpacing(8)
        target_layout.setVerticalSpacing(6)

        self.account_ids = QLineEdit()
        self.account_ids.setPlaceholderText("Account IDs, comma separated")
        self.destination_ids = QLineEdit()
        self.destination_ids.setPlaceholderText("Authorized Page / Group IDs, comma separated")
        self.device_policy = QComboBox()
        self.device_policy.addItem("Bound device first", "bound_first")
        self.device_policy.addItem("Any available device", "any_available")
        self.device_policy.addItem("Preferred provider order", "preferred_order")
        self.concurrency = QSpinBox()
        self.concurrency.setRange(1, 32)
        self.concurrency.setValue(4)

        target_layout.addWidget(QLabel("Accounts"), 0, 0)
        target_layout.addWidget(self.account_ids, 0, 1)
        target_layout.addWidget(QLabel("Destinations"), 0, 2)
        target_layout.addWidget(self.destination_ids, 0, 3)
        target_layout.addWidget(QLabel("Device policy"), 1, 0)
        target_layout.addWidget(self.device_policy, 1, 1)
        target_layout.addWidget(QLabel("Concurrency"), 1, 2)
        target_layout.addWidget(self.concurrency, 1, 3)
        root.addWidget(target_panel)

        body = QHBoxLayout()
        body.setSpacing(7)

        available = Panel()
        available_layout = QVBoxLayout(available)
        available_layout.setContentsMargins(8, 8, 8, 8)
        available_layout.setSpacing(5)
        available_title = QLabel("Available Actions")
        available_title.setProperty("sectionTitle", True)
        available_layout.addWidget(available_title)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.itemChanged.connect(self._tree_item_changed)
        self.tree.currentItemChanged.connect(self._tree_selection_changed)
        available_layout.addWidget(self.tree, stretch=1)

        self._building_tree = True
        for group_name, step_types in ACTION_GROUPS:
            group_item = QTreeWidgetItem([group_name])
            group_item.setFlags(group_item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            group_item.setExpanded(True)
            self.tree.addTopLevelItem(group_item)
            for step_type in step_types:
                info = CAPABILITY_MATRIX[step_type]
                child = QTreeWidgetItem([info.title])
                child.setData(0, Qt.ItemDataRole.UserRole, step_type.value)
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0, Qt.CheckState.Unchecked)
                child.setToolTip(0, info.description)
                group_item.addChild(child)
                self._tree_items[step_type] = child
        self._building_tree = False

        quick_select = QHBoxLayout()
        select_safe = SecondaryButton("Common Actions")
        select_safe.clicked.connect(self._select_common_flow)
        clear = SecondaryButton("Clear")
        clear.clicked.connect(self.clear_actions)
        quick_select.addWidget(select_safe)
        quick_select.addWidget(clear)
        available_layout.addLayout(quick_select)
        body.addWidget(available, stretch=2)

        selected_panel = Panel()
        selected_layout = QVBoxLayout(selected_panel)
        selected_layout.setContentsMargins(8, 8, 8, 8)
        selected_layout.setSpacing(5)
        selected_title = QLabel("Selected Actions · Execution Order")
        selected_title.setProperty("sectionTitle", True)
        selected_layout.addWidget(selected_title)

        self.selected_list = QListWidget()
        self.selected_list.currentRowChanged.connect(self._selected_row_changed)
        selected_layout.addWidget(self.selected_list, stretch=1)

        order_row = QHBoxLayout()
        up = SecondaryButton("↑ Up")
        down = SecondaryButton("↓ Down")
        remove = SecondaryButton("Remove")
        up.clicked.connect(lambda: self._move_selected(-1))
        down.clicked.connect(lambda: self._move_selected(1))
        remove.clicked.connect(self._remove_selected)
        order_row.addWidget(up)
        order_row.addWidget(down)
        order_row.addWidget(remove)
        selected_layout.addLayout(order_row)

        verification = QLabel(
            "Verification/checkpoint: workflow pauses for operator action, "
            "then resumes after successful verification."
        )
        verification.setProperty("muted", True)
        verification.setWordWrap(True)
        selected_layout.addWidget(verification)
        body.addWidget(selected_panel, stretch=2)

        self.config_editor = ActionConfigEditor()
        self.config_editor.changed.connect(self._refresh_status)
        body.addWidget(self.config_editor, stretch=3)
        root.addLayout(body, stretch=1)

        footer = QHBoxLayout()
        self.preset_name = QLineEdit()
        self.preset_name.setPlaceholderText("Preset name")
        self.preset_name.setText("Custom Action List")
        footer.addWidget(self.preset_name, stretch=1)

        save = SecondaryButton("Save Preset")
        save.clicked.connect(self._save_preset)
        footer.addWidget(save)

        dry = SecondaryButton("Dry Run")
        dry.setProperty("infoAction", True)
        dry.clicked.connect(self._dry_run)
        footer.addWidget(dry)

        run = PrimaryButton("▶ Start")
        run.setProperty("successAction", True)
        run.clicked.connect(self._run)
        footer.addWidget(run)

        queue = SecondaryButton("Open Queue")
        queue.clicked.connect(self.queue_requested.emit)
        footer.addWidget(queue)
        root.addLayout(footer)

    @staticmethod
    def _parse_ids(value: str) -> tuple[str, ...]:
        return tuple(
            part.strip()
            for part in value.replace("\n", ",").split(",")
            if part.strip()
        )

    def set_target_accounts(self, account_ids: tuple[str, ...] | list[str]) -> None:
        self.account_ids.setText(", ".join(str(value) for value in account_ids if str(value)))

    def set_target_destinations(self, destination_ids: tuple[str, ...] | list[str]) -> None:
        self.destination_ids.setText(
            ", ".join(str(value) for value in destination_ids if str(value))
        )

    def _tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._building_tree:
            return
        value = item.data(0, Qt.ItemDataRole.UserRole)
        if not value:
            return
        step_type = AutomationStepType(str(value))
        if item.checkState(0) == Qt.CheckState.Checked:
            if step_type not in self._selected_steps:
                self._selected_steps.append(step_type)
        elif step_type in self._selected_steps:
            self._selected_steps.remove(step_type)
        self._sync_selected_list()

    def _tree_selection_changed(
        self,
        current: QTreeWidgetItem | None,
        previous: QTreeWidgetItem | None,
    ) -> None:
        del previous
        if current is None:
            return
        value = current.data(0, Qt.ItemDataRole.UserRole)
        if value:
            self.config_editor.set_step(AutomationStepType(str(value)))

    def _selected_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._selected_steps):
            step_type = self._selected_steps[row]
            self.config_editor.set_step(step_type)
            item = self._tree_items.get(step_type)
            if item is not None:
                self.tree.setCurrentItem(item)

    def _sync_selected_list(self) -> None:
        current = self.selected_list.currentRow()
        self.selected_list.blockSignals(True)
        self.selected_list.clear()
        for index, step_type in enumerate(self._selected_steps, start=1):
            info = CAPABILITY_MATRIX[step_type]
            suffix = ""
            if info.support_tier is CapabilitySupport.REQUIRES_OPERATOR_APPROVAL:
                suffix = " · approval"
            elif info.support_tier is CapabilitySupport.CAPABILITY_GATED:
                suffix = " · capability gated"
            elif info.support_tier is CapabilitySupport.READ_ONLY_ANALYTICS:
                suffix = " · read-only"
            self.selected_list.addItem(f"{index:02d}. {info.title}{suffix}")
        self.selected_list.blockSignals(False)
        if self._selected_steps:
            self.selected_list.setCurrentRow(min(max(current, 0), len(self._selected_steps) - 1))
        else:
            self.config_editor.set_step(None)
        self._refresh_status()

    def clear_actions(self) -> None:
        self._building_tree = True
        for item in self._tree_items.values():
            item.setCheckState(0, Qt.CheckState.Unchecked)
        self._building_tree = False
        self._selected_steps.clear()
        self._sync_selected_list()

    def _select_common_flow(self) -> None:
        common = (
            AutomationStepType.RESTORE_WORKSPACE,
            AutomationStepType.OPEN_PREFERRED_APP,
            AutomationStepType.HEALTH_CHECK,
            AutomationStepType.REFRESH_ASSETS,
            AutomationStepType.BACKUP_WORKSPACE,
            AutomationStepType.RELEASE_DEVICE,
        )
        self.clear_actions()
        self._building_tree = True
        for step_type in common:
            self._tree_items[step_type].setCheckState(0, Qt.CheckState.Checked)
        self._building_tree = False
        self._selected_steps = list(common)
        self._sync_selected_list()

    def _move_selected(self, delta: int) -> None:
        row = self.selected_list.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if not 0 <= new_row < len(self._selected_steps):
            return
        self._selected_steps[row], self._selected_steps[new_row] = (
            self._selected_steps[new_row],
            self._selected_steps[row],
        )
        self._sync_selected_list()
        self.selected_list.setCurrentRow(new_row)

    def _remove_selected(self) -> None:
        row = self.selected_list.currentRow()
        if not 0 <= row < len(self._selected_steps):
            return
        step_type = self._selected_steps.pop(row)
        self._building_tree = True
        self._tree_items[step_type].setCheckState(0, Qt.CheckState.Unchecked)
        self._building_tree = False
        self._sync_selected_list()

    def _target_rules(self) -> TargetSelectionRules:
        return TargetSelectionRules(
            account_ids=self._parse_ids(self.account_ids.text()),
            device_policy=str(self.device_policy.currentData()),
            max_concurrent_devices=self.concurrency.value(),
            destination_ids=self._parse_ids(self.destination_ids.text()),
        )

    def _build_preset(self, preset_id: str | None = None) -> AutomationPreset:
        pid = preset_id or str(uuid.uuid4())
        steps: list[AutomationPresetStep] = []

        for order, step_type in enumerate(self._selected_steps, start=1):
            cfg = self.config_editor.step_config(step_type)
            requires_approval = bool(cfg.pop("_requires_approval", False))
            retry_policy = str(cfg.pop("_retry_policy", "no_retry"))
            timeout_seconds = int(cfg.pop("_timeout_seconds", 120))
            continue_on_error = bool(cfg.pop("_continue_on_error", False))

            info = CAPABILITY_MATRIX[step_type]
            if info.support_tier is CapabilitySupport.REQUIRES_OPERATOR_APPROVAL:
                requires_approval = True

            steps.append(
                AutomationPresetStep(
                    id=str(uuid.uuid4()),
                    preset_id=pid,
                    step_type=step_type,
                    enabled=True,
                    order=order,
                    configuration=cfg,
                    requires_approval=requires_approval,
                    continue_on_error=continue_on_error,
                    retry_policy=retry_policy,
                    timeout_seconds=timeout_seconds,
                )
            )

        return AutomationPreset(
            id=pid,
            name=self.preset_name.text().strip() or "Custom Action List",
            description="Created from the SP-Farms Farm-Reel-style Action List.",
            target_rules=self._target_rules(),
            steps=tuple(steps),
            tags=("action-list",),
            is_built_in=False,
        )

    def _validate(self, require_accounts: bool) -> AutomationPreset | None:
        if not self._selected_steps:
            QMessageBox.warning(self, "Action List", "Select at least one action.")
            return None
        if require_accounts and not self._parse_ids(self.account_ids.text()):
            QMessageBox.warning(
                self,
                "Action List",
                "Select or enter at least one authorized account before starting.",
            )
            return None

        preset = self._build_preset()
        errors = self._service.validate_preset(preset)
        if errors:
            QMessageBox.warning(
                self,
                "Action List validation",
                "\n".join(f"• {error}" for error in errors),
            )
            return None
        return preset

    def _dry_run(self) -> None:
        preset = self._validate(require_accounts=False)
        if preset is None:
            return
        report = self._service.generate_dry_run_report(
            preset,
            target_accounts=self._parse_ids(self.account_ids.text()) or None,
            target_destinations=self._parse_ids(self.destination_ids.text()) or None,
        )
        DryRunDialog(report, self).exec()

    def _run(self) -> None:
        preset = self._validate(require_accounts=True)
        if preset is None:
            return

        approval_steps = sum(step.requires_approval for step in preset.steps)
        message = (
            f"Start {len(preset.steps)} actions for "
            f"{len(preset.target_rules.account_ids)} account(s)?"
        )
        if approval_steps:
            message += f"\n\n{approval_steps} step(s) require operator approval."

        answer = QMessageBox.question(
            self,
            "Start Action List?",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        success, result_message, job_ids = self._service.execute_preset(
            preset,
            target_accounts=preset.target_rules.account_ids,
            target_destinations=preset.target_rules.destination_ids,
            initiator="farm_reel_action_list",
        )
        if success:
            self.status.update_state("active", f"{len(job_ids)} jobs queued")
            QMessageBox.information(
                self,
                "Workflow queued",
                f"{result_message}\n\nCreated jobs: {len(job_ids)}",
            )
            self.queue_requested.emit()
        else:
            self.status.update_state("error", "Workflow not started")
            QMessageBox.warning(self, "Workflow not started", result_message)

    def _save_preset(self) -> None:
        preset = self._validate(require_accounts=False)
        if preset is None:
            return

        saved = self._service.create_preset(
            name=preset.name,
            description=preset.description,
            target_rules=preset.target_rules,
            steps=(),
            tags=("action-list", "operator"),
        )
        bound_steps = tuple(
            replace(step, preset_id=saved.id)
            for step in preset.steps
        )
        saved = self._service.update_preset(
            replace(saved, steps=bound_steps)
        )
        self.status.update_state("success", f"Preset saved · v{saved.version}")
        QMessageBox.information(
            self,
            "Preset saved",
            f"Saved '{saved.name}' with {len(saved.steps)} action(s).",
        )

    def _refresh_status(self) -> None:
        count = len(self._selected_steps)
        if count:
            self.status.update_state("active", f"{count} actions selected")
        else:
            self.status.update_state("neutral", "0 actions selected")


class FarmReelActionListDialog(QDialog):
    """Reusable modal wrapper for account/page context launches."""

    def __init__(
        self,
        service: AutomationBuilderService,
        account_ids: tuple[str, ...] = (),
        destination_ids: tuple[str, ...] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("SP-Farms Action List")
        self.resize(1180, 760)
        self.setMinimumSize(980, 640)

        layout = QVBoxLayout(self)
        self.workspace = FarmReelActionListWorkspace(service)
        self.workspace.set_target_accounts(account_ids)
        self.workspace.set_target_destinations(destination_ids)
        layout.addWidget(self.workspace)

        footer = QHBoxLayout()
        footer.addStretch()
        close = SecondaryButton("Close")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        layout.addLayout(footer)
