from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.account_onboarding import AccountOnboardingPanel
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
from sp_farms.domain.accounts import AccountStatus
from sp_farms.domain.device_restore import RestoreWorkspaceResult

if TYPE_CHECKING:
    from sp_farms.application.restore_workspace_service import RestoreWorkspaceService


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
    restore_completed = Signal(object)

    def __init__(
        self,
        accounts: AccountService | None,
        onboarding: AccountOnboardingService | None,
        restore_service: "RestoreWorkspaceService | None" = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("accountWorkspace")
        self._accounts = accounts
        self._restore_service = restore_service
        self._workers: set[_Worker] = set()
        self._pool = QThreadPool.globalInstance()
        self._build_ui(onboarding)
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
        self.metrics = MetricRow((("Accounts", "0"), ("Active", "0"), ("Needs attention", "0")))
        listing_layout.addWidget(self.metrics)

        toolbar = Panel()
        toolbar_layout = QHBoxLayout(toolbar)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search accounts")
        self.search_input.textChanged.connect(self.refresh)

        self.status_chip = StatusChip("Ready", state="neutral")
        self.status_chip.setObjectName("accountStatusChip")

        self.restore_btn = SecondaryButton("Restore Workspace")
        self.restore_btn.setObjectName("restoreWorkspaceButton")
        self.restore_btn.setEnabled(False)
        self.restore_btn.clicked.connect(self.restore_selected_workspace)

        self.add_btn = PrimaryButton("Add account")
        self.add_btn.setObjectName("addAccountButton")
        self.add_btn.clicked.connect(self.open_onboarding)

        toolbar_layout.addWidget(self.search_input, stretch=1)
        toolbar_layout.addWidget(self.status_chip)
        toolbar_layout.addWidget(self.restore_btn)
        toolbar_layout.addWidget(self.add_btn)
        listing_layout.addWidget(toolbar)

        self.table = CompactTable()
        self.table.setObjectName("accountTable")
        self.model = QStandardItemModel(0, 6, self.table)
        self.model.setHorizontalHeaderLabels(
            ("Account", "Status", "Email", "Phone", "Preferred app", "Platform UID")
        )
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(CompactTable.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        listing_layout.addWidget(self.table, stretch=1)
        self.pages.addWidget(listing)

        self.onboarding_panel = AccountOnboardingPanel(onboarding)
        self.onboarding_panel.cancelled.connect(self.show_accounts)
        self.onboarding_panel.onboarding_completed.connect(self._onboarded)
        self.onboarding_panel.success_action_requested.connect(self.success_action_requested.emit)
        self.pages.addWidget(self.onboarding_panel)

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

    def _on_selection_changed(self) -> None:
        account_id = self.selected_account_id
        self.restore_btn.setEnabled(bool(account_id and self._restore_service is not None))

    def open_onboarding(self) -> None:
        self.onboarding_panel.reset()
        self.pages.setCurrentWidget(self.onboarding_panel)

    def show_accounts(self) -> None:
        self.refresh()
        self.pages.setCurrentIndex(0)

    def refresh(self) -> None:
        selected_id = self.selected_account_id
        self.model.removeRows(0, self.model.rowCount())
        if self._accounts is None:
            return
        query = self.search_input.text().casefold() if hasattr(self, "search_input") else ""
        accounts = tuple(
            account
            for account in self._accounts.list_accounts()
            if not query
            or query in account.display_name.casefold()
            or query in account.platform_uid.casefold()
        )
        for account in accounts:
            row = (
                QStandardItem(account.display_name),
                QStandardItem(account.status.value.replace("_", " ").title()),
                QStandardItem(mask_email(account.primary_email)),
                QStandardItem(mask_phone(account.phone)),
                QStandardItem(account.preferred_app.value.replace("_", " ").title()),
                QStandardItem(account.platform_uid),
            )
            row[0].setData(account.id, Qt.ItemDataRole.UserRole)
            self.model.appendRow(row)
        active = sum(account.status is AccountStatus.ACTIVE for account in accounts)
        attention = len(accounts) - active
        labels = self.metrics.findChildren(QLabel)
        for label, value in zip(labels[::2], (len(accounts), active, attention), strict=True):
            label.setText(str(value))

        if selected_id:
            self._select_row(selected_id)
        else:
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
