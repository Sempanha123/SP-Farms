import json
import logging
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sp_farms.domain.i18n import (
    SUPPORTED_LOCALES,
    LocaleMetadata,
    SupportedLocale,
    normalize_unicode,
)

logger = logging.getLogger(__name__)

DEFAULT_CATALOG_DIR = (
    Path(__file__).resolve().parent.parent / "infrastructure" / "i18n" / "catalogs"
)


class I18nService:
    """Internationalization service managing multilingual catalogs, formatting, and fallback."""

    def __init__(
        self,
        default_locale: SupportedLocale | str = SupportedLocale.EN_US,
        catalog_dir: Path | str | None = None,
    ) -> None:
        self._catalog_dir = Path(catalog_dir) if catalog_dir else DEFAULT_CATALOG_DIR
        self._catalogs: dict[SupportedLocale, dict[str, str]] = {}
        self._listeners: list[Callable[[SupportedLocale], None]] = []

        # Load all catalogs
        self._load_catalogs()

        # Set initial locale
        if isinstance(default_locale, str):
            try:
                self._current_locale = SupportedLocale(default_locale)
            except ValueError:
                self._current_locale = SupportedLocale.EN_US
        else:
            self._current_locale = default_locale

    @property
    def current_locale(self) -> SupportedLocale:
        return self._current_locale

    @property
    def metadata(self) -> LocaleMetadata:
        return SUPPORTED_LOCALES.get(self._current_locale, SUPPORTED_LOCALES[SupportedLocale.EN_US])

    def register_listener(self, listener: Callable[[SupportedLocale], None]) -> None:
        """Register a callback invoked when locale changes."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unregister_listener(self, listener: Callable[[SupportedLocale], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def set_locale(self, locale: SupportedLocale | str) -> bool:
        """Switch active locale and notify registered listeners."""
        target: SupportedLocale
        if isinstance(locale, str):
            try:
                target = SupportedLocale(locale)
            except ValueError:
                logger.warning("Unknown locale '%s'; ignoring switch", locale)
                return False
        else:
            target = locale

        if target not in self._catalogs:
            self._load_catalog_file(target)

        self._current_locale = target
        for listener in self._listeners:
            try:
                listener(target)
            except Exception as e:
                logger.error("Error invoking i18n listener: %s", e)
        return True

    def _load_catalogs(self) -> None:
        for loc in SupportedLocale:
            self._load_catalog_file(loc)

    def _load_catalog_file(self, locale: SupportedLocale) -> None:
        catalog_path = self._catalog_dir / f"{locale.value}.json"
        if not catalog_path.exists():
            logger.debug("Catalog file missing: %s", catalog_path)
            self._catalogs[locale] = {}
            return

        try:
            with open(catalog_path, encoding="utf-8") as f:
                raw_data = json.load(f)
                # Store NFC normalized strings
                normalized_data = {k: normalize_unicode(str(v)) for k, v in raw_data.items()}
                self._catalogs[locale] = normalized_data
        except Exception as e:
            logger.error("Failed loading catalog for %s: %s", locale, e)
            self._catalogs[locale] = {}

    def t(self, key: str, default: str | None = None, **kwargs: Any) -> str:
        """Translate a key using current locale, falling back to en_US, then default."""
        current_dict = self._catalogs.get(self._current_locale, {})
        en_dict = self._catalogs.get(SupportedLocale.EN_US, {})

        template = current_dict.get(key)
        if template is None:
            # Fallback to English
            template = en_dict.get(key)

        if template is None:
            template = default if default is not None else key

        if kwargs:
            try:
                template = template.format(**kwargs)
            except Exception as e:
                logger.warning("Formatting error in i18n key '%s': %s", key, e)

        return normalize_unicode(template)

    def format_date(self, dt: datetime | date) -> str:
        """Format date according to current locale."""
        meta = self.metadata
        return dt.strftime(meta.date_format)

    def format_datetime(self, dt: datetime) -> str:
        """Format datetime according to current locale."""
        meta = self.metadata
        fmt = f"{meta.date_format} {meta.time_format}"
        return dt.strftime(fmt)

    def format_number(self, value: int | float, precision: int | None = None) -> str:
        """Format numeric values with locale decimal and grouping separators."""
        meta = self.metadata
        if isinstance(value, int) or precision == 0:
            formatted_int = f"{int(value):,}"
            if meta.number_grouping_sep != ",":
                formatted_int = formatted_int.replace(",", meta.number_grouping_sep)
            return formatted_int

        p = precision if precision is not None else 2
        formatted_float = f"{float(value):,.{p}f}"
        if meta.number_grouping_sep != ",":
            # Temporary token swap to avoid collision with decimal sep
            formatted_float = (
                formatted_float.replace(",", "_GROUP_")
                .replace(".", meta.number_decimal_sep)
                .replace("_GROUP_", meta.number_grouping_sep)
            )
        elif meta.number_decimal_sep != ".":
            formatted_float = formatted_float.replace(".", meta.number_decimal_sep)
        return formatted_float

    def format_currency(self, value: float, currency_symbol: str = "$") -> str:
        """Format monetary amount with currency symbol and locale-appropriate separators."""
        formatted_num = self.format_number(value, precision=2)
        return f"{currency_symbol}{formatted_num}"

    @staticmethod
    def to_utf8_bom(content: str) -> bytes:
        """Encode text with UTF-8 BOM (Byte Order Mark) for Excel compatibility with Unicode."""
        nfc_content = normalize_unicode(content)
        return b"\xef\xbb\xbf" + nfc_content.encode("utf-8")
