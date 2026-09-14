import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class SupportedLanguage(StrEnum):
    ENGLISH = "en"
    KHMER = "km"
    THAI = "th"
    VIETNAMESE = "vi"


class AIOperationType(StrEnum):
    REWRITE = "rewrite"
    TRANSLATE = "translate"
    SPELLING_CLEANUP = "spelling_cleanup"
    TONE_VARIANTS = "tone_variants"
    HASHTAG_SUGGESTIONS = "hashtag_suggestions"


class ToneStyle(StrEnum):
    CASUAL = "casual"
    PROFESSIONAL = "professional"
    PROMOTIONAL = "promotional"
    FRIENDLY = "friendly"
    URGENT = "urgent"


@dataclass(frozen=True, slots=True)
class AIAssistRequest:
    operation: AIOperationType
    text: str
    target_language: SupportedLanguage = SupportedLanguage.ENGLISH
    tone: ToneStyle = ToneStyle.CASUAL
    reference_hashtags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class AIAssistResponse:
    operation: AIOperationType
    original_text: str
    suggested_text: str
    language: SupportedLanguage
    suggested_hashtags: tuple[str, ...] = field(default_factory=tuple)
    variants: tuple[str, ...] = field(default_factory=tuple)
    explanation: str = ""
    model_name: str = "sp-farms-multilingual-ai"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def normalize_multilingual_text(text: str) -> str:
    """Normalize text using Unicode NFC for safe storage and rendering.

    Ensures Khmer sub-scripts, Thai tone marks, and Vietnamese diacritics
    remain intact and correctly composed across SQLite, JSON, and PySide6 UI.
    """
    if not text:
        return ""
    # NFC: Canonical Decomposition followed by Canonical Composition
    return unicodedata.normalize("NFC", text).strip()


def detect_dominant_script(text: str) -> SupportedLanguage:
    """Detect script family from text characters."""
    counts: dict[SupportedLanguage, int] = {
        SupportedLanguage.KHMER: 0,
        SupportedLanguage.THAI: 0,
        SupportedLanguage.VIETNAMESE: 0,
        SupportedLanguage.ENGLISH: 0,
    }

    # Vietnamese specific diacritic characters
    vietnamese_chars = set("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
                           "ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ")

    has_vietnamese_diacritic = False
    for ch in text:
        cp = ord(ch)
        if 0x1780 <= cp <= 0x17FF or 0x19E0 <= cp <= 0x19FF:
            counts[SupportedLanguage.KHMER] += 1
        elif 0x0E00 <= cp <= 0x0E7F:
            counts[SupportedLanguage.THAI] += 1
        elif ch in vietnamese_chars:
            has_vietnamese_diacritic = True
            counts[SupportedLanguage.VIETNAMESE] += 1
        elif ch.isascii() and ch.isalpha():
            counts[SupportedLanguage.ENGLISH] += 1

    if counts[SupportedLanguage.KHMER] > 0:
        return SupportedLanguage.KHMER
    if counts[SupportedLanguage.THAI] > 0:
        return SupportedLanguage.THAI
    if has_vietnamese_diacritic:
        return SupportedLanguage.VIETNAMESE
    if counts[SupportedLanguage.ENGLISH] > 0:
        return SupportedLanguage.ENGLISH
    return SupportedLanguage.ENGLISH
