from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QDateTime, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.widgets import Panel, PrimaryButton, SecondaryButton, StatusChip
from sp_farms.domain.composer import (
    DraftPost,
    PostType,
    PublishDestination,
)

if TYPE_CHECKING:
    from sp_farms.application.caption_ai_service import CaptionAIService
    from sp_farms.application.composer_service import ComposerService
    from sp_farms.application.content_service import ContentService


class ComposerDialog(QDialog):
    """Publishing composer dialog for Posts, Reels, and Stories."""

    draft_saved = Signal(str)  # draft id

    def __init__(
        self,
        composer_service: "ComposerService",
        content_service: "ContentService",
        caption_ai_service: "CaptionAIService | None" = None,
        draft: DraftPost | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("SP-Farms — Post & Reel Composer")
        self.resize(1100, 750)
        self.setMinimumSize(950, 650)

        self._composer_service = composer_service
        self._content_service = content_service
        self._caption_ai_service = caption_ai_service
        self._current_draft = draft
        self._destinations: list[PublishDestination] = []
        self._selected_media_ids: list[str] = list(draft.media_asset_ids) if draft else []
        self._thumbnail_id: str | None = draft.thumbnail_asset_id if draft else None

        self._build_ui()
        self._load_destinations()
        if self._current_draft:
            self._populate_draft(self._current_draft)
        else:
            self._update_preview()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(4)

        # -------------------------------------------------------------
        # Left Panel: Composition Editor
        # -------------------------------------------------------------
        editor_scroll = QScrollArea()
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setFrameShape(QFrame.Shape.NoFrame)

        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setContentsMargins(6, 6, 12, 6)
        editor_layout.setSpacing(10)

        # Title / Draft Name
        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("Internal draft title (e.g. Summer Promo #1)")
        self.txt_title.textChanged.connect(self._on_draft_changed)

        # Destination & Post Type
        dest_type_layout = QHBoxLayout()
        self.cmb_dest = QComboBox()
        self.cmb_dest.currentIndexChanged.connect(self._on_destination_changed)

        self.cmb_post_type = QComboBox()
        self.cmb_post_type.addItems(["Feed Post", "Reel", "Story"])
        self.cmb_post_type.currentIndexChanged.connect(self._on_post_type_changed)

        dest_type_layout.addWidget(QLabel("Destination:"))
        dest_type_layout.addWidget(self.cmb_dest, 2)
        dest_type_layout.addWidget(QLabel("Type:"))
        dest_type_layout.addWidget(self.cmb_post_type, 1)

        # Caption text
        caption_box = QVBoxLayout()
        caption_header = QHBoxLayout()
        lbl_caption = QLabel("Caption / Description:")
        lbl_caption.setStyleSheet("font-weight: 600;")
        self.lbl_char_count = QLabel("0 chars")
        self.lbl_char_count.setStyleSheet("color: #718096; font-size: 11px;")
        caption_header.addWidget(lbl_caption)
        caption_header.addStretch()
        caption_header.addWidget(self.lbl_char_count)

        self.txt_caption = QTextEdit()
        self.txt_caption.setPlaceholderText(
            "Write your post copy, hashtags, or template variables..."
        )
        self.txt_caption.setMinimumHeight(120)
        self.txt_caption.textChanged.connect(self._on_caption_changed)

        caption_box.addLayout(caption_header)
        caption_box.addWidget(self.txt_caption)

        # Quick template & hashtag & AI insert helpers
        tag_bar = QHBoxLayout()
        btn_add_template = SecondaryButton("Insert Template")
        btn_add_template.clicked.connect(self._on_insert_template)
        btn_add_tag = SecondaryButton("Insert Tags")
        btn_add_tag.clicked.connect(self._on_insert_hashtag)
        self.btn_ai_assist = PrimaryButton("✨ AI Assist...")
        self.btn_ai_assist.clicked.connect(self._on_open_ai_assist)

        tag_bar.addWidget(btn_add_template)
        tag_bar.addWidget(btn_add_tag)
        tag_bar.addWidget(self.btn_ai_assist)
        tag_bar.addStretch()
        caption_box.addLayout(tag_bar)

        # Media Attachments
        media_group = Panel()
        media_layout = QVBoxLayout(media_group)
        media_btn_bar = QHBoxLayout()

        self.btn_select_media = SecondaryButton("Attach Media...")
        self.btn_select_media.clicked.connect(self._on_select_media)
        self.btn_clear_media = SecondaryButton("Clear Media")
        self.btn_clear_media.clicked.connect(self._on_clear_media)

        media_btn_bar.addWidget(self.btn_select_media)
        media_btn_bar.addWidget(self.btn_clear_media)
        media_btn_bar.addStretch()

        self.lbl_media_summary = QLabel("No media attached")
        self.lbl_media_summary.setStyleSheet("color: #718096; font-size: 12px;")

        media_layout.addLayout(media_btn_bar)
        media_layout.addWidget(self.lbl_media_summary)

        # Options Form: Location, First comment, Scheduling, Approval
        form_panel = Panel()
        form_layout = QFormLayout(form_panel)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.txt_location = QLineEdit()
        self.txt_location.setPlaceholderText("e.g. New York, NY (Optional)")
        self.txt_location.textChanged.connect(self._on_draft_changed)

        self.txt_first_comment = QLineEdit()
        self.txt_first_comment.setPlaceholderText("First comment on Page post (Optional)")
        self.txt_first_comment.textChanged.connect(self._on_draft_changed)

        # Schedule
        sched_box = QHBoxLayout()
        self.chk_schedule = QCheckBox("Schedule for later")
        self.chk_schedule.toggled.connect(self._on_schedule_toggled)

        self.dt_schedule = QDateTimeEdit(QDateTime.currentDateTime().addDays(1))
        self.dt_schedule.setCalendarPopup(True)
        self.dt_schedule.setEnabled(False)
        self.dt_schedule.dateTimeChanged.connect(self._on_draft_changed)

        sched_box.addWidget(self.chk_schedule)
        sched_box.addWidget(self.dt_schedule)
        sched_box.addStretch()

        self.chk_approval = QCheckBox("Requires human review before publishing")
        self.chk_approval.toggled.connect(self._on_draft_changed)

        form_layout.addRow("Location:", self.txt_location)
        form_layout.addRow("First Comment:", self.txt_first_comment)
        form_layout.addRow("Schedule:", sched_box)
        form_layout.addRow("Governance:", self.chk_approval)

        # Assemble editor
        editor_layout.addWidget(QLabel("Title:"))
        editor_layout.addWidget(self.txt_title)
        editor_layout.addLayout(dest_type_layout)
        editor_layout.addLayout(caption_box)
        editor_layout.addWidget(media_group)
        editor_layout.addWidget(form_panel)
        editor_layout.addStretch()

        editor_scroll.setWidget(editor_widget)
        splitter.addWidget(editor_scroll)

        # -------------------------------------------------------------
        # Right Panel: Live Interactive Preview & Validation
        # -------------------------------------------------------------
        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(12, 6, 6, 6)
        preview_layout.setSpacing(10)

        # Header with validation chips
        prev_header = QHBoxLayout()
        lbl_prev_title = QLabel("Live Social Preview")
        lbl_prev_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #2D3748;")
        self.chip_preview_type = StatusChip("Feed Post", "active")
        prev_header.addWidget(lbl_prev_title)
        prev_header.addStretch()
        prev_header.addWidget(self.chip_preview_type)
        preview_layout.addLayout(prev_header)

        # Duplicate Warning Banner
        self.banner_duplicate = QFrame()
        dup_card_css = (
            "background-color: #FEFCBF; border: 1px solid #D69E2E; "
            "border-radius: 6px; padding: 6px;"
        )
        self.banner_duplicate.setStyleSheet(dup_card_css)
        dup_layout = QHBoxLayout(self.banner_duplicate)
        dup_layout.setContentsMargins(8, 4, 8, 4)
        self.lbl_duplicate = QLabel()
        self.lbl_duplicate.setStyleSheet("color: #744210; font-size: 12px; font-weight: 500;")
        dup_layout.addWidget(self.lbl_duplicate)
        self.banner_duplicate.setVisible(False)
        preview_layout.addWidget(self.banner_duplicate)

        # Mockup Card Frame
        self.mockup_card = QFrame()
        self.mockup_card.setStyleSheet(
            "background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px;"
        )
        mockup_layout = QVBoxLayout(self.mockup_card)
        mockup_layout.setContentsMargins(14, 14, 14, 14)
        mockup_layout.setSpacing(10)

        # Author header
        author_layout = QHBoxLayout()
        self.lbl_avatar = QLabel("👤")
        self.lbl_avatar.setStyleSheet(
            "font-size: 20px; background: #EDF2F7; border-radius: 16px; padding: 4px;"
        )
        self.lbl_author = QLabel("Select Destination")
        self.lbl_author.setStyleSheet("font-weight: 700; font-size: 13px; color: #1A202C;")
        self.lbl_post_meta = QLabel("Just now • 🌐")
        self.lbl_post_meta.setStyleSheet("font-size: 11px; color: #718096;")

        author_text_box = QVBoxLayout()
        author_text_box.addWidget(self.lbl_author)
        author_text_box.addWidget(self.lbl_post_meta)

        author_layout.addWidget(self.lbl_avatar)
        author_layout.addLayout(author_text_box)
        author_layout.addStretch()
        mockup_layout.addLayout(author_layout)

        # Mockup Caption
        self.lbl_preview_caption = QLabel("Write a caption to preview your post content.")
        self.lbl_preview_caption.setWordWrap(True)
        self.lbl_preview_caption.setStyleSheet("font-size: 13px; color: #2D3748; line-height: 1.4;")
        mockup_layout.addWidget(self.lbl_preview_caption)

        # Media Box inside mockup
        self.preview_media_box = QLabel("🖼️ No media selected")
        self.preview_media_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_media_box.setMinimumHeight(240)
        media_box_css = (
            "background-color: #F7FAFC; border: 1px dashed #CBD5E0; "
            "border-radius: 6px; color: #A0AEC0;"
        )
        self.preview_media_box.setStyleSheet(media_box_css)
        mockup_layout.addWidget(self.preview_media_box)

        # Mockup Action Bar
        action_bar = QHBoxLayout()
        action_bar.addWidget(QLabel("👍 Like"))
        action_bar.addWidget(QLabel("💬 Comment"))
        action_bar.addWidget(QLabel("↗️ Share"))
        action_bar.addStretch()
        mockup_layout.addLayout(action_bar)

        # Mockup First Comment
        self.lbl_preview_comment = QLabel()
        comment_css = (
            "background: #F7FAFC; border-left: 3px solid #319795; "
            "padding: 6px; font-size: 11px; color: #4A5568;"
        )
        self.lbl_preview_comment.setStyleSheet(comment_css)
        self.lbl_preview_comment.setVisible(False)
        mockup_layout.addWidget(self.lbl_preview_comment)

        preview_layout.addWidget(self.mockup_card)

        # Validation Issues List
        self.panel_validation = Panel()
        val_layout = QVBoxLayout(self.panel_validation)
        val_title = QLabel("Content Validation")
        val_title.setStyleSheet("font-weight: bold; color: #a0aec0; margin-bottom: 4px;")
        val_layout.addWidget(val_title)
        self.list_issues = QListWidget()
        self.list_issues.setMaximumHeight(100)
        self.list_issues.setStyleSheet("border: none; background: transparent; font-size: 12px;")
        val_layout.addWidget(self.list_issues)
        preview_layout.addWidget(self.panel_validation)

        preview_layout.addStretch()
        splitter.addWidget(preview_panel)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter)

        # -------------------------------------------------------------
        # Bottom Button Bar
        # -------------------------------------------------------------
        btn_bar = QHBoxLayout()
        self.btn_check_dup = SecondaryButton("Check Duplicate")
        self.btn_check_dup.clicked.connect(self._on_check_duplicate_explicit)

        self.btn_save_draft = PrimaryButton("Save Draft")
        self.btn_save_draft.clicked.connect(self._on_save_draft)

        btn_cancel = SecondaryButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_bar.addWidget(self.btn_check_dup)
        btn_bar.addStretch()
        btn_bar.addWidget(btn_cancel)
        btn_bar.addWidget(self.btn_save_draft)
        main_layout.addLayout(btn_bar)

    def _load_destinations(self) -> None:
        self._destinations = self._composer_service.get_authorized_destinations()
        self.cmb_dest.clear()
        if not self._destinations:
            self.cmb_dest.addItem("No destinations configured", None)
            return

        for dest in self._destinations:
            self.cmb_dest.addItem(dest.name, dest)

    def _populate_draft(self, draft: DraftPost) -> None:
        self.txt_title.setText(draft.title)
        self.txt_caption.setPlainText(draft.caption)

        if draft.post_type == PostType.FEED:
            self.cmb_post_type.setCurrentIndex(0)
        elif draft.post_type == PostType.REEL:
            self.cmb_post_type.setCurrentIndex(1)
        elif draft.post_type == PostType.STORY:
            self.cmb_post_type.setCurrentIndex(2)

        if draft.destination:
            for i in range(self.cmb_dest.count()):
                d = self.cmb_dest.itemData(i)
                if d and d.id == draft.destination.id:
                    self.cmb_dest.setCurrentIndex(i)
                    break

        if draft.location_name:
            self.txt_location.setText(draft.location_name)
        if draft.first_comment:
            self.txt_first_comment.setText(draft.first_comment)

        if draft.scheduled_at:
            self.chk_schedule.setChecked(True)
            self.dt_schedule.setEnabled(True)
            self.dt_schedule.setDateTime(
                QDateTime.fromSecsSinceEpoch(int(draft.scheduled_at.timestamp()))
            )

        self.chk_approval.setChecked(draft.requires_approval)
        self._refresh_media_summary()
        self._update_preview()

    def _on_destination_changed(self) -> None:
        dest: PublishDestination | None = self.cmb_dest.currentData()
        if dest:
            self.lbl_author.setText(dest.name)
            # Toggle first comment support
            self.txt_first_comment.setEnabled(dest.supports_first_comment)
            if not dest.supports_first_comment:
                self.txt_first_comment.setPlaceholderText(
                    "First comment not supported on this destination"
                )
            else:
                self.txt_first_comment.setPlaceholderText("First comment on Page post (Optional)")
        self._on_draft_changed()

    def _on_post_type_changed(self) -> None:
        idx = self.cmb_post_type.currentIndex()
        names = ["Feed Post", "Reel", "Story"]
        self.chip_preview_type.setText(names[idx])
        self._on_draft_changed()

    def _on_caption_changed(self) -> None:
        text = self.txt_caption.toPlainText()
        self.lbl_char_count.setText(f"{len(text)} chars")
        self._on_draft_changed()

    def _on_schedule_toggled(self, checked: bool) -> None:
        self.dt_schedule.setEnabled(checked)
        self._on_draft_changed()

    def _on_draft_changed(self) -> None:
        self._update_preview()

    def _on_insert_hashtag(self) -> None:
        sets = self._content_service.list_hashtag_sets()
        if not sets:
            QMessageBox.information(
                self,
                "Hashtags",
                "No hashtag sets found in Content Library.\nCreate one under Content Workspace.",
            )
            return

        tag_options = [f"{s.name} ({len(s.hashtags)} tags)" for s in sets]
        dlg = QDialog(self)
        dlg.setWindowTitle("Select Hashtag Set")
        layout = QVBoxLayout(dlg)
        cmb = QComboBox()
        cmb.addItems(tag_options)
        layout.addWidget(QLabel("Choose Hashtag Set:"))
        layout.addWidget(cmb)

        btn_ok = PrimaryButton("Insert")
        btn_ok.clicked.connect(dlg.accept)
        layout.addWidget(btn_ok)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            chosen = sets[cmb.currentIndex()]
            text = self.txt_caption.toPlainText()
            separator = "\n\n" if text.strip() else ""
            self.txt_caption.setPlainText(f"{text}{separator}{chosen.formatted_string()}")

    def _on_insert_template(self) -> None:
        templates = self._content_service.list_caption_templates()
        if not templates:
            QMessageBox.information(
                self,
                "Templates",
                "No caption templates found in Content Library.\nCreate one in Content Workspace.",
            )
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Select Caption Template")
        layout = QVBoxLayout(dlg)
        cmb = QComboBox()
        for t in templates:
            cmb.addItem(f"{t.name} ({len(t.variables)} vars)", t)
        layout.addWidget(QLabel("Choose Template:"))
        layout.addWidget(cmb)

        btn_ok = PrimaryButton("Use Template")
        btn_ok.clicked.connect(dlg.accept)
        layout.addWidget(btn_ok)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            tpl = templates[cmb.currentIndex()]
            text = self.txt_caption.toPlainText()
            separator = "\n\n" if text.strip() else ""
            self.txt_caption.setPlainText(f"{text}{separator}{tpl.content}")

    def _on_open_ai_assist(self) -> None:
        if not self._caption_ai_service:
            QMessageBox.warning(
                self,
                "AI Assist",
                "AI Assistant service is not available in current session.",
            )
            return

        from sp_farms.app.ai_assist_dialog import AiAssistDialog

        dlg = AiAssistDialog(
            caption_ai_service=self._caption_ai_service,
            initial_text=self.txt_caption.toPlainText(),
            parent=self,
        )
        dlg.suggestion_applied.connect(self.txt_caption.setPlainText)
        dlg.exec()

    def _on_select_media(self) -> None:
        assets = self._content_service.list_assets()
        if not assets:
            QMessageBox.information(
                self,
                "Media",
                "No media assets found in Library.\nImport assets in the Content Workspace.",
            )
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Select Media Asset")
        dlg.resize(500, 400)
        layout = QVBoxLayout(dlg)

        asset_list = QListWidget()
        for a in assets:
            label_text = f"{a.file_name} [{a.media_type.value}] - {a.metadata.aspect_ratio}"
            item = QListWidgetItem(label_text)
            item.setData(Qt.ItemDataRole.UserRole, a.id)
            asset_list.addItem(item)
        layout.addWidget(asset_list)

        btn_ok = PrimaryButton("Attach Selected")
        btn_ok.clicked.connect(dlg.accept)
        layout.addWidget(btn_ok)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            cur = asset_list.currentItem()
            if cur:
                asset_id = cur.data(Qt.ItemDataRole.UserRole)
                if asset_id not in self._selected_media_ids:
                    self._selected_media_ids.append(asset_id)
                self._refresh_media_summary()
                self._update_preview()

    def _on_clear_media(self) -> None:
        self._selected_media_ids.clear()
        self._thumbnail_id = None
        self._refresh_media_summary()
        self._update_preview()

    def _refresh_media_summary(self) -> None:
        count = len(self._selected_media_ids)
        if count == 0:
            self.lbl_media_summary.setText("No media attached")
        else:
            self.lbl_media_summary.setText(f"{count} asset(s) attached")

    def _get_current_draft(self) -> DraftPost:
        p_type = PostType.FEED
        if self.cmb_post_type.currentIndex() == 1:
            p_type = PostType.REEL
        elif self.cmb_post_type.currentIndex() == 2:
            p_type = PostType.STORY

        dest = self.cmb_dest.currentData()
        sched_dt = None
        if self.chk_schedule.isChecked():
            qdt = self.dt_schedule.dateTime()
            sched_dt = datetime.fromtimestamp(qdt.toSecsSinceEpoch(), tz=UTC)

        return DraftPost.create(
            title=self.txt_title.text() or "Untitled Draft",
            post_type=p_type,
            destination=dest,
            caption=self.txt_caption.toPlainText(),
            media_asset_ids=self._selected_media_ids,
            thumbnail_asset_id=self._thumbnail_id,
            location_name=self.txt_location.text(),
            first_comment=self.txt_first_comment.text(),
            scheduled_at=sched_dt,
            requires_approval=self.chk_approval.isChecked(),
            draft_id=self._current_draft.id if self._current_draft else None,
        )

    def _update_preview(self) -> None:
        caption = self.txt_caption.toPlainText().strip()
        self.lbl_preview_caption.setText(caption or "Write a caption to preview your post content.")

        # First comment preview
        fc = self.txt_first_comment.text().strip()
        if fc and self.txt_first_comment.isEnabled():
            self.lbl_preview_comment.setText(f"💬 First comment: {fc}")
            self.lbl_preview_comment.setVisible(True)
        else:
            self.lbl_preview_comment.setVisible(False)

        # Media preview thumbnail
        if self._selected_media_ids:
            first_id = self._selected_media_ids[0]
            asset = self._content_service.get_asset(first_id)
            if asset and asset.thumbnail_path and Path(asset.thumbnail_path).exists():
                pixmap = QPixmap(asset.thumbnail_path)
                self.preview_media_box.setPixmap(
                    pixmap.scaled(
                        320,
                        220,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            elif asset:
                self.preview_media_box.setText(f"📎 {asset.file_name} ({asset.media_type.value})")
        else:
            self.preview_media_box.setText("🖼️ No media selected")

        # Validation list
        draft = self._get_current_draft()
        issues = self._composer_service.validate_draft(draft)
        self.list_issues.clear()

        if not issues:
            item = QListWidgetItem("✅ Ready to publish or schedule")
            item.setForeground(Qt.GlobalColor.darkGreen)
            self.list_issues.addItem(item)
        else:
            for issue in issues:
                icon = "❌" if issue.severity == "error" else "⚠️"
                item = QListWidgetItem(f"{icon} [{issue.field}] {issue.message}")
                color = (
                    Qt.GlobalColor.red if issue.severity == "error" else Qt.GlobalColor.darkYellow
                )
                item.setForeground(color)
                self.list_issues.addItem(item)

    def _on_check_duplicate_explicit(self) -> None:
        caption = self.txt_caption.toPlainText()
        warning = self._composer_service.check_duplicate(caption)
        if warning.is_duplicate:
            self.lbl_duplicate.setText(f"⚠️ Duplicate Detected: {warning.reason}")
            self.banner_duplicate.setVisible(True)
        else:
            self.banner_duplicate.setVisible(False)
            QMessageBox.information(
                self,
                "Duplicate Check",
                "No duplicate content detected in library.",
            )

    def _on_save_draft(self) -> None:
        draft = self._get_current_draft()
        issues = self._composer_service.validate_draft(draft)
        errors = [i for i in issues if i.severity == "error"]

        if errors:
            err_msg = "\n".join(f"• {e.message}" for e in errors)
            QMessageBox.warning(
                self,
                "Cannot Save Draft",
                f"Please fix the following errors before saving:\n\n{err_msg}",
            )
            return

        # Check duplicate silently or warn
        warning = self._composer_service.check_duplicate(draft.caption)
        if warning.is_duplicate:
            confirm = QMessageBox.question(
                self,
                "Duplicate Content Warning",
                f"{warning.reason}\n\nDo you want to save this draft anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        item = self._composer_service.save_draft(draft)
        self.draft_saved.emit(item.id)
        QMessageBox.information(self, "Draft Saved", f"Draft '{draft.title}' saved successfully.")
        self.accept()
