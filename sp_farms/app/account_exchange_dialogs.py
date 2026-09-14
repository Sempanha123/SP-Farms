from collections.abc import Sequence
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from sp_farms.app.theme import DARK_PALETTE
from sp_farms.app.widgets import PrimaryButton, SecondaryButton
from sp_farms.application.account_exchange_service import AccountExchangeService
from sp_farms.domain.account_exchange import (
    ConflictStrategy,
    ExportFormat,
    ExportPreset,
    ImportDryRunResult,
)


class AccountExportDialog(QDialog):
    def __init__(
        self,
        exchange_service: AccountExchangeService,
        selected_account_ids: Sequence[str] | None = None,
        total_account_count: int = 0,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Accounts Metadata")
        self.setMinimumWidth(540)
        self._exchange = exchange_service
        self._selected_ids = list(selected_account_ids or [])
        self._total_count = total_account_count

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        # 1. Scope selection
        scope_group = QGroupBox("Account Selection")
        scope_layout = QVBoxLayout(scope_group)
        self.scope_all = QRadioButton(f"All Accounts ({total_account_count})")
        self.scope_selected = QRadioButton(f"Selected Accounts ({len(self._selected_ids)})")
        if self._selected_ids:
            self.scope_selected.setChecked(True)
        else:
            self.scope_all.setChecked(True)
            self.scope_selected.setEnabled(False)
        scope_layout.addWidget(self.scope_selected)
        scope_layout.addWidget(self.scope_all)
        layout.addWidget(scope_group)

        # 2. Format selection
        format_group = QGroupBox("Export Format")
        fmt_layout = QHBoxLayout(format_group)
        self.fmt_group = QButtonGroup(self)
        self.radio_csv = QRadioButton("CSV (.csv)")
        self.radio_xlsx = QRadioButton("Excel (.xlsx)")
        self.radio_json = QRadioButton("JSON (.json)")
        self.radio_csv.setChecked(True)
        for idx, btn in enumerate((self.radio_csv, self.radio_xlsx, self.radio_json)):
            self.fmt_group.addButton(btn, idx)
            fmt_layout.addWidget(btn)
        layout.addWidget(format_group)

        # 3. Preset selection
        preset_group = QGroupBox("Export Profile Preset")
        preset_layout = QVBoxLayout(preset_group)
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Full Metadata (All safe attributes)", ExportPreset.FULL)
        self.preset_combo.addItem("Basic / Minimal (UID, Name, Email, Phone)", ExportPreset.BASIC)
        self.preset_combo.addItem(
            "Security & Audit (2FA, Status, Security State)", ExportPreset.SECURITY_AUDIT
        )
        self.preset_combo.addItem(
            "Operations (Device, Provider, Preferred App)", ExportPreset.OPERATIONS
        )
        self.preset_label = QLabel("Note: Passwords, tokens, and secrets are strictly excluded.")
        self.preset_label.setStyleSheet(f"color: {DARK_PALETTE.muted_text}; font-size: 11px;")
        preset_layout.addWidget(self.preset_combo)
        preset_layout.addWidget(self.preset_label)
        layout.addWidget(preset_group)

        # 4. Vault backup option
        vault_group = QGroupBox("Encrypted Vault Backup (Optional)")
        vault_layout = QVBoxLayout(vault_group)
        self.chk_vault = QCheckBox("Export encrypted credentials into separate .spvault file")
        self.chk_vault.stateChanged.connect(self._toggle_vault_fields)
        self.vault_pass_edit = QLineEdit()
        self.vault_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.vault_pass_edit.setPlaceholderText("Enter strong passphrase (min 8 characters)...")
        self.vault_pass_edit.setEnabled(False)
        vault_layout.addWidget(self.chk_vault)
        vault_layout.addWidget(self.vault_pass_edit)
        layout.addWidget(vault_group)

        # Buttons
        btn_layout = QHBoxLayout()
        self.cancel_btn = SecondaryButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.export_btn = PrimaryButton("Export...")
        self.export_btn.clicked.connect(self._handle_export)
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.export_btn)
        layout.addLayout(btn_layout)

    def _toggle_vault_fields(self) -> None:
        self.vault_pass_edit.setEnabled(self.chk_vault.isChecked())

    def _handle_export(self) -> None:
        fmt = ExportFormat.CSV
        ext = "csv"
        filter_str = "CSV Files (*.csv)"
        if self.radio_xlsx.isChecked():
            fmt = ExportFormat.XLSX
            ext = "xlsx"
            filter_str = "Excel Files (*.xlsx)"
        elif self.radio_json.isChecked():
            fmt = ExportFormat.JSON
            ext = "json"
            filter_str = "JSON Files (*.json)"

        preset = self.preset_combo.currentData()
        target_ids = self._selected_ids if self.scope_selected.isChecked() else None

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Export File",
            f"accounts_export.{ext}",
            filter_str,
        )
        if not file_path:
            return

        try:
            exported_bytes = self._exchange.export_accounts(
                account_ids=target_ids,
                export_format=fmt,
                preset=preset,
            )
            Path(file_path).write_bytes(exported_bytes)

            # Check vault backup option
            if self.chk_vault.isChecked():
                passphrase = self.vault_pass_edit.text()
                if len(passphrase) < 8:
                    QMessageBox.warning(
                        self, "Invalid Passphrase", "Passphrase must be at least 8 characters."
                    )
                    return
                vault_bytes = self._exchange.export_vault_archive(
                    passphrase, account_ids=target_ids
                )
                vault_path = Path(file_path).with_suffix(".spvault")
                vault_path.write_bytes(vault_bytes)

            QMessageBox.information(
                self,
                "Export Complete",
                f"Successfully exported accounts to:\n{file_path}",
            )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", f"Failed to export accounts:\n{exc}")


