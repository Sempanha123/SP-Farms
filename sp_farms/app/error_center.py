from collections.abc import Sequence
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
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
from sp_farms.application.audit_service import AuditService
from sp_farms.domain.audit import (
    AuditEvent,
    AuditResult,
    ErrorDiagnosticEntry,
)

if TYPE_CHECKING:
    pass

ERROR_COLUMNS = (
    ("timestamp", "Timestamp"),
    ("code", "Code"),
    ("action", "Action"),
    ("target", "Target"),
    ("summary", "Summary"),
    ("retryable", "Retryable"),
    ("job_id", "Job ID"),
)

AUDIT_COLUMNS = (
    ("timestamp", "Timestamp"),
    ("initiator", "Initiator"),
    ("action", "Action"),
    ("target_type", "Target Type"),
    ("target_id", "Target ID"),
    ("result", "Result"),
    ("error_code", "Error Code"),
    ("retry_count", "Retries"),
    ("job_id", "Job ID"),
)


_ROOT_INDEX = QModelIndex()


class ErrorTableModel(QAbstractTableModel):
    def __init__(
        self,
        errors: Sequence[ErrorDiagnosticEntry] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._errors = list(errors)

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = _ROOT_INDEX) -> int:
        return 0 if parent.isValid() else len(self._errors)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = _ROOT_INDEX) -> int:
        return 0 if parent.isValid() else len(ERROR_COLUMNS)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if not index.isValid() or not (0 <= index.row() < len(self._errors)):
            return None
        err = self._errors[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return err.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            elif col == 1:
                return err.error_code
            elif col == 2:
                return err.title
            elif col == 3:
                return f"{err.target_type}:{err.target_id}"
            elif col == 4:
                return err.friendly_summary
            elif col == 5:
                return "Yes" if err.is_retryable else "No"
            elif col == 6:
                return err.job_id or "—"
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (0, 1, 5, 6):
                return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        elif role == Qt.ItemDataRole.UserRole:
            return err

        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(ERROR_COLUMNS)
        ):
            return ERROR_COLUMNS[section][1]
        return None

    def set_errors(self, errors: Sequence[ErrorDiagnosticEntry]) -> None:
        self.beginResetModel()
        self._errors = list(errors)
        self.endResetModel()

    def get_entry(self, row: int) -> ErrorDiagnosticEntry | None:
        if 0 <= row < len(self._errors):
            return self._errors[row]
        return None


class AuditTableModel(QAbstractTableModel):
    def __init__(
        self,
        events: Sequence[AuditEvent] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._events = list(events)

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = _ROOT_INDEX) -> int:
        return 0 if parent.isValid() else len(self._events)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = _ROOT_INDEX) -> int:
        return 0 if parent.isValid() else len(AUDIT_COLUMNS)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if not index.isValid() or not (0 <= index.row() < len(self._events)):
            return None
        ev = self._events[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return ev.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            elif col == 1:
                return ev.initiator
            elif col == 2:
                return ev.action
            elif col == 3:
                return ev.target_type
            elif col == 4:
                return ev.target_id
            elif col == 5:
                return ev.result.value.upper()
            elif col == 6:
                return ev.error_code or "—"
            elif col == 7:
                return str(ev.retry_count)
            elif col == 8:
                return ev.job_id or "—"
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (0, 1, 5, 6, 7, 8):
                return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == 5:
                if ev.result == AuditResult.FAILURE:
                    return QColor("#EF4444")
                elif ev.result == AuditResult.WARNING:
                    return QColor("#F59E0B")
                elif ev.result == AuditResult.SUCCESS:
                    return QColor("#10B981")
        elif role == Qt.ItemDataRole.UserRole:
            return ev

        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(AUDIT_COLUMNS)
        ):
            return AUDIT_COLUMNS[section][1]
        return None

    def set_events(self, events: Sequence[AuditEvent]) -> None:
        self.beginResetModel()
        self._events = list(events)
        self.endResetModel()

    def get_event(self, row: int) -> AuditEvent | None:
        if 0 <= row < len(self._events):
            return self._events[row]
        return None


class ErrorFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._search_text = ""
        self._filter_type = "all"  # "all", "retryable", "auth", "ratelimit", "device"

    def set_search_text(self, text: str) -> None:
        self._search_text = text.strip().lower()
        self.invalidate()

    def set_filter_type(self, filter_type: str) -> None:
        self._filter_type = filter_type
        self.invalidate()

    def filterAcceptsRow(
        self,
        source_row: int,
        source_parent: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        model = self.sourceModel()
        if not isinstance(model, ErrorTableModel):
            return True

        entry = model.get_entry(source_row)
        if not entry:
            return False

        if self._filter_type == "retryable" and not entry.is_retryable:
            return False
        if self._filter_type == "auth" and "AUTH" not in entry.error_code:
            return False
        if self._filter_type == "ratelimit" and "RATE_LIMIT" not in entry.error_code:
            return False
        if self._filter_type == "device" and "DEVICE" not in entry.error_code:
            return False

        if not self._search_text:
            return True

        target_str = f"{entry.target_type}:{entry.target_id}".lower()
        return (
            self._search_text in entry.error_code.lower()
            or self._search_text in entry.title.lower()
            or self._search_text in target_str
            or self._search_text in entry.friendly_summary.lower()
        )


class ErrorInspectorPanel(Panel):
    retry_requested = Signal(str)  # job_id
    open_target_requested = Signal(str, str)  # target_type, target_id
    diagnostics_copied = Signal(str)  # status message

    def __init__(self, audit_service: AuditService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._audit_service = audit_service
        self._current_entry: ErrorDiagnosticEntry | None = None
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Header
        self.title_label = QLabel("Select an Error")
        self.title_label.setProperty("heading", True)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.status_chip = StatusChip("No selection", "neutral")
        layout.addWidget(self.status_chip, alignment=Qt.AlignmentFlag.AlignLeft)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(10)

        # 1. Friendly Summary
        summary_group = Panel()
        summary_layout = QVBoxLayout(summary_group)
        summary_title = QLabel("Friendly Summary")
        summary_title.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.summary_text = QLabel("Select an error row to inspect details.")
        self.summary_text.setWordWrap(True)
        self.summary_text.setStyleSheet("color: #4B5563;")
        summary_layout.addWidget(summary_title)
        summary_layout.addWidget(self.summary_text)
        scroll_layout.addWidget(summary_group)

        # 2. Safe Recovery Suggestion
        recovery_group = Panel()
        recovery_layout = QVBoxLayout(recovery_group)
        recovery_title = QLabel("Safe Recovery Suggestion")
        recovery_title.setStyleSheet("font-weight: 600; font-size: 13px; color: #059669;")
        self.recovery_text = QLabel("No action needed.")
        self.recovery_text.setWordWrap(True)
        recovery_layout.addWidget(recovery_title)
        recovery_layout.addWidget(self.recovery_text)
        scroll_layout.addWidget(recovery_group)

        # 3. Target Link
        target_group = Panel()
        target_layout = QHBoxLayout(target_group)
        self.target_label = QLabel("Target: —")
        self.target_label.setStyleSheet("font-weight: 500;")
        self.open_target_button = SecondaryButton("Open Target")
        self.open_target_button.setEnabled(False)
        self.open_target_button.clicked.connect(self._on_open_target)
        target_layout.addWidget(self.target_label)
        target_layout.addStretch()
        target_layout.addWidget(self.open_target_button)
        scroll_layout.addWidget(target_group)

        # 4. Technical Details
        tech_title = QLabel("Technical Details (Redacted)")
        tech_title.setStyleSheet("font-weight: 600; font-size: 13px;")
        scroll_layout.addWidget(tech_title)

        self.tech_edit = QTextEdit()
        self.tech_edit.setReadOnly(True)
        self.tech_edit.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 11px; background: #1E293B; "
            "color: #F1F5F9; border-radius: 6px; padding: 6px;"
        )
        self.tech_edit.setMinimumHeight(140)
        scroll_layout.addWidget(self.tech_edit)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        # Actions
        actions_layout = QHBoxLayout()
        self.copy_btn = SecondaryButton("Copy Diagnostics")
        self.copy_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self._copy_diagnostics)
        actions_layout.addWidget(self.copy_btn)

        self.retry_btn = PrimaryButton("Retry Operation")
        self.retry_btn.setEnabled(False)
        self.retry_btn.clicked.connect(self._retry_operation)
        actions_layout.addWidget(self.retry_btn)

        layout.addLayout(actions_layout)

    def set_entry(self, entry: ErrorDiagnosticEntry | None) -> None:
        self._current_entry = entry
        if not entry:
            self.title_label.setText("Select an Error")
            self.status_chip.update_state("neutral", "No selection")
            self.summary_text.setText("Select an error row to inspect details.")
            self.recovery_text.setText("No action needed.")
            self.target_label.setText("Target: —")
            self.open_target_button.setEnabled(False)
            self.tech_edit.setPlainText("")
            self.copy_btn.setEnabled(False)
            self.retry_btn.setEnabled(False)
            return

        self.title_label.setText(entry.title)
        self.status_chip.update_state(
            "active" if entry.is_retryable else "error",
            "Safe to Retry" if entry.is_retryable else "Manual Action Required",
        )
        self.summary_text.setText(entry.friendly_summary)
        self.recovery_text.setText(entry.safe_recovery_suggestion)
        self.target_label.setText(f"Target: {entry.target_type.upper()} ({entry.target_id})")
        self.open_target_button.setEnabled(bool(entry.target_type and entry.target_id))
        self.tech_edit.setPlainText(entry.technical_details)
        self.copy_btn.setEnabled(True)
        self.retry_btn.setEnabled(bool(entry.job_id and entry.is_retryable))

    def _copy_diagnostics(self) -> None:
        if not self._current_entry:
            return
        bundle = self._audit_service.generate_diagnostics_bundle(self._current_entry.id)
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(bundle)
            self.diagnostics_copied.emit("Diagnostics bundle copied to clipboard.")

    def _retry_operation(self) -> None:
        if not self._current_entry or not self._current_entry.job_id:
            return
        success = self._audit_service.retry_job(self._current_entry.job_id)
        if success:
            self.retry_requested.emit(self._current_entry.job_id)
            self.status_chip.update_state("active", "Retry Enqueued")
            self.retry_btn.setEnabled(False)

    def _on_open_target(self) -> None:
        if self._current_entry:
            self.open_target_requested.emit(
                self._current_entry.target_type, self._current_entry.target_id
            )


