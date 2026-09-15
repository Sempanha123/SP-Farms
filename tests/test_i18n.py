import os
import unicodedata
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from sp_farms.app.settings_workspace import SettingsWorkspace
from sp_farms.application.context import ApplicationContext
from sp_farms.application.i18n_service import I18nService
from sp_farms.domain.i18n import SupportedLocale, normalize_unicode
from sp_farms.infrastructure.clock import SystemClock


def get_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_catalogs_loaded_and_valid():
    service = I18nService()
    assert service.current_locale == SupportedLocale.EN_US

    for loc in SupportedLocale:
        service.set_locale(loc)
        # Check core navigation and action keys exist
        assert service.t("nav.home") != "nav.home"
        assert service.t("nav.accounts") != "nav.accounts"
        assert service.t("actions.save") != "actions.save"
        assert service.t("status.active") != "status.active"


def test_locale_switch_and_listener_notification():
    service = I18nService()
    received_locales: list[SupportedLocale] = []

    def on_locale_change(loc: SupportedLocale) -> None:
        received_locales.append(loc)

    service.register_listener(on_locale_change)

    # English
    assert service.t("nav.accounts") == "Accounts"

    # Switch to Khmer (First-class)
    assert service.set_locale(SupportedLocale.KM_KH) is True
    assert service.current_locale == SupportedLocale.KM_KH
    assert service.t("nav.accounts") == "គណនី"
    assert service.t("nav.devices") == "ឧបករណ៍"
    assert service.t("actions.save") == "រក្សាទុក"

    # Switch to Thai
    assert service.set_locale("th_TH") is True
    assert service.t("nav.accounts") == "บัญชี"

    # Switch to Vietnamese
    assert service.set_locale(SupportedLocale.VI_VN) is True
    assert service.t("nav.accounts") == "Tài khoản"

    assert received_locales == [
        SupportedLocale.KM_KH,
        SupportedLocale.TH_TH,
        SupportedLocale.VI_VN,
    ]


def test_missing_string_fallback():
    service = I18nService(default_locale=SupportedLocale.KM_KH)

    # In km_KH, key is present
    assert service.t("nav.accounts") == "គណនី"

    # Suppose a key is missing in km_KH, inject test scenario
    service._catalogs[SupportedLocale.KM_KH].pop("nav.accounts", None)

    # Should fall back to en_US
    assert service.t("nav.accounts") == "Accounts"

    # If completely non-existent key, should return default or key
    assert service.t("non.existent.key", default="Fallback Title") == "Fallback Title"
    assert service.t("non.existent.key") == "non.existent.key"


def test_khmer_unicode_nfc_normalization_and_interpolation():
    service = I18nService(default_locale=SupportedLocale.KM_KH)

    # Khmer greeting with parameter interpolation
    greeting = service.t("messages.welcome", name="សុខា")
    assert "សូមស្វាគមន៍មកវិញ, សុខា!" in greeting

    # Verify NFC normalization form
    assert unicodedata.is_normalized("NFC", greeting)
    unnormalized = "កី"  # decomposed or compound form
    normalized = normalize_unicode(unnormalized)
    assert unicodedata.is_normalized("NFC", normalized)


def test_date_and_number_formatting():
    service = I18nService(default_locale=SupportedLocale.EN_US)

    d = date(2026, 6, 15)
    assert service.format_date(d) == "2026-06-15"
    assert service.format_number(1250000) == "1,250,000"
    assert service.format_number(1250.5, precision=2) == "1,250.50"

    # Switch to Khmer
    service.set_locale(SupportedLocale.KM_KH)
    assert service.format_date(d) == "15/06/2026"

    # Switch to Vietnamese (uses period for grouping, comma for decimal)
    service.set_locale(SupportedLocale.VI_VN)
    assert service.format_number(1250000) == "1.250.000"
    assert service.format_number(1250.5, precision=2) == "1.250,50"


def test_export_encoding_utf8_bom():
    khmer_csv = "ឈ្មោះ,ប្រភេទ,ស្ថានភាព\nគណនីទី១,ទំព័រ,សកម្ម"
    bom_bytes = I18nService.to_utf8_bom(khmer_csv)

    # Check BOM prefix
    assert bom_bytes.startswith(b"\xef\xbb\xbf")
    # Decode without BOM should match original string
    decoded = bom_bytes[3:].decode("utf-8")
    assert decoded == khmer_csv


def test_settings_workspace_locale_selector(tmp_path):
    get_qapp()
    ini_path = tmp_path / "test_settings.ini"
    settings = QSettings(str(ini_path), QSettings.Format.IniFormat)
    i18n = I18nService()
    ctx = ApplicationContext(clock=SystemClock(), i18n_service=i18n)

    workspace = SettingsWorkspace(settings=settings, context=ctx)

    # Find Khmer in combo
    idx = workspace.language_selector.findData("km_KH")
    assert idx >= 0
    workspace.language_selector.setCurrentIndex(idx)

    requested_locales: list[str] = []
    workspace.locale_requested.connect(requested_locales.append)

    saved = workspace.save_all()
    assert saved is True
    assert settings.value("general/locale") == "km_KH"
    assert i18n.current_locale == SupportedLocale.KM_KH
    assert requested_locales == ["km_KH"]
