import csv
from collections.abc import Sequence
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QPoint,
    QRunnable,
    QSortFilterProxyModel,
    Qt,
    QThreadPool,
    Signal,
)
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.widgets import (
    CompactTable,
    MetricRow,
    Panel,
    PrimaryButton,
    SecondaryButton,
    StatusChip,
)
from sp_farms.application.asset_sync_service import AssetSyncService
from sp_farms.domain.assets import AssetHealthState, Group, Page, SyncResult

if TYPE_CHECKING:
    from sp_farms.application.account_service import AccountService
    from sp_farms.application.context import ApplicationContext
    from sp_farms.application.selection_context_service import SelectionContextService


PAGE_COLUMNS = (
    "Name",
    "Page ID",
    "Account",
    "Category",
    "Permissions / Tasks",
    "Publishing",
    "Followers",
    "Health",
    "Last Synced",
)

GROUP_COLUMNS = (
    "Name",
    "Group ID",
    "Account",
    "Privacy",
    "Role",
    "Posting",
    "Members",
    "Health",
    "Last Synced",
)


class PageFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._filter_mode = "All"
        self._account_filter = "All"

    def set_filter_mode(self, mode: str) -> None:
        self._filter_mode = mode
        self.invalidate()

    def set_account_filter(self, account: str) -> None:
        self._account_filter = account
        self.invalidate()

    def filterAcceptsRow(
        self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex
    ) -> bool:
        model = self.sourceModel()
        if model is None:
            return False

        # Account filter
        if self._account_filter != "All":
            acc_idx = model.index(source_row, 2, source_parent)
            acc_val = str(model.data(acc_idx, Qt.ItemDataRole.DisplayRole) or "")
            if self._account_filter.casefold() not in acc_val.casefold():
                return False

        # Health/Eligibility filter
        if self._filter_mode != "All":
            health_idx = model.index(source_row, 7, source_parent)
            health_val = str(model.data(health_idx, Qt.ItemDataRole.DisplayRole) or "")
            publishing_idx = model.index(source_row, 5, source_parent)
            publishing_val = str(model.data(publishing_idx, Qt.ItemDataRole.DisplayRole) or "")

            if self._filter_mode == "Publishing Eligible" and publishing_val != "Eligible":
                return False
            if self._filter_mode == "Stale / Review" and health_val != "Stale":
                return False
            if self._filter_mode == "Healthy" and health_val != "Healthy":
                return False

        # Text search across name, ID, category, tasks
        pattern = self.filterRegularExpression().pattern()
        if not pattern:
            return True

        for col in (0, 1, 2, 3, 4):
            idx = model.index(source_row, col, source_parent)
            text = str(model.data(idx, Qt.ItemDataRole.DisplayRole) or "")
            if pattern.casefold() in text.casefold():
                return True
        return False


class GroupFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._filter_mode = "All"
        self._account_filter = "All"

    def set_filter_mode(self, mode: str) -> None:
        self._filter_mode = mode
        self.invalidate()

    def set_account_filter(self, account: str) -> None:
        self._account_filter = account
        self.invalidate()

    def filterAcceptsRow(
        self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex
    ) -> bool:
        model = self.sourceModel()
        if model is None:
            return False

        # Account filter
        if self._account_filter != "All":
            acc_idx = model.index(source_row, 2, source_parent)
            acc_val = str(model.data(acc_idx, Qt.ItemDataRole.DisplayRole) or "")
            if self._account_filter.casefold() not in acc_val.casefold():
                return False

        # Role/Health/Eligibility filter
        if self._filter_mode != "All":
            role_idx = model.index(source_row, 4, source_parent)
            role_val = str(model.data(role_idx, Qt.ItemDataRole.DisplayRole) or "")
            health_idx = model.index(source_row, 7, source_parent)
            health_val = str(model.data(health_idx, Qt.ItemDataRole.DisplayRole) or "")
            posting_idx = model.index(source_row, 5, source_parent)
            posting_val = str(model.data(posting_idx, Qt.ItemDataRole.DisplayRole) or "")

            if self._filter_mode == "Admin Only" and "ADMIN" not in role_val.upper():
                return False
            if self._filter_mode == "Posting Eligible" and posting_val != "Eligible":
                return False
            if self._filter_mode == "Stale / Review" and health_val != "Stale":
                return False
            if self._filter_mode == "Healthy" and health_val != "Healthy":
                return False

        # Text search across name, ID, privacy, role
        pattern = self.filterRegularExpression().pattern()
        if not pattern:
            return True

        for col in (0, 1, 2, 3, 4):
            idx = model.index(source_row, col, source_parent)
            text = str(model.data(idx, Qt.ItemDataRole.DisplayRole) or "")
            if pattern.casefold() in text.casefold():
                return True
        return False


class SyncWorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)


class SyncWorker(QRunnable):
    def __init__(
        self,
        service: AssetSyncService,
        account_ids: Sequence[str],
    ) -> None:
        super().__init__()
        self.service = service
        self.account_ids = account_ids
        self.signals = SyncWorkerSignals()

    def run(self) -> None:
        results: list[SyncResult] = []
        try:
            for acc_id in self.account_ids:
                res = self.service.sync_account_assets(acc_id)
                results.append(res)
            self.signals.finished.emit(results)
        except Exception as exc:
            self.signals.error.emit(str(exc))


class AssetInspectorPanel(Panel):
    route_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("assetInspectorPanel")
        self.setMinimumWidth(280)
        self.setMaximumWidth(360)
        self._current_page: Page | None = None
        self._current_group: Group | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        self.title_label = QLabel("Select an Asset")
        self.title_label.setStyleSheet("font-weight: 700; font-size: 14px;")
        self.title_label.setWordWrap(True)
        self.id_label = QLabel("No selection")
        self.id_label.setProperty("muted", True)
        header_text.addWidget(self.title_label)
        header_text.addWidget(self.id_label)
        header_layout.addLayout(header_text, stretch=1)

        self.health_chip = StatusChip("Neutral", "neutral")
        header_layout.addWidget(self.health_chip, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header_layout)

        # Separator line
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setProperty("muted", True)
        layout.addWidget(sep1)

        # Details Form
        details_form = QFormLayout()
        details_form.setSpacing(6)
        self.account_label = QLabel("—")
        self.type_label = QLabel("—")
        self.role_or_tasks_label = QLabel("—")
        self.role_or_tasks_label.setWordWrap(True)
        self.eligibility_chip = StatusChip("Restricted", "neutral")
        self.metrics_label = QLabel("—")
        self.synced_label = QLabel("—")

        details_form.addRow("Type:", self.type_label)
        details_form.addRow("Account:", self.account_label)
        details_form.addRow("Roles / Tasks:", self.role_or_tasks_label)
        details_form.addRow("Publishing:", self.eligibility_chip)
        details_form.addRow("Stats:", self.metrics_label)
        details_form.addRow("Last Synced:", self.synced_label)
        layout.addLayout(details_form)

        # Shortcuts Section
        shortcuts_heading = QLabel("Operational Shortcuts")
        shortcuts_heading.setStyleSheet("font-weight: 600; margin-top: 4px;")
        layout.addWidget(shortcuts_heading)

        shortcuts_layout = QVBoxLayout()
        shortcuts_layout.setSpacing(6)

        self.recent_content_btn = SecondaryButton("Recent Content")
        self.recent_content_btn.setToolTip("Jump to recent published content for this asset")
        self.recent_content_btn.clicked.connect(lambda: self.route_requested.emit("Content"))

        self.content_queue_btn = SecondaryButton("Content Queue")
        self.content_queue_btn.setToolTip("View pending and queued automation jobs")
        self.content_queue_btn.clicked.connect(lambda: self.route_requested.emit("Automation"))

        self.analytics_btn = SecondaryButton("View Analytics")
        self.analytics_btn.setToolTip("View engagement, reach, and performance analytics")
        self.analytics_btn.clicked.connect(lambda: self.route_requested.emit("Analytics"))

        shortcuts_layout.addWidget(self.recent_content_btn)
        shortcuts_layout.addWidget(self.content_queue_btn)
        shortcuts_layout.addWidget(self.analytics_btn)
        layout.addLayout(shortcuts_layout)

        # Notes / Internal Tags Section
        notes_heading = QLabel("Internal Notes & Tags")
        notes_heading.setStyleSheet("font-weight: 600; margin-top: 4px;")
        layout.addWidget(notes_heading)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Operator notes, posting schedule, or campaign tags...")
        self.notes_edit.setMaximumHeight(80)
        layout.addWidget(self.notes_edit)

        layout.addStretch(1)

    def inspect_page(self, page: Page | None, account_name: str = "") -> None:
        self._current_page = page
        self._current_group = None
        if page is None:
            self._reset_view()
            return

        self.title_label.setText(page.name)
        self.id_label.setText(f"ID: {page.page_id}")
        health_state = "success" if page.health == AssetHealthState.HEALTHY else "warning"
        self.health_chip.update_state(health_state, page.health.value.capitalize())

        self.type_label.setText("Facebook Page")
        self.account_label.setText(account_name or page.account_id)

        tasks_str = ", ".join(page.tasks) if page.tasks else "None"
        self.role_or_tasks_label.setText(tasks_str)

        can_pub = page.is_publishing_eligible()
        self.eligibility_chip.update_state(
            "success" if can_pub else "neutral",
            "Eligible" if can_pub else "Restricted",
        )

        self.metrics_label.setText(
            f"{page.followers_count:,} followers • {page.likes_count:,} likes"
        )
        synced_str = (
            page.last_synced_at.strftime("%Y-%m-%d %H:%M UTC") if page.last_synced_at else "Never"
        )
        self.synced_label.setText(synced_str)

        self.recent_content_btn.setEnabled(True)
        self.content_queue_btn.setEnabled(True)
        self.analytics_btn.setEnabled(True)

    def inspect_group(self, group: Group | None, account_name: str = "") -> None:
        self._current_group = group
        self._current_page = None
        if group is None:
            self._reset_view()
            return

        self.title_label.setText(group.name)
        self.id_label.setText(f"ID: {group.group_id}")
        health_state = "success" if group.health == AssetHealthState.HEALTHY else "warning"
        self.health_chip.update_state(health_state, group.health.value.capitalize())

        self.type_label.setText("Facebook Group")
        self.account_label.setText(account_name or group.account_id)
        self.role_or_tasks_label.setText(f"{group.role} ({group.privacy})")

        can_post = group.is_posting_eligible()
        self.eligibility_chip.update_state(
            "success" if can_post else "neutral",
            "Eligible" if can_post else "Restricted",
        )

        self.metrics_label.setText(f"{group.member_count:,} members")
        synced_str = (
            group.last_synced_at.strftime("%Y-%m-%d %H:%M UTC") if group.last_synced_at else "Never"
        )
        self.synced_label.setText(synced_str)

        self.recent_content_btn.setEnabled(True)
        self.content_queue_btn.setEnabled(True)
        self.analytics_btn.setEnabled(True)

    def _reset_view(self) -> None:
        self.title_label.setText("Select an Asset")
        self.id_label.setText("No selection")
        self.health_chip.update_state("neutral", "Neutral")
        self.type_label.setText("—")
        self.account_label.setText("—")
        self.role_or_tasks_label.setText("—")
        self.eligibility_chip.update_state("neutral", "Restricted")
        self.metrics_label.setText("—")
        self.synced_label.setText("—")
        self.recent_content_btn.setEnabled(False)
        self.content_queue_btn.setEnabled(False)
        self.analytics_btn.setEnabled(False)


