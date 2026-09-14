from PySide6.QtCore import Qt, Signal
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
from sp_farms.app.widgets import CompactTable, MetricRow, Panel, PrimaryButton
from sp_farms.application.account_onboarding_service import AccountOnboardingService
from sp_farms.application.account_service import AccountService
from sp_farms.domain.account_onboarding import mask_email, mask_phone
from sp_farms.domain.accounts import AccountStatus


class AccountWorkspace(QWidget):
    success_action_requested = Signal(str, str)

    def __init__(
        self,
        accounts: AccountService | None,
        onboarding: AccountOnboardingService | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("accountWorkspace")
        self._accounts = accounts
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
        self.metrics = MetricRow(
            (("Accounts", "0"), ("Active", "0"), ("Needs attention", "0"))
        )
        listing_layout.addWidget(self.metrics)
        toolbar = Panel()
        toolbar_layout = QHBoxLayout(toolbar)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search accounts")
        self.search_input.textChanged.connect(self.refresh)
        self.add_btn = PrimaryButton("Add account")
        self.add_btn.setObjectName("addAccountButton")
        self.add_btn.clicked.connect(self.open_onboarding)
        toolbar_layout.addWidget(self.search_input, stretch=1)
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
        listing_layout.addWidget(self.table, stretch=1)
        self.pages.addWidget(listing)

        self.onboarding_panel = AccountOnboardingPanel(onboarding)
        self.onboarding_panel.cancelled.connect(self.show_accounts)
        self.onboarding_panel.onboarding_completed.connect(self._onboarded)
        self.onboarding_panel.success_action_requested.connect(
            self.success_action_requested.emit
        )
        self.pages.addWidget(self.onboarding_panel)

    def open_onboarding(self) -> None:
        self.onboarding_panel.reset()
        self.pages.setCurrentWidget(self.onboarding_panel)

    def show_accounts(self) -> None:
        self.refresh()
        self.pages.setCurrentIndex(0)

    def refresh(self) -> None:
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

    def select_account(self, account_id: str) -> None:
        self.show_accounts()
        self._select_row(account_id)

    def _select_row(self, account_id: str) -> None:
        for row in range(self.model.rowCount()):
            if self.model.item(row, 0).data(Qt.ItemDataRole.UserRole) == account_id:
                self.table.selectRow(row)
                self.table.scrollTo(self.model.index(row, 0))
                break

    def _onboarded(self, account_id: str) -> None:
        self.refresh()
        self._select_row(account_id)
