import csv
import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QPoint, QRunnable, QSettings, Qt, QThreadPool, Signal
from PySide6.QtGui import QAction, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.account_dialogs import (
    BulkCategoryDialog,
    BulkTagDialog,
    ColumnPickerDialog,
)
from sp_farms.app.account_exchange_dialogs import (
    AccountExportDialog,
    AccountImportDialog,
)
from sp_farms.app.account_onboarding import AccountOnboardingPanel
from sp_farms.app.batch_restore_dialog import BatchRestoreDialog
from sp_farms.app.security_center import SecurityCenterWorkspace
from sp_farms.app.widgets import (
    CompactTable,
    MetricRow,
    Panel,
    PrimaryButton,
    SecondaryButton,
    StatusChip,
)
from sp_farms.application.account_onboarding_service import AccountOnboardingService
from sp_farms.application.account_service import AccountService
from sp_farms.domain.account_onboarding import mask_email, mask_phone
from sp_farms.domain.accounts import (
    AccountHealthState,
    AccountStatus,
    PermissionState,
    SecurityState,
    calculate_account_health,
)
from sp_farms.domain.device_restore import RestoreWorkspaceResult

if TYPE_CHECKING:
    from sp_farms.application.account_exchange_service import AccountExchangeService
    from sp_farms.application.context import ApplicationContext
    from sp_farms.application.device_pool_service import DevicePoolService
    from sp_farms.application.restore_workspace_service import RestoreWorkspaceService
    from sp_farms.application.security_service import SecurityService
    from sp_farms.application.selection_context_service import SelectionContextService
    from sp_farms.application.snapshot_service import SnapshotService


COLUMNS: tuple[tuple[str, str, bool], ...] = (
    ("account", "Account", True),
    ("status", "Status", True),
    ("email", "Email", True),
    ("phone", "Phone", True),
    ("uid", "UID", True),
    ("category", "Category", True),
    ("device", "Device", True),
    ("network", "Network", True),
    ("2fa", "2FA", True),
    ("pages", "Pages", True),
    ("groups", "Groups", True),
    ("last_active", "Last Active", True),
    ("app", "App", True),
    ("provider", "Provider", False),
    ("birthday", "Birthday", False),
    ("gender", "Gender", False),
    ("country", "Country", False),
    ("locale", "Locale", False),
    ("timezone", "Timezone", False),
    ("notes", "Notes", False),
    ("last_verified", "Last Verified", False),
    ("security_state", "Security State", False),
    ("created_date", "Created Date", False),
    ("health", "Health", False),
)


class _WorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)


