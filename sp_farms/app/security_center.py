import csv
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QDesktopServices, QStandardItem, QStandardItemModel
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
from sp_farms.domain.security import (
    AccountSecurityAudit,
    SystemSecurityReport,
)

if TYPE_CHECKING:
    from sp_farms.application.security_service import SecurityService


AUDIT_COLUMNS = (
    "Account",
    "UID",
    "Security Score",
    "Auth State",
    "2FA",
    "Token Health",
    "Expires In",
    "Session",
    "Vault",
    "Primary Warning",
)


class SecurityFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._filter_mode = "All"

    def set_filter_mode(self, mode: str) -> None:
        self._filter_mode = mode
        self.invalidate()

    def filterAcceptsRow(
        self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex
    ) -> bool:
        model = self.sourceModel()
        if model is None:
            return False

        # Filter mode
        if self._filter_mode != "All":
            score_val = int(
                str(
                    model.data(
                        model.index(source_row, 2, source_parent),
                        Qt.ItemDataRole.DisplayRole,
                    )
                    or "0"
                )
                .replace("/ 100", "")
                .strip()
            )
            auth_val = str(
                model.data(
                    model.index(source_row, 3, source_parent),
                    Qt.ItemDataRole.DisplayRole,
                )
                or ""
            )
            two_fa_val = str(
                model.data(
                    model.index(source_row, 4, source_parent),
                    Qt.ItemDataRole.DisplayRole,
                )
                or ""
            )
            token_val = str(
                model.data(
                    model.index(source_row, 5, source_parent),
                    Qt.ItemDataRole.DisplayRole,
                )
                or ""
            )
            session_val = str(
                model.data(
                    model.index(source_row, 7, source_parent),
                    Qt.ItemDataRole.DisplayRole,
                )
                or ""
            )

            if self._filter_mode == "Action Required" and score_val >= 80:
                return False
            if self._filter_mode == "Missing 2FA" and "Enabled" in two_fa_val:
                return False
            if self._filter_mode == "Token Expiring / Expired" and not (
                "Expiring" in token_val or "Expired" in token_val
            ):
                return False
            if self._filter_mode == "Stale Sessions" and "Stale" not in session_val:
                return False
            if self._filter_mode == "Challenge Required" and "Challenge" not in auth_val:
                return False

        # Text search
        pattern = self.filterRegularExpression().pattern()
        if not pattern:
            return True

        for col in (0, 1, 9):
            idx = model.index(source_row, col, source_parent)
            text = str(model.data(idx, Qt.ItemDataRole.DisplayRole) or "")
            if pattern.casefold() in text.casefold():
                return True
        return False