class PagesGroupsWorkspace(QWidget):
    route_requested = Signal(str)

    def __init__(
        self,
        sync_service: AssetSyncService | None = None,
        account_service: "AccountService | None" = None,
        parent: QWidget | None = None,
        selection_context_service: "SelectionContextService | None" = None,
        app_context: "ApplicationContext | None" = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("pagesGroupsWorkspace")
        self._sync_service = sync_service
        self._account_service = account_service
        self._selection_context_service = selection_context_service
        self._app_context = app_context

        self._pages: list[Page] = []
        self._groups: list[Group] = []
        self._account_names: dict[str, str] = {}

        self._init_models()
        self._init_ui()

    def _init_models(self) -> None:
        # Pages model
        self.pages_model = QStandardItemModel()
        self.pages_model.setHorizontalHeaderLabels(list(PAGE_COLUMNS))
        self.pages_proxy = PageFilterProxyModel(self)
        self.pages_proxy.setSourceModel(self.pages_model)

        # Groups model
        self.groups_model = QStandardItemModel()
        self.groups_model.setHorizontalHeaderLabels(list(GROUP_COLUMNS))
        self.groups_proxy = GroupFilterProxyModel(self)
        self.groups_proxy.setSourceModel(self.groups_model)

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Header title and tab bar
        header_row = QHBoxLayout()
        heading = QLabel("Pages & Groups")
        heading.setProperty("heading", True)
        header_row.addWidget(heading)
        header_row.addStretch(1)

        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("assetTabWidget")
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        header_row.addWidget(self.tab_widget)

        root.addLayout(header_row)

        # Metrics bar
        self.pages_metrics = MetricRow(
            [
                ("Total Pages", "0"),
                ("Publishing Eligible", "0"),
                ("Followers Reach", "0"),
                ("Stale / Review", "0"),
            ]
        )
        self.groups_metrics = MetricRow(
            [
                ("Total Groups", "0"),
                ("Posting Eligible", "0"),
                ("Community Members", "0"),
                ("Admin Privileges", "0"),
            ]
        )
        self.groups_metrics.hide()
        root.addWidget(self.pages_metrics)
        root.addWidget(self.groups_metrics)

        # Search & Filter Bar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name, ID, category, or role...")
        self.search_input.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_input, stretch=2)

        self.filter_combo = QComboBox()
        self._populate_filter_combo("Pages")
        self.filter_combo.currentTextChanged.connect(self._on_filter_mode_changed)
        toolbar.addWidget(self.filter_combo)

        self.account_combo = QComboBox()
        self.account_combo.addItem("All Accounts")
        self.account_combo.currentTextChanged.connect(self._on_account_filter_changed)
        toolbar.addWidget(self.account_combo)

        self.sync_btn = PrimaryButton("Sync Assets")
        self.sync_btn.clicked.connect(self._on_sync_clicked)
        toolbar.addWidget(self.sync_btn)

        self.actions_btn = PrimaryButton("Actions...")
        self.actions_btn.setObjectName("contextActionsButton")
        self.actions_btn.setEnabled(False)
        self.actions_btn.clicked.connect(self.open_context_actions)
        toolbar.addWidget(self.actions_btn)

        self.bulk_menu_btn = SecondaryButton("Bulk Actions ▾")
        self.bulk_menu = QMenu(self)
        mark_stale_action = self.bulk_menu.addAction("Mark Selected Stale")
        mark_stale_action.triggered.connect(self._bulk_mark_stale)
        export_action = self.bulk_menu.addAction("Export Assets (CSV)")
        export_action.triggered.connect(self._export_assets_csv)
        self.bulk_menu_btn.setMenu(self.bulk_menu)
        toolbar.addWidget(self.bulk_menu_btn)

        self.refresh_btn = SecondaryButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(self.refresh_btn)

        root.addLayout(toolbar)

        # Center area: Splitter with Table and Right Inspector
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("assetSplitter")
        splitter.setChildrenCollapsible(False)

        # Left/Center Table Stack
        self.table_container = QWidget()
        table_layout = QVBoxLayout(self.table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)

        # Pages Table
        self.pages_table = CompactTable()
        self.pages_table.setModel(self.pages_proxy)
        self.pages_table.setSortingEnabled(True)
        self.pages_table.selectionModel().selectionChanged.connect(self._on_page_selected)
        self.pages_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.pages_table.customContextMenuRequested.connect(self._show_page_context_menu)
        self._format_header(self.pages_table)

        # Groups Table
        self.groups_table = CompactTable()
        self.groups_table.setModel(self.groups_proxy)
        self.groups_table.setSortingEnabled(True)
        self.groups_table.selectionModel().selectionChanged.connect(self._on_group_selected)
        self.groups_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.groups_table.customContextMenuRequested.connect(self._show_group_context_menu)
        self._format_header(self.groups_table)
        self.groups_table.hide()

        table_layout.addWidget(self.pages_table)
        table_layout.addWidget(self.groups_table)
        splitter.addWidget(self.table_container)

        # Right Inspector
        self.inspector = AssetInspectorPanel()
        self.inspector.route_requested.connect(self.route_requested.emit)
        splitter.addWidget(self.inspector)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([850, 320])

        root.addWidget(splitter, stretch=1)

        # Setup tab titles
        self.tab_widget.addTab(QWidget(), "Pages")
        self.tab_widget.addTab(QWidget(), "Groups")

    def _format_header(self, table: CompactTable) -> None:
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 9):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

    def _populate_filter_combo(self, tab: str) -> None:
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        if tab == "Pages":
            self.filter_combo.addItems(["All", "Publishing Eligible", "Stale / Review", "Healthy"])
        else:
            self.filter_combo.addItems(
                ["All", "Admin Only", "Posting Eligible", "Stale / Review", "Healthy"]
            )
        self.filter_combo.blockSignals(False)

    def set_tab(self, tab_name_or_index: str | int) -> None:
        if isinstance(tab_name_or_index, str):
            idx = 0 if tab_name_or_index.casefold() == "pages" else 1
        else:
            idx = tab_name_or_index
        self.tab_widget.setCurrentIndex(idx)

    def _on_tab_changed(self, index: int) -> None:
        is_pages = index == 0
        self.pages_table.setVisible(is_pages)
        self.groups_table.setVisible(not is_pages)
        self.pages_metrics.setVisible(is_pages)
        self.groups_metrics.setVisible(not is_pages)
        self._populate_filter_combo("Pages" if is_pages else "Groups")
        self._on_search_changed(self.search_input.text())
        self.inspector._reset_view()

    def _on_search_changed(self, text: str) -> None:
        if self.tab_widget.currentIndex() == 0:
            self.pages_proxy.setFilterRegularExpression(text)
        else:
            self.groups_proxy.setFilterRegularExpression(text)

    def _on_filter_mode_changed(self, mode: str) -> None:
        if self.tab_widget.currentIndex() == 0:
            self.pages_proxy.set_filter_mode(mode)
        else:
            self.groups_proxy.set_filter_mode(mode)

    def _on_account_filter_changed(self, account: str) -> None:
        self.pages_proxy.set_account_filter(account)
        self.groups_proxy.set_account_filter(account)

    def refresh(self) -> None:
        self._load_accounts()
        self._load_pages()
        self._load_groups()

    def _load_accounts(self) -> None:
        if self._account_service is None:
            return
        try:
            accounts = self._account_service.list_accounts()
            self._account_names = {a.id: a.display_name for a in accounts}

            curr = self.account_combo.currentText()
            self.account_combo.blockSignals(True)
            self.account_combo.clear()
            self.account_combo.addItem("All Accounts")
            for acc in accounts:
                self.account_combo.addItem(acc.display_name, acc.id)
            idx = self.account_combo.findText(curr)
            if idx >= 0:
                self.account_combo.setCurrentIndex(idx)
            self.account_combo.blockSignals(False)
        except Exception:
            pass

    def _load_pages(self) -> None:
        if self._sync_service is None:
            return
        self._pages = list(self._sync_service.list_all_pages())
        self.pages_model.setRowCount(0)

        pub_count = 0
        followers_sum = 0
        stale_count = 0

        for page in self._pages:
            acc_name = self._account_names.get(page.account_id, page.account_id[:8])
            can_pub = page.is_publishing_eligible()
            if can_pub:
                pub_count += 1
            if page.health == AssetHealthState.STALE:
                stale_count += 1
            followers_sum += page.followers_count

            items = [
                QStandardItem(page.name),
                QStandardItem(page.page_id),
                QStandardItem(acc_name),
                QStandardItem(page.category or "—"),
                QStandardItem(", ".join(page.tasks) if page.tasks else "None"),
                QStandardItem("Eligible" if can_pub else "Restricted"),
                QStandardItem(f"{page.followers_count:,}"),
                QStandardItem(page.health.value.capitalize()),
                QStandardItem(
                    page.last_synced_at.strftime("%Y-%m-%d %H:%M")
                    if page.last_synced_at
                    else "Never"
                ),
            ]
            for it in items:
                it.setEditable(False)
            self.pages_model.appendRow(items)

        # Update metric row
        self.pages_metrics.value_labels[0].setText(f"{len(self._pages):,}")
        self.pages_metrics.value_labels[1].setText(f"{pub_count:,}")
        self.pages_metrics.value_labels[2].setText(f"{followers_sum:,}")
        self.pages_metrics.value_labels[3].setText(f"{stale_count:,}")

    def _load_groups(self) -> None:
        if self._sync_service is None:
            return
        self._groups = list(self._sync_service.list_all_groups())
        self.groups_model.setRowCount(0)

        post_count = 0
        members_sum = 0
        admin_count = 0

        for group in self._groups:
            acc_name = self._account_names.get(group.account_id, group.account_id[:8])
            can_post = group.is_posting_eligible()
            if can_post:
                post_count += 1
            if group.is_admin():
                admin_count += 1
            members_sum += group.member_count

            items = [
                QStandardItem(group.name),
                QStandardItem(group.group_id),
                QStandardItem(acc_name),
                QStandardItem(group.privacy),
                QStandardItem(group.role),
                QStandardItem("Eligible" if can_post else "Restricted"),
                QStandardItem(f"{group.member_count:,}"),
                QStandardItem(group.health.value.capitalize()),
                QStandardItem(
                    group.last_synced_at.strftime("%Y-%m-%d %H:%M")
                    if group.last_synced_at
                    else "Never"
                ),
            ]
            for it in items:
                it.setEditable(False)
            self.groups_model.appendRow(items)

        # Update metric row
        self.groups_metrics.value_labels[0].setText(f"{len(self._groups):,}")
        self.groups_metrics.value_labels[1].setText(f"{post_count:,}")
        self.groups_metrics.value_labels[2].setText(f"{members_sum:,}")
        self.groups_metrics.value_labels[3].setText(f"{admin_count:,}")

    def _on_page_selected(self) -> None:
        indexes = self.pages_table.selectionModel().selectedRows()
        self.actions_btn.setEnabled(bool(indexes))
        if not indexes:
            self.inspector.inspect_page(None)
            return
        source_idx = self.pages_proxy.mapToSource(indexes[0])
        row = source_idx.row()
        if 0 <= row < len(self._pages):
            page = self._pages[row]
            acc_name = self._account_names.get(page.account_id, page.account_id)
            self.inspector.inspect_page(page, acc_name)

    def _on_group_selected(self) -> None:
        indexes = self.groups_table.selectionModel().selectedRows()
        self.actions_btn.setEnabled(bool(indexes))
        if not indexes:
            self.inspector.inspect_group(None)
            return
        source_idx = self.groups_proxy.mapToSource(indexes[0])
        row = source_idx.row()
        if 0 <= row < len(self._groups):
            group = self._groups[row]
            acc_name = self._account_names.get(group.account_id, group.account_id)
            self.inspector.inspect_group(group, acc_name)

    def _show_page_context_menu(self, point: QPoint) -> None:
        menu = QMenu(self)
        indexes = self.pages_table.selectionModel().selectedRows()
        act_actions = menu.addAction(f"Actions ({len(indexes)})...")
        font = act_actions.font()
        font.setBold(True)
        act_actions.setFont(font)
        act_actions.triggered.connect(self.open_context_actions)
        menu.addSeparator()

        copy_id = menu.addAction("Copy Page ID")
        copy_id.triggered.connect(self._copy_selected_id)
        open_content = menu.addAction("View Content Queue")
        open_content.triggered.connect(lambda: self.route_requested.emit("Automation"))
        menu.exec(self.pages_table.viewport().mapToGlobal(point))

    def _show_group_context_menu(self, point: QPoint) -> None:
        menu = QMenu(self)
        indexes = self.groups_table.selectionModel().selectedRows()
        act_actions = menu.addAction(f"Actions ({len(indexes)})...")
        font = act_actions.font()
        font.setBold(True)
        act_actions.setFont(font)
        act_actions.triggered.connect(self.open_context_actions)
        menu.addSeparator()

        copy_id = menu.addAction("Copy Group ID")
        copy_id.triggered.connect(self._copy_selected_id)
        open_content = menu.addAction("View Content Queue")
        open_content.triggered.connect(lambda: self.route_requested.emit("Automation"))
        menu.exec(self.groups_table.viewport().mapToGlobal(point))

    def open_context_actions(self) -> None:
        from sp_farms.app.context_action_dialog import ContextActionDialog
        from sp_farms.domain.selection_context import SelectionContext, SelectionSource

        if self.tab_widget.currentIndex() == 0:
            indexes = self.pages_table.selectionModel().selectedRows()
            if not indexes:
                return
            selected_page_ids = []
            for idx in indexes:
                s_idx = self.pages_proxy.mapToSource(idx)
                if 0 <= s_idx.row() < len(self._pages):
                    selected_page_ids.append(self._pages[s_idx.row()].id)

            if self._selection_context_service:
                ctx = self._selection_context_service.resolve_context(
                    source_module=SelectionSource.PAGES,
                    page_ids=selected_page_ids,
                )
            else:
                ctx = SelectionContext(
                    source_module=SelectionSource.PAGES,
                    selected_page_ids=tuple(selected_page_ids),
                )
        else:
            indexes = self.groups_table.selectionModel().selectedRows()
            if not indexes:
                return
            selected_group_ids = []
            for idx in indexes:
                s_idx = self.groups_proxy.mapToSource(idx)
                if 0 <= s_idx.row() < len(self._groups):
                    selected_group_ids.append(self._groups[s_idx.row()].id)

            if self._selection_context_service:
                ctx = self._selection_context_service.resolve_context(
                    source_module=SelectionSource.GROUPS,
                    group_ids=selected_group_ids,
                )
            else:
                ctx = SelectionContext(
                    source_module=SelectionSource.GROUPS,
                    selected_group_ids=tuple(selected_group_ids),
                )

        dialog = ContextActionDialog(
            context=ctx,
            app_context=self._app_context,
            parent=self,
        )
        dialog.exec()

    def _copy_selected_id(self) -> None:
        # Simple ID lookup based on active tab
        if self.tab_widget.currentIndex() == 0:
            indexes = self.pages_table.selectionModel().selectedRows()
            if indexes:
                source_idx = self.pages_proxy.mapToSource(indexes[0])
                page = self._pages[source_idx.row()]
                from PySide6.QtGui import QGuiApplication

                clip = QGuiApplication.clipboard()
                if clip:
                    clip.setText(page.page_id)
        else:
            indexes = self.groups_table.selectionModel().selectedRows()
            if indexes:
                source_idx = self.groups_proxy.mapToSource(indexes[0])
                group = self._groups[source_idx.row()]
                from PySide6.QtGui import QGuiApplication

                clip = QGuiApplication.clipboard()
                if clip:
                    clip.setText(group.group_id)

    def _on_sync_clicked(self) -> None:
        if self._sync_service is None or self._account_service is None:
            QMessageBox.information(self, "Sync Assets", "Asset sync service is not initialized.")
            return

        # Check account selection
        target_account_id = self.account_combo.currentData()
        if target_account_id:
            account_ids = [str(target_account_id)]
        else:
            accounts = self._account_service.list_accounts()
            account_ids = [a.id for a in accounts]

        if not account_ids:
            QMessageBox.information(
                self, "Sync Assets", "No managed accounts found to synchronize."
            )
            return

        self.sync_btn.setEnabled(False)
        self.sync_btn.setText("Syncing...")

        worker = SyncWorker(self._sync_service, account_ids)
        worker.signals.finished.connect(self._on_sync_finished)
        worker.signals.error.connect(self._on_sync_error)
        QThreadPool.globalInstance().start(worker)

    def _on_sync_finished(self, results: list[SyncResult]) -> None:
        self.sync_btn.setEnabled(True)
        self.sync_btn.setText("Sync Assets")
        total_pages = sum(r.synced_pages_count for r in results)
        total_groups = sum(r.synced_groups_count for r in results)
        errors = [err for r in results for err in r.errors]

        msg = (
            f"Synchronized {total_pages} Pages and {total_groups} Groups "
            f"across {len(results)} accounts."
        )
        if errors:
            msg += f"\n\nNotices/Errors ({len(errors)}):\n" + "\n".join(errors[:3])

        QMessageBox.information(self, "Asset Synchronization Complete", msg)
        self.refresh()

    def _on_sync_error(self, err: str) -> None:
        self.sync_btn.setEnabled(True)
        self.sync_btn.setText("Sync Assets")
        QMessageBox.critical(self, "Synchronization Error", f"Sync failed: {err}")

    def _bulk_mark_stale(self) -> None:
        is_pages = self.tab_widget.currentIndex() == 0
        table = self.pages_table if is_pages else self.groups_table
        indexes = table.selectionModel().selectedRows()
        if not indexes:
            QMessageBox.information(
                self, "Bulk Action", "Please select one or more items in the table."
            )
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Mark Stale",
            f"Are you sure you want to mark {len(indexes)} selected assets as STALE?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        # Reload
        self.refresh()

    def _export_assets_csv(self) -> None:
        is_pages = self.tab_widget.currentIndex() == 0
        default_name = "facebook_pages.csv" if is_pages else "facebook_groups.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Assets to CSV",
            default_name,
            "CSV Files (*.csv)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                if is_pages:
                    writer.writerow(
                        ["ID", "Page ID", "Account ID", "Name", "Category", "Followers", "Health"]
                    )
                    for p in self._pages:
                        writer.writerow(
                            [
                                p.id,
                                p.page_id,
                                p.account_id,
                                p.name,
                                p.category or "",
                                p.followers_count,
                                p.health.value,
                            ]
                        )
                else:
                    writer.writerow(
                        [
                            "ID",
                            "Group ID",
                            "Account ID",
                            "Name",
                            "Privacy",
                            "Role",
                            "Members",
                            "Health",
                        ]
                    )
                    for g in self._groups:
                        writer.writerow(
                            [
                                g.id,
                                g.group_id,
                                g.account_id,
                                g.name,
                                g.privacy,
                                g.role,
                                g.member_count,
                                g.health.value,
                            ]
                        )
            QMessageBox.information(
                self, "Export Complete", f"Exported successfully to {file_path}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Could not write CSV: {exc}")
