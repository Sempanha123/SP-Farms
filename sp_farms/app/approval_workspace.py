"""Approval Queue workspace UI for human-in-the-loop review and policy management."""

import json
import logging
from collections.abc import Sequence

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QSplitter,
    QTableView,
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
)
from sp_farms.application.approval_service import ApprovalService
from sp_farms.domain.approvals import (
    ApprovalRequest,
    ApprovalStatus,
)

logger = logging.getLogger(__name__)


class ApprovalRequestTableModel(QAbstractTableModel):
    HEADERS = ["Created", "Action", "Target", "Summary", "Requested By", "Status", "Expires"]

    def __init__(self, requests: Sequence[ApprovalRequest] = ()) -> None:
        super().__init__()
        self._requests: list[ApprovalRequest] = list(requests)

    def set_requests(self, requests: Sequence[ApprovalRequest]) -> None:
        self.beginResetModel()
        self._requests = list(requests)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex | None = None) -> int:
        return len(self._requests)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex | None = None) -> int:
        return len(self.HEADERS)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> str | None:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> str | None:
        if not index.isValid() or not (0 <= index.row() < len(self._requests)):
            return None
        req = self._requests[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return req.created_at.strftime("%Y-%m-%d %H:%M")
            if col == 1:
                return req.action_type.value.replace("_", " ").title()
            if col == 2:
                return req.target_name
            if col == 3:
                return req.summary
            if col == 4:
                return req.requested_by
            if col == 5:
                return req.status.value.upper()
            if col == 6:
                return req.expires_at.strftime("%Y-%m-%d %H:%M") if req.expires_at else "Never"

        return None

    def get_request(self, row: int) -> ApprovalRequest | None:
        if 0 <= row < len(self._requests):
            return self._requests[row]
        return None


class ApprovalDecisionDialog(QDialog):
    def __init__(
        self,
        request: ApprovalRequest,
        decision: str,  # "Approve" or "Reject"
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{decision}: {request.action_type.value}")
        self.resize(420, 240)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        form.addRow("Target:", QLabel(f"<b>{request.target_name}</b> ({request.target_id})"))
        form.addRow("Summary:", QLabel(request.summary))

        self.reviewer_edit = QLineEdit("Operator")
        form.addRow("Reviewer Name:", self.reviewer_edit)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Optional review notes or decision rationale...")
        self.notes_edit.setMaximumHeight(80)
        form.addRow("Notes:", self.notes_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(decision)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_reviewer(self) -> str:
        return self.reviewer_edit.text().strip() or "Operator"

    def get_notes(self) -> str:
        return self.notes_edit.toPlainText().strip()


class ApprovalInspectorPanel(Panel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.title_label = QLabel("<b>Approval Details</b>")
        layout.addWidget(self.title_label)

        self.details_label = QLabel("Select a request to inspect details.")
        self.details_label.setWordWrap(True)
        layout.addWidget(self.details_label)

        self.payload_view = QTextEdit()
        self.payload_view.setReadOnly(True)
        self.payload_view.setPlaceholderText("Payload metadata...")
        layout.addWidget(self.payload_view)

        # Action buttons
        btn_layout = QHBoxLayout()
        self.approve_btn = PrimaryButton("✔ Approve")
        self.approve_btn.setEnabled(False)
        self.reject_btn = SecondaryButton("✖ Reject")
        self.reject_btn.setEnabled(False)

        btn_layout.addWidget(self.approve_btn)
        btn_layout.addWidget(self.reject_btn)
        layout.addLayout(btn_layout)

    def set_request(self, req: ApprovalRequest | None) -> None:
        if req is None:
            self.title_label.setText("<b>Approval Details</b>")
            self.details_label.setText("Select a request to inspect details.")
            self.payload_view.clear()
            self.approve_btn.setEnabled(False)
            self.reject_btn.setEnabled(False)
            return

        self.title_label.setText(
            f"<b>{req.action_type.value.replace('_', ' ').title()}</b> — {req.status.value.upper()}"
        )
        expires_str = req.expires_at.strftime("%Y-%m-%d %H:%M") if req.expires_at else "Never"
        self.details_label.setText(
            f"<b>Target:</b> {req.target_name} ({req.target_id})<br>"
            f"<b>Summary:</b> {req.summary}<br>"
            f"<b>Requested By:</b> {req.requested_by}<br>"
            f"<b>Linked Job:</b> {req.job_id or 'None'}<br>"
            f"<b>Expires:</b> {expires_str}"
        )
        try:
            self.payload_view.setText(json.dumps(dict(req.payload), indent=2))
        except Exception:
            self.payload_view.setText(str(req.payload))

        is_pending = req.status == ApprovalStatus.PENDING
        self.approve_btn.setEnabled(is_pending)
        self.reject_btn.setEnabled(is_pending)


class ApprovalWorkspace(QWidget):
    """Central workspace for human authorization inbox and policy rules."""

    request_selected = Signal(str)

    def __init__(
        self,
        approval_service: ApprovalService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.approval_service = approval_service
        self._current_filter: ApprovalStatus | None = ApprovalStatus.PENDING
        self._selected_request: ApprovalRequest | None = None

        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Tabs: Inbox / Policy Rules
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Inbox
        inbox_tab = QWidget()
        inbox_layout = QVBoxLayout(inbox_tab)
        inbox_layout.setContentsMargins(0, 8, 0, 0)
        inbox_layout.setSpacing(10)

        # Filter bar
        top_bar = QHBoxLayout()
        self.filter_group = QButtonGroup(self)
        self.pending_btn = QRadioButton("Pending Reviews")
        self.pending_btn.setChecked(True)
        self.approved_btn = QRadioButton("Approved")
        self.rejected_btn = QRadioButton("Rejected")
        self.all_btn = QRadioButton("All Requests")

        self.filter_group.addButton(self.pending_btn)
        self.filter_group.addButton(self.approved_btn)
        self.filter_group.addButton(self.rejected_btn)
        self.filter_group.addButton(self.all_btn)

        self.pending_btn.toggled.connect(lambda: self._on_filter_changed(ApprovalStatus.PENDING))
        self.approved_btn.toggled.connect(lambda: self._on_filter_changed(ApprovalStatus.APPROVED))
        self.rejected_btn.toggled.connect(lambda: self._on_filter_changed(ApprovalStatus.REJECTED))
        self.all_btn.toggled.connect(lambda: self._on_filter_changed(None))

        top_bar.addWidget(QLabel("Filter:"))
        top_bar.addWidget(self.pending_btn)
        top_bar.addWidget(self.approved_btn)
        top_bar.addWidget(self.rejected_btn)
        top_bar.addWidget(self.all_btn)
        top_bar.addStretch()

        self.expire_stale_btn = SecondaryButton("Expire Stale")
        self.expire_stale_btn.clicked.connect(self._expire_stale)
        top_bar.addWidget(self.expire_stale_btn)

        inbox_layout.addLayout(top_bar)

        # Metrics Row
        self.metrics = MetricRow(
            [
                ("Pending Reviews", "0"),
                ("Approved", "0"),
                ("Rejected", "0"),
                ("Expired", "0"),
            ]
        )
        inbox_layout.addWidget(self.metrics)

        # Splitter: Table & Inspector
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.table_model = ApprovalRequestTableModel()
        self.table = CompactTable()
        self.table.setModel(self.table_model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.clicked.connect(self._on_table_select)
        splitter.addWidget(self.table)

        self.inspector = ApprovalInspectorPanel()
        self.inspector.approve_btn.clicked.connect(self._on_approve)
        self.inspector.reject_btn.clicked.connect(self._on_reject)
        splitter.addWidget(self.inspector)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        inbox_layout.addWidget(splitter)
        self.tabs.addTab(inbox_tab, "Approval Inbox")

    def _on_filter_changed(self, status: ApprovalStatus | None) -> None:
        self._current_filter = status
        self.refresh()

    def _on_table_select(self, index: QModelIndex) -> None:
        req = self.table_model.get_request(index.row())
        self._selected_request = req
        self.inspector.set_request(req)
        if req:
            self.request_selected.emit(req.id)

    def _on_approve(self) -> None:
        if not self._selected_request:
            return
        dlg = ApprovalDecisionDialog(self._selected_request, "Approve", self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            reviewer = dlg.get_reviewer()
            notes = dlg.get_notes()
            res = self.approval_service.approve_request(
                self._selected_request.id, reviewer=reviewer, notes=notes
            )
            if not res.is_success:
                QMessageBox.critical(
                    self, "Approval Failed", res.error.message if res.error else "Error"
                )
            else:
                self.refresh()

    def _on_reject(self) -> None:
        if not self._selected_request:
            return
        dlg = ApprovalDecisionDialog(self._selected_request, "Reject", self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            reviewer = dlg.get_reviewer()
            notes = dlg.get_notes()
            res = self.approval_service.reject_request(
                self._selected_request.id, reviewer=reviewer, notes=notes
            )
            if not res.is_success:
                QMessageBox.critical(
                    self, "Rejection Failed", res.error.message if res.error else "Error"
                )
            else:
                self.refresh()

    def _expire_stale(self) -> None:
        expired = self.approval_service.expire_stale_requests()
        QMessageBox.information(
            self, "Expired Stale", f"Processed and expired {len(expired)} stale request(s)."
        )
        self.refresh()

    def refresh(self) -> None:
        # Load filtered requests
        reqs = self.approval_service.list_inbox(status=self._current_filter, limit=200)
        self.table_model.set_requests(reqs)

        # Update metrics
        all_reqs = self.approval_service.list_inbox(status=None, limit=500)
        pending_count = sum(1 for r in all_reqs if r.status == ApprovalStatus.PENDING)
        approved_count = sum(1 for r in all_reqs if r.status == ApprovalStatus.APPROVED)
        rejected_count = sum(1 for r in all_reqs if r.status == ApprovalStatus.REJECTED)
        expired_count = sum(1 for r in all_reqs if r.status == ApprovalStatus.EXPIRED)

        if len(self.metrics.value_labels) >= 4:
            self.metrics.value_labels[0].setText(str(pending_count))
            self.metrics.value_labels[1].setText(str(approved_count))
            self.metrics.value_labels[2].setText(str(rejected_count))
            self.metrics.value_labels[3].setText(str(expired_count))

        # Reset selection if invalid
        if self._selected_request and self._selected_request.id not in [r.id for r in reqs]:
            self._selected_request = None
            self.inspector.set_request(None)
