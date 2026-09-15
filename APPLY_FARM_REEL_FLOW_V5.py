from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
APP = ROOT / "sp_farms" / "app"

ACTION_LIST_PAYLOAD = 'from __future__ import annotations\n\nimport uuid\nfrom dataclasses import replace\nfrom typing import Any\n\nfrom PySide6.QtCore import Qt, Signal\nfrom PySide6.QtWidgets import (\n    QCheckBox,\n    QComboBox,\n    QDialog,\n    QFormLayout,\n    QGridLayout,\n    QHBoxLayout,\n    QLabel,\n    QLineEdit,\n    QListWidget,\n    QMessageBox,\n    QSpinBox,\n    QStackedWidget,\n    QTextEdit,\n    QTreeWidget,\n    QTreeWidgetItem,\n    QVBoxLayout,\n    QWidget,\n)\n\nfrom sp_farms.app.automation_builder_workspace import DryRunDialog\nfrom sp_farms.app.widgets import Panel, PrimaryButton, SecondaryButton, StatusChip\nfrom sp_farms.application.automation_builder import AutomationBuilderService\nfrom sp_farms.domain.automation_builder import (\n    CAPABILITY_MATRIX,\n    AutomationPreset,\n    AutomationPresetStep,\n    AutomationStepType,\n    CapabilitySupport,\n    TargetSelectionRules,\n)\n\n\n# Farm-Reel-like grouping, backed only by SP-Farms\' existing authorized step types.\nACTION_GROUPS: tuple[tuple[str, tuple[AutomationStepType, ...]], ...] = (\n    (\n        "Workspace",\n        (\n            AutomationStepType.RESTORE_WORKSPACE,\n            AutomationStepType.OPEN_PREFERRED_APP,\n            AutomationStepType.HEALTH_CHECK,\n            AutomationStepType.REFRESH_ASSETS,\n        ),\n    ),\n    (\n        "Content",\n        (\n            AutomationStepType.PUBLISH_TEXT,\n            AutomationStepType.PUBLISH_IMAGE,\n            AutomationStepType.PUBLISH_MULTI_IMAGE,\n            AutomationStepType.PUBLISH_VIDEO,\n            AutomationStepType.PUBLISH_REEL,\n            AutomationStepType.PUBLISH_STORY,\n            AutomationStepType.PUBLISH_LINK,\n            AutomationStepType.SCHEDULE_CONTENT,\n        ),\n    ),\n    (\n        "Comments & Inbox",\n        (\n            AutomationStepType.READ_COMMENTS,\n            AutomationStepType.REPLY_COMMENTS,\n            AutomationStepType.MODERATE_COMMENTS,\n            AutomationStepType.READ_INBOX,\n            AutomationStepType.REPLY_INBOX,\n            AutomationStepType.ASSIGN_INBOX,\n            AutomationStepType.ADD_INTERNAL_NOTE,\n            AutomationStepType.MARK_RESOLVED,\n        ),\n    ),\n    (\n        "Analytics",\n        (\n            AutomationStepType.COLLECT_POST_ANALYTICS,\n            AutomationStepType.COLLECT_REACTION_ANALYTICS,\n            AutomationStepType.COLLECT_SHARE_VIEW_ANALYTICS,\n            AutomationStepType.COLLECT_FOLLOWER_ANALYTICS,\n        ),\n    ),\n    (\n        "Device Queue",\n        (\n            AutomationStepType.BACKUP_WORKSPACE,\n            AutomationStepType.RELEASE_DEVICE,\n            AutomationStepType.START_NEXT_ACCOUNT,\n        ),\n    ),\n)\n\n\nclass ActionConfigEditor(Panel):\n    """Configuration editor for one real AutomationStepType."""\n\n    changed = Signal()\n\n    def __init__(self, parent: QWidget | None = None) -> None:\n        super().__init__(parent)\n        self._step_type: AutomationStepType | None = None\n        self._configs: dict[AutomationStepType, dict[str, Any]] = {}\n\n        root = QVBoxLayout(self)\n        root.setContentsMargins(10, 9, 10, 9)\n        root.setSpacing(7)\n\n        self.title = QLabel("Select an action")\n        self.title.setProperty("heading", True)\n        root.addWidget(self.title)\n\n        self.description = QLabel(\n            "Select a checked action to configure its content, approval, retry, and timeout."\n        )\n        self.description.setProperty("muted", True)\n        self.description.setWordWrap(True)\n        root.addWidget(self.description)\n\n        self.capability = StatusChip("No action", "neutral")\n        root.addWidget(self.capability)\n\n        self.dynamic = QStackedWidget()\n        root.addWidget(self.dynamic, stretch=1)\n\n        self.empty_page = QWidget()\n        empty_layout = QVBoxLayout(self.empty_page)\n        empty_layout.addStretch()\n        empty = QLabel("Action settings appear here.")\n        empty.setProperty("muted", True)\n        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)\n        empty_layout.addWidget(empty)\n        empty_layout.addStretch()\n        self.dynamic.addWidget(self.empty_page)\n\n        self.form_page = QWidget()\n        self.form_layout = QFormLayout(self.form_page)\n        self.form_layout.setContentsMargins(0, 4, 0, 4)\n        self.form_layout.setHorizontalSpacing(10)\n        self.form_layout.setVerticalSpacing(7)\n        self.dynamic.addWidget(self.form_page)\n\n        self._field_widgets: dict[str, QWidget] = {}\n\n        common = Panel()\n        common_layout = QFormLayout(common)\n        common_layout.setContentsMargins(8, 7, 8, 7)\n        common_layout.setVerticalSpacing(6)\n\n        self.approval = QCheckBox("Require operator approval before execution")\n        self.approval.toggled.connect(self.changed.emit)\n        common_layout.addRow("Approval:", self.approval)\n\n        self.retry = QComboBox()\n        self.retry.addItem("No retry", "no_retry")\n        self.retry.addItem("Retry once", "once")\n        self.retry.addItem("Retry up to 3", "up_to_3")\n        self.retry.currentIndexChanged.connect(self.changed.emit)\n        common_layout.addRow("Retry:", self.retry)\n\n        self.timeout = QSpinBox()\n        self.timeout.setRange(10, 3600)\n        self.timeout.setValue(120)\n        self.timeout.setSuffix(" sec")\n        self.timeout.valueChanged.connect(self.changed.emit)\n        common_layout.addRow("Timeout:", self.timeout)\n\n        self.delay = QSpinBox()\n        self.delay.setRange(0, 3600)\n        self.delay.setValue(0)\n        self.delay.setSuffix(" sec")\n        self.delay.setToolTip(\n            "Stored in the step configuration and applied by workers that support delayed execution."\n        )\n        self.delay.valueChanged.connect(self.changed.emit)\n        common_layout.addRow("Delay:", self.delay)\n\n        self.continue_on_error = QCheckBox("Continue workflow if this step fails")\n        self.continue_on_error.toggled.connect(self.changed.emit)\n        common_layout.addRow("On failure:", self.continue_on_error)\n\n        root.addWidget(common)\n\n    def _clear_form(self) -> None:\n        while self.form_layout.rowCount():\n            self.form_layout.removeRow(0)\n        self._field_widgets.clear()\n\n    def _add_line(\n        self,\n        key: str,\n        label: str,\n        placeholder: str = "",\n        value: str = "",\n    ) -> QLineEdit:\n        widget = QLineEdit(value)\n        widget.setPlaceholderText(placeholder)\n        widget.textChanged.connect(self._save_current)\n        self.form_layout.addRow(label, widget)\n        self._field_widgets[key] = widget\n        return widget\n\n    def _add_text(\n        self,\n        key: str,\n        label: str,\n        placeholder: str = "",\n        value: str = "",\n        height: int = 100,\n    ) -> QTextEdit:\n        widget = QTextEdit()\n        widget.setPlaceholderText(placeholder)\n        widget.setPlainText(value)\n        widget.setMinimumHeight(height)\n        widget.textChanged.connect(self._save_current)\n        self.form_layout.addRow(label, widget)\n        self._field_widgets[key] = widget\n        return widget\n\n    def _add_check(self, key: str, label: str, checked: bool = False) -> QCheckBox:\n        widget = QCheckBox()\n        widget.setChecked(checked)\n        widget.toggled.connect(self._save_current)\n        self.form_layout.addRow(label, widget)\n        self._field_widgets[key] = widget\n        return widget\n\n    def _add_spin(\n        self,\n        key: str,\n        label: str,\n        value: int,\n        minimum: int,\n        maximum: int,\n    ) -> QSpinBox:\n        widget = QSpinBox()\n        widget.setRange(minimum, maximum)\n        widget.setValue(value)\n        widget.valueChanged.connect(self._save_current)\n        self.form_layout.addRow(label, widget)\n        self._field_widgets[key] = widget\n        return widget\n\n    def _value(self, key: str, default: Any = None) -> Any:\n        return self._configs.get(self._step_type, {}).get(key, default)\n\n    def set_step(self, step_type: AutomationStepType | None) -> None:\n        self._save_current()\n        self._step_type = step_type\n        self._clear_form()\n\n        if step_type is None:\n            self.title.setText("Select an action")\n            self.description.setText(\n                "Select a checked action to configure its content, approval, retry, and timeout."\n            )\n            self.capability.update_state("neutral", "No action")\n            self.dynamic.setCurrentWidget(self.empty_page)\n            return\n\n        info = CAPABILITY_MATRIX[step_type]\n        self.title.setText(info.title)\n        self.description.setText(info.description)\n\n        if info.support_tier is CapabilitySupport.OFFICIALLY_SUPPORTED:\n            tone, label = "success", "Supported"\n        elif info.support_tier is CapabilitySupport.REQUIRES_OPERATOR_APPROVAL:\n            tone, label = "warning", "Approval required"\n        elif info.support_tier is CapabilitySupport.READ_ONLY_ANALYTICS:\n            tone, label = "active", "Read-only"\n        else:\n            tone, label = "warning", "Capability gated"\n        self.capability.update_state(tone, label)\n\n        cfg = self._configs.setdefault(step_type, {})\n        self.dynamic.setCurrentWidget(self.form_page)\n\n        if step_type is AutomationStepType.RESTORE_WORKSPACE:\n            self._add_check("launch_app", "Launch preferred app:", bool(cfg.get("launch_app", True)))\n            self._add_check(\n                "allow_fallback_device",\n                "Allow fallback device:",\n                bool(cfg.get("allow_fallback_device", True)),\n            )\n            self._add_check(\n                "require_network",\n                "Require stored network:",\n                bool(cfg.get("require_network", True)),\n            )\n\n        elif step_type is AutomationStepType.OPEN_PREFERRED_APP:\n            self._add_line(\n                "preferred_app",\n                "Preferred app:",\n                "facebook / facebook_lite / business_suite / browser",\n                str(cfg.get("preferred_app", "")),\n            )\n\n        elif step_type is AutomationStepType.PUBLISH_TEXT:\n            self._add_text(\n                "text",\n                "Post text:",\n                "Write the authorized Page/Group post text...",\n                str(cfg.get("text", "")),\n                130,\n            )\n            self._add_line(\n                "caption_template_id",\n                "Template ID:",\n                "Optional saved caption template ID",\n                str(cfg.get("caption_template_id", "")),\n            )\n\n        elif step_type in (\n            AutomationStepType.PUBLISH_IMAGE,\n            AutomationStepType.PUBLISH_MULTI_IMAGE,\n        ):\n            self._add_text(\n                "media_paths",\n                "Media paths:",\n                "One local path per line",\n                "\\n".join(cfg.get("media_paths", [])),\n                90,\n            )\n            self._add_line(\n                "media_pool_tag",\n                "Media pool tag:",\n                "Optional content-library tag",\n                str(cfg.get("media_pool_tag", "")),\n            )\n            self._add_text(\n                "caption",\n                "Caption:",\n                "Post caption...",\n                str(cfg.get("caption", "")),\n                90,\n            )\n\n        elif step_type in (\n            AutomationStepType.PUBLISH_VIDEO,\n            AutomationStepType.PUBLISH_REEL,\n        ):\n            self._add_line(\n                "video_path",\n                "Video:",\n                "Local .mp4 path",\n                str(cfg.get("video_path", "")),\n            )\n            self._add_line(\n                "media_pool_tag",\n                "Media pool tag:",\n                "Optional content-library tag",\n                str(cfg.get("media_pool_tag", "")),\n            )\n            self._add_text(\n                "caption",\n                "Caption:",\n                "Video/Reel caption...",\n                str(cfg.get("caption", "")),\n                90,\n            )\n            if step_type is AutomationStepType.PUBLISH_REEL:\n                self._add_line(\n                    "aspect_ratio",\n                    "Aspect ratio:",\n                    "9:16",\n                    str(cfg.get("aspect_ratio", "9:16")),\n                )\n\n        elif step_type is AutomationStepType.PUBLISH_STORY:\n            self._add_line(\n                "media_path",\n                "Story media:",\n                "Image or video path",\n                str(cfg.get("media_path", "")),\n            )\n            self._add_text(\n                "caption",\n                "Caption:",\n                "Optional story caption",\n                str(cfg.get("caption", "")),\n                70,\n            )\n\n        elif step_type is AutomationStepType.PUBLISH_LINK:\n            self._add_line(\n                "url",\n                "Link:",\n                "https://...",\n                str(cfg.get("url", "")),\n            )\n            self._add_text(\n                "text",\n                "Caption:",\n                "Link post text...",\n                str(cfg.get("text", "")),\n                80,\n            )\n\n        elif step_type is AutomationStepType.SCHEDULE_CONTENT:\n            self._add_line(\n                "schedule_at",\n                "Schedule at:",\n                "YYYY-MM-DD HH:MM",\n                str(cfg.get("schedule_at", "")),\n            )\n            self._add_line(\n                "timezone",\n                "Timezone:",\n                "e.g. Asia/Phnom_Penh",\n                str(cfg.get("timezone", "")),\n            )\n\n        elif step_type is AutomationStepType.REPLY_COMMENTS:\n            self._add_text(\n                "reply_template",\n                "Reply template:",\n                "Operator-approved reply template...",\n                str(cfg.get("reply_template", "")),\n                90,\n            )\n            self._add_check(\n                "use_ai_suggestion",\n                "AI suggestion:",\n                bool(cfg.get("use_ai_suggestion", False)),\n            )\n            self._add_spin(\n                "max_replies_per_run",\n                "Max selected replies:",\n                int(cfg.get("max_replies_per_run", 5)),\n                1,\n                50,\n            )\n\n        elif step_type is AutomationStepType.MODERATE_COMMENTS:\n            self._add_line(\n                "rule",\n                "Moderation rule:",\n                "spam / profanity / configured rule",\n                str(cfg.get("rule", "spam")),\n            )\n\n        elif step_type is AutomationStepType.REPLY_INBOX:\n            self._add_text(\n                "saved_reply",\n                "Saved reply:",\n                "Operator-approved customer reply...",\n                str(cfg.get("saved_reply", "")),\n                90,\n            )\n            self._add_check(\n                "use_ai_suggestion",\n                "AI suggestion:",\n                bool(cfg.get("use_ai_suggestion", False)),\n            )\n            self._add_spin(\n                "max_replies_per_run",\n                "Max selected replies:",\n                int(cfg.get("max_replies_per_run", 5)),\n                1,\n                25,\n            )\n\n        elif step_type is AutomationStepType.ASSIGN_INBOX:\n            self._add_line(\n                "assignee",\n                "Assign to:",\n                "Operator / queue",\n                str(cfg.get("assignee", "")),\n            )\n\n        elif step_type is AutomationStepType.ADD_INTERNAL_NOTE:\n            self._add_text(\n                "note",\n                "Internal note:",\n                "Internal-only note...",\n                str(cfg.get("note", "")),\n                80,\n            )\n\n        elif step_type is AutomationStepType.MARK_RESOLVED:\n            self._add_line(\n                "resolution_note",\n                "Resolution note:",\n                "Optional internal note",\n                str(cfg.get("resolution_note", "")),\n            )\n\n        elif step_type in (\n            AutomationStepType.COLLECT_POST_ANALYTICS,\n            AutomationStepType.COLLECT_REACTION_ANALYTICS,\n            AutomationStepType.COLLECT_SHARE_VIEW_ANALYTICS,\n            AutomationStepType.COLLECT_FOLLOWER_ANALYTICS,\n        ):\n            self._add_spin(\n                "range_days",\n                "Date range:",\n                int(cfg.get("range_days", 7)),\n                1,\n                90,\n            )\n\n        elif step_type is AutomationStepType.BACKUP_WORKSPACE:\n            self._add_line(\n                "notes",\n                "Snapshot notes:",\n                "Optional backup label / note",\n                str(cfg.get("notes", "")),\n            )\n\n        elif step_type is AutomationStepType.HEALTH_CHECK:\n            self._add_check(\n                "include_device",\n                "Include device:",\n                bool(cfg.get("include_device", True)),\n            )\n            self._add_check(\n                "include_auth",\n                "Include auth:",\n                bool(cfg.get("include_auth", True)),\n            )\n\n        elif step_type is AutomationStepType.REFRESH_ASSETS:\n            self._add_check("pages", "Refresh Pages:", bool(cfg.get("pages", True)))\n            self._add_check(\n                "groups",\n                "Refresh authorized Groups:",\n                bool(cfg.get("groups", True)),\n            )\n\n        else:\n            note = QLabel("This action uses its existing service defaults.")\n            note.setProperty("muted", True)\n            note.setWordWrap(True)\n            self.form_layout.addRow("", note)\n\n        self.approval.setChecked(bool(cfg.get("_requires_approval", False)))\n        self.retry.setCurrentIndex(\n            max(\n                0,\n                self.retry.findData(str(cfg.get("_retry_policy", "no_retry"))),\n            )\n        )\n        self.timeout.setValue(int(cfg.get("_timeout_seconds", 120)))\n        self.delay.setValue(int(cfg.get("delay_seconds", 0)))\n        self.continue_on_error.setChecked(bool(cfg.get("_continue_on_error", False)))\n\n    def _save_current(self) -> None:\n        step_type = self._step_type\n        if step_type is None:\n            return\n        cfg = self._configs.setdefault(step_type, {})\n\n        for key, widget in self._field_widgets.items():\n            if isinstance(widget, QLineEdit):\n                value: Any = widget.text().strip()\n                if key == "media_paths":\n                    value = [p.strip() for p in widget.text().splitlines() if p.strip()]\n            elif isinstance(widget, QTextEdit):\n                if key == "media_paths":\n                    value = [p.strip() for p in widget.toPlainText().splitlines() if p.strip()]\n                else:\n                    value = widget.toPlainText().strip()\n            elif isinstance(widget, QCheckBox):\n                value = widget.isChecked()\n            elif isinstance(widget, QSpinBox):\n                value = widget.value()\n            else:\n                continue\n            cfg[key] = value\n\n        cfg["_requires_approval"] = self.approval.isChecked()\n        cfg["_retry_policy"] = self.retry.currentData()\n        cfg["_timeout_seconds"] = self.timeout.value()\n        cfg["delay_seconds"] = self.delay.value()\n        cfg["_continue_on_error"] = self.continue_on_error.isChecked()\n        self.changed.emit()\n\n    def step_config(self, step_type: AutomationStepType) -> dict[str, Any]:\n        if self._step_type is step_type:\n            self._save_current()\n        return dict(self._configs.get(step_type, {}))\n\n    def common_settings(self, step_type: AutomationStepType) -> tuple[bool, str, int, bool]:\n        cfg = self.step_config(step_type)\n        info = CAPABILITY_MATRIX[step_type]\n        requires_approval = bool(cfg.pop("_requires_approval", False))\n        if info.support_tier is CapabilitySupport.REQUIRES_OPERATOR_APPROVAL:\n            requires_approval = True\n        return (\n            requires_approval,\n            str(cfg.pop("_retry_policy", "no_retry")),\n            int(cfg.pop("_timeout_seconds", 120)),\n            bool(cfg.pop("_continue_on_error", False)),\n        )\n\n\nclass FarmReelActionListWorkspace(QWidget):\n    """Farm-Reel-style action selection backed by the existing AutomationBuilderService."""\n\n    queue_requested = Signal()\n    accounts_requested = Signal()\n\n    def __init__(\n        self,\n        service: AutomationBuilderService,\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n        self._service = service\n        self._selected_steps: list[AutomationStepType] = []\n        self._tree_items: dict[AutomationStepType, QTreeWidgetItem] = {}\n        self._building_tree = False\n        self.setObjectName("farmReelActionListWorkspace")\n        self._build_ui()\n\n    def _build_ui(self) -> None:\n        root = QVBoxLayout(self)\n        root.setContentsMargins(9, 8, 9, 8)\n        root.setSpacing(7)\n\n        header = QHBoxLayout()\n        title_stack = QVBoxLayout()\n        title_stack.setSpacing(0)\n        title = QLabel("Action List")\n        title.setProperty("heading", True)\n        title_stack.addWidget(title)\n        subtitle = QLabel(\n            "Farm-Reel-style selection, using SP-Farms\' existing authorized workflow engine."\n        )\n        subtitle.setProperty("muted", True)\n        title_stack.addWidget(subtitle)\n        header.addLayout(title_stack)\n        header.addStretch()\n        self.status = StatusChip("0 actions selected", "neutral")\n        header.addWidget(self.status)\n        root.addLayout(header)\n\n        target_panel = Panel()\n        target_layout = QGridLayout(target_panel)\n        target_layout.setContentsMargins(9, 7, 9, 7)\n        target_layout.setHorizontalSpacing(8)\n        target_layout.setVerticalSpacing(6)\n\n        self.account_ids = QLineEdit()\n        self.account_ids.setPlaceholderText("Account IDs, comma separated")\n        self.destination_ids = QLineEdit()\n        self.destination_ids.setPlaceholderText("Authorized Page / Group IDs, comma separated")\n        self.device_policy = QComboBox()\n        self.device_policy.addItem("Bound device first", "bound_first")\n        self.device_policy.addItem("Any available device", "any_available")\n        self.device_policy.addItem("Preferred provider order", "preferred_order")\n        self.concurrency = QSpinBox()\n        self.concurrency.setRange(1, 32)\n        self.concurrency.setValue(4)\n\n        target_layout.addWidget(QLabel("Accounts"), 0, 0)\n        target_layout.addWidget(self.account_ids, 0, 1)\n        target_layout.addWidget(QLabel("Destinations"), 0, 2)\n        target_layout.addWidget(self.destination_ids, 0, 3)\n        target_layout.addWidget(QLabel("Device policy"), 1, 0)\n        target_layout.addWidget(self.device_policy, 1, 1)\n        target_layout.addWidget(QLabel("Concurrency"), 1, 2)\n        target_layout.addWidget(self.concurrency, 1, 3)\n        root.addWidget(target_panel)\n\n        body = QHBoxLayout()\n        body.setSpacing(7)\n\n        available = Panel()\n        available_layout = QVBoxLayout(available)\n        available_layout.setContentsMargins(8, 8, 8, 8)\n        available_layout.setSpacing(5)\n        available_title = QLabel("Available Actions")\n        available_title.setProperty("sectionTitle", True)\n        available_layout.addWidget(available_title)\n\n        self.tree = QTreeWidget()\n        self.tree.setHeaderHidden(True)\n        self.tree.setRootIsDecorated(True)\n        self.tree.itemChanged.connect(self._tree_item_changed)\n        self.tree.currentItemChanged.connect(self._tree_selection_changed)\n        available_layout.addWidget(self.tree, stretch=1)\n\n        self._building_tree = True\n        for group_name, step_types in ACTION_GROUPS:\n            group_item = QTreeWidgetItem([group_name])\n            group_item.setFlags(group_item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)\n            group_item.setExpanded(True)\n            self.tree.addTopLevelItem(group_item)\n            for step_type in step_types:\n                info = CAPABILITY_MATRIX[step_type]\n                child = QTreeWidgetItem([info.title])\n                child.setData(0, Qt.ItemDataRole.UserRole, step_type.value)\n                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)\n                child.setCheckState(0, Qt.CheckState.Unchecked)\n                child.setToolTip(0, info.description)\n                group_item.addChild(child)\n                self._tree_items[step_type] = child\n        self._building_tree = False\n\n        quick_select = QHBoxLayout()\n        select_safe = SecondaryButton("Common Flow")\n        select_safe.clicked.connect(self._select_common_flow)\n        clear = SecondaryButton("Clear")\n        clear.clicked.connect(self.clear_actions)\n        quick_select.addWidget(select_safe)\n        quick_select.addWidget(clear)\n        available_layout.addLayout(quick_select)\n        body.addWidget(available, stretch=2)\n\n        selected_panel = Panel()\n        selected_layout = QVBoxLayout(selected_panel)\n        selected_layout.setContentsMargins(8, 8, 8, 8)\n        selected_layout.setSpacing(5)\n        selected_title = QLabel("Selected Actions · Execution Order")\n        selected_title.setProperty("sectionTitle", True)\n        selected_layout.addWidget(selected_title)\n\n        self.selected_list = QListWidget()\n        self.selected_list.currentRowChanged.connect(self._selected_row_changed)\n        selected_layout.addWidget(self.selected_list, stretch=1)\n\n        order_row = QHBoxLayout()\n        up = SecondaryButton("↑ Up")\n        down = SecondaryButton("↓ Down")\n        remove = SecondaryButton("Remove")\n        up.clicked.connect(lambda: self._move_selected(-1))\n        down.clicked.connect(lambda: self._move_selected(1))\n        remove.clicked.connect(self._remove_selected)\n        order_row.addWidget(up)\n        order_row.addWidget(down)\n        order_row.addWidget(remove)\n        selected_layout.addLayout(order_row)\n\n        verification = QLabel(\n            "Verification/checkpoint: workflow pauses for operator action, then resumes after successful verification."\n        )\n        verification.setProperty("muted", True)\n        verification.setWordWrap(True)\n        selected_layout.addWidget(verification)\n        body.addWidget(selected_panel, stretch=2)\n\n        self.config_editor = ActionConfigEditor()\n        self.config_editor.changed.connect(self._refresh_status)\n        body.addWidget(self.config_editor, stretch=3)\n        root.addLayout(body, stretch=1)\n\n        footer = QHBoxLayout()\n        self.preset_name = QLineEdit()\n        self.preset_name.setPlaceholderText("Preset name")\n        self.preset_name.setText("Custom Action List")\n        footer.addWidget(self.preset_name, stretch=1)\n\n        save = SecondaryButton("Save Preset")\n        save.clicked.connect(self._save_preset)\n        footer.addWidget(save)\n\n        dry = SecondaryButton("Dry Run")\n        dry.setProperty("infoAction", True)\n        dry.clicked.connect(self._dry_run)\n        footer.addWidget(dry)\n\n        run = PrimaryButton("▶ Start")\n        run.setProperty("successAction", True)\n        run.clicked.connect(self._run)\n        footer.addWidget(run)\n\n        queue = SecondaryButton("Open Queue")\n        queue.clicked.connect(self.queue_requested.emit)\n        footer.addWidget(queue)\n        root.addLayout(footer)\n\n    @staticmethod\n    def _parse_ids(value: str) -> tuple[str, ...]:\n        return tuple(\n            part.strip()\n            for part in value.replace("\\n", ",").split(",")\n            if part.strip()\n        )\n\n    def set_target_accounts(self, account_ids: tuple[str, ...] | list[str]) -> None:\n        self.account_ids.setText(", ".join(str(value) for value in account_ids if str(value)))\n\n    def set_target_destinations(self, destination_ids: tuple[str, ...] | list[str]) -> None:\n        self.destination_ids.setText(\n            ", ".join(str(value) for value in destination_ids if str(value))\n        )\n\n    def _tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:\n        if self._building_tree:\n            return\n        value = item.data(0, Qt.ItemDataRole.UserRole)\n        if not value:\n            return\n        step_type = AutomationStepType(str(value))\n        if item.checkState(0) == Qt.CheckState.Checked:\n            if step_type not in self._selected_steps:\n                self._selected_steps.append(step_type)\n        elif step_type in self._selected_steps:\n            self._selected_steps.remove(step_type)\n        self._sync_selected_list()\n\n    def _tree_selection_changed(\n        self,\n        current: QTreeWidgetItem | None,\n        previous: QTreeWidgetItem | None,\n    ) -> None:\n        del previous\n        if current is None:\n            return\n        value = current.data(0, Qt.ItemDataRole.UserRole)\n        if value:\n            self.config_editor.set_step(AutomationStepType(str(value)))\n\n    def _selected_row_changed(self, row: int) -> None:\n        if 0 <= row < len(self._selected_steps):\n            step_type = self._selected_steps[row]\n            self.config_editor.set_step(step_type)\n            item = self._tree_items.get(step_type)\n            if item is not None:\n                self.tree.setCurrentItem(item)\n\n    def _sync_selected_list(self) -> None:\n        current = self.selected_list.currentRow()\n        self.selected_list.blockSignals(True)\n        self.selected_list.clear()\n        for index, step_type in enumerate(self._selected_steps, start=1):\n            info = CAPABILITY_MATRIX[step_type]\n            suffix = ""\n            if info.support_tier is CapabilitySupport.REQUIRES_OPERATOR_APPROVAL:\n                suffix = " · approval"\n            elif info.support_tier is CapabilitySupport.CAPABILITY_GATED:\n                suffix = " · capability gated"\n            elif info.support_tier is CapabilitySupport.READ_ONLY_ANALYTICS:\n                suffix = " · read-only"\n            self.selected_list.addItem(f"{index:02d}. {info.title}{suffix}")\n        self.selected_list.blockSignals(False)\n        if self._selected_steps:\n            self.selected_list.setCurrentRow(min(max(current, 0), len(self._selected_steps) - 1))\n        else:\n            self.config_editor.set_step(None)\n        self._refresh_status()\n\n    def clear_actions(self) -> None:\n        self._building_tree = True\n        for item in self._tree_items.values():\n            item.setCheckState(0, Qt.CheckState.Unchecked)\n        self._building_tree = False\n        self._selected_steps.clear()\n        self._sync_selected_list()\n\n    def _select_common_flow(self) -> None:\n        common = (\n            AutomationStepType.RESTORE_WORKSPACE,\n            AutomationStepType.OPEN_PREFERRED_APP,\n            AutomationStepType.HEALTH_CHECK,\n            AutomationStepType.REFRESH_ASSETS,\n            AutomationStepType.BACKUP_WORKSPACE,\n            AutomationStepType.RELEASE_DEVICE,\n        )\n        self.clear_actions()\n        self._building_tree = True\n        for step_type in common:\n            self._tree_items[step_type].setCheckState(0, Qt.CheckState.Checked)\n        self._building_tree = False\n        self._selected_steps = list(common)\n        self._sync_selected_list()\n\n    def _move_selected(self, delta: int) -> None:\n        row = self.selected_list.currentRow()\n        if row < 0:\n            return\n        new_row = row + delta\n        if not 0 <= new_row < len(self._selected_steps):\n            return\n        self._selected_steps[row], self._selected_steps[new_row] = (\n            self._selected_steps[new_row],\n            self._selected_steps[row],\n        )\n        self._sync_selected_list()\n        self.selected_list.setCurrentRow(new_row)\n\n    def _remove_selected(self) -> None:\n        row = self.selected_list.currentRow()\n        if not 0 <= row < len(self._selected_steps):\n            return\n        step_type = self._selected_steps.pop(row)\n        self._building_tree = True\n        self._tree_items[step_type].setCheckState(0, Qt.CheckState.Unchecked)\n        self._building_tree = False\n        self._sync_selected_list()\n\n    def _target_rules(self) -> TargetSelectionRules:\n        return TargetSelectionRules(\n            account_ids=self._parse_ids(self.account_ids.text()),\n            device_policy=str(self.device_policy.currentData()),\n            max_concurrent_devices=self.concurrency.value(),\n            destination_ids=self._parse_ids(self.destination_ids.text()),\n        )\n\n    def _build_preset(self, preset_id: str | None = None) -> AutomationPreset:\n        pid = preset_id or str(uuid.uuid4())\n        steps: list[AutomationPresetStep] = []\n\n        for order, step_type in enumerate(self._selected_steps, start=1):\n            cfg = self.config_editor.step_config(step_type)\n            requires_approval = bool(cfg.pop("_requires_approval", False))\n            retry_policy = str(cfg.pop("_retry_policy", "no_retry"))\n            timeout_seconds = int(cfg.pop("_timeout_seconds", 120))\n            continue_on_error = bool(cfg.pop("_continue_on_error", False))\n\n            info = CAPABILITY_MATRIX[step_type]\n            if info.support_tier is CapabilitySupport.REQUIRES_OPERATOR_APPROVAL:\n                requires_approval = True\n\n            steps.append(\n                AutomationPresetStep(\n                    id=str(uuid.uuid4()),\n                    preset_id=pid,\n                    step_type=step_type,\n                    enabled=True,\n                    order=order,\n                    configuration=cfg,\n                    requires_approval=requires_approval,\n                    continue_on_error=continue_on_error,\n                    retry_policy=retry_policy,\n                    timeout_seconds=timeout_seconds,\n                )\n            )\n\n        return AutomationPreset(\n            id=pid,\n            name=self.preset_name.text().strip() or "Custom Action List",\n            description="Created from the SP-Farms Farm-Reel-style Action List.",\n            target_rules=self._target_rules(),\n            steps=tuple(steps),\n            tags=("action-list",),\n            is_built_in=False,\n        )\n\n    def _validate(self, require_accounts: bool) -> AutomationPreset | None:\n        if not self._selected_steps:\n            QMessageBox.warning(self, "Action List", "Select at least one action.")\n            return None\n        if require_accounts and not self._parse_ids(self.account_ids.text()):\n            QMessageBox.warning(\n                self,\n                "Action List",\n                "Select or enter at least one authorized account before starting.",\n            )\n            return None\n\n        preset = self._build_preset()\n        errors = self._service.validate_preset(preset)\n        if errors:\n            QMessageBox.warning(\n                self,\n                "Action List validation",\n                "\\n".join(f"• {error}" for error in errors),\n            )\n            return None\n        return preset\n\n    def _dry_run(self) -> None:\n        preset = self._validate(require_accounts=False)\n        if preset is None:\n            return\n        report = self._service.generate_dry_run_report(\n            preset,\n            target_accounts=self._parse_ids(self.account_ids.text()) or None,\n            target_destinations=self._parse_ids(self.destination_ids.text()) or None,\n        )\n        DryRunDialog(report, self).exec()\n\n    def _run(self) -> None:\n        preset = self._validate(require_accounts=True)\n        if preset is None:\n            return\n\n        approval_steps = sum(step.requires_approval for step in preset.steps)\n        message = (\n            f"Start {len(preset.steps)} actions for "\n            f"{len(preset.target_rules.account_ids)} account(s)?"\n        )\n        if approval_steps:\n            message += f"\\n\\n{approval_steps} step(s) require operator approval."\n\n        answer = QMessageBox.question(\n            self,\n            "Start Action List?",\n            message,\n            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,\n            QMessageBox.StandardButton.No,\n        )\n        if answer != QMessageBox.StandardButton.Yes:\n            return\n\n        success, result_message, job_ids = self._service.execute_preset(\n            preset,\n            target_accounts=preset.target_rules.account_ids,\n            target_destinations=preset.target_rules.destination_ids,\n            initiator="farm_reel_action_list",\n        )\n        if success:\n            self.status.update_state("active", f"{len(job_ids)} jobs queued")\n            QMessageBox.information(\n                self,\n                "Workflow queued",\n                f"{result_message}\\n\\nCreated jobs: {len(job_ids)}",\n            )\n            self.queue_requested.emit()\n        else:\n            self.status.update_state("error", "Workflow not started")\n            QMessageBox.warning(self, "Workflow not started", result_message)\n\n    def _save_preset(self) -> None:\n        preset = self._validate(require_accounts=False)\n        if preset is None:\n            return\n\n        saved = self._service.create_preset(\n            name=preset.name,\n            description=preset.description,\n            target_rules=preset.target_rules,\n            steps=(),\n            tags=("action-list", "operator"),\n        )\n        bound_steps = tuple(\n            replace(step, preset_id=saved.id)\n            for step in preset.steps\n        )\n        saved = self._service.update_preset(\n            replace(saved, steps=bound_steps)\n        )\n        self.status.update_state("success", f"Preset saved · v{saved.version}")\n        QMessageBox.information(\n            self,\n            "Preset saved",\n            f"Saved \'{saved.name}\' with {len(saved.steps)} action(s).",\n        )\n\n    def _refresh_status(self) -> None:\n        count = len(self._selected_steps)\n        if count:\n            self.status.update_state("active", f"{count} actions selected")\n        else:\n            self.status.update_state("neutral", "0 actions selected")\n\n\nclass FarmReelActionListDialog(QDialog):\n    """Reusable modal wrapper for account/page context launches."""\n\n    def __init__(\n        self,\n        service: AutomationBuilderService,\n        account_ids: tuple[str, ...] = (),\n        destination_ids: tuple[str, ...] = (),\n        parent: QWidget | None = None,\n    ) -> None:\n        super().__init__(parent)\n        self.setWindowTitle("SP-Farms Action List")\n        self.resize(1180, 760)\n        self.setMinimumSize(980, 640)\n\n        layout = QVBoxLayout(self)\n        self.workspace = FarmReelActionListWorkspace(service)\n        self.workspace.set_target_accounts(account_ids)\n        self.workspace.set_target_destinations(destination_ids)\n        layout.addWidget(self.workspace)\n\n        footer = QHBoxLayout()\n        footer.addStretch()\n        close = SecondaryButton("Close")\n        close.clicked.connect(self.accept)\n        footer.addWidget(close)\n        layout.addLayout(footer)\n'
TEST_PAYLOAD = 'import os\n\nos.environ.setdefault("QT_QPA_PLATFORM", "offscreen")\n\nfrom PySide6.QtWidgets import QApplication\n\nfrom sp_farms.app.farm_reel_action_list import (\n    ACTION_GROUPS,\n    FarmReelActionListWorkspace,\n)\nfrom sp_farms.application.automation_builder import (\n    AutomationBuilderService,\n    InMemoryAutomationPresetRepository,\n)\nfrom sp_farms.domain.automation_builder import AutomationStepType\n\n\ndef application() -> QApplication:\n    existing = QApplication.instance()\n    if isinstance(existing, QApplication):\n        return existing\n    return QApplication([])\n\n\ndef test_action_list_exposes_every_authorized_step_once() -> None:\n    application()\n    service = AutomationBuilderService(InMemoryAutomationPresetRepository())\n    view = FarmReelActionListWorkspace(service)\n\n    exposed = [step for _group, steps in ACTION_GROUPS for step in steps]\n\n    assert len(exposed) == len(set(exposed))\n    assert set(exposed) == set(AutomationStepType)\n    assert len(view._tree_items) == len(AutomationStepType)\n    view.close()\n\n\ndef test_common_flow_builds_valid_non_content_preset() -> None:\n    application()\n    service = AutomationBuilderService(InMemoryAutomationPresetRepository())\n    view = FarmReelActionListWorkspace(service)\n\n    view._select_common_flow()\n    view.set_target_accounts(("account-1",))\n    preset = view._build_preset()\n\n    assert preset.target_rules.account_ids == ("account-1",)\n    assert len(preset.steps) == 6\n    assert service.validate_preset(preset) == []\n    view.close()\n\n\ndef test_publish_text_requires_content() -> None:\n    application()\n    service = AutomationBuilderService(InMemoryAutomationPresetRepository())\n    view = FarmReelActionListWorkspace(service)\n\n    view._selected_steps = [AutomationStepType.PUBLISH_TEXT]\n    preset = view._build_preset()\n    errors = service.validate_preset(preset)\n\n    assert any("Publish Text" in error for error in errors)\n    view.close()\n'