class _Worker(QRunnable):
    def __init__(self, operation: Callable[[], Any]) -> None:
        super().__init__()
        self.operation = operation
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            result = self.operation()
            self.signals.succeeded.emit(result)
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class AccountWorkspace(QWidget):
    success_action_requested = Signal(str, str)
    local_navigation_requested = Signal(str)
    action_list_requested = Signal(tuple)
    restore_completed = Signal(object)

    def __init__(
        self,
        accounts: AccountService | None,
        onboarding: AccountOnboardingService | None,
        restore_service: "RestoreWorkspaceService | None" = None,
        pool_service: "DevicePoolService | None" = None,
        snapshot_service: "SnapshotService | None" = None,
        exchange_service: "AccountExchangeService | None" = None,
        security_service: "SecurityService | None" = None,
        settings: QSettings | None = None,
        parent: QWidget | None = None,
        selection_context_service: "SelectionContextService | None" = None,
        app_context: "ApplicationContext | None" = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("accountWorkspace")
        self._accounts = accounts
        self._restore_service = restore_service
        self._pool_service = pool_service
        self._snapshot_service = snapshot_service
        self._exchange_service = exchange_service
        self._security_service = security_service
        self._selection_context_service = selection_context_service
        self._app_context = app_context
        self._workers: set[_Worker] = set()
        self._pool = QThreadPool.globalInstance()
        self._settings = (
            settings if settings is not None else QSettings("sp_farms", "account_workspace")
        )
        self._build_ui(onboarding)
        self._load_column_visibility()
        self.refresh()

    def _build_ui(self, onboarding: AccountOnboardingService | None) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 8)
        root.setSpacing(7)
        self.pages = QStackedWidget()
        root.addWidget(self.pages, stretch=1)

        listing = QWidget()
        listing_layout = QVBoxLayout(listing)
        listing_layout.setContentsMargins(0, 0, 0, 0)
        listing_layout.setSpacing(7)

        heading_row = QHBoxLayout()
        heading_stack = QVBoxLayout()
        heading_stack.setSpacing(0)
        self.heading = QLabel("Accounts Management (0)")
        self.heading.setProperty("heading", True)
        heading_stack.addWidget(self.heading)
        subheading = QLabel("Manage accounts, assignments, restore jobs, and snapshots")
        subheading.setProperty("muted", True)
        heading_stack.addWidget(subheading)
        heading_row.addLayout(heading_stack)
        heading_row.addStretch()
        date_card = Panel()
        date_card.setProperty("metric", True)
        date_layout = QVBoxLayout(date_card)
        date_layout.setContentsMargins(12, 6, 12, 6)
        now = datetime.now().astimezone()
        date_value = QLabel(now.strftime("%H:%M"))
        date_value.setProperty("metricValue", True)
        date_layout.addWidget(date_value)
        date_name = QLabel(now.strftime("%a, %d %b %Y"))
        date_name.setProperty("muted", True)
        date_layout.addWidget(date_name)
        heading_row.addWidget(date_card)
        listing_layout.addLayout(heading_row)

        self.metrics = MetricRow(
            (("Total Accounts", "0"), ("Online", "0"), ("Running", "0"), ("Needs Attention", "0"))
        )
        listing_layout.addWidget(self.metrics)

        # Real operator flow: selected context moves forward without re-selecting.
        account_flow = Panel()
        account_flow.setProperty("flowPanel", True)
        account_flow_layout = QHBoxLayout(account_flow)
        account_flow_layout.setContentsMargins(8, 6, 8, 6)
        account_flow_layout.setSpacing(5)

        flow_caption = QLabel("ACCOUNT FLOW")
        flow_caption.setProperty("sectionTitle", True)
        account_flow_layout.addWidget(flow_caption)

        self.account_flow_select = QPushButton("1  Select\n    Account")
        self.account_flow_select.setProperty("flowStep", True)
        self.account_flow_select.setProperty("flowState", "next")
        self.account_flow_select.setEnabled(False)

        self.account_flow_resolve = QPushButton("2  Resolve\n    Device + Network")
        self.account_flow_resolve.setProperty("flowStep", True)
        self.account_flow_resolve.clicked.connect(self.open_context_actions)

        self.account_flow_restore = QPushButton("3  Restore\n    Workspace")
        self.account_flow_restore.setProperty("flowStep", True)
        self.account_flow_restore.clicked.connect(self.restore_selected_workspace)

        self.account_flow_actions = QPushButton("4  Actions\n    Build Workflow")
        self.account_flow_actions.setProperty("flowStep", True)
        self.account_flow_actions.clicked.connect(
            lambda: self.action_list_requested.emit(self.selected_account_ids)
        )

        self.account_flow_monitor = QPushButton("5  Monitor\n    Job Queue")
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

        local_nav = Panel()
        local_nav_layout = QHBoxLayout(local_nav)
        local_nav_layout.setContentsMargins(4, 3, 4, 3)
        local_nav_layout.setSpacing(2)
        self.local_nav_buttons: dict[str, QPushButton] = {}
        for index, label in enumerate(
            ("Local Accounts", "Security Center", "Error Center", "Pages", "Groups")
        ):
            button = QPushButton(label)
            button.setObjectName(f"local{label.replace(' ', '')}Button")
            button.setProperty("localNav", True)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setChecked(index == 0)
            if label == "Local Accounts":
                route = "Accounts"
            elif label == "Security Center":
                route = "Security"
            elif label == "Error Center":
                route = "Error Center"
            else:
                route = label
            button.clicked.connect(
                lambda checked=False, name=route: self._request_local_navigation(name)
            )
            self.local_nav_buttons[route] = button
            local_nav_layout.addWidget(button)
        local_nav_layout.addStretch()
        listing_layout.addWidget(local_nav)

        toolbar = Panel()
        toolbar_layout = QHBoxLayout(toolbar)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search accounts")
        self.search_input.setAccessibleName("Search accounts")
        self.search_input.setAccessibleDescription("Filter account list by name or username")
        self.search_input.textChanged.connect(self.refresh)

        self.status_chip = StatusChip("Ready", state="neutral")
        self.status_chip.setObjectName("accountStatusChip")

        self.actions_btn = PrimaryButton("Actions...")
        self.actions_btn.setObjectName("contextActionsButton")
        self.actions_btn.setEnabled(False)
        self.actions_btn.clicked.connect(self.open_context_actions)

        self.workflow_btn = SecondaryButton("Action List...")
        self.workflow_btn.setObjectName("actionListButton")
        self.workflow_btn.setEnabled(False)
        self.workflow_btn.clicked.connect(
            lambda: self.action_list_requested.emit(self.selected_account_ids)
        )

        self.restore_btn = SecondaryButton("Restore")
        self.restore_btn.setObjectName("restoreWorkspaceButton")
        self.restore_btn.setEnabled(False)
        self.restore_btn.clicked.connect(self.restore_selected_workspace)

        self.restore_selected_btn = SecondaryButton("Restore Selected")
        self.restore_selected_btn.setObjectName("restoreSelectedButton")
        self.restore_selected_btn.setEnabled(False)
        self.restore_selected_btn.clicked.connect(self.restore_batch_workspace)

        self.backup_btn = SecondaryButton("Backup")
        self.backup_btn.setObjectName("backupSelectedButton")
        self.backup_btn.setEnabled(False)
        self.backup_btn.clicked.connect(self.backup_selected_workspace)

        self.release_btn = SecondaryButton("Release")
        self.release_btn.setObjectName("releaseDeviceButton")
        self.release_btn.setEnabled(False)
        self.release_btn.clicked.connect(self.release_selected_device)

        self.pool_btn = SecondaryButton("Device Pool")
        self.pool_btn.setObjectName("devicePoolButton")
        self.pool_btn.clicked.connect(self.open_device_pool_dialog)

        self.add_btn = PrimaryButton("Add account")
        self.add_btn.setObjectName("addAccountButton")
        self.add_btn.clicked.connect(self.open_onboarding)

        self.smart_filter = QComboBox()
        self.smart_filter.setObjectName("smartFilter")
        self.smart_filter.setAccessibleName("Smart filter")
        self.smart_filter.addItems(
            (
                "All Smart Filters",
                "Device Offline",
                "No Device",
                "Expiring Session",
                "Permission Issue",
                "Needs Review",
            )
        )

        self.category_filter = QComboBox()
        self.category_filter.setAccessibleName("Category filter")
        self.category_filter.addItem("All Categories", None)
        self.status_filter = QComboBox()
        self.status_filter.setAccessibleName("Status filter")
        self.status_filter.addItems(("All Status", "Active", "Attention", "Disabled"))
        self.device_filter = QComboBox()
        self.device_filter.setAccessibleName("Device filter")
        self.device_filter.addItems(("All Devices", "Assigned", "Unassigned"))
        self.network_filter = QComboBox()
        self.network_filter.setAccessibleName("Network filter")
        self.network_filter.addItems(("All Networks", "Connected", "Offline"))
        for filter_box in (
            self.smart_filter,
            self.category_filter,
            self.status_filter,
            self.device_filter,
            self.network_filter,
        ):
            filter_box.currentIndexChanged.connect(lambda _index: self.refresh())

        self.columns_btn = SecondaryButton("Columns")
        self.columns_btn.setObjectName("columnsButton")
        self.columns_btn.clicked.connect(self.open_column_picker)

        self.bulk_btn = SecondaryButton("Bulk Actions")
        self.bulk_btn.setObjectName("bulkActionsButton")
        self.bulk_menu = QMenu(self)
        self.bulk_cat_action = self.bulk_menu.addAction("Assign Category...")
        self.bulk_cat_action.triggered.connect(self.open_bulk_category_dialog)
        self.bulk_tag_action = self.bulk_menu.addAction("Set Tags...")
        self.bulk_tag_action.triggered.connect(self.open_bulk_tag_dialog)
        self.bulk_archive_action = self.bulk_menu.addAction("Archive Selected")
        self.bulk_archive_action.triggered.connect(self.bulk_archive_selected)
        self.bulk_export_action = self.bulk_menu.addAction("Export Metadata...")
        self.bulk_export_action.triggered.connect(self.open_export_metadata_dialog)
        self.bulk_import_action = self.bulk_menu.addAction("Import Metadata...")
        self.bulk_import_action.triggered.connect(self.open_import_metadata_dialog)
        self.bulk_btn.setMenu(self.bulk_menu)

        toolbar_layout.addWidget(self.search_input, stretch=1)
        toolbar_layout.addWidget(self.smart_filter)
        toolbar_layout.addWidget(self.category_filter)
        toolbar_layout.addWidget(self.status_filter)
        toolbar_layout.addWidget(self.device_filter)
        toolbar_layout.addWidget(self.network_filter)
        toolbar_layout.addWidget(self.columns_btn)
        toolbar_layout.addWidget(self.bulk_btn)
        toolbar_layout.addWidget(self.workflow_btn)
        toolbar_layout.addWidget(self.actions_btn)
        toolbar_layout.addWidget(self.status_chip)
        toolbar_layout.addWidget(self.add_btn)
        listing_layout.addWidget(toolbar)

        # Main content area: Table + Right Inspector Splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(4)

        self.table = CompactTable()
        self.table.setObjectName("accountTable")
        self.table.setAccessibleName("Accounts Table")
        self.table.setAccessibleDescription(
            "Table listing all managed social accounts, devices, and statuses"
        )
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.setSortingEnabled(True)

        self.model = QStandardItemModel(0, len(COLUMNS), self.table)
        self.model.setHorizontalHeaderLabels(tuple(label for _key, label, _default in COLUMNS))
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(CompactTable.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(CompactTable.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, len(COLUMNS)):
            self.table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        table_layout.addWidget(self.table, stretch=1)

        # Bottom stats strip
        self.bottom_strip = QLabel(
            "Selected: 0 | Available Devices: 0 | Waiting Accounts: 0 | "
            "Restoring: 0 | Ready: 0 | Failed: 0"
        )
        self.bottom_strip.setObjectName("accountBottomStrip")
        self.bottom_strip.setStyleSheet(
            "font-size: 11px; padding: 4px 8px; border-top: 1px solid rgba(128,128,128,0.2);"
        )
        table_layout.addWidget(self.bottom_strip)

        main_splitter.addWidget(table_container)

        self.inspector = Panel()
        self.inspector.setObjectName("accountActions")
        self.inspector.setMinimumWidth(345)
        self.inspector.setMaximumWidth(470)
        inspector_layout = QVBoxLayout(self.inspector)
        inspector_layout.setContentsMargins(9, 9, 9, 9)
        inspector_layout.setSpacing(7)

        insp_heading = QLabel("Account Actions")
        insp_heading.setProperty("heading", True)
        inspector_layout.addWidget(insp_heading)

        action_body = QHBoxLayout()
        action_nav = QVBoxLayout()
        action_nav.setSpacing(3)
        self.action_pages = QStackedWidget()
        self.action_pages.setObjectName("accountActionPages")
        self.action_nav_buttons: list[QPushButton] = []
        for index, title in enumerate(
            ("Overview", "Restore Workspace", "Backup Snapshot", "Device Pool", "Release Device")
        ):
            button = QPushButton(title)
            button.setObjectName(f"accountAction{index}Button")
            button.setProperty("actionNav", True)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setChecked(index == 0)
            button.clicked.connect(
                lambda checked=False, page=index: self.action_pages.setCurrentIndex(page)
            )
            self.action_nav_buttons.append(button)
            action_nav.addWidget(button)
        action_nav.addStretch()
        action_body.addLayout(action_nav)

        overview = QWidget()
        overview_layout = QVBoxLayout(overview)
        overview_layout.setContentsMargins(0, 0, 0, 0)
        detail_heading = QLabel("Selected Account Workspace")
        detail_heading.setStyleSheet("font-weight: 700;")
        overview_layout.addWidget(detail_heading)
        insp_form = QFormLayout()
        insp_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.insp_bound_device = QLabel("—")
        self.insp_bound_device.setObjectName("inspBoundDevice")
        insp_form.addRow("Bound Device:", self.insp_bound_device)
        self.insp_current_device = QLabel("—")
        self.insp_current_device.setObjectName("inspCurrentDevice")
        insp_form.addRow("Current Device:", self.insp_current_device)
        self.insp_health = QLabel("—")
        self.insp_health.setObjectName("inspHealth")
        insp_form.addRow("Health:", self.insp_health)
        self.insp_security_state = QLabel("—")
        self.insp_security_state.setObjectName("inspSecurityState")
        insp_form.addRow("Security State:", self.insp_security_state)
        self.insp_permission_state = QLabel("—")
        self.insp_permission_state.setObjectName("inspPermissionState")
        insp_form.addRow("Permissions:", self.insp_permission_state)
        self.insp_2fa = QLabel("—")
        self.insp_2fa.setObjectName("insp2FA")
        insp_form.addRow("2FA:", self.insp_2fa)
        self.insp_tags = QLabel("—")
        self.insp_tags.setObjectName("inspTags")
        insp_form.addRow("Tags:", self.insp_tags)
        self.insp_backup_status = QLabel("—")
        self.insp_backup_status.setObjectName("inspBackupStatus")
        insp_form.addRow("Backup Status:", self.insp_backup_status)
        self.insp_latest_snapshot = QLabel("—")
        self.insp_latest_snapshot.setObjectName("inspLatestSnapshot")
        insp_form.addRow("Latest Snapshot:", self.insp_latest_snapshot)
        self.insp_preferred_app = QLabel("—")
        self.insp_preferred_app.setObjectName("inspPreferredApp")
        insp_form.addRow("Preferred App:", self.insp_preferred_app)
        self.insp_queue_state = QLabel("Idle")
        self.insp_queue_state.setObjectName("inspQueueState")
        insp_form.addRow("Queue State:", self.insp_queue_state)
        overview_layout.addLayout(insp_form)
        overview_layout.addStretch()
        self.action_pages.addWidget(overview)
        self.action_pages.addWidget(
            self._action_page(
                "Restore account workspace",
                "Restore one selected account, or queue all selected accounts.",
                (self.restore_btn, self.restore_selected_btn),
            )
        )
        self.action_pages.addWidget(
            self._action_page(
                "Backup snapshot",
                "Create lightweight snapshots for the selected accounts.",
                (self.backup_btn,),
            )
        )
        self.action_pages.addWidget(
            self._action_page(
                "Device pool",
                "Inspect available devices and active account leases.",
                (self.pool_btn,),
            )
        )
        self.action_pages.addWidget(
            self._action_page(
                "Release device",
                "Release the selected account's current device lease.",
                (self.release_btn,),
            )
        )
        action_body.addWidget(self.action_pages, stretch=1)
        inspector_layout.addLayout(action_body, stretch=1)

        main_splitter.addWidget(self.inspector)
        main_splitter.setStretchFactor(0, 5)
        main_splitter.setStretchFactor(1, 3)
        main_splitter.setSizes((760, 450))

        listing_layout.addWidget(main_splitter, stretch=1)
        self.pages.addWidget(listing)

        self.onboarding_panel = AccountOnboardingPanel(onboarding)
        self.onboarding_panel.cancelled.connect(self.show_accounts)
        self.onboarding_panel.onboarding_completed.connect(self._onboarded)
        self.onboarding_panel.success_action_requested.connect(self.success_action_requested.emit)
        self.pages.addWidget(self.onboarding_panel)

        self.security_workspace = SecurityCenterWorkspace(self._security_service)
        self.pages.addWidget(self.security_workspace)

    @staticmethod
    def _action_page(
        title: str,
        description: str,
        buttons: tuple[QPushButton, ...],
    ) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        heading = QLabel(title)
        heading.setStyleSheet("font-weight: 700;")
        layout.addWidget(heading)
        text = QLabel(description)
        text.setProperty("muted", True)
        text.setWordWrap(True)
        layout.addWidget(text)
        layout.addStretch()
        for button in buttons:
            layout.addWidget(button)
        return page

    def _request_local_navigation(self, route: str) -> None:
        if route == "Accounts":
            self.pages.setCurrentIndex(0)
            return
        if route == "Security":
            self.pages.setCurrentIndex(2)
            self.security_workspace.refresh()
            return
        self.local_nav_buttons["Accounts"].setChecked(True)
        self.local_navigation_requested.emit(route)

    def show_security_center(self) -> None:
        if "Security" in self.local_nav_buttons:
            self.local_nav_buttons["Security"].setChecked(True)
        self._request_local_navigation("Security")

    def _load_column_visibility(self) -> None:
        raw = self._settings.value("columns_visible")
        if raw is not None and isinstance(raw, str):
            try:
                visible = {int(x) for x in raw.split(",") if x.strip()}
            except Exception:
                visible = {i for i, (_k, _l, d) in enumerate(COLUMNS) if d}
        else:
            visible = {i for i, (_k, _l, d) in enumerate(COLUMNS) if d}
        for i in range(len(COLUMNS)):
            self.table.setColumnHidden(i, i not in visible)

    def open_column_picker(self) -> None:
        current_visible = {i for i in range(len(COLUMNS)) if not self.table.isColumnHidden(i)}
        dlg = ColumnPickerDialog(COLUMNS, current_visible, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected = dlg.selected_column_indices
            for i in range(len(COLUMNS)):
                self.table.setColumnHidden(i, i not in selected)
            self._settings.setValue("columns_visible", ",".join(str(i) for i in sorted(selected)))
            self._settings.sync()

    def _show_context_menu(self, pos: QPoint) -> None:
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        sel_model = self.table.selectionModel()
        if sel_model and not sel_model.isRowSelected(index.row(), index.parent()):
            self.table.selectRow(index.row())

        sel_ids = self.selected_account_ids
        count = len(sel_ids)
        if count == 0:
            return

        menu = QMenu(self)
        act_actions = QAction(f"Actions ({count})...", self)
        font = act_actions.font()
        font.setBold(True)
        act_actions.setFont(font)
        act_actions.triggered.connect(self.open_context_actions)
        menu.addAction(act_actions)

        menu.addSeparator()

        act_restore = QAction("Restore Workspace", self)
        act_restore.setEnabled(bool(self._restore_service and count == 1))
        act_restore.triggered.connect(self.restore_selected_workspace)
        menu.addAction(act_restore)

        act_batch = QAction(f"Batch Restore Selected ({count})...", self)
        act_batch.setEnabled(bool(self._pool_service and count >= 1))
        act_batch.triggered.connect(self.restore_batch_workspace)
        menu.addAction(act_batch)

        menu.addSeparator()

        act_backup = QAction(f"Backup Snapshot ({count})...", self)
        act_backup.setEnabled(bool(self._snapshot_service and count >= 1))
        act_backup.triggered.connect(self.backup_selected_workspace)
        menu.addAction(act_backup)

        act_release = QAction(f"Release Device Lease ({count})", self)
        act_release.setEnabled(bool(self._pool_service and count >= 1))
        act_release.triggered.connect(self.release_selected_device)
        menu.addAction(act_release)

        menu.addSeparator()

        act_cat = QAction("Assign Category...", self)
        act_cat.triggered.connect(self.open_bulk_category_dialog)
        menu.addAction(act_cat)

        act_tags = QAction("Set Tags...", self)
        act_tags.triggered.connect(self.open_bulk_tag_dialog)
        menu.addAction(act_tags)

        act_archive = QAction(f"Archive Selected ({count})...", self)
        act_archive.triggered.connect(self.bulk_archive_selected)
        menu.addAction(act_archive)

        menu.addSeparator()

        act_export = QAction(f"Export Metadata ({count})...", self)
        act_export.triggered.connect(self.open_export_metadata_dialog)
        menu.addAction(act_export)

        act_import = QAction("Import Metadata...", self)
        act_import.triggered.connect(self.open_import_metadata_dialog)
        menu.addAction(act_import)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def open_context_actions(self) -> None:
        sel_ids = self.selected_account_ids
        if not sel_ids:
            QMessageBox.information(self, "No Selection", "Please select one or more accounts.")
            return

        from sp_farms.app.context_action_dialog import ContextActionDialog
        from sp_farms.domain.selection_context import SelectionContext, SelectionSource

        if self._selection_context_service:
            context = self._selection_context_service.resolve_context(
                source_module=SelectionSource.ACCOUNTS,
                account_ids=sel_ids,
            )
        else:
            context = SelectionContext(
                source_module=SelectionSource.ACCOUNTS,
                selected_account_ids=sel_ids,
            )

        dialog = ContextActionDialog(
            context=context,
            app_context=self._app_context,
            parent=self,
        )
        dialog.exec()

    def open_bulk_category_dialog(self) -> None:
        if not self._accounts:
            return
        sel_ids = self.selected_account_ids
        if not sel_ids:
            QMessageBox.information(
                self, "No Selection", "Please select one or more accounts to assign category."
            )
            return
        categories = tuple((c.id, c.name) for c in self._accounts.list_categories())
        dlg = BulkCategoryDialog(categories, len(sel_ids), parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cat_id = dlg.selected_category_id
            self._accounts.bulk_assign_category(sel_ids, cat_id)
            self.refresh()
            self.status_chip.update_state(
                "success", f"Updated category for {len(sel_ids)} accounts."
            )

    def open_bulk_tag_dialog(self) -> None:
        if not self._accounts:
            return
        sel_ids = self.selected_account_ids
        if not sel_ids:
            QMessageBox.information(
                self, "No Selection", "Please select one or more accounts to set tags."
            )
            return
        tags = tuple((t.id, t.name) for t in self._accounts.list_tags())
        dlg = BulkTagDialog(tags, len(sel_ids), parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            tag_ids = dlg.selected_tag_ids
            self._accounts.bulk_set_tags(sel_ids, tag_ids)
            self.refresh()
            self.status_chip.update_state("success", f"Updated tags for {len(sel_ids)} accounts.")

    def bulk_archive_selected(self) -> None:
        if not self._accounts:
            return
        sel_ids = self.selected_account_ids
        if not sel_ids:
            return
        res = QMessageBox.question(
            self,
            "Confirm Archive",
            f"Are you sure you want to archive {len(sel_ids)} selected accounts?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res == QMessageBox.StandardButton.Yes:
            self._accounts.bulk_archive(sel_ids)
            self.refresh()
            self.status_chip.update_state("success", f"Archived {len(sel_ids)} accounts.")

    def export_metadata(
        self,
        account_ids: Sequence[str] | None = None,
        destination_path: Path | None = None,
        export_format: str = "json",
    ) -> list[dict[str, Any]]:
        if not self._accounts:
            return []
        all_accounts = self._accounts.list_accounts()
        if account_ids:
            target_ids = set(account_ids)
            accounts = [a for a in all_accounts if a.id in target_ids]
        else:
            accounts = list(all_accounts)

        categories = {c.id: c.name for c in self._accounts.list_categories()}
        tags = {t.id: t.name for t in self._accounts.list_tags()}

        records: list[dict[str, Any]] = []
        for a in accounts:
            rec = {
                "id": a.id,
                "platform_uid": a.platform_uid,
                "display_name": a.display_name,
                "first_name": a.first_name,
                "last_name": a.last_name,
                "primary_email": mask_email(a.primary_email),
                "phone": mask_phone(a.phone),
                "country": a.country,
                "locale": a.locale,
                "timezone": a.timezone,
                "birthday": a.birthday.isoformat() if a.birthday else None,
                "gender": a.gender.value if a.gender else None,
                "status": a.status.value,
                "two_factor_enabled": a.two_factor_enabled,
                "preferred_app": a.preferred_app.value,
                "permission_state": a.permission_state.value,
                "security_state": a.security_state.value,
                "category": categories.get(a.category_id or ""),
                "tags": [tags.get(tid, tid) for tid in a.tag_ids],
                "page_count": a.page_count,
                "group_count": a.group_count,
                "last_login_at": a.last_login_at.isoformat() if a.last_login_at else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "notes": a.notes,
            }
            records.append(rec)

        if destination_path:
            destination_path = Path(destination_path)
            if export_format.lower() == "csv":
                with open(destination_path, "w", newline="", encoding="utf-8") as f:
                    if records:
                        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
                        writer.writeheader()
                        for r in records:
                            row_copy = dict(r)
                            row_copy["tags"] = ";".join(r["tags"])
                            writer.writerow(row_copy)
            else:
                with open(destination_path, "w", encoding="utf-8") as f:
                    json.dump(records, f, indent=2)

        return records

    def open_export_metadata_dialog(self) -> None:
        sel_ids = self.selected_account_ids
        target_ids = sel_ids if sel_ids else None
        count = len(target_ids) if target_ids else (self.model.rowCount())
        if count == 0:
            QMessageBox.information(self, "No Accounts", "No accounts to export.")
            return

        if self._exchange_service is not None:
            dlg = AccountExportDialog(
                exchange_service=self._exchange_service,
                selected_account_ids=target_ids,
                total_account_count=self.model.rowCount(),
                parent=self,
            )
            dlg.exec()
            return

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Safe Metadata",
            str(Path.home() / "sp_farms_accounts_export.json"),
            "JSON (*.json);;CSV (*.csv)",
        )
        if not file_path:
            return

        fmt = "csv" if "csv" in selected_filter.lower() else "json"
        self.export_metadata(target_ids, Path(file_path), export_format=fmt)
        self.status_chip.update_state(
            "success", f"Exported {count} accounts metadata to {fmt.upper()}."
        )

    def open_import_metadata_dialog(self) -> None:
        if self._exchange_service is None:
            QMessageBox.warning(
                self,
                "Import Unavailable",
                "Account exchange service is not configured.",
            )
            return

        dlg = AccountImportDialog(self._exchange_service, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
            self.status_chip.update_state("success", "Accounts imported successfully.")

    @property
    def selected_account_id(self) -> str | None:
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return None
        indexes = selection_model.selectedRows()
        if not indexes:
            return None
        item = self.model.item(indexes[0].row(), 0)
        return str(item.data(Qt.ItemDataRole.UserRole)) if item else None

    @property
    def selected_account_ids(self) -> tuple[str, ...]:
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return ()
        ids: list[str] = []
        for idx in selection_model.selectedRows():
            item = self.model.item(idx.row(), 0)
            if item:
                val = item.data(Qt.ItemDataRole.UserRole)
                if val:
                    ids.append(str(val))
        return tuple(ids)

    def _on_selection_changed(self) -> None:
        sel_ids = self.selected_account_ids
        count = len(sel_ids)
        self.actions_btn.setEnabled(bool(count >= 1))
        self.restore_btn.setEnabled(bool(count == 1 and self._restore_service is not None))
        self.restore_selected_btn.setEnabled(bool(count >= 1 and self._pool_service is not None))
        self.backup_btn.setEnabled(bool(count >= 1 and self._snapshot_service is not None))
        self.release_btn.setEnabled(bool(count >= 1 and self._pool_service is not None))
        self.workflow_btn.setEnabled(bool(count >= 1))

        if hasattr(self, "account_flow_buttons"):
            states = (
                "done" if count else "next",
                "next" if count else "",
                "",
                "",
                "",
            )
            for button, state in zip(self.account_flow_buttons, states, strict=True):
                button.setProperty("flowState", state)
                button.style().unpolish(button)
                button.style().polish(button)
            self.account_flow_resolve.setEnabled(bool(count))
            self.account_flow_restore.setEnabled(
                bool(count == 1 and self._restore_service is not None)
            )
            self.account_flow_actions.setEnabled(bool(count))
            self.account_flow_monitor.setEnabled(True)

        # Update Inspector
        primary_id = self.selected_account_id
        if primary_id and self._accounts:
            try:
                acct = self._accounts.get_account(primary_id)
                self.insp_preferred_app.setText(acct.preferred_app.value.title())
                if acct.assigned_device:
                    self.insp_bound_device.setText(
                        f"{acct.assigned_device.provider}:{acct.assigned_device.external_id}"
                    )
                else:
                    self.insp_bound_device.setText("None")

                health = self._accounts.health(primary_id)
                self.insp_health.setText(f"{health.state.value.title()} ({health.score}/100)")
                self.insp_security_state.setText(
                    acct.security_state.value.replace("_", " ").title()
                )
                self.insp_permission_state.setText(
                    acct.permission_state.value.replace("_", " ").title()
                )
                self.insp_2fa.setText("Enabled" if acct.two_factor_enabled else "Disabled")

                tags_dict = {t.id: t.name for t in self._accounts.list_tags()}
                tag_names = [tags_dict.get(t, t) for t in acct.tag_ids]
                self.insp_tags.setText(", ".join(tag_names) if tag_names else "None")
            except Exception:
                self.insp_bound_device.setText("—")
                self.insp_preferred_app.setText("—")
                self.insp_health.setText("—")
                self.insp_security_state.setText("—")
                self.insp_permission_state.setText("—")
                self.insp_2fa.setText("—")
                self.insp_tags.setText("—")

            if self._pool_service:
                locks = {
                    d.current_account_id: d
                    for d in self._pool_service.list_pool_devices()
                    if d.current_account_id
                }
                cur_dev = locks.get(primary_id)
                self.insp_current_device.setText(cur_dev.device_key if cur_dev else "None")

                q_items = [q for q in self._pool_service.list_queue() if q.account_id == primary_id]
                if q_items:
                    self.insp_queue_state.setText(q_items[-1].status.title())
                else:
                    self.insp_queue_state.setText("Idle")
            else:
                self.insp_current_device.setText("—")
                self.insp_queue_state.setText("Idle")

            if self._snapshot_service:
                snaps = self._snapshot_service.list_snapshots_for_account(primary_id)
                if snaps:
                    latest = snaps[0]
                    self.insp_backup_status.setText(f"Backed up ({len(snaps)} total)")
                    self.insp_latest_snapshot.setText(latest.created_at.strftime("%Y-%m-%d %H:%M"))
                else:
                    self.insp_backup_status.setText("No snapshots")
                    self.insp_latest_snapshot.setText("Never")
            else:
                self.insp_backup_status.setText("—")
                self.insp_latest_snapshot.setText("—")
        else:
            self.insp_bound_device.setText("—")
            self.insp_current_device.setText("—")
            self.insp_backup_status.setText("—")
            self.insp_latest_snapshot.setText("—")
            self.insp_preferred_app.setText("—")
            self.insp_health.setText("—")
            self.insp_security_state.setText("—")
            self.insp_permission_state.setText("—")
            self.insp_2fa.setText("—")
            self.insp_tags.setText("—")
            self.insp_queue_state.setText("Idle")

        # Update bottom strip
        avail_count = 0
        waiting_count = 0
        restoring_count = 0
        if self._pool_service:
            avail_count = len(self._pool_service.get_available_devices())
            q = self._pool_service.list_queue()
            waiting_count = sum(1 for item in q if item.status == "queued")
            restoring_count = sum(1 for item in q if item.status == "restoring")

        ready_count = getattr(self, "_cached_ready_count", 0)
        failed_count = getattr(self, "_cached_failed_count", 0)

        self.bottom_strip.setText(
            f"Selected: {count} | Available Devices: {avail_count} | "
            f"Waiting Accounts: {waiting_count} | Restoring: {restoring_count} | "
            f"Ready: {ready_count} | Attention/Failed: {failed_count}"
        )

    def open_onboarding(self) -> None:
        self.onboarding_panel.reset()
        self.pages.setCurrentWidget(self.onboarding_panel)

    def show_accounts(self) -> None:
        self.refresh()
        self.pages.setCurrentIndex(0)

    def refresh(self) -> None:
        selected_ids = set(self.selected_account_ids)
        self.table.setSortingEnabled(False)
        self.model.removeRows(0, self.model.rowCount())
        if self._accounts is None:
            return
        categories = {category.id: category.name for category in self._accounts.list_categories()}
        selected_category = self.category_filter.currentData()
        if selected_category is None and self.category_filter.currentIndex() > 0:
            selected_category = self.category_filter.currentText()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("All Categories", None)
        for category_id, name in sorted(categories.items(), key=lambda item: item[1].casefold()):
            self.category_filter.addItem(name, category_id)
        selected_index = self.category_filter.findData(selected_category)
        if selected_index < 0 and isinstance(selected_category, str):
            selected_index = self.category_filter.findText(selected_category)
        self.category_filter.setCurrentIndex(max(0, selected_index))
        self.category_filter.blockSignals(False)

        query = self.search_input.text().casefold()
        category_filter = self.category_filter.currentData()
        status_filter = self.status_filter.currentText()
        device_filter = self.device_filter.currentText()
        network_filter = self.network_filter.currentText()
        smart_filter = self.smart_filter.currentText()

        all_accounts = self._accounts.list_accounts()
        now = datetime.now(UTC)

        accounts = []
        for account in all_accounts:
            # Text search across display_name, platform_uid, primary_email, phone, notes
            if query:
                in_search = (
                    query in account.display_name.casefold()
                    or query in account.platform_uid.casefold()
                    or query in account.primary_email.casefold()
                    or query in account.phone.casefold()
                    or query in account.notes.casefold()
                )
                if not in_search:
                    continue

            # Category filter
            if category_filter is not None and account.category_id != category_filter:
                continue

            # Status filter
            if (
                status_filter != "All Status"
                and account.status.value.replace("_", " ").casefold() != status_filter.casefold()
            ):
                continue

            # Device filter
            if device_filter == "Assigned" and account.assigned_device is None:
                continue
            if device_filter == "Unassigned" and account.assigned_device is not None:
                continue

            # Network filter
            if network_filter == "Connected" and account.assigned_device is None:
                continue
            if network_filter == "Offline" and account.assigned_device is not None:
                continue

            # Smart filters
            if smart_filter == "No Device" and account.assigned_device is not None:
                continue
            if smart_filter == "Device Offline" and account.assigned_device is None:
                continue
            if (
                smart_filter == "Expiring Session"
                and account.last_login_at is not None
                and (now - account.last_login_at).days < 30
            ):
                continue
            if smart_filter == "Permission Issue" and account.permission_state not in (
                PermissionState.LIMITED,
                PermissionState.REVOKED,
            ):
                continue
            if smart_filter == "Needs Review":
                health = calculate_account_health(account)
                needs_rev = (
                    account.status is AccountStatus.ATTENTION
                    or account.security_state
                    in (SecurityState.REVIEW_REQUIRED, SecurityState.COMPROMISED)
                    or health.state in (AccountHealthState.ATTENTION, AccountHealthState.CRITICAL)
                )
                if not needs_rev:
                    continue

            accounts.append(account)

        for account in accounts:
            assignment = account.assigned_device
            device_str = (
                f"{assignment.provider}:{assignment.external_id}" if assignment else "Unassigned"
            )
            provider_str = assignment.provider if assignment else "—"
            last_active = (
                account.last_login_at.astimezone().strftime("%Y-%m-%d %H:%M")
                if account.last_login_at
                else "Never"
            )
            created_str = (
                account.created_at.astimezone().strftime("%Y-%m-%d") if account.created_at else "—"
            )
            verified_str = (
                account.last_verified_at.astimezone().strftime("%Y-%m-%d")
                if account.last_verified_at
                else "Never"
            )
            health = calculate_account_health(account)

            item_account = QStandardItem(account.display_name)
            item_account.setData(account.id, Qt.ItemDataRole.UserRole)
            item_status = QStandardItem(account.status.value.replace("_", " ").title())
            item_email = QStandardItem(mask_email(account.primary_email))
            item_phone = QStandardItem(mask_phone(account.phone))
            item_uid = QStandardItem(account.platform_uid)
            item_cat = QStandardItem(
                categories.get(account.category_id, "—") if account.category_id else "—"
            )
            item_dev = QStandardItem(device_str)
            item_net = QStandardItem("Connected" if assignment else "Offline")
            item_2fa = QStandardItem("Enabled" if account.two_factor_enabled else "Disabled")

            item_pages = QStandardItem(str(account.page_count))
            item_pages.setData(account.page_count, Qt.ItemDataRole.EditRole)

            item_groups = QStandardItem(str(account.group_count))
            item_groups.setData(account.group_count, Qt.ItemDataRole.EditRole)

            item_last_active = QStandardItem(last_active)
            item_app = QStandardItem(account.preferred_app.value.replace("_", " ").title())

            # Optional columns
            item_provider = QStandardItem(provider_str)
            item_bday = QStandardItem(account.birthday.isoformat() if account.birthday else "—")
            item_gender = QStandardItem(account.gender.value.title() if account.gender else "—")
            item_country = QStandardItem(account.country or "—")
            item_locale = QStandardItem(account.locale or "—")
            item_tz = QStandardItem(account.timezone or "UTC")
            item_notes = QStandardItem(account.notes or "—")
            item_verified = QStandardItem(verified_str)
            item_sec = QStandardItem(account.security_state.value.replace("_", " ").title())
            item_created = QStandardItem(created_str)
            item_health = QStandardItem(f"{health.state.value.title()} ({health.score})")

            row_items = (
                item_account,
                item_status,
                item_email,
                item_phone,
                item_uid,
                item_cat,
                item_dev,
                item_net,
                item_2fa,
                item_pages,
                item_groups,
                item_last_active,
                item_app,
                item_provider,
                item_bday,
                item_gender,
                item_country,
                item_locale,
                item_tz,
                item_notes,
                item_verified,
                item_sec,
                item_created,
                item_health,
            )
            self.model.appendRow(row_items)

        self.table.setSortingEnabled(True)

        assigned = sum(account.assigned_device is not None for account in accounts)
        attention = sum(account.status is not AccountStatus.ACTIVE for account in accounts)
        self._cached_ready_count = sum(
            account.status is AccountStatus.ACTIVE and account.assigned_device is not None
            for account in accounts
        )
        self._cached_failed_count = sum(
            account.status is AccountStatus.DISABLED for account in accounts
        )
        queue = tuple(self._pool_service.list_queue()) if self._pool_service else ()
        running = sum(item.status == "restoring" for item in queue)
        self.heading.setText(f"Accounts Management ({len(accounts)})")
        for label, value in zip(
            self.metrics.value_labels,
            (len(accounts), assigned, running, attention),
            strict=True,
        ):
            label.setText(str(value))

        if selected_ids:
            for row in range(self.model.rowCount()):
                item = self.model.item(row, 0)
                if item and item.data(Qt.ItemDataRole.UserRole) in selected_ids:
                    self.table.selectRow(row)
        self._on_selection_changed()

    def select_account(self, account_id: str) -> None:
        self.show_accounts()
        self._select_row(account_id)

    def _select_row(self, account_id: str) -> None:
        for row in range(self.model.rowCount()):
            if self.model.item(row, 0).data(Qt.ItemDataRole.UserRole) == account_id:
                self.table.selectRow(row)
                self.table.scrollTo(self.model.index(row, 0))
                self._on_selection_changed()
                break

    def _onboarded(self, account_id: str) -> None:
        self.refresh()
        self._select_row(account_id)

    def restore_selected_workspace(self) -> None:
        account_id = self.selected_account_id
        if not account_id or self._restore_service is None:
            return

        self.restore_btn.setEnabled(False)
        self.status_chip.update_state("active", "Restoring workspace...")

        worker = _Worker(lambda: self._restore_service.restore_workspace(account_id))  # type: ignore[union-attr]
        self._workers.add(worker)

        def _cleanup() -> None:
            self._workers.discard(worker)
            self._on_selection_changed()

        def _on_success(result: Any) -> None:
            _cleanup()
            if isinstance(result, RestoreWorkspaceResult):
                if result.success:
                    state = "warning" if result.reauth_required else "success"
                    self.status_chip.update_state(state, result.message)
                else:
                    self.status_chip.update_state("error", result.message)
                self.restore_completed.emit(result)
            self.refresh()

        def _on_error(err: str) -> None:
            _cleanup()
            self.status_chip.update_state("error", f"Restore error: {err}")

        worker.signals.succeeded.connect(_on_success)
        worker.signals.failed.connect(_on_error)
        self._pool.start(worker)

    def restore_batch_workspace(self) -> None:
        sel_ids = self.selected_account_ids
        if not sel_ids or self._pool_service is None:
            return

        available_devices = self._pool_service.get_available_devices()
        dialog = BatchRestoreDialog(len(sel_ids), available_devices, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        policy = dialog.selected_policy
        priority = dialog.priority

        self.status_chip.update_state("active", f"Enqueuing {len(sel_ids)} accounts...")
        self._pool_service.enqueue_restore(
            account_ids=sel_ids,
            scheduling_policy=policy,
            priority=priority,
        )

        def _run_batch() -> list[RestoreWorkspaceResult]:
            results: list[RestoreWorkspaceResult] = []
            while True:
                res = self._pool_service.dispatch_next()  # type: ignore[union-attr]
                if res is None:
                    break
                results.append(res)
            return results

        worker = _Worker(_run_batch)
        self._workers.add(worker)

        def _cleanup() -> None:
            self._workers.discard(worker)
            self._on_selection_changed()

        def _on_success(results: Any) -> None:
            _cleanup()
            self.status_chip.update_state("success", f"Dispatched {len(results)} restores")
            self.refresh()

        def _on_error(err: str) -> None:
            _cleanup()
            self.status_chip.update_state("error", f"Batch restore error: {err}")

        worker.signals.succeeded.connect(_on_success)
        worker.signals.failed.connect(_on_error)
        self._pool.start(worker)

    def backup_selected_workspace(self) -> None:
        sel_ids = self.selected_account_ids
        if not sel_ids or self._snapshot_service is None:
            return

        self.backup_btn.setEnabled(False)
        self.status_chip.update_state("active", f"Backing up {len(sel_ids)} accounts...")

        def _run_backup() -> int:
            count = 0
            for aid in sel_ids:
                self._snapshot_service.create_snapshot(aid)  # type: ignore[union-attr]
                count += 1
            return count

        worker = _Worker(_run_backup)
        self._workers.add(worker)

        def _cleanup() -> None:
            self._workers.discard(worker)
            self._on_selection_changed()

        def _on_success(count: Any) -> None:
            _cleanup()
            self.status_chip.update_state("success", f"Backed up {count} accounts")
            self.refresh()

        def _on_error(err: str) -> None:
            _cleanup()
            self.status_chip.update_state("error", f"Backup error: {err}")

        worker.signals.succeeded.connect(_on_success)
        worker.signals.failed.connect(_on_error)
        self._pool.start(worker)

    def release_selected_device(self) -> None:
        sel_ids = self.selected_account_ids
        if not sel_ids or self._pool_service is None:
            return

        self.release_btn.setEnabled(False)
        self.status_chip.update_state("active", f"Releasing {len(sel_ids)} devices...")

        def _run_release() -> tuple[int, list[RestoreWorkspaceResult]]:
            released_count = 0
            next_results = []
            for aid in sel_ids:
                rel, next_res = self._pool_service.release_device_and_restore_next(aid)  # type: ignore[union-attr]
                if rel:
                    released_count += 1
                if next_res:
                    next_results.append(next_res)
            return released_count, next_results

        worker = _Worker(_run_release)
        self._workers.add(worker)

        def _cleanup() -> None:
            self._workers.discard(worker)
            self._on_selection_changed()

        def _on_success(data: Any) -> None:
            _cleanup()
            rel_count, next_res = data
            msg = f"Released {rel_count} devices."
            if next_res:
                msg += f" Started {len(next_res)} queued restores."
            self.status_chip.update_state("success", msg)
            self.refresh()

        def _on_error(err: str) -> None:
            _cleanup()
            self.status_chip.update_state("error", f"Release error: {err}")

        worker.signals.succeeded.connect(_on_success)
        worker.signals.failed.connect(_on_error)
        self._pool.start(worker)

    def open_device_pool_dialog(self) -> None:
        if self._pool_service is None:
            return
        devices = self._pool_service.list_pool_devices()
        dlg = QDialog(self)
        dlg.setWindowTitle("Device Pool Fleet")
        dlg.resize(500, 350)
        layout = QVBoxLayout(dlg)
        label = QLabel(f"Connected Fleet: {len(devices)} Devices")
        label.setStyleSheet("font-weight: 650; font-size: 14px;")
        layout.addWidget(label)

        table = CompactTable()
        model = QStandardItemModel(0, 4, table)
        model.setHorizontalHeaderLabels(("Device", "Provider", "State", "Account"))
        table.setModel(model)
        for d in devices:
            model.appendRow(
                (
                    QStandardItem(d.display_name),
                    QStandardItem(d.provider),
                    QStandardItem(d.state.value.title()),
                    QStandardItem(d.current_account_id or "—"),
                )
            )
        layout.addWidget(table, stretch=1)
        dlg.exec()
