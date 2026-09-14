from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QSize,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.composer_dialog import ComposerDialog
from sp_farms.app.media_preview import MediaPreviewDialog
from sp_farms.app.widgets import (
    CompactTable,
    MetricRow,
    Panel,
    PrimaryButton,
    SecondaryButton,
    StatusChip,
)
from sp_farms.application.composer_service import ComposerService
from sp_farms.application.media_prep_service import (
    MediaInspectionService,
    MediaPreparationService,
)
from sp_farms.domain.content import (
    CaptionTemplate,
    HashtagSet,
    MediaAsset,
    MediaType,
)

if TYPE_CHECKING:
    from sp_farms.application.caption_ai_service import CaptionAIService
    from sp_farms.application.content_service import ContentService


ASSET_COLUMNS = (
    ("preview", "Preview"),
    ("file_name", "File Name"),
    ("media_type", "Type"),
    ("resolution", "Resolution"),
    ("size", "Size"),
    ("folder", "Folder"),
    ("tags", "Tags"),
    ("favorite", "Fav"),
    ("created_at", "Date Added"),
)

_ROOT_INDEX = QModelIndex()


class MediaAssetTableModel(QAbstractTableModel):
    def __init__(
        self,
        assets: Sequence[MediaAsset] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._assets = list(assets)
        self._pixmap_cache: dict[str, QPixmap] = {}

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = _ROOT_INDEX) -> int:
        return 0 if parent.isValid() else len(self._assets)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = _ROOT_INDEX) -> int:
        return 0 if parent.isValid() else len(ASSET_COLUMNS)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if not index.isValid() or not (0 <= index.row() < len(self._assets)):
            return None
        asset = self._assets[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return ""  # Thumbnail drawn or via decoration
            elif col == 1:
                return asset.file_name
            elif col == 2:
                return asset.media_type.value
            elif col == 3:
                return asset.metadata.resolution_label
            elif col == 4:
                return asset.metadata.formatted_size
            elif col == 5:
                return asset.folder
            elif col == 6:
                return ", ".join(asset.tags) if asset.tags else "—"
            elif col == 7:
                return "★" if asset.is_favorite else "☆"
            elif col == 8:
                return asset.created_at.strftime("%Y-%m-%d %H:%M")
        elif role == Qt.ItemDataRole.DecorationRole and col == 0:
            thumb_path = asset.thumbnail_path or asset.file_path
            if thumb_path:
                if thumb_path not in self._pixmap_cache:
                    pix = QPixmap(thumb_path)
                    if not pix.isNull():
                        self._pixmap_cache[thumb_path] = pix.scaled(
                            36,
                            36,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                return self._pixmap_cache.get(thumb_path)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (0, 2, 3, 4, 5, 7, 8):
                return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        elif role == Qt.ItemDataRole.ForegroundRole and col == 7 and asset.is_favorite:
            return QColor("#eab308")  # Gold star
        elif role == Qt.ItemDataRole.UserRole:
            return asset

        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(ASSET_COLUMNS)
        ):
            return ASSET_COLUMNS[section][1]
        return None

    def set_assets(self, assets: Sequence[MediaAsset]) -> None:
        self.beginResetModel()
        self._assets = list(assets)
        self.endResetModel()

    def get_asset(self, row: int) -> MediaAsset | None:
        if 0 <= row < len(self._assets):
            return self._assets[row]
        return None


class MediaFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._search_text: str = ""
        self._filter_type: str = "All"
        self._folder_filter: str = "All"

    def set_search_text(self, text: str) -> None:
        self._search_text = text.lower().strip()
        self.invalidate()

    def set_filter_type(self, filter_type: str) -> None:
        self._filter_type = filter_type
        self.invalidate()

    def set_folder_filter(self, folder: str) -> None:
        self._folder_filter = folder
        self.invalidate()

    def filterAcceptsRow(
        self,
        source_row: int,
        source_parent: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        model = self.sourceModel()
        if not isinstance(model, MediaAssetTableModel):
            return True

        asset = model.get_asset(source_row)
        if asset is None:
            return False

        # Type / Tab filters
        if self._filter_type == "Images" and asset.media_type != MediaType.IMAGE:
            return False
        if self._filter_type == "Videos" and asset.media_type != MediaType.VIDEO:
            return False
        if self._filter_type == "Favorites" and not asset.is_favorite:
            return False
        if self._filter_type == "Archived" and not asset.is_archived:
            return False
        if self._filter_type != "Archived" and asset.is_archived:
            return False

        # Folder filter
        if self._folder_filter != "All" and asset.folder != self._folder_filter:
            return False

        # Search text
        if self._search_text:
            text_match = (
                self._search_text in asset.file_name.lower()
                or any(self._search_text in t.lower() for t in asset.tags)
                or self._search_text in asset.folder.lower()
            )
            if not text_match:
                return False

        return True


class MediaInspectorPanel(Panel):
    asset_updated = Signal()

    def __init__(
        self,
        content_service: "ContentService",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._content_service = content_service
        self._current_asset: MediaAsset | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel("Asset Inspector")
        header.setStyleSheet("font-size: 15px; font-weight: 600;")
        layout.addWidget(header)

        # Preview Thumbnail Box
        self.preview_frame = QFrame()
        self.preview_frame.setStyleSheet(
            "background-color: #1e293b; border-radius: 8px; min-height: 180px; max-height: 220px;"
        )
        preview_box = QVBoxLayout(self.preview_frame)
        preview_box.setContentsMargins(4, 4, 4, 4)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_box.addWidget(self.preview_label)
        layout.addWidget(self.preview_frame)

        self.inspect_btn = SecondaryButton("Inspect & Prepare")
        self.inspect_btn.clicked.connect(self._on_open_preview_dialog)
        layout.addWidget(self.inspect_btn)

        # Details Form
        form = QFormLayout()
        form.setSpacing(8)

        self.name_label = QLabel("—")
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet("font-weight: 600;")
        form.addRow("File:", self.name_label)

        self.type_chip = StatusChip("Unknown", "neutral")
        form.addRow("Media Type:", self.type_chip)

        self.resolution_label = QLabel("—")
        form.addRow("Dimensions:", self.resolution_label)

        self.aspect_label = QLabel("—")
        form.addRow("Aspect Ratio:", self.aspect_label)

        self.size_label = QLabel("—")
        form.addRow("File Size:", self.size_label)

        self.hash_label = QLabel("—")
        self.hash_label.setStyleSheet("font-family: monospace; font-size: 11px;")
        self.hash_label.setWordWrap(True)
        form.addRow("SHA-256:", self.hash_label)

        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Folder name")
        form.addRow("Folder:", self.folder_input)

        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("comma, separated, tags")
        form.addRow("Tags:", self.tags_input)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = PrimaryButton("Save Changes")
        self.save_btn.clicked.connect(self._on_save_metadata)
        self.fav_btn = SecondaryButton("★ Favorite")
        self.fav_btn.clicked.connect(self._on_toggle_favorite)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.fav_btn)
        layout.addLayout(btn_layout)

        action_row = QHBoxLayout()
        self.archive_btn = SecondaryButton("Archive")
        self.archive_btn.clicked.connect(self._on_toggle_archive)
        self.delete_btn = SecondaryButton("Delete")
        self.delete_btn.setStyleSheet("color: #ef4444;")
        self.delete_btn.clicked.connect(self._on_delete)
        action_row.addWidget(self.archive_btn)
        action_row.addWidget(self.delete_btn)
        layout.addLayout(action_row)

        layout.addStretch()

    def set_asset(self, asset: MediaAsset | None) -> None:
        self._current_asset = asset
        if asset is None:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("No Asset Selected")
            self.name_label.setText("—")
            self.type_chip.update_state("neutral", text="None")
            self.resolution_label.setText("—")
            self.aspect_label.setText("—")
            self.size_label.setText("—")
            self.hash_label.setText("—")
            self.folder_input.clear()
            self.tags_input.clear()
            self.save_btn.setEnabled(False)
            self.fav_btn.setEnabled(False)
            self.archive_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.inspect_btn.setEnabled(False)
            return

        self.save_btn.setEnabled(True)
        self.fav_btn.setEnabled(True)
        self.archive_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.inspect_btn.setEnabled(True)

        self.name_label.setText(asset.file_name)
        type_tone = "success" if asset.media_type == MediaType.IMAGE else "active"
        self.type_chip.update_state(type_tone, text=asset.media_type.value)
        self.resolution_label.setText(asset.metadata.resolution_label)
        self.aspect_label.setText(asset.metadata.aspect_ratio or "—")
        self.size_label.setText(asset.metadata.formatted_size)
        self.hash_label.setText(
            f"{asset.metadata.sha256_hash[:16]}...{asset.metadata.sha256_hash[-8:]}"
        )
        self.folder_input.setText(asset.folder)
        self.tags_input.setText(", ".join(asset.tags))
        self.fav_btn.setText("★ Unfavorite" if asset.is_favorite else "☆ Favorite")
        self.archive_btn.setText("Restore" if asset.is_archived else "Archive")

        # Load Thumbnail
        thumb_path = asset.thumbnail_path or asset.file_path
        if thumb_path and Path(thumb_path).exists():
            pix = QPixmap(thumb_path)
            if not pix.isNull():
                self.preview_label.setPixmap(
                    pix.scaled(
                        200,
                        200,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self.preview_label.setText("")
            else:
                self.preview_label.setPixmap(QPixmap())
                self.preview_label.setText(f"[{asset.media_type.value}]")
        else:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText(f"[{asset.media_type.value}]")

    def _on_save_metadata(self) -> None:
        if not self._current_asset:
            return
        folder = self.folder_input.text().strip() or "default"
        raw_tags = self.tags_input.text().split(",")
        tags = [t.strip() for t in raw_tags if t.strip()]
        updated = self._content_service.update_asset(
            self._current_asset.id,
            folder=folder,
            tags=tags,
        )
        if updated:
            self.set_asset(updated)
            self.asset_updated.emit()

    def _on_toggle_favorite(self) -> None:
        if not self._current_asset:
            return
        updated = self._content_service.toggle_asset_favorite(self._current_asset.id)
        if updated:
            self.set_asset(updated)
            self.asset_updated.emit()

    def _on_toggle_archive(self) -> None:
        if not self._current_asset:
            return
        if self._current_asset.is_archived:
            updated = self._content_service.unarchive_asset(self._current_asset.id)
        else:
            updated = self._content_service.archive_asset(self._current_asset.id)
        if updated:
            self.set_asset(updated)
            self.asset_updated.emit()

    def _on_delete(self) -> None:
        if not self._current_asset:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Asset",
            f"Are you sure you want to permanently delete '{self._current_asset.file_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self._content_service.delete_asset(self._current_asset.id)
            self.set_asset(None)
            self.asset_updated.emit()

    def _on_open_preview_dialog(self) -> None:
        if not self._current_asset:
            return
        output_dir = Path(self._current_asset.file_path).parent / "prepared"
        inspector = MediaInspectionService()
        prep = MediaPreparationService(output_dir=output_dir)
        dialog = MediaPreviewDialog(
            file_path=self._current_asset.file_path,
            inspection_service=inspector,
            prep_service=prep,
            parent=self,
        )
        dialog.exec()


class ContentWorkspace(QWidget):
    def __init__(
        self,
        content_service: "ContentService",
        composer_service: ComposerService | None = None,
        caption_ai_service: "CaptionAIService | None" = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._content_service = content_service
        self._composer_service = composer_service or ComposerService(
            unit_of_work=content_service._uow,
            content_repo_factory=content_service._repo_factory,
        )
        self._caption_ai_service = caption_ai_service
        self.setAcceptDrops(True)
        self._build_ui()
        self.reload_data()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(10)

        # Top Bar: Header + Metrics + Quick Import
        top_bar = QHBoxLayout()
        header_box = QVBoxLayout()
        title = QLabel("Content Library")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        subtitle = QLabel(
            "Reusable media assets, caption templates, hashtag sets, and composed items."
        )
        subtitle.setStyleSheet("color: #64748b; font-size: 12px;")
        header_box.addWidget(title)
        header_box.addWidget(subtitle)
        top_bar.addLayout(header_box)
        top_bar.addStretch()

        self.import_btn = SecondaryButton("+ Import Media")
        self.import_btn.clicked.connect(self._on_import_dialog)
        top_bar.addWidget(self.import_btn)

        self.composer_btn = PrimaryButton("✨ Compose Post/Reel")
        self.composer_btn.clicked.connect(self._on_open_composer)
        top_bar.addWidget(self.composer_btn)

        layout.addLayout(top_bar)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #334155; "
            "border-radius: 8px; background: #0f172a; }"
            "QTabBar::tab { padding: 8px 18px; font-weight: 600; }"
        )

        # Tab 1: Media Library
        self.media_tab = self._build_media_tab()
        self.tabs.addTab(self.media_tab, "Media Library")

        # Tab 2: Caption Templates & Hashtags
        self.templates_tab = self._build_templates_tab()
        self.tabs.addTab(self.templates_tab, "Captions & Hashtags")

        # Tab 3: Content Items
        self.items_tab = self._build_items_tab()
        self.tabs.addTab(self.items_tab, "Composed Items")

        layout.addWidget(self.tabs)

    def _build_media_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Metric Row
        self.metrics = MetricRow(
            [
                ("Total Assets", "0"),
                ("Images", "0"),
                ("Videos", "0"),
                ("Storage Used", "0 MB"),
            ]
        )
        layout.addWidget(self.metrics)

        # Filter Strip
        filter_strip = QHBoxLayout()
        filter_strip.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search file name, tags, folder...")
        self.search_input.textChanged.connect(self._on_search_changed)
        filter_strip.addWidget(self.search_input, stretch=2)

        self.type_filter = QComboBox()
        self.type_filter.addItems(["All", "Images", "Videos", "Favorites", "Archived"])
        self.type_filter.currentTextChanged.connect(self._on_filter_changed)
        filter_strip.addWidget(self.type_filter)

        self.folder_filter = QComboBox()
        self.folder_filter.addItems(["All Folders"])
        self.folder_filter.currentTextChanged.connect(self._on_folder_filter_changed)
        filter_strip.addWidget(self.folder_filter)

        self.refresh_btn = SecondaryButton("Refresh")
        self.refresh_btn.clicked.connect(self.reload_data)
        filter_strip.addWidget(self.refresh_btn)

        layout.addLayout(filter_strip)

        # Main Splitter: Table | Inspector
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Table
        self.table_model = MediaAssetTableModel()
        self.proxy_model = MediaFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)

        self.table = CompactTable()
        self.table.setModel(self.proxy_model)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setIconSize(QSize(36, 36))
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        splitter.addWidget(self.table)

        # Inspector Panel
        self.inspector = MediaInspectorPanel(self._content_service)
        self.inspector.asset_updated.connect(self.reload_data)
        splitter.addWidget(self.inspector)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)
        return widget

    def _build_templates_tab(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # Left Column: Caption Templates
        left_box = QVBoxLayout()
        lbl1 = QLabel("Caption Templates")
        lbl1.setStyleSheet("font-weight: 600; font-size: 14px;")
        left_box.addWidget(lbl1)

        self.template_list = QListWidget()
        self.template_list.itemClicked.connect(self._on_template_selected)
        left_box.addWidget(self.template_list)

        t_form = QFormLayout()
        self.t_name_input = QLineEdit()
        self.t_name_input.setPlaceholderText("Template Name")
        t_form.addRow("Name:", self.t_name_input)

        self.t_content_input = QTextEdit()
        self.t_content_input.setPlaceholderText("Caption content with {variable} placeholders...")
        t_form.addRow("Content:", self.t_content_input)

        left_box.addLayout(t_form)

        t_btns = QHBoxLayout()
        self.add_template_btn = PrimaryButton("+ Save Template")
        self.add_template_btn.clicked.connect(self._on_save_template)
        self.del_template_btn = SecondaryButton("Delete")
        self.del_template_btn.clicked.connect(self._on_delete_template)
        t_btns.addWidget(self.add_template_btn)
        t_btns.addWidget(self.del_template_btn)
        left_box.addLayout(t_btns)

        layout.addLayout(left_box)

        # Right Column: Hashtag Sets
        right_box = QVBoxLayout()
        lbl2 = QLabel("Hashtag Sets")
        lbl2.setStyleSheet("font-weight: 600; font-size: 14px;")
        right_box.addWidget(lbl2)

        self.hashtag_list = QListWidget()
        self.hashtag_list.itemClicked.connect(self._on_hashtag_selected)
        right_box.addWidget(self.hashtag_list)

        h_form = QFormLayout()
        self.h_name_input = QLineEdit()
        self.h_name_input.setPlaceholderText("Hashtag Set Name")
        h_form.addRow("Name:", self.h_name_input)

        self.h_tags_input = QTextEdit()
        self.h_tags_input.setPlaceholderText("#farm #organic #fresh (space or newline separated)")
        h_form.addRow("Tags:", self.h_tags_input)

        right_box.addLayout(h_form)

        h_btns = QHBoxLayout()
        self.add_hashtag_btn = PrimaryButton("+ Save Hashtag Set")
        self.add_hashtag_btn.clicked.connect(self._on_save_hashtag_set)
        self.del_hashtag_btn = SecondaryButton("Delete")
        self.del_hashtag_btn.clicked.connect(self._on_delete_hashtag_set)
        h_btns.addWidget(self.add_hashtag_btn)
        h_btns.addWidget(self.del_hashtag_btn)
        right_box.addLayout(h_btns)

        layout.addLayout(right_box)
        return widget

    def _build_items_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        lbl = QLabel("Composed Content Items")
        lbl.setStyleSheet("font-weight: 600; font-size: 14px;")
        layout.addWidget(lbl)

        self.items_list = QListWidget()
        layout.addWidget(self.items_list)

        item_form = QFormLayout()
        self.item_title_input = QLineEdit()
        self.item_title_input.setPlaceholderText("Post title...")
        item_form.addRow("Title:", self.item_title_input)

        self.item_body_input = QTextEdit()
        self.item_body_input.setPlaceholderText("Composed post text / copy...")
        item_form.addRow("Body:", self.item_body_input)

        layout.addLayout(item_form)

        btn_box = QHBoxLayout()
        self.create_item_btn = PrimaryButton("+ Create Draft Item")
        self.create_item_btn.clicked.connect(self._on_create_item)
        btn_box.addWidget(self.create_item_btn)
        btn_box.addStretch()
        layout.addLayout(btn_box)

        return widget

    # -------------------------------------------------------------------------
    # Drag & Drop Import
    # -------------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        imported = 0
        for url in urls:
            path = Path(url.toLocalFile())
            if path.exists() and path.is_file():
                try:
                    self._content_service.import_media(path)
                    imported += 1
                except Exception as e:
                    QMessageBox.warning(self, "Import Error", f"Failed to import {path.name}: {e}")
        if imported > 0:
            self.reload_data()

    # -------------------------------------------------------------------------
    # Actions & Reloads
    # -------------------------------------------------------------------------

    def reload_data(self) -> None:
        assets = self._content_service.list_assets(limit=1000, is_archived=None)
        self.table_model.set_assets(assets)

        # Update Metrics
        total_count = len(assets)
        images = sum(1 for a in assets if a.media_type == MediaType.IMAGE)
        videos = sum(1 for a in assets if a.media_type == MediaType.VIDEO)
        total_bytes = sum(a.metadata.file_size_bytes for a in assets)
        size_mb = total_bytes / (1024 * 1024)

        if len(self.metrics.value_labels) >= 4:
            self.metrics.value_labels[0].setText(str(total_count))
            self.metrics.value_labels[1].setText(str(images))
            self.metrics.value_labels[2].setText(str(videos))
            self.metrics.value_labels[3].setText(f"{size_mb:.1f} MB")

        # Update Folders dropdown
        folders = self._content_service.list_folders()
        cur_folder = self.folder_filter.currentText()
        self.folder_filter.blockSignals(True)
        self.folder_filter.clear()
        self.folder_filter.addItem("All Folders")
        for f in folders:
            self.folder_filter.addItem(f)
        idx = self.folder_filter.findText(cur_folder)
        if idx >= 0:
            self.folder_filter.setCurrentIndex(idx)
        self.folder_filter.blockSignals(False)

        # Reload Templates & Hashtags
        self._reload_templates()
        self._reload_hashtags()
        self._reload_items()

    def _reload_templates(self) -> None:
        templates = self._content_service.list_caption_templates()
        self.template_list.clear()
        for t in templates:
            item = QListWidgetItem(f"{t.name} ({len(t.variables)} vars)")
            item.setData(Qt.ItemDataRole.UserRole, t)
            self.template_list.addItem(item)

    def _reload_hashtags(self) -> None:
        hsets = self._content_service.list_hashtag_sets()
        self.hashtag_list.clear()
        for h in hsets:
            item = QListWidgetItem(f"{h.name} [{h.category}] — {len(h.hashtags)} tags")
            item.setData(Qt.ItemDataRole.UserRole, h)
            self.hashtag_list.addItem(item)

    def _reload_items(self) -> None:
        items = self._content_service.list_content_items(limit=100)
        self.items_list.clear()
        for i in items:
            row = QListWidgetItem(f"[{i.status.value}] {i.title} (media: {len(i.media_asset_ids)})")
            row.setData(Qt.ItemDataRole.UserRole, i)
            self.items_list.addItem(row)

    def _on_selection_changed(self) -> None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            self.inspector.set_asset(None)
            return
        proxy_idx = indexes[0]
        source_idx = self.proxy_model.mapToSource(proxy_idx)
        asset = self.table_model.get_asset(source_idx.row())
        self.inspector.set_asset(asset)

    def _on_search_changed(self, text: str) -> None:
        self.proxy_model.set_search_text(text)

    def _on_filter_changed(self, filter_type: str) -> None:
        self.proxy_model.set_filter_type(filter_type)

    def _on_folder_filter_changed(self, folder: str) -> None:
        val = "All" if folder == "All Folders" else folder
        self.proxy_model.set_folder_filter(val)

    def _on_import_dialog(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Media Assets",
            "",
            "Media Files (*.jpg *.jpeg *.png *.gif *.mp4 *.mov *.webp);;All Files (*.*)",
        )
        if files:
            imported = 0
            for f in files:
                try:
                    self._content_service.import_media(f)
                    imported += 1
                except Exception as e:
                    QMessageBox.warning(self, "Import Failed", f"Could not import {f}: {e}")
            if imported:
                self.reload_data()

    def _on_save_template(self) -> None:
        name = self.t_name_input.text().strip()
        content = self.t_content_input.toPlainText().strip()
        if not name or not content:
            QMessageBox.information(self, "Validation", "Template name and content are required.")
            return
        # Detect variables in format {name}
        import re

        vars_found = tuple(set(re.findall(r"\{([a-zA-Z0-9_]+)\}", content)))
        self._content_service.create_caption_template(
            name=name,
            content=content,
            variables=vars_found,
        )
        self.t_name_input.clear()
        self.t_content_input.clear()
        self._reload_templates()

    def _on_template_selected(self, item: QListWidgetItem) -> None:
        t: CaptionTemplate = item.data(Qt.ItemDataRole.UserRole)
        if t:
            self.t_name_input.setText(t.name)
            self.t_content_input.setPlainText(t.content)

    def _on_delete_template(self) -> None:
        item = self.template_list.currentItem()
        if item:
            t: CaptionTemplate = item.data(Qt.ItemDataRole.UserRole)
            if t:
                self._content_service.delete_caption_template(t.id)
                self.t_name_input.clear()
                self.t_content_input.clear()
                self._reload_templates()

    def _on_save_hashtag_set(self) -> None:
        name = self.h_name_input.text().strip()
        raw = self.h_tags_input.toPlainText().strip()
        if not name or not raw:
            QMessageBox.information(self, "Validation", "Hashtag set name and tags are required.")
            return
        tags = [t for t in raw.replace("\n", " ").split(" ") if t.strip()]
        self._content_service.create_hashtag_set(name=name, hashtags=tags)
        self.h_name_input.clear()
        self.h_tags_input.clear()
        self._reload_hashtags()

    def _on_hashtag_selected(self, item: QListWidgetItem) -> None:
        h: HashtagSet = item.data(Qt.ItemDataRole.UserRole)
        if h:
            self.h_name_input.setText(h.name)
            self.h_tags_input.setPlainText(" ".join(h.hashtags))

    def _on_delete_hashtag_set(self) -> None:
        item = self.hashtag_list.currentItem()
        if item:
            h: HashtagSet = item.data(Qt.ItemDataRole.UserRole)
            if h:
                self._content_service.delete_hashtag_set(h.id)
                self.h_name_input.clear()
                self.h_tags_input.clear()
                self._reload_hashtags()

    def _on_create_item(self) -> None:
        title = self.item_title_input.text().strip()
        body = self.item_body_input.toPlainText().strip()
        if not title:
            QMessageBox.information(self, "Validation", "Item title is required.")
            return
        self._content_service.create_content_item(title=title, body=body)
        self.item_title_input.clear()
        self.item_body_input.clear()
        self._reload_items()

    def _on_open_composer(self) -> None:
        dialog = ComposerDialog(
            composer_service=self._composer_service,
            content_service=self._content_service,
            caption_ai_service=self._caption_ai_service,
            parent=self,
        )
        dialog.draft_saved.connect(lambda _: self._reload_items())
        dialog.exec()
