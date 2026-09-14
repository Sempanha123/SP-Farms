from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from PySide6.QtWidgets import QApplication

from sp_farms.app.ai_assist_dialog import AiAssistDialog
from sp_farms.app.composer_dialog import ComposerDialog
from sp_farms.application.caption_ai_service import CaptionAIService
from sp_farms.application.composer_service import ComposerService
from sp_farms.application.content_service import ContentService
from sp_farms.application.secret_service import SecretService
from sp_farms.application.vault import Vault
from sp_farms.domain.caption_ai import (
    AIAssistRequest,
    AIOperationType,
    SupportedLanguage,
    ToneStyle,
    detect_dominant_script,
    normalize_multilingual_text,
)
from sp_farms.domain.content import CaptionTemplate, HashtagSet
from sp_farms.infrastructure.clock import SystemClock
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyContentRepository,
    SqlAlchemySecretRepository,
    run_migrations,
)
from sp_farms.infrastructure.fake_ai_provider import FakeMultilingualAIProvider


class MemoryVault(Vault):
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def store(self, key: str, secret: str) -> None:
        self._store[key] = secret

    def retrieve(self, key: str) -> str | None:
        return self._store.get(key)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    assert isinstance(app, QApplication)
    return app


@pytest.fixture
def test_setup() -> Generator[
    tuple[Database, ContentService, CaptionAIService, FakeMultilingualAIProvider, Path],
    None,
    None,
]:
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_path = tmp_path / "ai_test.db"
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir(parents=True, exist_ok=True)

        database = Database(db_path)
        run_migrations(database, Path(__file__).resolve().parents[1] / "migrations")
        clock = SystemClock()
        vault = MemoryVault()
        secret_service = SecretService(vault)

        content_service = ContentService(
            unit_of_work=database.unit_of_work,
            content_repository_factory=SqlAlchemyContentRepository,
            clock=clock,
            storage_dir=storage_dir,
        )

        fake_ai = FakeMultilingualAIProvider(configured=True)
        caption_ai_service = CaptionAIService(
            unit_of_work=database.unit_of_work,
            content_repo_factory=SqlAlchemyContentRepository,
            secret_service=secret_service,
            secret_repo_factory=SqlAlchemySecretRepository,
            ai_provider=fake_ai,
        )

        try:
            yield database, content_service, caption_ai_service, fake_ai, tmp_path
        finally:
            database.close()


def test_multilingual_unicode_normalization_and_detection() -> None:
    # 1. Khmer text
    km_text = "  សួស្តីកសិករទាំងអស់គ្នា 🚜  "
    norm_km = normalize_multilingual_text(km_text)
    assert norm_km == "សួស្តីកសិករទាំងអស់គ្នា 🚜"
    assert detect_dominant_script(norm_km) == SupportedLanguage.KHMER

    # 2. Thai text
    th_text = "  สวัสดีชาวสวนทุกคน 🌱  "
    norm_th = normalize_multilingual_text(th_text)
    assert norm_th == "สวัสดีชาวสวนทุกคน 🌱"
    assert detect_dominant_script(norm_th) == SupportedLanguage.THAI

    # 3. Vietnamese text
    vi_text = "  Dâu tây tươi ngon từ nông trại sạch 🍓  "
    norm_vi = normalize_multilingual_text(vi_text)
    assert norm_vi == "Dâu tây tươi ngon từ nông trại sạch 🍓"
    assert detect_dominant_script(norm_vi) == SupportedLanguage.VIETNAMESE

    # 4. English text
    en_text = "  Fresh organic vegetables every weekend! 🥦  "
    norm_en = normalize_multilingual_text(en_text)
    assert norm_en == "Fresh organic vegetables every weekend! 🥦"
    assert detect_dominant_script(norm_en) == SupportedLanguage.ENGLISH


def test_template_and_hashtag_rendering_safely(
    test_setup: tuple[Database, ContentService, CaptionAIService, FakeMultilingualAIProvider, Path],
) -> None:
    _, _, caption_ai_service, _, _ = test_setup

    # Template with Khmer values
    tpl = CaptionTemplate.create(
        name="Khmer Promo",
        content="សូមស្វាគមន៍មកកាន់ {farm_name}! យើងមាន {product} ស្រស់ៗជារៀងរាល់ថ្ងៃ។",
        variables=("farm_name", "product"),
    )
    rendered = caption_ai_service.render_template_safely(
        tpl,
        {"farm_name": "ចំការបៃតង SP", "product": "ផ្លែស្ត្របឺរី"},
    )
    assert "ចំការបៃតង SP" in rendered
    assert "ផ្លែស្ត្របឺរី" in rendered

    # Hashtag set assembly
    hset = HashtagSet.create(
        name="Farming Set",
        hashtags=["#agriculture", "#spfarms", "#organic"],
    )
    full_copy = caption_ai_service.assemble_post_copy(
        caption="Our weekly harvest is ready!",
        hashtag_sets=[hset],
        custom_tags=["#freshproduce", "weekenddeal"],
    )
    assert "Our weekly harvest is ready!" in full_copy
    assert "#agriculture #spfarms #organic #freshproduce #weekenddeal" in full_copy


