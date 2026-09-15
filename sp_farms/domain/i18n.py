import unicodedata
from dataclasses import dataclass
from enum import StrEnum


class SupportedLocale(StrEnum):
    EN_US = "en_US"
    KM_KH = "km_KH"
    TH_TH = "th_TH"
    VI_VN = "vi_VN"


@dataclass(frozen=True, slots=True)
class LocaleMetadata:
    code: SupportedLocale
    name: str
    native_name: str
    date_format: str
    time_format: str
    number_grouping_sep: str
    number_decimal_sep: str
    recommended_font: str = "Segoe UI"


SUPPORTED_LOCALES: dict[SupportedLocale, LocaleMetadata] = {
    SupportedLocale.EN_US: LocaleMetadata(
        code=SupportedLocale.EN_US,
        name="English (United States)",
        native_name="English",
        date_format="%Y-%m-%d",
        time_format="%H:%M:%S",
        number_grouping_sep=",",
        number_decimal_sep=".",
        recommended_font="Segoe UI",
    ),
    SupportedLocale.KM_KH: LocaleMetadata(
        code=SupportedLocale.KM_KH,
        name="Khmer (Cambodia)",
        native_name="ភាសាខ្មែរ",
        date_format="%d/%m/%Y",
        time_format="%H:%M:%S",
        number_grouping_sep=",",
        number_decimal_sep=".",
        recommended_font="Khmer OS Content, Hanuman, Segoe UI",
    ),
    SupportedLocale.TH_TH: LocaleMetadata(
        code=SupportedLocale.TH_TH,
        name="Thai (Thailand)",
        native_name="ไทย",
        date_format="%d/%m/%Y",
        time_format="%H:%M:%S",
        number_grouping_sep=",",
        number_decimal_sep=".",
        recommended_font="Leelawadee UI, Tahoma, Segoe UI",
    ),
    SupportedLocale.VI_VN: LocaleMetadata(
        code=SupportedLocale.VI_VN,
        name="Vietnamese (Vietnam)",
        native_name="Tiếng Việt",
        date_format="%d/%m/%Y",
        time_format="%H:%M:%S",
        number_grouping_sep=".",
        number_decimal_sep=",",
        recommended_font="Segoe UI",
    ),
}


def normalize_unicode(text: str) -> str:
    """Normalize string to Unicode Normalization Form C (NFC) for robust script storage."""
    if not text:
        return ""
    return unicodedata.normalize("NFC", text)