class AccountImportDialog(QDialog):
    def __init__(
        self,
        exchange_service: AccountExchangeService,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import Accounts Metadata")
        self.resize(760, 560)
        self._exchange = exchange_service
        self._dry_run_result: ImportDryRunResult | None = None
        self._raw_file_bytes: bytes | None = None
        self._filename: str = ""

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 1. File selection row
        file_box = QGroupBox("Import Source File")
        file_layout = QHBoxLayout(file_box)
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("Select CSV, XLSX, or JSON metadata file...")
        self.browse_btn = SecondaryButton("Browse...")
        self.browse_btn.clicked.connect(self._choose_file)
        self.validate_btn = PrimaryButton("Dry Run / Validate")
        self.validate_btn.setEnabled(False)
        self.validate_btn.clicked.connect(self._run_dry_run)
        file_layout.addWidget(self.path_edit, stretch=1)
        file_layout.addWidget(self.browse_btn)
        file_layout.addWidget(self.validate_btn)
        layout.addWidget(file_box)

        # 2. Conflict strategy
        conflict_box = QGroupBox("Duplicate Conflict Strategy")
        conflict_layout = QHBoxLayout(conflict_box)
        self.radio_skip = QRadioButton("Skip duplicates (Keep existing)")
        self.radio_overwrite = QRadioButton("Overwrite existing accounts")
        self.radio_error = QRadioButton("Abort import if duplicates found")
        self.radio_skip.setChecked(True)
        conflict_layout.addWidget(self.radio_skip)
        conflict_layout.addWidget(self.radio_overwrite)
        conflict_layout.addWidget(self.radio_error)
        layout.addWidget(conflict_box)

        # 3. Validation Summary Card
        self.summary_label = QLabel("Select a file and click 'Dry Run / Validate' to preview.")
        self.summary_label.setStyleSheet(
            f"background-color: {DARK_PALETTE.surface}; padding: 8px 12px; "
            f"border-radius: 4px; border: 1px solid {DARK_PALETTE.border}; font-weight: 500;"
        )
        layout.addWidget(self.summary_label)

        # 4. Preview table
        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(5)
        headers = ["Row", "Status", "UID", "Name", "Details / Errors"]
        self.preview_table.setHorizontalHeaderLabels(headers)
        hdr = self.preview_table.horizontalHeader()
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.preview_table.setAlternatingRowColors(True)
        layout.addWidget(self.preview_table, stretch=1)

        # 5. Buttons
        btn_layout = QHBoxLayout()
        self.cancel_btn = SecondaryButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.import_btn = PrimaryButton("Execute Import")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._execute_import)
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.import_btn)
        layout.addLayout(btn_layout)

    def _choose_file(self) -> None:
        file_filters = (
            "Supported Files (*.csv *.xlsx *.json);;"
            "CSV Files (*.csv);;Excel Files (*.xlsx);;JSON Files (*.json)"
        )
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Account Metadata File",
            "",
            file_filters,
        )
        if not file_path:
            return

        self._filename = file_path
        self.path_edit.setText(file_path)
        self._raw_file_bytes = Path(file_path).read_bytes()
        self.validate_btn.setEnabled(True)
        self.import_btn.setEnabled(False)
        filename_only = Path(file_path).name
        self.summary_label.setText(f"Loaded {filename_only}. Click 'Dry Run / Validate' to verify.")

    def _run_dry_run(self) -> None:
        if not self._raw_file_bytes:
            return

        try:
            dry_run = self._exchange.dry_run_import(self._raw_file_bytes, filename=self._filename)
            self._dry_run_result = dry_run
            self._render_dry_run(dry_run)
            self.import_btn.setEnabled(dry_run.valid_count > 0)
        except Exception as exc:
            QMessageBox.critical(self, "Parse Error", f"Failed to parse import file:\n{exc}")

    def _render_dry_run(self, dry_run: ImportDryRunResult) -> None:
        status_text = (
            f"Dry Run Completed: Total {dry_run.total_rows} rows | "
            f"Valid: {dry_run.valid_count} | "
            f"Duplicates: {dry_run.duplicate_count} | "
            f"Errors: {dry_run.error_count}"
        )
        if dry_run.error_count > 0:
            self.summary_label.setText(f"⚠️ {status_text}")
            self.summary_label.setStyleSheet(
                f"background-color: {DARK_PALETTE.surface}; color: {DARK_PALETTE.warning}; "
                f"padding: 8px 12px; border-radius: 4px; border: 1px solid {DARK_PALETTE.warning};"
            )
        else:
            self.summary_label.setText(f"✓ {status_text}")
            self.summary_label.setStyleSheet(
                f"background-color: {DARK_PALETTE.surface}; color: {DARK_PALETTE.success}; "
                f"padding: 8px 12px; border-radius: 4px; border: 1px solid {DARK_PALETTE.success};"
            )

        self.preview_table.setRowCount(len(dry_run.rows))
        for r_idx, row in enumerate(dry_run.rows):
            item_row = QTableWidgetItem(str(row.row_index))
            item_row.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            if not row.is_valid:
                item_status = QTableWidgetItem("Invalid")
                item_status.setForeground(Qt.GlobalColor.red)
                details = "; ".join(row.errors)
            elif row.is_duplicate:
                item_status = QTableWidgetItem("Duplicate")
                item_status.setForeground(Qt.GlobalColor.yellow)
                details = f"Matches existing account {row.existing_account_id or ''}"
            else:
                item_status = QTableWidgetItem("Valid")
                item_status.setForeground(Qt.GlobalColor.green)
                details = "Ready to import"

            item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_uid = QTableWidgetItem(row.platform_uid)
            item_name = QTableWidgetItem(row.display_name)
            item_details = QTableWidgetItem(details)

            self.preview_table.setItem(r_idx, 0, item_row)
            self.preview_table.setItem(r_idx, 1, item_status)
            self.preview_table.setItem(r_idx, 2, item_uid)
            self.preview_table.setItem(r_idx, 3, item_name)
            self.preview_table.setItem(r_idx, 4, item_details)

    def _execute_import(self) -> None:
        if not self._dry_run_result:
            return

        strategy = ConflictStrategy.SKIP
        if self.radio_overwrite.isChecked():
            strategy = ConflictStrategy.OVERWRITE
        elif self.radio_error.isChecked():
            strategy = ConflictStrategy.ERROR

        try:
            result = self._exchange.execute_import(self._dry_run_result, conflict_strategy=strategy)
            QMessageBox.information(
                self,
                "Import Finished",
                f"Import complete:\n"
                f"• Created: {result.created_count}\n"
                f"• Updated: {result.updated_count}\n"
                f"• Skipped: {result.skipped_count}",
            )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Import Failed", f"Execution failed:\n{exc}")