def test_fake_ai_provider_operations(
    test_setup: tuple[Database, ContentService, CaptionAIService, FakeMultilingualAIProvider, Path],
) -> None:
    _, _, caption_ai_service, fake_ai, _ = test_setup

    # 1. Rewrite with promotional tone
    req_rewrite = AIAssistRequest(
        operation=AIOperationType.REWRITE,
        text="Strawberries available now.",
        tone=ToneStyle.PROMOTIONAL,
    )
    res_rewrite = caption_ai_service.assist(req_rewrite)
    assert "Special Offer!" in res_rewrite.suggested_text
    assert "Strawberries available now." in res_rewrite.suggested_text

    # 2. Translation to Khmer
    req_translate = AIAssistRequest(
        operation=AIOperationType.TRANSLATE,
        text="Hello",
        target_language=SupportedLanguage.KHMER,
    )
    res_translate = caption_ai_service.assist(req_translate)
    assert res_translate.suggested_text == "សួស្តី"
    assert res_translate.language == SupportedLanguage.KHMER

    # 3. Translation to Vietnamese
    req_vi = AIAssistRequest(
        operation=AIOperationType.TRANSLATE,
        text="fresh strawberries",
        target_language=SupportedLanguage.VIETNAMESE,
    )
    res_vi = caption_ai_service.assist(req_vi)
    assert res_vi.suggested_text == "Dâu tây tươi"

    # 4. Spelling and punctuation cleanup
    req_clean = AIAssistRequest(
        operation=AIOperationType.SPELLING_CLEANUP,
        text="fresh organic strawberries now available at our stand",
    )
    res_clean = caption_ai_service.assist(req_clean)
    assert res_clean.suggested_text.startswith("Fresh")
    assert res_clean.suggested_text.endswith(".")

    # 5. Tone variants
    req_variants = AIAssistRequest(
        operation=AIOperationType.TONE_VARIANTS,
        text="Visit our weekend market",
    )
    res_variants = caption_ai_service.assist(req_variants)
    assert len(res_variants.variants) >= 3

    # 6. Hashtag suggestions
    req_tags = AIAssistRequest(
        operation=AIOperationType.HASHTAG_SUGGESTIONS,
        text="Fresh vegetables grown in Cambodia",
    )
    res_tags = caption_ai_service.assist(req_tags)
    assert len(res_tags.suggested_hashtags) > 0
    assert any("spfarms" in tag for tag in res_tags.suggested_hashtags)


def test_ai_provider_vault_secret_management(
    test_setup: tuple[Database, ContentService, CaptionAIService, FakeMultilingualAIProvider, Path],
) -> None:
    _, _, caption_ai_service, fake_ai, _ = test_setup

    # Store API key in vault
    caption_ai_service.set_ai_api_key("sk-test-ai-key-secret-12345")
    revealed = caption_ai_service.get_ai_api_key()
    assert revealed == "sk-test-ai-key-secret-12345"
    assert caption_ai_service.is_ai_available() is True

    # Remove API key from vault
    caption_ai_service.remove_ai_api_key()
    assert caption_ai_service.get_ai_api_key() is None


def test_ai_assist_dialog_ui_interaction(
    qapp: QApplication,
    test_setup: tuple[Database, ContentService, CaptionAIService, FakeMultilingualAIProvider, Path],
) -> None:
    _, _, caption_ai_service, _, _ = test_setup

    dialog = AiAssistDialog(
        caption_ai_service=caption_ai_service,
        initial_text="hello",
    )
    assert dialog.windowTitle() == "SP-Farms — Multilingual AI Writing Assistant"
    assert dialog.txt_source.toPlainText() == "hello"

    # Execute translation via UI action
    dialog.cmb_operation.setCurrentIndex(0)  # Translate
    dialog.cmb_target_lang.setCurrentIndex(0)  # Khmer
    dialog._on_generate()

    assert dialog.txt_proposal.toPlainText() == "សួស្តី"

    # Capture signal emission on apply
    captured_result = []
    dialog.suggestion_applied.connect(captured_result.append)
    dialog._on_apply()

    assert len(captured_result) == 1
    assert captured_result[0] == "សួស្តី"
    dialog.close()


def test_composer_dialog_with_ai_assist_and_template(
    qapp: QApplication,
    test_setup: tuple[Database, ContentService, CaptionAIService, FakeMultilingualAIProvider, Path],
) -> None:
    database, content_service, caption_ai_service, _, _ = test_setup
    clock = SystemClock()

    composer_service = ComposerService(
        unit_of_work=database.unit_of_work,
        content_repo_factory=SqlAlchemyContentRepository,
        clock=clock,
    )

    # Seed a template
    tpl = content_service.create_caption_template(
        name="Daily Harvest Announcement",
        content="Today's fresh harvest includes organic vegetables! Visit us at the farm stand.",
    )
    assert tpl.id is not None

    composer = ComposerDialog(
        composer_service=composer_service,
        content_service=content_service,
        caption_ai_service=caption_ai_service,
    )

    # Verify buttons are present
    assert composer.btn_ai_assist is not None
    assert composer.btn_ai_assist.text() == "✨ AI Assist..."
    composer.close()