class ErrorCenterWorkspace(QWidget):
    route_requested = Signal(str)

    def __init__(self, audit_service: AuditService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._audit_service = audit_service
        self.setObjectName("errorCenterWorkspace")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Header metrics
        header = QHBoxLayout()
        title_block = QVBoxLayout()
        heading = QLabel("Audit Trail & Error Center")
        heading.setProperty("heading", True)
        subtitle = QLabel("Accountability, traceability, and safe recovery.")
        subtitle.setProperty("muted", True)
        title_block.addWidget(heading)
        title_block.addWidget(subtitle)
        header.addLayout(title_block)
        header.addStretch()

        self.refresh_btn = PrimaryButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self.refresh_btn)
        root.addLayout(header)

        # Metric summary
        self.metrics = MetricRow(
            (
                ("Total Audits", "0"),
                ("Errors & Failures", "0"),
                ("Retryable Errors", "0"),
                ("Security Alerts", "0"),
            )
        )
        root.addWidget(self.metrics)

        # Tabs for Error Center and Audit Trail
        self.tabs = QTabWidget()
        self._build_error_tab()
        self._build_audit_tab()
        self._build_retention_tab()
        root.addWidget(self.tabs, stretch=1)

        self.refresh()

    def _build_error_tab(self) -> None:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(6, 6, 6, 6)
        page_layout.setSpacing(8)

        # Filter bar
        filter_bar = QHBoxLayout()
        self.error_search = QLineEdit()
        self.error_search.setPlaceholderText("Search error codes, summaries, target IDs...")
        self.error_search.textChanged.connect(self._on_error_search_changed)
        filter_bar.addWidget(self.error_search, stretch=2)

        self.error_filter_combo = QComboBox()
        self.error_filter_combo.addItem("All Errors", "all")
        self.error_filter_combo.addItem("Retryable Only", "retryable")
        self.error_filter_combo.addItem("Authentication Issues", "auth")
        self.error_filter_combo.addItem("Rate Limit Issues", "ratelimit")
        self.error_filter_combo.addItem("Device Offline", "device")
        self.error_filter_combo.currentIndexChanged.connect(self._on_error_filter_changed)
        filter_bar.addWidget(self.error_filter_combo, stretch=1)
        page_layout.addLayout(filter_bar)

        # Splitter: Table and Inspector
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.error_table_model = ErrorTableModel()
        self.error_proxy = ErrorFilterProxyModel()
        self.error_proxy.setSourceModel(self.error_table_model)

        self.error_table = CompactTable()
        self.error_table.setModel(self.error_proxy)
        self.error_table.setSelectionBehavior(CompactTable.SelectionBehavior.SelectRows)
        self.error_table.setSelectionMode(CompactTable.SelectionMode.SingleSelection)
        self.error_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.error_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.error_table.selectionModel().selectionChanged.connect(self._on_error_selection_changed)
        splitter.addWidget(self.error_table)

        self.error_inspector = ErrorInspectorPanel(self._audit_service)
        self.error_inspector.retry_requested.connect(self._on_job_retried)
        self.error_inspector.open_target_requested.connect(self._on_open_target)
        splitter.addWidget(self.error_inspector)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        page_layout.addWidget(splitter, stretch=1)
        self.tabs.addTab(page, "Error Center")

    def _build_audit_tab(self) -> None:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(6, 6, 6, 6)
        page_layout.setSpacing(8)

        # Filter bar
        filter_bar = QHBoxLayout()
        self.audit_search = QLineEdit()
        self.audit_search.setPlaceholderText("Filter action, target, or initiator...")
        self.audit_search.textChanged.connect(self._on_audit_search_changed)
        filter_bar.addWidget(self.audit_search, stretch=2)

        self.audit_result_combo = QComboBox()
        self.audit_result_combo.addItem("All Results", "all")
        self.audit_result_combo.addItem("Failures Only", "failure")
        self.audit_result_combo.addItem("Success Only", "success")
        self.audit_result_combo.addItem("Warnings", "warning")
        self.audit_result_combo.currentIndexChanged.connect(self._on_audit_result_changed)
        filter_bar.addWidget(self.audit_result_combo, stretch=1)
        page_layout.addLayout(filter_bar)

        self.audit_model = AuditTableModel()
        self.audit_table = CompactTable()
        self.audit_table.setModel(self.audit_model)
        self.audit_table.setSelectionBehavior(CompactTable.SelectionBehavior.SelectRows)
        self.audit_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.audit_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        page_layout.addWidget(self.audit_table, stretch=1)

        self.tabs.addTab(page, "Audit Trail")

    def _build_retention_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        panel = Panel()
        p_layout = QVBoxLayout(panel)
        p_title = QLabel("Retention & Log Pruning Policy")
        p_title.setProperty("heading", True)
        p_layout.addWidget(p_title)

        p_desc = QLabel(
            "Audit records and error diagnostic logs are automatically retained locally in "
            "SQLite WAL. To prevent disk growth over long production runs, configure automated "
            "retention and prune records."
        )
        p_desc.setWordWrap(True)
        p_desc.setProperty("muted", True)
        p_layout.addWidget(p_desc)

        form = QFormLayout()
        self.retention_combo = QComboBox()
        self.retention_combo.addItem("7 Days", 7)
        self.retention_combo.addItem("14 Days", 14)
        self.retention_combo.addItem("30 Days (Default)", 30)
        self.retention_combo.addItem("60 Days", 60)
        self.retention_combo.addItem("90 Days", 90)
        self.retention_combo.addItem("180 Days", 180)
        self.retention_combo.setCurrentIndex(2)
        form.addRow("Log Retention Window:", self.retention_combo)
        p_layout.addLayout(form)

        prune_btn = SecondaryButton("Prune Expired Logs Now")
        prune_btn.clicked.connect(self._prune_logs)
        p_layout.addWidget(prune_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        p_layout.addStretch()

        layout.addWidget(panel)
        layout.addStretch()
        self.tabs.addTab(page, "Retention Policy")

    def refresh(self) -> None:
        events = tuple(self._audit_service.list_events(limit=250))
        errors = self._audit_service.list_error_diagnostics(limit=100)

        self.audit_model.set_events(events)
        self.error_table_model.set_errors(errors)

        total_audits = len(events)
        total_errors = len(errors)
        retryable_errors = sum(1 for e in errors if e.is_retryable)
        sec_alerts = sum(
            1
            for ev in events
            if ev.action.startswith("security.") and ev.result != AuditResult.SUCCESS
        )

        for label, val in zip(
            self.metrics.value_labels,
            (str(total_audits), str(total_errors), str(retryable_errors), str(sec_alerts)),
            strict=True,
        ):
            label.setText(val)

    def _on_error_search_changed(self, text: str) -> None:
        self.error_proxy.set_search_text(text)

    def _on_error_filter_changed(self) -> None:
        filter_type = self.error_filter_combo.currentData()
        self.error_proxy.set_filter_type(filter_type)

    def _on_error_selection_changed(self) -> None:
        selected_indexes = self.error_table.selectionModel().selectedRows()
        if not selected_indexes:
            self.error_inspector.set_entry(None)
            return

        proxy_idx = selected_indexes[0]
        source_idx = self.error_proxy.mapToSource(proxy_idx)
        entry = self.error_table_model.get_entry(source_idx.row())
        self.error_inspector.set_entry(entry)

    def _on_audit_search_changed(self, text: str) -> None:
        search = text.strip().lower()
        all_events = self._audit_service.list_events(limit=250)
        filtered = [
            ev
            for ev in all_events
            if search in ev.action.lower()
            or search in ev.target_id.lower()
            or search in ev.initiator.lower()
        ]
        self.audit_model.set_events(filtered)

    def _on_audit_result_changed(self) -> None:
        selected = self.audit_result_combo.currentData()
        res_filter = None if selected == "all" else AuditResult(selected)
        events = self._audit_service.list_events(limit=250, result=res_filter)
        self.audit_model.set_events(events)

    def _on_job_retried(self, job_id: str) -> None:
        self.refresh()

    def _on_open_target(self, target_type: str, target_id: str) -> None:
        ttype = target_type.lower()
        if ttype == "account":
            self.route_requested.emit("Accounts")
        elif ttype == "job":
            self.route_requested.emit("Automation")
        elif ttype == "device":
            self.route_requested.emit("Devices")
        elif ttype in ("page", "pages"):
            self.route_requested.emit("Pages")
        elif ttype in ("group", "groups"):
            self.route_requested.emit("Groups")

    def _prune_logs(self) -> None:
        days = int(self.retention_combo.currentData())
        pruned = self._audit_service.prune_audit_logs(retention_days=days)
        QMessageBox.information(
            self,
            "Log Pruning Complete",
            f"Successfully pruned {pruned} audit record(s) older than {days} days.",
        )
        self.refresh()
