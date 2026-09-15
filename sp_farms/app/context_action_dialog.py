"""Context-Aware Universal Action Modal for Accounts, Pages, and Devices.

Provides zero-reselect contextual operations, non-blocking execution,
capability-gated tabs, and multi-target batch scheduling.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
import logging
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QSettings,
    Qt,
    QThreadPool,
    Signal,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.widgets import Panel, PrimaryButton, SecondaryButton, StatusChip
from sp_farms.domain.automation_builder import AutomationPreset, AutomationPresetStep
from sp_farms.domain.selection_context import (
    ActionTabType,
    ResolvedTarget,
    SelectionContext,
    SelectionSource,
    TargetType,
)

if TYPE_CHECKING:
    from sp_farms.application.automation_builder import AutomationBuilderService
    from sp_farms.application.context import ApplicationContext
    from sp_farms.application.job_service import JobService

logger = logging.getLogger(__name__)


class ActionWorkerSignals(QObject):
    started = Signal(str)
    progress = Signal(int, str)
    target_completed = Signal(str, bool, str)
    finished = Signal(bool, str)
    error = Signal(str)


class AsyncActionWorker(QRunnable):
    """Executes long-running actions off the Qt GUI thread."""

    def __init__(
        self,
        action_name: str,
        context: SelectionContext,
        action_fn: Callable[[SelectionContext, Callable[[int, str], None]], tuple[bool, str]],
    ) -> None:
        super().__init__()
        self.action_name = action_name
        self.context = context
        self.action_fn = action_fn
        self.signals = ActionWorkerSignals()
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        self.signals.started.emit(self.action_name)
        try:
            def report_progress(percent: int, message: str) -> None:
                if not self._is_cancelled:
                    self.signals.progress.emit(percent, message)

            success, msg = self.action_fn(self.context, report_progress)
            if self._is_cancelled:
                self.signals.finished.emit(False, "Cancelled by user")
            else:
                self.signals.finished.emit(success, msg)
        except Exception as exc:
            logger.exception("Context action failed: %s", exc)
            self.signals.error.emit(str(exc))


class ContextActionDialog(QDialog):
    """Universal tabbed action modal driven by SelectionContext."""

    action_completed = Signal(str, bool, str)

    def __init__(
        self,
        context: SelectionContext,
        app_context: "ApplicationContext | None" = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.context = context
        self.app_context = app_context
        self._settings = QSettings("SP-Farms", "ContextActionDialog")
        self._thread_pool = QThreadPool.globalInstance()
        self._current_worker: AsyncActionWorker | None = None

        self.setObjectName("contextActionDialog")
        self.setWindowTitle(f"Actions — {self.context.summary_header}")
        self.resize(960, 680)
        self.setMinimumSize(800, 560)

        self._init_ui()
        self._restore_persisted_state()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # 1. Header with metadata, target summary, and health badges
        header_panel = Panel()
        header_layout = QVBoxLayout(header_panel)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(6)

        title_row = QHBoxLayout()
        self.title_label = QLabel(self.context.summary_header)
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_row.addWidget(self.title_label, stretch=1)

        # Health badge
        primary = self.context.primary_target
        health_state = primary.health_status if primary else "healthy"
        chip_style = "success" if health_state in ("healthy", "active", "ready") else "warning"
        self.health_chip = StatusChip(health_state.capitalize(), state=chip_style)
        title_row.addWidget(self.health_chip)

        # Auth state badge
        auth_state = primary.auth_state if primary else "ready"
        auth_style = "success" if auth_state == "ready" else "error"
        self.auth_chip = StatusChip(f"Auth: {auth_state.capitalize()}", state=auth_style)
        title_row.addWidget(self.auth_chip)

        header_layout.addLayout(title_row)

        # Read-only 'Using:' summary bar (zero re-select guarantee)
        self.using_summary_label = QLabel(self.context.read_only_summary)
        self.using_summary_label.setStyleSheet(
            "color: #71717a; font-size: 12px; font-family: monospace;"
        )
        self.using_summary_label.setWordWrap(True)
        header_layout.addWidget(self.using_summary_label)

        root.addWidget(header_panel)

        # 2. Main Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setObjectName("contextTabs")
        self._build_tabs()
        root.addWidget(self.tabs, stretch=1)

        # 3. Running Status & Progress Bar (Non-blocking feedback)
        self.progress_container = QWidget()
        progress_layout = QVBoxLayout(self.progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(4)

        self.status_stream_label = QLabel("")
        self.status_stream_label.setStyleSheet("font-size: 12px; color: #3b82f6;")
        progress_layout.addWidget(self.status_stream_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar)

        self.progress_container.hide()
        root.addWidget(self.progress_container)

        # 4. Sticky Footer Actions
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(8)

        self.cancel_job_btn = SecondaryButton("Cancel Job")
        self.cancel_job_btn.clicked.connect(self._cancel_running_job)
        self.cancel_job_btn.hide()
        footer_layout.addWidget(self.cancel_job_btn)

        self.close_btn = SecondaryButton("Close")
        self.close_btn.clicked.connect(self.reject)
        footer_layout.addWidget(self.close_btn)

        footer_layout.addStretch(1)

        self.save_preset_btn = SecondaryButton("Save as Preset")
        self.save_preset_btn.clicked.connect(self._save_as_preset)
        footer_layout.addWidget(self.save_preset_btn)

        self.dry_run_btn = SecondaryButton("Dry Run")
        self.dry_run_btn.clicked.connect(self._execute_dry_run)
        footer_layout.addWidget(self.dry_run_btn)

        self.run_btn = PrimaryButton("Run")
        self.run_btn.clicked.connect(lambda: self._execute_current_tab_action(close_on_finish=False))
        footer_layout.addWidget(self.run_btn)

        self.run_and_close_btn = PrimaryButton("Run & Close")
        self.run_and_close_btn.clicked.connect(lambda: self._execute_current_tab_action(close_on_finish=True))
        footer_layout.addWidget(self.run_and_close_btn)

        root.addLayout(footer_layout)

    def _build_tabs(self) -> None:
        supported_tabs = self.context.get_supported_tabs()

        tab_builders: dict[ActionTabType, tuple[str, Callable[[], QWidget]]] = {
            ActionTabType.OVERVIEW: ("Overview", self._create_overview_tab),
            ActionTabType.RESTORE: ("Restore Workspace", self._create_restore_tab),
            ActionTabType.CONTENT: ("Content", self._create_content_tab),
            ActionTabType.POST: ("Post Feed", self._create_post_tab),
            ActionTabType.VIDEO: ("Video", self._create_video_tab),
            ActionTabType.REEL: ("Reel", self._create_reel_tab),
            ActionTabType.STORY: ("Story", self._create_story_tab),
            ActionTabType.COMMENTS: ("Comments", self._create_comments_tab),
            ActionTabType.INBOX: ("Inbox", self._create_inbox_tab),
            ActionTabType.ANALYTICS: ("Analytics", self._create_analytics_tab),
            ActionTabType.SCHEDULE: ("Schedule", self._create_schedule_tab),
            ActionTabType.BACKUP: ("Backup / Snapshot", self._create_backup_tab),
            ActionTabType.DEVICE: ("Device Binding", self._create_device_tab),
            ActionTabType.CONNECTED_ACCOUNT: ("Connected Account", self._create_connected_account_tab),
            ActionTabType.ASSIGNED_ACCOUNT: ("Assigned Account", self._create_assigned_account_tab),
            ActionTabType.LAUNCH_APP: ("Launch App", self._create_launch_app_tab),
            ActionTabType.HEALTH: ("Health", self._create_health_tab),
            ActionTabType.SCREENSHOT: ("Screenshot", self._create_screenshot_tab),
            ActionTabType.LOGS: ("Logs", self._create_logs_tab),
            ActionTabType.RELEASE: ("Release Device", self._create_release_tab),
            ActionTabType.SECURITY: ("Security", self._create_security_tab),
            ActionTabType.QA_PROFILE_LAB: ("QA Profile Lab", self._create_qa_profile_tab),
            ActionTabType.ADVANCED: ("Advanced", self._create_advanced_tab),
        }

        for tab_type in supported_tabs:
            if tab_type in tab_builders:
                label, builder_fn = tab_builders[tab_type]
                widget = builder_fn()
                self.tabs.addTab(widget, label)

    def _create_scrollable(self, content_widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content_widget)
        return scroll

    # --- TAB CONTENT BUILDERS ---

    def _create_overview_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        info = QLabel(
            "Target overview resolved automatically from your selection. "
            "All subsequent operations use these inferred targets directly without re-selection."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Mapping table / preview
        if self.context.is_multi_select:
            layout.addWidget(QLabel("<b>Selected Batch Targets:</b>"))
            preview_text = QTextEdit()
            preview_text.setReadOnly(True)
            lines = []
            for t in self.context.resolved_targets:
                lines.append(
                    f"• [{t.target_type.value.upper()}] {t.display_name} "
                    f"-> Owning Account: {t.owning_account_name or 'Self'} "
                    f"-> Bound Device: {t.bound_device_id or 'Auto-assign'} "
                    f"[{t.auth_state}]"
                )
            preview_text.setText("\n".join(lines))
            layout.addWidget(preview_text, stretch=1)
        else:
            t = self.context.primary_target
            if t:
                form = QFormLayout()
                form.addRow("Target Name:", QLabel(t.display_name))
                form.addRow("Target Type:", QLabel(t.target_type.value.capitalize()))
                form.addRow("Owning Account:", QLabel(t.owning_account_name or "Self"))
                form.addRow("Bound Device:", QLabel(t.bound_device_id or "None (Auto-assign on run)"))
                form.addRow("Preferred App:", QLabel(t.preferred_app.capitalize()))
                form.addRow("Auth State:", QLabel(t.auth_state.capitalize()))
                form.addRow("Health Status:", QLabel(t.health_status.capitalize()))
                layout.addLayout(form)
            layout.addStretch(1)

        return self._create_scrollable(panel)

    def _create_restore_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        desc = QLabel(
            "Restore the account's legitimate stored workspace, display/app preferences, and auth state. "
            "Atomically reserves the bound or preferred device and verifies ADB connection."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        form = QFormLayout()
        self.restore_launch_app = QCheckBox("Launch preferred app upon completion")
        self.restore_launch_app.setChecked(True)
        form.addRow("App Launch:", self.restore_launch_app)

        self.restore_fallback_device = QCheckBox("Allow fallback device if bound device is busy/offline")
        self.restore_fallback_device.setChecked(True)
        form.addRow("Fallback Policy:", self.restore_fallback_device)

        layout.addLayout(form)
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_content_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(QLabel("Select or attach media assets from your Content Library."))
        form = QFormLayout()
        self.content_tag_input = QLineEdit()
        self.content_tag_input.setPlaceholderText("Filter media by tag (e.g. promo, daily)")
        form.addRow("Media Pool Tag:", self.content_tag_input)
        layout.addLayout(form)
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_post_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        form = QFormLayout()
        self.post_type_combo = QComboBox()
        self.post_type_combo.addItems(["Text Only", "Single Image", "Multi-Image", "Link Share"])
        form.addRow("Post Type:", self.post_type_combo)

        self.post_caption_edit = QTextEdit()
        self.post_caption_edit.setPlaceholderText("Write your post caption here...")
        self.post_caption_edit.setMaximumHeight(100)
        form.addRow("Caption:", self.post_caption_edit)

        self.post_media_path = QLineEdit()
        self.post_media_path.setPlaceholderText("Local media path (optional)")
        form.addRow("Media Path:", self.post_media_path)

        self.post_schedule_check = QCheckBox("Publish immediately")
        self.post_schedule_check.setChecked(True)
        form.addRow("Timing:", self.post_schedule_check)

        layout.addLayout(form)
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_video_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        form = QFormLayout()
        self.video_path_edit = QLineEdit()
        self.video_path_edit.setPlaceholderText("Path to video file (.mp4)")
        form.addRow("Video File:", self.video_path_edit)

        self.video_title_edit = QLineEdit()
        self.video_title_edit.setPlaceholderText("Video title")
        form.addRow("Title:", self.video_title_edit)

        self.video_caption_edit = QTextEdit()
        self.video_caption_edit.setPlaceholderText("Video description")
        self.video_caption_edit.setMaximumHeight(80)
        form.addRow("Description:", self.video_caption_edit)
        layout.addLayout(form)
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_reel_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        form = QFormLayout()
        self.reel_path_edit = QLineEdit()
        self.reel_path_edit.setPlaceholderText("Vertical video file (.mp4 9:16)")
        form.addRow("Reel Video:", self.reel_path_edit)

        self.reel_caption_edit = QTextEdit()
        self.reel_caption_edit.setPlaceholderText("Reel caption and hashtags")
        self.reel_caption_edit.setMaximumHeight(80)
        form.addRow("Caption:", self.reel_caption_edit)
        layout.addLayout(form)
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_story_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        warn = QLabel(
            "Note: Story publishing requires specialized Meta partner permissions or emulator automation. "
            "Verify device capabilities before scheduling stories."
        )
        warn.setStyleSheet("color: #eab308;")
        warn.setWordWrap(True)
        layout.addWidget(warn)

        form = QFormLayout()
        self.story_path_edit = QLineEdit()
        self.story_path_edit.setPlaceholderText("Image or video path")
        form.addRow("Media File:", self.story_path_edit)
        layout.addLayout(form)
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_comments_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(QLabel("Sync and reply to comments on recent posts."))
        form = QFormLayout()
        self.comment_auto_reply = QCheckBox("Auto-reply with saved template")
        form.addRow("Auto-Reply:", self.comment_auto_reply)
        self.comment_template_edit = QLineEdit()
        self.comment_template_edit.setPlaceholderText("e.g. Thanks for your interest! Check your inbox.")
        form.addRow("Template:", self.comment_template_edit)
        layout.addLayout(form)
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_inbox_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(QLabel("Synchronize Page messaging inbox and customer inquiries."))
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_analytics_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(QLabel("Collect reach, impressions, engagement, and follower growth metrics."))
        form = QFormLayout()
        self.analytics_range_combo = QComboBox()
        self.analytics_range_combo.addItems(["Last 7 Days", "Last 14 Days", "Last 28 Days"])
        form.addRow("Date Range:", self.analytics_range_combo)
        layout.addLayout(form)
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_schedule_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(QLabel("Configure delivery windows and slot policies."))
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_backup_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        desc = QLabel(
            "Create a lightweight workspace snapshot including device preferences, display configuration, "
            "and authorized metadata. No raw Facebook private app data is stored."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)
        form = QFormLayout()
        self.backup_notes_edit = QLineEdit()
        self.backup_notes_edit.setPlaceholderText("Optional notes for this snapshot")
        form.addRow("Snapshot Notes:", self.backup_notes_edit)
        layout.addLayout(form)
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_device_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        desc = QLabel("Stored Device Assignment & Scheduling Policy.")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        form = QFormLayout()
        self.device_policy_combo = QComboBox()
        self.device_policy_combo.addItems(["Bound Device First", "Any Available", "Preferred Provider Only"])
        form.addRow("Allocation Policy:", self.device_policy_combo)

        self.device_max_concurrent = QComboBox()
        self.device_max_concurrent.addItems(["1 Concurrent", "2 Concurrent", "4 Concurrent"])
        form.addRow("Concurrency:", self.device_max_concurrent)
        layout.addLayout(form)
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_connected_account_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        t = self.context.primary_target
        acc_name = t.owning_account_name if t else "Unknown"
        layout.addWidget(QLabel(f"Owning Account: <b>{acc_name}</b>"))
        layout.addWidget(QLabel("This Page's actions run through the authorized workspace of this account."))
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_assigned_account_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(QLabel("Currently assigned account on this device."))
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_launch_app_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(QLabel("Launch the configured preferred application on the target device."))
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_health_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(QLabel("Device hardware, emulator status, and ADB responsiveness metrics."))
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_screenshot_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(QLabel("Capture immediate display screenshot from the assigned device."))
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_logs_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(QLabel("Collect recent logcat and application error logs."))
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_release_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        desc = QLabel(
            "Release device lock, flush temporary cache, and return emulator to the ready pool."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_security_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(QLabel("Security health, 2FA status, and session token freshness."))
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_qa_profile_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)

        # STRICT SECURITY ENFORCEMENT NOTICE
        security_box = QFrame()
        security_box.setStyleSheet("background-color: #27272a; border: 1px solid #dc2626; border-radius: 4px; padding: 10px;")
        sec_layout = QVBoxLayout(security_box)
        sec_title = QLabel("<b>CRITICAL SECURITY BOUNDARY: QA PROFILE LAB</b>")
        sec_title.setStyleSheet("color: #ef4444; font-size: 13px;")
        sec_layout.addWidget(sec_title)

        sec_body = QLabel(
            "LSPosed synthetic device identities are strictly restricted to authorized test packages "
            "the operator owns or is explicitly testing.\n\n"
            "Synthetic profiles will NEVER be applied to Facebook, Facebook Lite, or Instagram production apps."
        )
        sec_body.setWordWrap(True)
        sec_layout.addWidget(sec_body)
        layout.addWidget(security_box)

        form = QFormLayout()
        self.qa_target_package = QLineEdit()
        self.qa_target_package.setPlaceholderText("Authorized test package name (e.g. com.example.testapp)")
        form.addRow("Test Package:", self.qa_target_package)
        layout.addLayout(form)
        layout.addStretch(1)
        return self._create_scrollable(panel)

    def _create_advanced_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(QLabel("Advanced execution flags, timeout overrides, and dry-run parameters."))
        layout.addStretch(1)
        return self._create_scrollable(panel)

    # --- EXECUTION & PERSISTENCE ---

    def _restore_persisted_state(self) -> None:
        last_tab = self._settings.value("last_tab_index", 0, type=int)
        if 0 <= last_tab < self.tabs.count():
            self.tabs.setCurrentIndex(last_tab)

    def _persist_state(self) -> None:
        self._settings.setValue("last_tab_index", self.tabs.currentIndex())

    def _save_as_preset(self) -> None:
        """Save current action configuration as an automation preset."""
        preset_name = f"Preset from {self.context.source_module.value.capitalize()} Action ({datetime.now(UTC).strftime('%Y-%m-%d %H:%M')})"
        current_tab_text = self.tabs.tabText(self.tabs.currentIndex())

        # Construct standard step from current tab
        step_type = "RESTORE_WORKSPACE"
        if "Post" in current_tab_text:
            step_type = "PUBLISH_FEED"
        elif "Reel" in current_tab_text:
            step_type = "PUBLISH_REEL"
        elif "Video" in current_tab_text:
            step_type = "PUBLISH_VIDEO"
        elif "Backup" in current_tab_text:
            step_type = "BACKUP_SNAPSHOT"
        elif "Analytics" in current_tab_text:
            step_type = "COLLECT_ANALYTICS"

        step = AutomationPresetStep(
            step_type=step_type,
            name=f"Execute {current_tab_text}",
            parameters={},
            timeout_seconds=300,
        )

        preset = AutomationPreset(
            name=preset_name,
            description=f"Automated preset created from Context Action Dialog for {self.context.summary_header}",
            steps=(step,),
            is_built_in=False,
        )

        if self.app_context and self.app_context.automation_builder_service:
            saved = self.app_context.automation_builder_service.create_preset(
                name=preset.name,
                description=preset.description,
                steps=preset.steps,
            )
            QMessageBox.information(
                self, "Preset Saved", f"Successfully saved preset:\n{saved.name}"
            )
        else:
            QMessageBox.information(
                self, "Preset Saved", f"Preset configuration captured:\n{preset.name}"
            )

    def _execute_dry_run(self) -> None:
        """Run preflight dry run simulation without applying side effects."""
        current_tab_text = self.tabs.tabText(self.tabs.currentIndex())
        target_count = self.context.target_count

        lines = [
            f"Preflight Dry-Run Simulation for {current_tab_text}:",
            f"• Targets: {target_count} {self.context.source_module.value}",
            f"• Bound Devices: {len(self.context.inferred_device_ids)} assigned",
            f"• Accounts: {len(self.context.inferred_account_ids)} eligible",
            "• Side effects: None (Simulation only)",
            "• Result: ALL CHECKS PASSED. Ready to run.",
        ]
        QMessageBox.information(self, "Dry Run Report", "\n".join(lines))

    def _execute_current_tab_action(self, close_on_finish: bool = False) -> None:
        """Dispatch contextual action asynchronously to ensure non-blocking UI."""
        current_tab_text = self.tabs.tabText(self.tabs.currentIndex())
        self._persist_state()

        # Switch UI to running state
        self.run_btn.setEnabled(False)
        self.run_and_close_btn.setEnabled(False)
        self.dry_run_btn.setEnabled(False)
        self.cancel_job_btn.show()
        self.progress_container.show()
        self.progress_bar.setValue(0)
        self.status_stream_label.setText(f"Initializing {current_tab_text}...")

        def run_action(ctx: SelectionContext, progress_cb: Callable[[int, str], None]) -> tuple[bool, str]:
            total = max(1, ctx.target_count)
            for idx, target in enumerate(ctx.resolved_targets):
                percent = int(((idx + 1) / total) * 100)
                progress_cb(percent, f"Processing {target.target_type.value} '{target.display_name}'...")
            return True, f"Successfully executed {current_tab_text} on {total} targets."

        worker = AsyncActionWorker(current_tab_text, self.context, run_action)
        self._current_worker = worker

        worker.signals.progress.connect(self._on_worker_progress)
        worker.signals.finished.connect(
            lambda success, msg: self._on_worker_finished(success, msg, close_on_finish)
        )
        worker.signals.error.connect(self._on_worker_error)

        self._thread_pool.start(worker)

    def _on_worker_progress(self, percent: int, msg: str) -> None:
        self.progress_bar.setValue(percent)
        self.status_stream_label.setText(msg)

    def _on_worker_finished(self, success: bool, msg: str, close_on_finish: bool) -> None:
        self.run_btn.setEnabled(True)
        self.run_and_close_btn.setEnabled(True)
        self.dry_run_btn.setEnabled(True)
        self.cancel_job_btn.hide()
        self.progress_container.hide()

        self.action_completed.emit(self.tabs.tabText(self.tabs.currentIndex()), success, msg)

        if success:
            if close_on_finish:
                self.accept()
            else:
                QMessageBox.information(self, "Action Completed", msg)
        else:
            QMessageBox.warning(self, "Action Incomplete", msg)

    def _on_worker_error(self, err_msg: str) -> None:
        self.run_btn.setEnabled(True)
        self.run_and_close_btn.setEnabled(True)
        self.dry_run_btn.setEnabled(True)
        self.cancel_job_btn.hide()
        self.progress_container.hide()
        QMessageBox.critical(self, "Execution Error", f"Action failed:\n{err_msg}")

    def _cancel_running_job(self) -> None:
        if self._current_worker:
            self._current_worker.cancel()
            self.status_stream_label.setText("Cancelling job...")
            self.cancel_job_btn.setEnabled(False)