def fail(message: str) -> None:
    print(f"[ERROR] {message}")
    raise SystemExit(1)


def backup_files(names: tuple[str, ...]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = ROOT / f".farm_reel_v5_backup_{stamp}"
    for name in names:
        src = APP / name
        if src.exists():
            dst = backup / "sp_farms" / "app" / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return backup


def replace_once(text: str, old: str, new: str, label: str, required: bool = False) -> str:
    if new in text:
        print(f"[OK] {label}: already applied")
        return text
    if old not in text:
        if required:
            fail(f"{label}: expected source block not found")
        print(f"[SKIP] {label}: source block not found")
        return text
    print(f"[PATCH] {label}")
    return text.replace(old, new, 1)


def patch_main_window() -> None:
    path = APP / "main_window.py"
    text = path.read_text(encoding="utf-8")

    import_anchor = "from sp_farms.app.error_center import ErrorCenterWorkspace\n"
    import_line = "from sp_farms.app.farm_reel_action_list import FarmReelActionListWorkspace\n"
    if import_line not in text:
        if import_anchor not in text:
            fail("main_window import anchor not found")
        text = text.replace(import_anchor, import_anchor + import_line, 1)
        print("[PATCH] main window Action List import")

    quick_block = (
        "        self.quick_automation_workspace: QuickAutomationWorkspace | None = (\n"
        "            QuickAutomationWorkspace(self._context.automation_builder_service)\n"
        "            if self._context.automation_builder_service\n"
        "            else None\n"
        "        )\n"
    )
    action_block = quick_block + (
        "        self.action_list_workspace: FarmReelActionListWorkspace | None = (\n"
        "            FarmReelActionListWorkspace(self._context.automation_builder_service)\n"
        "            if self._context.automation_builder_service\n"
        "            else None\n"
        "        )\n"
        "        if self.action_list_workspace is not None:\n"
        "            self.action_list_workspace.queue_requested.connect(\n"
        "                self._open_automation_queue\n"
        "            )\n"
        "            self.action_list_workspace.accounts_requested.connect(\n"
        '                lambda: self.navigate("Accounts")\n'
        "            )\n"
    )
    if "self.action_list_workspace:" not in text:
        text = replace_once(
            text, quick_block, action_block, "create Action List workspace", required=True
        )

    connect_anchor = "        self.account_workspace.local_navigation_requested.connect(self.navigate)\n"
    connect_new = connect_anchor + (
        "        self.account_workspace.action_list_requested.connect(\n"
        "            self._open_action_list_for_accounts\n"
        "        )\n"
    )
    if "self.account_workspace.action_list_requested.connect" not in text:
        text = replace_once(
            text,
            connect_anchor,
            connect_new,
            "connect account selection to Action List",
            required=True,
        )

    tab_anchor = (
        "                self.automation_tabs = QTabWidget()\n"
        "                automation_tabs = self.automation_tabs\n"
    )
    tab_new = tab_anchor + (
        "                if self.action_list_workspace is not None:\n"
        '                    automation_tabs.addTab(self.action_list_workspace, "Action List")\n'
    )
    if 'automation_tabs.addTab(self.action_list_workspace, "Action List")' not in text:
        text = replace_once(
            text, tab_anchor, tab_new, "add Action List Automation tab", required=True
        )

    nav_anchor = (
        '        elif section == "Automation":\n'
        "            self.job_queue_view.refresh()\n"
    )
    nav_new = (
        '        elif section == "Automation":\n'
        "            self.job_queue_view.refresh()\n"
        "            if self.action_list_workspace is not None:\n"
        "                self.action_list_workspace._refresh_status()\n"
    )
    if "self.action_list_workspace._refresh_status()" not in text:
        text = replace_once(text, nav_anchor, nav_new, "Automation Action List refresh")

    helper_anchor = "    def set_theme(self, mode: ThemeMode) -> None:\n"
    helpers = (
        "    def _open_action_list_for_accounts(self, account_ids: tuple[str, ...]) -> None:\n"
        "        if self.action_list_workspace is None:\n"
        "            return\n"
        "        self.action_list_workspace.set_target_accounts(account_ids)\n"
        '        self.navigate("Automation")\n'
        '        if hasattr(self, "automation_tabs"):\n'
        "            self.automation_tabs.setCurrentWidget(self.action_list_workspace)\n"
        "\n"
        "    def _open_automation_queue(self) -> None:\n"
        '        self.navigate("Automation")\n'
        '        if hasattr(self, "automation_tabs"):\n'
        "            self.automation_tabs.setCurrentWidget(self.job_queue_view)\n"
        "\n"
    )
    if "def _open_action_list_for_accounts" not in text:
        if helper_anchor not in text:
            fail("main_window set_theme anchor not found")
        text = text.replace(helper_anchor, helpers + helper_anchor, 1)
        print("[PATCH] Action List routing helpers")

    path.write_text(text, encoding="utf-8")


def patch_account_workspace() -> None:
    path = APP / "account_workspace.py"
    text = path.read_text(encoding="utf-8")

    signal_anchor = (
        "class AccountWorkspace(QWidget):\n"
        "    success_action_requested = Signal(str, str)\n"
        "    local_navigation_requested = Signal(str)\n"
        "    restore_completed = Signal(object)\n"
    )
    signal_new = (
        "class AccountWorkspace(QWidget):\n"
        "    success_action_requested = Signal(str, str)\n"
        "    local_navigation_requested = Signal(str)\n"
        "    action_list_requested = Signal(tuple)\n"
        "    restore_completed = Signal(object)\n"
    )
    if "action_list_requested = Signal(tuple)" not in text:
        text = replace_once(
            text, signal_anchor, signal_new, "Account Action List signal", required=True
        )

    old_flow = '''        # Normal operator flow: select -> resolve -> restore -> actions -> monitor.
        account_flow = Panel()
        account_flow.setProperty("flowPanel", True)
        account_flow_layout = QHBoxLayout(account_flow)
        account_flow_layout.setContentsMargins(8, 6, 8, 6)
        account_flow_layout.setSpacing(5)
        flow_caption = QLabel("ACCOUNT FLOW")
        flow_caption.setProperty("sectionTitle", True)
        account_flow_layout.addWidget(flow_caption)
        for index, (name, detail) in enumerate(
            (
                ("Select", "Account"),
                ("Resolve", "Device + Network"),
                ("Restore", "Workspace"),
                ("Actions", "Content / Maintenance"),
                ("Monitor", "Job Queue"),
            ),
            start=1,
        ):
            step = QPushButton(f"{index}  {name}\\n    {detail}")
            step.setProperty("flowStep", True)
            if index == 1:
                step.setProperty("flowState", "next")
            step.setEnabled(False)
            account_flow_layout.addWidget(step, stretch=1)
            if index < 5:
                arrow = QLabel("→")
                arrow.setProperty("flowArrow", True)
                account_flow_layout.addWidget(arrow)
        listing_layout.addWidget(account_flow)
'''
    new_flow = '''        # Real operator flow: selected context moves forward without re-selecting.
        account_flow = Panel()
        account_flow.setProperty("flowPanel", True)
        account_flow_layout = QHBoxLayout(account_flow)
        account_flow_layout.setContentsMargins(8, 6, 8, 6)
        account_flow_layout.setSpacing(5)

        flow_caption = QLabel("ACCOUNT FLOW")
        flow_caption.setProperty("sectionTitle", True)
        account_flow_layout.addWidget(flow_caption)

        self.account_flow_select = QPushButton("1  Select\\n    Account")
        self.account_flow_select.setProperty("flowStep", True)
        self.account_flow_select.setProperty("flowState", "next")
        self.account_flow_select.setEnabled(False)

        self.account_flow_resolve = QPushButton("2  Resolve\\n    Device + Network")
        self.account_flow_resolve.setProperty("flowStep", True)
        self.account_flow_resolve.clicked.connect(self.open_context_actions)

        self.account_flow_restore = QPushButton("3  Restore\\n    Workspace")
        self.account_flow_restore.setProperty("flowStep", True)
        self.account_flow_restore.clicked.connect(self.restore_selected_workspace)

        self.account_flow_actions = QPushButton("4  Actions\\n    Build Workflow")
        self.account_flow_actions.setProperty("flowStep", True)
        self.account_flow_actions.clicked.connect(
            lambda: self.action_list_requested.emit(self.selected_account_ids)
        )

        self.account_flow_monitor = QPushButton("5  Monitor\\n    Job Queue")
        self.account_flow_monitor.setProperty("flowStep", True)
        self.account_flow_monitor.clicked.connect(
            lambda: self.local_navigation_requested.emit("Automation")
        )

        self.account_flow_buttons = (
            self.account_flow_select,
            self.account_flow_resolve,
            self.account_flow_restore,
            self.account_flow_actions,
            self.account_flow_monitor,
        )
        for index, button in enumerate(self.account_flow_buttons):
            account_flow_layout.addWidget(button, stretch=1)
            if index < len(self.account_flow_buttons) - 1:
                arrow = QLabel("→")
                arrow.setProperty("flowArrow", True)
                account_flow_layout.addWidget(arrow)

        listing_layout.addWidget(account_flow)
'''
    if "self.account_flow_select =" not in text:
        text = replace_once(text, old_flow, new_flow, "functional Account Flow", required=True)

    actions_block = (
        '        self.actions_btn = PrimaryButton("Actions...")\n'
        '        self.actions_btn.setObjectName("contextActionsButton")\n'
        "        self.actions_btn.setEnabled(False)\n"
        "        self.actions_btn.clicked.connect(self.open_context_actions)\n"
    )
    workflow_block = actions_block + (
        "\n"
        '        self.workflow_btn = SecondaryButton("Action List...")\n'
        '        self.workflow_btn.setObjectName("actionListButton")\n'
        "        self.workflow_btn.setEnabled(False)\n"
        "        self.workflow_btn.clicked.connect(\n"
        "            lambda: self.action_list_requested.emit(self.selected_account_ids)\n"
        "        )\n"
    )
    if "self.workflow_btn = SecondaryButton" not in text:
        text = replace_once(
            text, actions_block, workflow_block, "Accounts Action List button", required=True
        )

    toolbar_anchor = (
        "        toolbar_layout.addWidget(self.bulk_btn)\n"
        "        toolbar_layout.addWidget(self.actions_btn)\n"
    )
    toolbar_new = (
        "        toolbar_layout.addWidget(self.bulk_btn)\n"
        "        toolbar_layout.addWidget(self.workflow_btn)\n"
        "        toolbar_layout.addWidget(self.actions_btn)\n"
    )
    if "toolbar_layout.addWidget(self.workflow_btn)" not in text:
        text = replace_once(
            text, toolbar_anchor, toolbar_new, "Accounts toolbar Action List", required=True
        )

    release_anchor = (
        "        self.release_btn.setEnabled(bool(count >= 1 and self._pool_service is not None))\n"
    )
    workflow_enable = release_anchor + "        self.workflow_btn.setEnabled(bool(count >= 1))\n"
    if "self.workflow_btn.setEnabled(bool(count >= 1))" not in text:
        text = replace_once(
            text, release_anchor, workflow_enable, "Action List selection state", required=True
        )

    # Fill the existing V4 flow-state block with real enable/disable controls if missing.
    flow_marker = '        if hasattr(self, "account_flow_buttons"):\n'
    if flow_marker in text and "self.account_flow_actions.setEnabled(bool(count))" not in text:
        insert_at = text.find(flow_marker)
        # Find the next blank-line method boundary after this block.
        next_def = text.find("\n    def ", insert_at)
        if next_def != -1:
            segment = text[insert_at:next_def]
            segment += (
                "        self.account_flow_resolve.setEnabled(bool(count))\n"
                "        self.account_flow_restore.setEnabled(\n"
                "            bool(count == 1 and self._restore_service is not None)\n"
                "        )\n"
                "        self.account_flow_actions.setEnabled(bool(count))\n"
                "        self.account_flow_monitor.setEnabled(True)\n"
            )
            text = text[:insert_at] + segment + text[next_def:]
            print("[PATCH] functional Account Flow state")

    path.write_text(text, encoding="utf-8")


def patch_quick_automation() -> None:
    path = APP / "quick_automation_workspace.py"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")

    if "action_list_requested = Signal()" not in text:
        text = replace_once(
            text,
            "    advanced_requested = Signal()\n",
            "    advanced_requested = Signal()\n    action_list_requested = Signal()\n",
            "Quick Mode Action List signal",
            required=True,
        )

    button_anchor = (
        '        advanced = SecondaryButton("Advanced Builder")\n'
        "        advanced.clicked.connect(self.advanced_requested.emit)\n"
        "        header.addWidget(advanced)\n"
    )
    button_new = (
        '        action_list = SecondaryButton("Action List")\n'
        "        action_list.clicked.connect(self.action_list_requested.emit)\n"
        "        header.addWidget(action_list)\n"
        "\n"
        '        advanced = SecondaryButton("Advanced Builder")\n'
        "        advanced.clicked.connect(self.advanced_requested.emit)\n"
        "        header.addWidget(advanced)\n"
    )
    if "action_list.clicked.connect(self.action_list_requested.emit)" not in text:
        text = replace_once(
            text, button_anchor, button_new, "Quick Mode Action List button", required=True
        )

    path.write_text(text, encoding="utf-8")


def patch_quick_connection_main_window() -> None:
    path = APP / "main_window.py"
    text = path.read_text(encoding="utf-8")

    if "self.quick_automation_workspace.action_list_requested.connect" not in text:
        anchor = (
            "                if self.quick_automation_workspace is not None:\n"
            "                    self.quick_automation_workspace.advanced_requested.connect(\n"
        )
        idx = text.find(anchor)
        if idx == -1:
            fail("Quick Mode advanced connection anchor not found")
        hook = (
            "                if self.quick_automation_workspace is not None:\n"
            "                    self.quick_automation_workspace.action_list_requested.connect(\n"
            "                        lambda: automation_tabs.setCurrentWidget(\n"
            "                            self.action_list_workspace\n"
            "                        )\n"
            "                        if self.action_list_workspace is not None\n"
            "                        else None\n"
            "                    )\n"
        )
        text = text[:idx] + hook + text[idx:]
        print("[PATCH] Quick Mode → Action List")

    path.write_text(text, encoding="utf-8")


def main() -> None:
    if not (APP / "main_window.py").exists():
        fail("Run APPLY_FARM_REEL_FLOW_V5.py from the SP-Farms repository root.")

    touched = (
        "main_window.py",
        "account_workspace.py",
        "quick_automation_workspace.py",
        "farm_reel_action_list.py",
    )
    backup = backup_files(touched)
    print(f"[OK] Backup created: {backup}")

    (APP / "farm_reel_action_list.py").write_text(ACTION_LIST_PAYLOAD, encoding="utf-8")
    print("[COPY] farm_reel_action_list.py")

    patch_main_window()
    patch_account_workspace()
    patch_quick_automation()
    patch_quick_connection_main_window()

    tests_dir = ROOT / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_farm_reel_action_list.py").write_text(
        TEST_PAYLOAD,
        encoding="utf-8",
    )
    print("[COPY] tests/test_farm_reel_action_list.py")

    print()
    print("SP-Farms Farm Reel Flow V5 applied.")
    print("Run:")
    print(r'  .\.venv\Scripts\python.exe -m pytest tests/test_design_system.py tests/test_main_window.py tests/test_farm_reel_action_list.py -q')
    print(r'  .\.venv\Scripts\python.exe -m ruff check sp_farms')
    print(r'  .\.venv\Scripts\python.exe -m sp_farms.app.main')
    print()
    print(f"Rollback backup: {backup}")


if __name__ == "__main__":
    main()