class SecurityInspectorPanel(Panel):
    reauth_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("securityInspectorPanel")
        self.setMinimumWidth(320)
        self.setMaximumWidth(440)
        self._current_audit: AccountSecurityAudit | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)

        # Header
        header_row = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        self.title_label = QLabel("Select an Account")
        self.title_label.setStyleSheet("font-weight: 700; font-size: 14px;")
        self.title_label.setWordWrap(True)
        self.uid_label = QLabel("No selection")
        self.uid_label.setProperty("muted", True)
        header_text.addWidget(self.title_label)
        header_text.addWidget(self.uid_label)
        header_row.addLayout(header_text, stretch=1)

        self.score_chip = StatusChip("—", "neutral")
        header_row.addWidget(self.score_chip, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setProperty("muted", True)
        layout.addWidget(sep)

        # Form breakdown
        form = QFormLayout()
        form.setSpacing(6)
        self.auth_label = QLabel("—")
        self.two_fa_label = QLabel("—")
        self.token_label = QLabel("—")
        self.expires_label = QLabel("—")
        self.scopes_label = QLabel("—")
        self.scopes_label.setWordWrap(True)
        self.session_label = QLabel("—")
        self.vault_label = QLabel("—")
        self.backup_label = QLabel("—")

        form.addRow("Auth State:", self.auth_label)
        form.addRow("2FA Status:", self.two_fa_label)
        form.addRow("Token Health:", self.token_label)
        form.addRow("Expires In:", self.expires_label)
        form.addRow("Granted Scopes:", self.scopes_label)
        form.addRow("Session Health:", self.session_label)
        form.addRow("Keyring Vault:", self.vault_label)
        form.addRow("Backup Protection:", self.backup_label)
        layout.addLayout(form)

        # Warnings & Remediation Section
        remed_heading = QLabel("Remediation Guidance")
        remed_heading.setStyleSheet("font-weight: 600; margin-top: 4px;")
        layout.addWidget(remed_heading)

        self.remed_list = QListWidget()
        self.remed_list.setMaximumHeight(110)
        self.remed_list.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.remed_list)

        # Actions Section
        action_heading = QLabel("Supported Actions")
        action_heading.setStyleSheet("font-weight: 600; margin-top: 4px;")
        layout.addWidget(action_heading)

        btn_box = QVBoxLayout()
        btn_box.setSpacing(6)

        self.reauth_btn = PrimaryButton("Re-Authenticate via Meta OAuth")
        self.reauth_btn.setToolTip(
            "Trigger official OAuth authorization to refresh token and scopes safely."
        )
        self.reauth_btn.clicked.connect(self._on_reauth_clicked)
        btn_box.addWidget(self.reauth_btn)

        self.copy_diagnostics_btn = SecondaryButton("Copy Security Diagnostics")
        self.copy_diagnostics_btn.clicked.connect(self._copy_diagnostics)
        btn_box.addWidget(self.copy_diagnostics_btn)

        layout.addLayout(btn_box)

        # Notice
        safety_notice = QLabel(
            "SP-Farms Security Policy: Operator credentials are never bypassed or spoofed. "
            "Meta challenges or checkpoints must be verified in browser or device."
        )
        safety_notice.setProperty("muted", True)
        safety_notice.setStyleSheet("font-size: 11px; font-style: italic;")
        safety_notice.setWordWrap(True)
        layout.addWidget(safety_notice)

        layout.addStretch(1)

    def inspect_audit(self, audit: AccountSecurityAudit | None) -> None:
        self._current_audit = audit
        if audit is None:
            self._reset_view()
            return

        self.title_label.setText(audit.display_name)
        self.uid_label.setText(f"UID: {audit.platform_uid or 'Unlinked'}")

        # Score Chip
        if audit.security_score >= 80:
            self.score_chip.update_state("success", f"{audit.security_score} / 100")
        elif audit.security_score >= 50:
            self.score_chip.update_state("warning", f"{audit.security_score} / 100")
        else:
            self.score_chip.update_state("error", f"{audit.security_score} / 100")

        self.auth_label.setText(audit.auth_state.value.replace("_", " ").title())
        self.two_fa_label.setText("Enabled (2FA)" if audit.two_factor_enabled else "Disabled ⚠️")
        self.token_label.setText(audit.token_health.value.replace("_", " ").title())

        if audit.days_until_expiration is not None:
            self.expires_label.setText(f"{audit.days_until_expiration} days")
        else:
            self.expires_label.setText("Never / Unknown")

        scopes_str = ", ".join(audit.granted_scopes) if audit.granted_scopes else "None"
        self.scopes_label.setText(scopes_str)

        self.session_label.setText("Stale (>14 days)" if audit.session_stale else "Active / Fresh")
        self.vault_label.setText(
            "Secured in OS Keyring" if audit.vault_synced else "Missing Vault Secret"
        )
        self.backup_label.setText("Authenticated AES-256-GCM")

        # Remediation
        self.remed_list.clear()
        if audit.remediation_steps:
            for step in audit.remediation_steps:
                item = QListWidgetItem(f"• {step}")
                self.remed_list.addItem(item)
        else:
            item = QListWidgetItem("✓ No urgent remediation required.")
            self.remed_list.addItem(item)

        self.reauth_btn.setEnabled(True)
        self.copy_diagnostics_btn.setEnabled(True)

    def _reset_view(self) -> None:
        self.title_label.setText("Select an Account")
        self.uid_label.setText("No selection")
        self.score_chip.update_state("neutral", "—")
        self.auth_label.setText("—")
        self.two_fa_label.setText("—")
        self.token_label.setText("—")
        self.expires_label.setText("—")
        self.scopes_label.setText("—")
        self.session_label.setText("—")
        self.vault_label.setText("—")
        self.backup_label.setText("—")
        self.remed_list.clear()
        self.reauth_btn.setEnabled(False)
        self.copy_diagnostics_btn.setEnabled(False)

    def _on_reauth_clicked(self) -> None:
        if self._current_audit:
            self.reauth_requested.emit(self._current_audit.account_id)

    def _copy_diagnostics(self) -> None:
        if not self._current_audit:
            return
        from PySide6.QtGui import QGuiApplication

        clip = QGuiApplication.clipboard()
        if clip:
            diag = (
                f"Account: {self._current_audit.display_name} ({self._current_audit.account_id})\n"
                f"Platform UID: {self._current_audit.platform_uid}\n"
                f"Score: {self._current_audit.security_score}/100\n"
                f"Auth State: {self._current_audit.auth_state.value}\n"
                f"2FA: {self._current_audit.two_factor_enabled}\n"
                f"Token Health: {self._current_audit.token_health.value}\n"
                f"Session Stale: {self._current_audit.session_stale}\n"
                f"Vault Synced: {self._current_audit.vault_synced}\n"
                f"Warnings: {'; '.join(self._current_audit.warnings)}\n"
            )
            clip.setText(diag)


