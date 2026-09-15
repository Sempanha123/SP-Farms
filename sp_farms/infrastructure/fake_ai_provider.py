from collections.abc import Sequence

from sp_farms.application.ai_provider_port import AIProviderPort
from sp_farms.domain.caption_ai import (
    AIAssistRequest,
    AIAssistResponse,
    AIOperationType,
    SupportedLanguage,
    ToneStyle,
    detect_dominant_script,
    normalize_multilingual_text,
)


class FakeMultilingualAIProvider(AIProviderPort):
    """Deterministic offline AI assistant for development, tests, and airgapped environments."""

    def __init__(self, configured: bool = True) -> None:
        self._configured = configured

    def is_configured(self) -> bool:
        return self._configured

    def set_configured(self, configured: bool) -> None:
        self._configured = configured

    def generate(self, request: AIAssistRequest) -> AIAssistResponse:
        if not self._configured:
            raise RuntimeError("AI Provider is not configured or missing API credentials.")

        clean_text = normalize_multilingual_text(request.text)
        detected_lang = detect_dominant_script(clean_text)

        if request.operation == AIOperationType.TRANSLATE:
            target_lang = (
                request.target_language
                if isinstance(request.target_language, SupportedLanguage)
                else SupportedLanguage(request.target_language)
            )
            suggested = self._fake_translate(clean_text, target_lang)
            return AIAssistResponse(
                operation=request.operation,
                original_text=clean_text,
                suggested_text=suggested,
                language=target_lang,
                explanation=f"Translated from {detected_lang.value} to {target_lang.value}.",
                model_name="fake-multilingual-translator-v1",
            )

        if request.operation == AIOperationType.REWRITE:
            suggested = self._fake_rewrite(clean_text, request.tone, detected_lang)
            return AIAssistResponse(
                operation=request.operation,
                original_text=clean_text,
                suggested_text=suggested,
                language=detected_lang,
                explanation=f"Rewritten in {request.tone.value} tone.",
                model_name="fake-multilingual-rewriter-v1",
            )

        if request.operation == AIOperationType.SPELLING_CLEANUP:
            cleaned = self._fake_cleanup(clean_text)
            return AIAssistResponse(
                operation=request.operation,
                original_text=clean_text,
                suggested_text=cleaned,
                language=detected_lang,
                explanation="Punctuation, spacing, and casing normalized.",
                model_name="fake-spelling-cleanup-v1",
            )

        if request.operation == AIOperationType.TONE_VARIANTS:
            variants = self._fake_tone_variants(clean_text, detected_lang)
            primary = variants[0] if variants else clean_text
            return AIAssistResponse(
                operation=request.operation,
                original_text=clean_text,
                suggested_text=primary,
                language=detected_lang,
                variants=tuple(variants),
                explanation="Generated multiple tone variants for human selection.",
                model_name="fake-tone-variants-v1",
            )

        if request.operation == AIOperationType.HASHTAG_SUGGESTIONS:
            tags = self._fake_hashtag_suggestions(clean_text, detected_lang)
            return AIAssistResponse(
                operation=request.operation,
                original_text=clean_text,
                suggested_text=" ".join(tags),
                language=detected_lang,
                suggested_hashtags=tuple(tags),
                explanation="Suggested relevant hashtags based on copy content.",
                model_name="fake-hashtag-suggester-v1",
            )

        raise ValueError(f"Unsupported AI operation: {request.operation}")

    def _fake_translate(self, text: str, target: SupportedLanguage) -> str:
        # Predefined phrases or fallback indicator
        sample_dict: dict[tuple[str, SupportedLanguage], str] = {
            ("hello", SupportedLanguage.KHMER): "សួស្តី",
            ("hello", SupportedLanguage.THAI): "สวัสดี",
            ("hello", SupportedLanguage.VIETNAMESE): "Xin chào",
            ("fresh strawberries", SupportedLanguage.KHMER): "ផ្លែស្ត្របឺរីស្រស់",
            ("fresh strawberries", SupportedLanguage.THAI): "สตรอว์เบอร์รีสด",
            ("fresh strawberries", SupportedLanguage.VIETNAMESE): "Dâu tây tươi",
        }
        key = (text.strip().lower(), target)
        if key in sample_dict:
            return sample_dict[key]

        if target == SupportedLanguage.KHMER:
            return f"{text} (បកប្រែជាភាសាខ្មែរ)"
        if target == SupportedLanguage.THAI:
            return f"{text} (แปลเป็นภาษาไทย)"
        if target == SupportedLanguage.VIETNAMESE:
            return f"{text} (Bản dịch tiếng Việt)"
        return f"{text} [Translated to English]"

    def _fake_rewrite(self, text: str, tone: ToneStyle, lang: SupportedLanguage) -> str:
        if lang == SupportedLanguage.KHMER:
            return f"{text} សូមអរគុណសម្រាប់ការគាំទ្រ!"
        if lang == SupportedLanguage.THAI:
            return f"{text} ขอบคุณสำหรับการสนับสนุนครับ/ค่ะ!"
        if lang == SupportedLanguage.VIETNAMESE:
            return f"{text} Cảm ơn quý khách đã luôn ủng hộ!"

        if tone == ToneStyle.PROMOTIONAL:
            return f"Special Offer! {text} Available now while supplies last!"
        if tone == ToneStyle.PROFESSIONAL:
            return f"Official Update: {text}"
        if tone == ToneStyle.URGENT:
            return f"Limited Time! {text} Act today!"
        if tone == ToneStyle.FRIENDLY:
            return f"Hey everyone! {text} Have a wonderful day!"
        return f"{text} ✨"

    def _fake_cleanup(self, text: str) -> str:
        # Clean double spaces, strip, capitalize
        words = text.split()
        joined = " ".join(words)
        if joined and joined[0].islower():
            joined = joined[0].upper() + joined[1:]
        if joined and not joined.endswith((".", "!", "?", "។")):
            joined += "."
        return joined

    def _fake_tone_variants(self, text: str, lang: SupportedLanguage) -> Sequence[str]:
        return [
            self._fake_rewrite(text, ToneStyle.FRIENDLY, lang),
            self._fake_rewrite(text, ToneStyle.PROFESSIONAL, lang),
            self._fake_rewrite(text, ToneStyle.PROMOTIONAL, lang),
        ]

    def _fake_hashtag_suggestions(self, text: str, lang: SupportedLanguage) -> Sequence[str]:
        base_tags = ["#spfarms", "#agriculture", "#freshproduce"]
        if lang == SupportedLanguage.KHMER:
            return ["#កសិកម្ម", "#ធម្មជាតិ", "#កម្ពុជា"] + base_tags
        if lang == SupportedLanguage.THAI:
            return ["#ฟาร์ม", "#สดใหม่", "#เกษตรกรรม"] + base_tags
        if lang == SupportedLanguage.VIETNAMESE:
            return ["#nongsan", "#sach", "#vietnam"] + base_tags
        return base_tags + ["#organic", "#farmfresh"]
