from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.widgets import Panel, PrimaryButton, SecondaryButton, StatusChip
from sp_farms.application.account_onboarding_service import AccountOnboardingService
from sp_farms.domain.account_onboarding import AccountOnboardingRequest, OnboardingSource
from sp_farms.domain.accounts import PreferredApp

_SUCCESS_ACTIONS = (
    ("Open Account", "open_account"),
    ("Assign Device", "assign_device"),
    ("Add Category", "add_category"),
    ("Security Center", "security_center"),
    ("Pages", "pages"),
    ("Content", "content"),
    ("Scheduler", "scheduler"),
    ("Export Metadata", "export_metadata"),
)


class AccountOnboardingPanel(Panel):
    onboarding_completed = Signal(str)
    success_action_requested = Signal(str, str)
    cancelled = Signal()

    def __init__(
        self,
        service: AccountOnboardingService | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("accountOnboardingPanel")
        self._service = service
        self._account_id = ""
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)
        heading = QLabel("Add authorized account")
        heading.setStyleSheet("font-size: 17px; font-weight: 700;")
        root.addWidget(heading)
        notice = QLabel(
            "Add an account you own or are authorized to manage. This does not create accounts, "
            "solve challenges, or collect credentials."
        )
        notice.setWordWrap(True)
        notice.setProperty("muted", True)
        root.addWidget(notice)

        self.pages = QStackedWidget()
        root.addWidget(self.pages, stretch=1)
        self.pages.addWidget(self._build_form())
        self.pages.addWidget(self._build_success())

    def _build_form(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        self.source_input = QComboBox()
        for label, source in (
            ("Manual local record", OnboardingSource.MANUAL),
            ("Authorized metadata import", OnboardingSource.AUTHORIZED_METADATA_IMPORT),
            ("Development/test account", OnboardingSource.DEVELOPMENT_TEST),
            ("Official Facebook login", OnboardingSource.OFFICIAL_FACEBOOK),
            ("Authorized session attachment", OnboardingSource.AUTHORIZED_SESSION),
        ):
            self.source_input.addItem(label, source.value)
        self.display_name_input = QLineEdit()
        self.platform_uid_input = QLineEdit()
        self.primary_email_input = QLineEdit()
        self.recovery_email_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.country_input = QLineEdit()
        self.locale_input = QLineEdit()
        self.preferred_app_input = QComboBox()
        for label, app in (
            ("Facebook", PreferredApp.FACEBOOK),
            ("Facebook Lite", PreferredApp.FACEBOOK_LITE),
            ("Browser", PreferredApp.BROWSER),
        ):
            self.preferred_app_input.addItem(label, app.value)
        self.notes_input = QPlainTextEdit()
        self.notes_input.setMaximumHeight(72)
        form.addRow("Source", self.source_input)
        form.addRow("Display name *", self.display_name_input)
        form.addRow("Platform UID *", self.platform_uid_input)
        form.addRow("Primary email *", self.primary_email_input)
        form.addRow("Recovery email", self.recovery_email_input)
        form.addRow("Phone", self.phone_input)
        form.addRow("Country", self.country_input)
        form.addRow("Locale", self.locale_input)
        form.addRow("Preferred app", self.preferred_app_input)
        form.addRow("Notes", self.notes_input)
        layout.addLayout(form)

        guidance = QLabel(
            "Use a persistent mailbox you control: Gmail, Outlook/Hotmail, iCloud, or Proton. "
            "Disposable email and temporary-number services are unsupported."
        )
        guidance.setWordWrap(True)
        guidance.setProperty("muted", True)
        layout.addWidget(guidance)
        self.import_input = QPlainTextEdit()
        self.import_input.setObjectName("accountMetadataImport")
        self.import_input.setPlaceholderText("Paste versioned authorized metadata JSON")
        self.import_input.setMaximumHeight(100)
        layout.addWidget(self.import_input)

        actions = QHBoxLayout()
        cancel = SecondaryButton("Cancel")
        cancel.clicked.connect(self.cancelled.emit)
        self.submit_btn = PrimaryButton("Add account")
        self.submit_btn.setObjectName("submitAccountOnboarding")
        self.submit_btn.clicked.connect(self._submit)
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(self.submit_btn)
        layout.addLayout(actions)
        self.status = StatusChip("Ready", "neutral")
        layout.addWidget(self.status)
        return page

    def _build_success(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.success_label = QLabel("Account added")
        self.success_label.setStyleSheet("font-size: 17px; font-weight: 700;")
        layout.addWidget(self.success_label)
        layout.addWidget(QLabel("Choose the next workspace action."))
        actions = QHBoxLayout()
        for label, key in _SUCCESS_ACTIONS:
            button = QPushButton(label)
            button.setProperty("actionKey", key)
            button.clicked.connect(lambda checked=False, action=key: self._request_action(action))
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        self.export_output = QPlainTextEdit()
        self.export_output.setObjectName("accountMetadataExport")
        self.export_output.setReadOnly(True)
        self.export_output.hide()
        layout.addWidget(self.export_output)
        layout.addStretch()
        return page

    def reset(self) -> None:
        for line_edit in (
            self.display_name_input,
            self.platform_uid_input,
            self.primary_email_input,
            self.recovery_email_input,
            self.phone_input,
            self.country_input,
            self.locale_input,
        ):
            line_edit.clear()
        self.notes_input.clear()
        self.import_input.clear()
        self.export_output.clear()
        self.export_output.hide()
        self.status.update_state("neutral", "Ready")
        self.pages.setCurrentIndex(0)

    def _submit(self) -> None:
        if self._service is None:
            self.status.update_state("error", "Account storage is unavailable")
            return
        try:
            source = OnboardingSource(str(self.source_input.currentData()))
            if source is OnboardingSource.AUTHORIZED_METADATA_IMPORT:
                account = self._service.import_metadata(self.import_input.toPlainText())
            elif source in {
                OnboardingSource.OFFICIAL_FACEBOOK,
                OnboardingSource.AUTHORIZED_SESSION,
            }:
                account = self._service.connect(source)
            else:
                account = self._service.onboard(
                    AccountOnboardingRequest(
                        source=source,
                        display_name=self.display_name_input.text(),
                        platform_uid=self.platform_uid_input.text(),
                        primary_email=self.primary_email_input.text(),
                        recovery_email=self.recovery_email_input.text() or None,
                        phone=self.phone_input.text(),
                        country=self.country_input.text(),
                        locale=self.locale_input.text(),
                        notes=self.notes_input.toPlainText(),
                        preferred_app=PreferredApp(
                            str(self.preferred_app_input.currentData())
                        ),
                    )
                )
        except ValueError as exc:
            self.status.update_state("error", str(exc))
            return
        self._account_id = account.id
        self.success_label.setText(f"{account.display_name} added")
        self.pages.setCurrentIndex(1)
        self.onboarding_completed.emit(account.id)

    def _request_action(self, action: str) -> None:
        if not self._account_id or self._service is None:
            return
        if action == "export_metadata":
            self.export_output.setPlainText(self._service.export_metadata(self._account_id))
            self.export_output.show()
        self.success_action_requested.emit(self._account_id, action)