class SecurityCenterWorkspace(QWidget):
    route_requested = Signal(str)

    def __init__(
        self,
        security_service: "SecurityService | None" = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("securityCenterWorkspace")
        self._security_service = security_service
        self._audits: list[AccountSecurityAudit] = []

        self._init_models()
        self._init_ui()

    def _init_models(self) -> None:
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(list(AUDIT_COLUMNS))
        self.proxy = SecurityFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Header Title
        header_row = QHBoxLayout()
        heading = QLabel("Security Center")
        heading.setProperty("heading", True)
        header_row.addWidget(heading)
        header_row.addStretch(1)

        self.audit_btn = PrimaryButton("Run Security Audit")
        self.audit_btn.clicked.connect(self.refresh)
        header_row.addWidget(self.audit_btn)
        root.addLayout(header_row)

        # Metrics Bar
        self.metrics_bar = MetricRow(
            [
                ("Total Accounts", "0"),
                ("Secure (80+)", "0"),
                ("Missing 2FA", "0"),
                ("Token Issues", "0"),
                ("Stale Sessions", "0"),
            ]
        )
        root.addWidget(self.metrics_bar)

        # Filter & Search Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search account security status by name or UID...")
        self.search_input.textChanged.connect(self.proxy.setFilterRegularExpression)
        toolbar.addWidget(self.search_input, stretch=2)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(
            [
                "All",
                "Action Required",
                "Missing 2FA",
                "Token Expiring / Expired",
                "Stale Sessions",
                "Challenge Required",
            ]
        )
        self.filter_combo.currentTextChanged.connect(self.proxy.set_filter_mode)
        toolbar.addWidget(self.filter_combo)

        self.export_btn = SecondaryButton("Export Audit (CSV)")
        self.export_btn.clicked.connect(self._export_csv)
        toolbar.addWidget(self.export_btn)

        root.addLayout(toolbar)

        # Splitter with Table and Inspector
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("securitySplitter")
        splitter.setChildrenCollapsible(False)

        # Table
        self.table = CompactTable()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.selectionModel().selectionChanged.connect(self._on_row_selected)
        self._format_header()
        splitter.addWidget(self.table)

        # Inspector
        self.inspector = SecurityInspectorPanel()
        self.inspector.reauth_requested.connect(self._handle_reauth)
        splitter.addWidget(self.inspector)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([850, 360])

        root.addWidget(splitter, stretch=1)

    def _format_header(self) -> None:
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(AUDIT_COLUMNS)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

    def refresh(self) -> None:
        if self._security_service is None:
            return

        report: SystemSecurityReport = self._security_service.generate_system_report()
        self.metrics_bar.value_labels[0].setText(str(report.total_accounts))
        self.metrics_bar.value_labels[1].setText(str(report.secure_accounts))
        self.metrics_bar.value_labels[2].setText(str(report.missing_2fa_count))
        self.metrics_bar.value_labels[3].setText(
            str(report.expiring_tokens_count + report.expired_tokens_count)
        )
        self.metrics_bar.value_labels[4].setText(str(report.stale_sessions_count))

        # Re-fetch audits
        accounts = list(self._security_service._account_service.list_accounts())
        self._audits = [self._security_service.audit_account(a) for a in accounts]

        self.model.setRowCount(0)
        for audit in self._audits:
            exp_str = (
                f"{audit.days_until_expiration}d"
                if audit.days_until_expiration is not None
                else "—"
            )
            warning_text = audit.warnings[0] if audit.warnings else "None"

            items = [
                QStandardItem(audit.display_name),
                QStandardItem(audit.platform_uid or "—"),
                QStandardItem(f"{audit.security_score} / 100"),
                QStandardItem(audit.auth_state.value.replace("_", " ").title()),
                QStandardItem("Enabled" if audit.two_factor_enabled else "Missing"),
                QStandardItem(audit.token_health.value.replace("_", " ").title()),
                QStandardItem(exp_str),
                QStandardItem("Stale" if audit.session_stale else "Healthy"),
                QStandardItem("Vaulted" if audit.vault_synced else "Missing"),
                QStandardItem(warning_text),
            ]
            for it in items:
                it.setEditable(False)
            self.model.appendRow(items)

    def _on_row_selected(self) -> None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            self.inspector.inspect_audit(None)
            return
        source_idx = self.proxy.mapToSource(indexes[0])
        row = source_idx.row()
        if 0 <= row < len(self._audits):
            self.inspector.inspect_audit(self._audits[row])

    def _handle_reauth(self, account_id: str) -> None:
        if self._security_service is None:
            return
        res = self._security_service.generate_reauth_url_or_guidance(account_id)
        if res.get("status") == "error":
            QMessageBox.critical(self, "Re-Authentication Error", res.get("message", "Error"))
            return

        oauth_url = res.get("oauth_url", "")
        guidance = res.get("guidance", "")

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Meta OAuth Re-Authentication")
        msg_box.setText(f"Re-Authorization for {res.get('account_name')}")
        msg_box.setInformativeText(guidance)

        if oauth_url:
            open_btn = msg_box.addButton("Open in Browser", QMessageBox.ButtonRole.ActionRole)
        msg_box.addButton("Close", QMessageBox.ButtonRole.RejectRole)

        msg_box.exec()

        if oauth_url and msg_box.clickedButton() == open_btn:
            from PySide6.QtCore import QUrl

            QDesktopServices.openUrl(QUrl(oauth_url))

    def _export_csv(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Security Audit to CSV",
            "security_audit.csv",
            "CSV Files (*.csv)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "Account ID",
                        "Name",
                        "Platform UID",
                        "Security Score",
                        "Auth State",
                        "2FA Enabled",
                        "Token Health",
                        "Days to Expiry",
                        "Session Stale",
                        "Vault Synced",
                        "Warnings",
                        "Remediation",
                    ]
                )
                for a in self._audits:
                    writer.writerow(
                        [
                            a.account_id,
                            a.display_name,
                            a.platform_uid,
                            a.security_score,
                            a.auth_state.value,
                            a.two_factor_enabled,
                            a.token_health.value,
                            a.days_until_expiration if a.days_until_expiration is not None else "",
                            a.session_stale,
                            a.vault_synced,
                            "; ".join(a.warnings),
                            "; ".join(a.remediation_steps),
                        ]
                    )
            QMessageBox.information(
                self, "Export Complete", f"Exported successfully to {file_path}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Could not write CSV: {exc}")
