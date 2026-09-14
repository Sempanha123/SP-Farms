from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.theme import ThemeMode
from sp_farms.app.widgets import Panel, PrimaryButton, StatusChip
from sp_farms.application.context import ApplicationContext


@dataclass(frozen=True, slots=True)
class SettingFieldMeta:
    section: str
    key: str
    title: str
    description: str
    requires_restart: bool = False


class SettingsWorkspace(QWidget):
    """Complete Settings Center with 14 sections, validation, and search."""

    theme_requested = Signal(str)
    queue_visibility_requested = Signal(bool)
    locale_requested = Signal(str)

    SECTION_NAMES = (
        "General",
        "Appearance",
        "Accounts",
        "Devices",
        "Meta Integration",
        "Storage",
        "Security",
        "Scheduler",
        "Network",
        "Notifications",
        "Backup",
        "Plugins",
        "Updates",
        "Diagnostics",
    )

    def __init__(
        self,
        settings: QSettings,
        context: ApplicationContext | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingsWorkspace")
        self._settings = settings
        self._context = context
        self._section_forms: dict[str, QFormLayout] = {}
        self._section_widgets: dict[str, QWidget] = {}
        self._field_meta: list[tuple[SettingFieldMeta, QWidget]] = []

        self._build_ui()
        self.load_all_settings()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header with Search
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title_col = QVBoxLayout()
        title = QLabel("Settings Center")
        title.setProperty("heading", True)
        subtitle = QLabel("Configure system preferences, operational defaults, and integrations")
        subtitle.setProperty("muted", True)
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header_row.addLayout(title_col, stretch=1)

        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 Search settings by name or keyword...")
        self.search.setFixedWidth(320)
        self.search.setAccessibleName("Search Settings")
        self.search.setAccessibleDescription("Filter settings by name or description")
        self.search.textChanged.connect(self._filter_settings)
        header_row.addWidget(self.search)

        root.addLayout(header_row)

        # Main Body: Split navigation sidebar + detail content
        content_split = QHBoxLayout()
        content_split.setSpacing(16)

        # Left Section Nav
        nav_panel = Panel()
        nav_panel.setFixedWidth(200)
        nav_layout = QVBoxLayout(nav_panel)
        nav_layout.setContentsMargins(4, 8, 4, 8)
        nav_layout.setSpacing(4)

        self.nav_list = QListWidget()
        self.nav_list.setFrameShape(QFrame.Shape.NoFrame)
        self.nav_list.setAccessibleName("Settings Sections")
        self.nav_list.setAccessibleDescription("List of available configuration sections")
        for section in self.SECTION_NAMES:
            item = QListWidgetItem(section)
            self.nav_list.addItem(item)
        self.nav_list.currentRowChanged.connect(self._on_section_selected)
        nav_layout.addWidget(self.nav_list)
        content_split.addWidget(nav_panel)
        QWidget.setTabOrder(self.search, self.nav_list)

        # Right Form Stack inside ScrollArea
        self.stack = QStackedWidget()
        for section in self.SECTION_NAMES:
            panel = self._build_section_panel(section)
            self.stack.addWidget(panel)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.stack)
        content_split.addWidget(scroll, stretch=1)

        root.addLayout(content_split, stretch=1)

        # Bottom Action Bar
        bottom_bar = QHBoxLayout()
        self.status_label = QLabel()
        self.status_label.setProperty("muted", True)
        bottom_bar.addWidget(self.status_label)
        bottom_bar.addStretch()

        self.btn_reset = QPushButton("Reset Section Defaults")
        self.btn_reset.clicked.connect(self.reset_current_section)
        bottom_bar.addWidget(self.btn_reset)

        self.btn_save = PrimaryButton("Save Settings")
        self.btn_save.clicked.connect(self.save_all)
        bottom_bar.addWidget(self.btn_save)

        root.addLayout(bottom_bar)

        self.nav_list.setCurrentRow(0)

    def _build_section_panel(self, section: str) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        panel = Panel()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 16, 16, 16)
        panel_layout.setSpacing(16)

        sec_title = QLabel(section)
        sec_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        panel_layout.addWidget(sec_title)

        form = QFormLayout()
        form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self._section_forms[section] = form

        self._populate_section_fields(section, form)

        panel_layout.addLayout(form)
        layout.addWidget(panel)
        layout.addStretch()

        self._section_widgets[section] = container
        return container

    def _populate_section_fields(self, section: str, form: QFormLayout) -> None:
        if section == "General":
            self.app_name_input = QLineEdit("SP-Farms")
            self.app_name_input.setReadOnly(True)
            self._add_field(
                form,
                section,
                "general/app_name",
                "Application Name",
                "Official SP-Farms title",
                self.app_name_input,
            )

            self.language_selector = QComboBox()
            self.language_selector.addItem("English (United States)", "en_US")
            self.language_selector.addItem("ភាសាខ្មែរ (Khmer)", "km_KH")
            self.language_selector.addItem("ไทย (Thai)", "th_TH")
            self.language_selector.addItem("Tiếng Việt (Vietnamese)", "vi_VN")
            self._add_field(
                form,
                section,
                "general/locale",
                "Display Language",
                "User interface language catalog (English, Khmer, Thai, Vietnamese)",
                self.language_selector,
            )

            self.start_minimized = QCheckBox("Start minimized to system tray")
            self._add_field(
                form,
                section,
                "general/start_minimized",
                "Startup State",
                "Run in background at boot",
                self.start_minimized,
            )

            self.auto_sync_interval = QSpinBox()
            self.auto_sync_interval.setRange(5, 3600)
            self.auto_sync_interval.setSuffix(" sec")
            self._add_field(
                form,
                section,
                "general/sync_interval",
                "Auto-Sync Interval",
                "Telemetry refresh frequency",
                self.auto_sync_interval,
            )

        elif section == "Appearance":
            self.theme = QComboBox()
            self.theme.addItems(("Dark", "Light"))
            self._add_field(
                form,
                section,
                "appearance/theme",
                "Theme Mode",
                "Active user interface palette",
                self.theme,
            )

            self.queue_visible = QCheckBox("Show job queue drawer")
            self._add_field(
                form,
                section,
                "window/jobQueueVisible",
                "Queue Drawer",
                "Visibility of bottom job execution tray",
                self.queue_visible,
            )

            self.compact_density = QCheckBox("Enable compact high-density tables")
            self._add_field(
                form,
                section,
                "appearance/compact_density",
                "Table Density",
                "Maximum visible items without excessive scrolling",
                self.compact_density,
            )

        elif section == "Accounts":
            self.max_active_accounts = QSpinBox()
            self.max_active_accounts.setRange(1, 1000)
            self._add_field(
                form,
                section,
                "accounts/max_active",
                "Max Active Accounts",
                "Concurrency limit for simultaneous account actions",
                self.max_active_accounts,
            )

            self.strict_fingerprinting = QCheckBox("Enforce strict device fingerprint binding")
            self.strict_fingerprinting.setChecked(True)
            self._add_field(
                form,
                section,
                "accounts/strict_fingerprint",
                "Fingerprint Binding",
                "Prevent accidental profile switching across devices",
                self.strict_fingerprinting,
            )

        elif section == "Devices":
            self.adb_path_input = QLineEdit()
            self.adb_path_input.setPlaceholderText("Auto-detect or custom adb.exe path")
            self._add_field(
                form,
                section,
                "devices/adb_path",
                "ADB Binary Path",
                "Path to Android platform-tools ADB",
                self.adb_path_input,
                restart=True,
            )

            self.default_provider = QComboBox()
            self.default_provider.addItems(("Auto-Detect", "LDPlayer", "MuMu", "Physical"))
            self._add_field(
                form,
                section,
                "devices/default_provider",
                "Preferred Provider",
                "Primary device emulator or hardware adapter",
                self.default_provider,
            )

            self.device_timeout = QSpinBox()
            self.device_timeout.setRange(5, 300)
            self.device_timeout.setSuffix(" sec")
            self._add_field(
                form,
                section,
                "devices/timeout",
                "Command Timeout",
                "Maximum wait time for ADB bridge commands",
                self.device_timeout,
            )

        elif section == "Meta Integration":
            self.meta_app_id = QLineEdit()
            self.meta_app_id.setPlaceholderText("15 to 16 digit Meta Application ID")
            self._add_field(
                form,
                section,
                "meta/app_id",
                "Meta App ID",
                "Official Facebook Developer Application ID",
                self.meta_app_id,
            )

            self.meta_app_secret_masked = QLineEdit()
            self.meta_app_secret_masked.setEchoMode(QLineEdit.EchoMode.Password)
            self.meta_app_secret_masked.setPlaceholderText("●●●●●●●● (Encrypted in OS Keyring)")
            self._add_field(
                form,
                section,
                "meta/app_secret",
                "Meta App Secret",
                "Stored securely in Credential Vault (Never in plaintext)",
                self.meta_app_secret_masked,
            )

            self.meta_redirect_uri = QLineEdit("https://localhost/oauth/callback")
            self._add_field(
                form,
                section,
                "meta/redirect_uri",
                "OAuth Callback URI",
                "Registered Meta login redirect endpoint",
                self.meta_redirect_uri,
            )

            self.meta_api_version = QComboBox()
            self.meta_api_version.addItems(("v21.0", "v20.0", "v19.0"))
            self._add_field(
                form,
                section,
                "meta/api_version",
                "Graph API Version",
                "Target Meta Graph API version",
                self.meta_api_version,
            )

        elif section == "Storage":
            self.db_path_input = QLineEdit()
            self.db_path_input.setPlaceholderText("sqlite:///sp_farms.db")
            self._add_field(
                form,
                section,
                "storage/database_path",
                "Database Location",
                "SQLite WAL primary database file",
                self.db_path_input,
                restart=True,
            )

            self.asset_cache_limit = QSpinBox()
            self.asset_cache_limit.setRange(100, 50000)
            self.asset_cache_limit.setSuffix(" MB")
            self._add_field(
                form,
                section,
                "storage/cache_limit",
                "Media Cache Limit",
                "Maximum storage allocated to cached media items",
                self.asset_cache_limit,
            )

        elif section == "Security":
            self.auto_lock_vault = QCheckBox("Automatically lock secret vault on idle")
            self.auto_lock_vault.setChecked(True)
            self._add_field(
                form,
                section,
                "security/auto_lock",
                "Auto-Lock Vault",
                "Lock memory-resident credentials when inactive",
                self.auto_lock_vault,
            )

            self.idle_lock_minutes = QSpinBox()
            self.idle_lock_minutes.setRange(1, 120)
            self.idle_lock_minutes.setSuffix(" min")
            self._add_field(
                form,
                section,
                "security/idle_timeout",
                "Idle Timeout",
                "Period before credential vault memory wipes",
                self.idle_lock_minutes,
            )

            self.enforce_https = QCheckBox("Reject non-HTTPS external network calls")
            self.enforce_https.setChecked(True)
            self._add_field(
                form,
                section,
                "security/enforce_https",
                "HTTPS Only",
                "Block insecure plaintext HTTP traffic",
                self.enforce_https,
            )

        elif section == "Scheduler":
            self.scheduler_poll_rate = QSpinBox()
            self.scheduler_poll_rate.setRange(1, 60)
            self.scheduler_poll_rate.setSuffix(" sec")
            self._add_field(
                form,
                section,
                "scheduler/poll_rate",
                "Poll Frequency",
                "Timer resolution for scheduled publication jobs",
                self.scheduler_poll_rate,
            )

            self.max_retries = QSpinBox()
            self.max_retries.setRange(0, 10)
            self._add_field(
                form,
                section,
                "scheduler/max_retries",
                "Max Failure Retries",
                "Times a failed scheduled post is retried",
                self.max_retries,
            )

        elif section == "Network":
            self.network_timeout = QSpinBox()
            self.network_timeout.setRange(5, 120)
            self.network_timeout.setSuffix(" sec")
            self._add_field(
                form,
                section,
                "network/timeout",
                "HTTP Request Timeout",
                "Socket connection and read timeout",
                self.network_timeout,
            )

            self.proxy_url = QLineEdit()
            self.proxy_url.setPlaceholderText("Optional proxy: http://proxy.corp:8080")
            self._add_field(
                form,
                section,
                "network/proxy",
                "Proxy Configuration",
                "Routing proxy for external API traffic",
                self.proxy_url,
                restart=True,
            )

        elif section == "Notifications":
            self.desktop_notifications = QCheckBox("Show Windows desktop toast notifications")
            self.desktop_notifications.setChecked(True)
            self._add_field(
                form,
                section,
                "notifications/toast",
                "Desktop Toasts",
                "Alerts on job completion and device disconnects",
                self.desktop_notifications,
            )

            self.sound_alerts = QCheckBox("Play sound on operational error")
            self._add_field(
                form,
                section,
                "notifications/sound",
                "Audio Alerts",
                "Audible chime when a job enters failed state",
                self.sound_alerts,
            )

        elif section == "Backup":
            self.auto_backup_enabled = QCheckBox("Enable automated daily backups")
            self.auto_backup_enabled.setChecked(True)
            self._add_field(
                form,
                section,
                "backup/auto_enabled",
                "Daily Auto-Backup",
                "Automated system snapshot creation",
                self.auto_backup_enabled,
            )

            self.backup_retention_count = QSpinBox()
            self.backup_retention_count.setRange(1, 100)
            self._add_field(
                form,
                section,
                "backup/retention_count",
                "Retained Backups",
                "Number of archives preserved before pruning",
                self.backup_retention_count,
            )

            self.backup_retention_days = QSpinBox()
            self.backup_retention_days.setRange(1, 365)
            self.backup_retention_days.setSuffix(" days")
            self._add_field(
                form,
                section,
                "backup/retention_days",
                "Max Backup Age",
                "Days before older archives are pruned",
                self.backup_retention_days,
            )

        elif section == "Plugins":
            self.allow_plugins = QCheckBox("Enable experimental plugin system")
            self._add_field(
                form,
                section,
                "plugins/enabled",
                "Plugin Runtime",
                "Load external extension hooks",
                self.allow_plugins,
                restart=True,
            )

            self.sandbox_plugins = QCheckBox("Enforce process isolation for plugins")
            self.sandbox_plugins.setChecked(True)
            self._add_field(
                form,
                section,
                "plugins/sandbox",
                "Plugin Sandboxing",
                "Execute plugins in restricted subprocesses",
                self.sandbox_plugins,
            )

        elif section == "Updates":
            self.check_updates_startup = QCheckBox("Check for application updates on launch")
            self.check_updates_startup.setChecked(True)
            self._add_field(
                form,
                section,
                "updates/check_startup",
                "Auto-Check Updates",
                "Query update channel on application launch",
                self.check_updates_startup,
            )

            self.update_channel = QComboBox()
            self.update_channel.addItems(("Stable", "Beta", "Dev"))
            self._add_field(
                form,
                section,
                "updates/channel",
                "Release Channel",
                "Target release stability tier",
                self.update_channel,
            )

        elif section == "Diagnostics":
            self.log_level = QComboBox()
            self.log_level.addItems(("INFO", "DEBUG", "WARNING", "ERROR"))
            self._add_field(
                form,
                section,
                "diagnostics/log_level",
                "Logging Verbosity",
                "Detail level recorded to log files",
                self.log_level,
                restart=True,
            )

            self.enable_telemetry = QCheckBox("Enable local device reliability metrics")
            self.enable_telemetry.setChecked(True)
            self._add_field(
                form,
                section,
                "diagnostics/telemetry",
                "Operational Telemetry",
                "Track uptime and provider error statistics",
                self.enable_telemetry,
            )

    def _add_field(
        self,
        form: QFormLayout,
        section: str,
        key: str,
        title: str,
        description: str,
        widget: QWidget,
        restart: bool = False,
    ) -> None:
        label_col = QVBoxLayout()
        label_col.setSpacing(2)

        header_row = QHBoxLayout()
        header_row.setSpacing(6)
        label = QLabel(title)
        label.setStyleSheet("font-weight: 600;")
        header_row.addWidget(label)

        if restart:
            chip = StatusChip("Restart Required", "warning")
            header_row.addWidget(chip)

        header_row.addStretch()
        label_col.addLayout(header_row)

        desc = QLabel(description)
        desc.setProperty("muted", True)
        desc.setStyleSheet("font-size: 11px;")
        label_col.addWidget(desc)

        lbl_container = QWidget()
        lbl_container.setLayout(label_col)

        widget.setAccessibleName(title)
        widget.setAccessibleDescription(description)

        form.addRow(lbl_container, widget)
        meta = SettingFieldMeta(section, key, title, description, restart)
        self._field_meta.append((meta, widget))

    def _on_section_selected(self, index: int) -> None:
        if 0 <= index < self.stack.count():
            self.stack.setCurrentIndex(index)

    def _filter_settings(self, query: str) -> None:
        q = query.strip().casefold()
        if not q:
            for item_idx in range(self.nav_list.count()):
                self.nav_list.item(item_idx).setHidden(False)
            return

        matching_sections: set[str] = set()
        for meta, _ in self._field_meta:
            haystack = f"{meta.section} {meta.title} {meta.description} {meta.key}".casefold()
            if q in haystack:
                matching_sections.add(meta.section)

        for item_idx in range(self.nav_list.count()):
            item = self.nav_list.item(item_idx)
            item.setHidden(item.text() not in matching_sections)

        current_item = self.nav_list.currentItem()
        if current_item and current_item.isHidden():
            for item_idx in range(self.nav_list.count()):
                it = self.nav_list.item(item_idx)
                if not it.isHidden():
                    self.nav_list.setCurrentRow(item_idx)
                    break

    def validate_settings(self) -> tuple[bool, list[str]]:
        """Validate all current settings inputs before saving."""
        errors: list[str] = []

        # Meta validation
        app_id = self.meta_app_id.text().strip()
        if app_id and not app_id.isdigit():
            errors.append("Meta App ID must contain only numeric digits.")

        redirect_uri = self.meta_redirect_uri.text().strip()
        if redirect_uri and not (
            redirect_uri.startswith("http://") or redirect_uri.startswith("https://")
        ):
            errors.append("Meta OAuth Redirect URI must start with http:// or https://")

        # Proxy validation
        proxy = self.proxy_url.text().strip()
        if proxy and not (
            proxy.startswith("http://")
            or proxy.startswith("https://")
            or proxy.startswith("socks5://")
        ):
            errors.append("Network Proxy must start with http://, https://, or socks5://")

        # ADB path validation
        adb_path = self.adb_path_input.text().strip()
        if adb_path:
            p = Path(adb_path)
            if p.exists() and p.is_dir():
                errors.append("ADB Path must point to an executable file, not a directory.")

        return (len(errors) == 0, errors)

    def load_all_settings(self) -> None:
        """Load values from QSettings into UI controls."""
        saved_theme = str(self._settings.value("appearance/theme", ThemeMode.DARK.value)).title()
        self.theme.setCurrentText(saved_theme)

        self.queue_visible.setChecked(
            bool(self._settings.value("window/jobQueueVisible", False, type=bool))
        )
        self.compact_density.setChecked(
            bool(self._settings.value("appearance/compact_density", False, type=bool))
        )
        saved_locale = str(self._settings.value("general/locale", "en_US"))
        idx = self.language_selector.findData(saved_locale)
        if idx >= 0:
            self.language_selector.setCurrentIndex(idx)

        self.start_minimized.setChecked(
            bool(self._settings.value("general/start_minimized", False, type=bool))
        )
        self.auto_sync_interval.setValue(
            int(self._settings.value("general/sync_interval", 30, type=int))
        )

        self.max_active_accounts.setValue(
            int(self._settings.value("accounts/max_active", 5, type=int))
        )
        self.strict_fingerprinting.setChecked(
            bool(self._settings.value("accounts/strict_fingerprint", True, type=bool))
        )

        self.adb_path_input.setText(str(self._settings.value("devices/adb_path", "")))
        self.default_provider.setCurrentText(
            str(self._settings.value("devices/default_provider", "Auto-Detect"))
        )
        self.device_timeout.setValue(int(self._settings.value("devices/timeout", 30, type=int)))

        self.meta_app_id.setText(str(self._settings.value("meta/app_id", "")))
        self.meta_redirect_uri.setText(
            str(self._settings.value("meta/redirect_uri", "https://localhost/oauth/callback"))
        )
        self.meta_api_version.setCurrentText(
            str(self._settings.value("meta/api_version", "v21.0"))
        )

        self.db_path_input.setText(str(self._settings.value("storage/database_path", "")))
        self.asset_cache_limit.setValue(
            int(self._settings.value("storage/cache_limit", 2048, type=int))
        )

        self.auto_lock_vault.setChecked(
            bool(self._settings.value("security/auto_lock", True, type=bool))
        )
        self.idle_lock_minutes.setValue(
            int(self._settings.value("security/idle_timeout", 15, type=int))
        )
        self.enforce_https.setChecked(
            bool(self._settings.value("security/enforce_https", True, type=bool))
        )

        self.scheduler_poll_rate.setValue(
            int(self._settings.value("scheduler/poll_rate", 5, type=int))
        )
        self.max_retries.setValue(int(self._settings.value("scheduler/max_retries", 3, type=int)))

        self.network_timeout.setValue(int(self._settings.value("network/timeout", 30, type=int)))
        self.proxy_url.setText(str(self._settings.value("network/proxy", "")))

        self.desktop_notifications.setChecked(
            bool(self._settings.value("notifications/toast", True, type=bool))
        )
        self.sound_alerts.setChecked(
            bool(self._settings.value("notifications/sound", False, type=bool))
        )

        self.auto_backup_enabled.setChecked(
            bool(self._settings.value("backup/auto_enabled", True, type=bool))
        )
        self.backup_retention_count.setValue(
            int(self._settings.value("backup/retention_count", 10, type=int))
        )
        self.backup_retention_days.setValue(
            int(self._settings.value("backup/retention_days", 30, type=int))
        )

        self.allow_plugins.setChecked(
            bool(self._settings.value("plugins/enabled", False, type=bool))
        )
        self.sandbox_plugins.setChecked(
            bool(self._settings.value("plugins/sandbox", True, type=bool))
        )

        self.check_updates_startup.setChecked(
            bool(self._settings.value("updates/check_startup", True, type=bool))
        )
        self.update_channel.setCurrentText(str(self._settings.value("updates/channel", "Stable")))

        self.log_level.setCurrentText(str(self._settings.value("diagnostics/log_level", "INFO")))
        self.enable_telemetry.setChecked(
            bool(self._settings.value("diagnostics/telemetry", True, type=bool))
        )

    def save_all(self) -> bool:
        """Validate and persist all settings."""
        is_valid, errors = self.validate_settings()
        if not is_valid:
            self.status_label.setText(f"❌ Validation failed: {errors[0]}")
            self.status_label.setStyleSheet("color: #e57373;")
            return False

        theme = self.theme.currentText().casefold()
        self._settings.setValue("appearance/theme", theme)
        self._settings.setValue("window/jobQueueVisible", self.queue_visible.isChecked())
        self._settings.setValue("appearance/compact_density", self.compact_density.isChecked())
        selected_locale = self.language_selector.currentData() or "en_US"
        self._settings.setValue("general/locale", selected_locale)
        if self._context and self._context.i18n_service:
            self._context.i18n_service.set_locale(selected_locale)
        self.locale_requested.emit(str(selected_locale))

        self._settings.setValue("general/start_minimized", self.start_minimized.isChecked())
        self._settings.setValue("general/sync_interval", self.auto_sync_interval.value())

        self._settings.setValue("accounts/max_active", self.max_active_accounts.value())
        self._settings.setValue(
            "accounts/strict_fingerprint", self.strict_fingerprinting.isChecked()
        )

        self._settings.setValue("devices/adb_path", self.adb_path_input.text().strip())
        self._settings.setValue("devices/default_provider", self.default_provider.currentText())
        self._settings.setValue("devices/timeout", self.device_timeout.value())

        self._settings.setValue("meta/app_id", self.meta_app_id.text().strip())
        self._settings.setValue("meta/redirect_uri", self.meta_redirect_uri.text().strip())
        self._settings.setValue("meta/api_version", self.meta_api_version.currentText())

        self._settings.setValue("storage/database_path", self.db_path_input.text().strip())
        self._settings.setValue("storage/cache_limit", self.asset_cache_limit.value())

        self._settings.setValue("security/auto_lock", self.auto_lock_vault.isChecked())
        self._settings.setValue("security/idle_timeout", self.idle_lock_minutes.value())
        self._settings.setValue("security/enforce_https", self.enforce_https.isChecked())

        self._settings.setValue("scheduler/poll_rate", self.scheduler_poll_rate.value())
        self._settings.setValue("scheduler/max_retries", self.max_retries.value())

        self._settings.setValue("network/timeout", self.network_timeout.value())
        self._settings.setValue("network/proxy", self.proxy_url.text().strip())

        self._settings.setValue("notifications/toast", self.desktop_notifications.isChecked())
        self._settings.setValue("notifications/sound", self.sound_alerts.isChecked())

        self._settings.setValue("backup/auto_enabled", self.auto_backup_enabled.isChecked())
        self._settings.setValue("backup/retention_count", self.backup_retention_count.value())
        self._settings.setValue("backup/retention_days", self.backup_retention_days.value())

        self._settings.setValue("plugins/enabled", self.allow_plugins.isChecked())
        self._settings.setValue("plugins/sandbox", self.sandbox_plugins.isChecked())

        self._settings.setValue("updates/check_startup", self.check_updates_startup.isChecked())
        self._settings.setValue("updates/channel", self.update_channel.currentText())

        self._settings.setValue("diagnostics/log_level", self.log_level.currentText())
        self._settings.setValue("diagnostics/telemetry", self.enable_telemetry.isChecked())

        self._settings.sync()

        self.theme_requested.emit(theme)
        self.queue_visibility_requested.emit(self.queue_visible.isChecked())

        self.status_label.setText("✓ Settings saved successfully.")
        self.status_label.setStyleSheet("color: #81c784;")
        return True

    def reset_current_section(self) -> None:
        """Reset the active section to factory defaults."""
        current_item = self.nav_list.currentItem()
        if not current_item:
            return
        section = current_item.text()

        if section == "General":
            idx = self.language_selector.findData("en_US")
            if idx >= 0:
                self.language_selector.setCurrentIndex(idx)
            self.start_minimized.setChecked(False)
            self.auto_sync_interval.setValue(30)
        elif section == "Appearance":
            self.theme.setCurrentText("Dark")
            self.queue_visible.setChecked(False)
            self.compact_density.setChecked(False)
        elif section == "Accounts":
            self.max_active_accounts.setValue(5)
            self.strict_fingerprinting.setChecked(True)
        elif section == "Devices":
            self.adb_path_input.setText("")
            self.default_provider.setCurrentText("Auto-Detect")
            self.device_timeout.setValue(30)
        elif section == "Meta Integration":
            self.meta_app_id.setText("")
            self.meta_redirect_uri.setText("https://localhost/oauth/callback")
            self.meta_api_version.setCurrentText("v21.0")
        elif section == "Storage":
            self.db_path_input.setText("")
            self.asset_cache_limit.setValue(2048)
        elif section == "Security":
            self.auto_lock_vault.setChecked(True)
            self.idle_lock_minutes.setValue(15)
            self.enforce_https.setChecked(True)
        elif section == "Scheduler":
            self.scheduler_poll_rate.setValue(5)
            self.max_retries.setValue(3)
        elif section == "Network":
            self.network_timeout.setValue(30)
            self.proxy_url.setText("")
        elif section == "Notifications":
            self.desktop_notifications.setChecked(True)
            self.sound_alerts.setChecked(False)
        elif section == "Backup":
            self.auto_backup_enabled.setChecked(True)
            self.backup_retention_count.setValue(10)
            self.backup_retention_days.setValue(30)
        elif section == "Plugins":
            self.allow_plugins.setChecked(False)
            self.sandbox_plugins.setChecked(True)
        elif section == "Updates":
            self.check_updates_startup.setChecked(True)
            self.update_channel.setCurrentText("Stable")
        elif section == "Diagnostics":
            self.log_level.setCurrentText("INFO")
            self.enable_telemetry.setChecked(True)

        self.status_label.setText(f"↺ {section} reset to default values (click Save to apply).")
        self.status_label.setStyleSheet("color: #ffb74d;")

    def save(self) -> None:
        self.save_all()

    def reset(self) -> None:
        self.reset_current_section()
