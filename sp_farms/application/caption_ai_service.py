from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from sp_farms.application.ai_provider_port import AIProviderPort
from sp_farms.domain.caption_ai import (
    AIAssistRequest,
    AIAssistResponse,
    normalize_multilingual_text,
)
from sp_farms.domain.content import CaptionTemplate, HashtagSet
from sp_farms.domain.secrets import SecretType

if TYPE_CHECKING:
    from sp_farms.application.content_repository import ContentRepositoryPort
    from sp_farms.application.secret_service import SecretService
    from sp_farms.application.secrets import SecretRepository
    from sp_farms.application.unit_of_work import UnitOfWork


AI_SYSTEM_OWNER_ID = "system:multilingual_ai"


class CaptionAIService:
    """Orchestrates caption templates, hashtag management, and optional AI assist."""

    def __init__(
        self,
        unit_of_work: "Callable[[], UnitOfWork]",
        content_repo_factory: "Callable[[UnitOfWork], ContentRepositoryPort]",
        secret_service: "SecretService | None" = None,
        secret_repo_factory: "Callable[[UnitOfWork], SecretRepository] | None" = None,
        ai_provider: AIProviderPort | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._content_repo_factory = content_repo_factory
        self._secret_service = secret_service
        self._secret_repo_factory = secret_repo_factory
        self._ai_provider = ai_provider

    # -------------------------------------------------------------------------
    # Secret Key Management for AI Provider
    # -------------------------------------------------------------------------

    def set_ai_api_key(self, api_key: str) -> None:
        """Store the AI provider API key securely in the OS Keyring."""
        if not self._secret_service or not self._secret_repo_factory:
            raise RuntimeError("Secret service not configured for storing AI key.")

        with self._uow() as uow:
            repo = self._secret_repo_factory(uow)
            existing = repo.list_by_owner_ids([AI_SYSTEM_OWNER_ID])
            for ref in existing:
                self._secret_service.delete(ref)
                repo.delete(ref.id)

            ref = self._secret_service.create_reference(
                secret_type=SecretType.API_KEY,
                owner_id=AI_SYSTEM_OWNER_ID,
                value=api_key.strip(),
            )
            repo.save(ref)
            uow.commit()

    def get_ai_api_key(self) -> str | None:
        """Retrieve the active AI API key from the vault without exposing it to logs."""
        if not self._secret_service or not self._secret_repo_factory:
            return None

        with self._uow() as uow:
            repo = self._secret_repo_factory(uow)
            refs = repo.list_by_owner_ids([AI_SYSTEM_OWNER_ID])
            if not refs:
                return None
            return self._secret_service.reveal(refs[0])

    def remove_ai_api_key(self) -> None:
        """Delete AI API key from keyring and secret repository."""
        if not self._secret_service or not self._secret_repo_factory:
            return

        with self._uow() as uow:
            repo = self._secret_repo_factory(uow)
            refs = repo.list_by_owner_ids([AI_SYSTEM_OWNER_ID])
            for ref in refs:
                self._secret_service.delete(ref)
                repo.delete(ref.id)
            uow.commit()

    def is_ai_available(self) -> bool:
        """Return True if AI assistance is configured and ready."""
        if self._ai_provider and self._ai_provider.is_configured():
            return True
        key = self.get_ai_api_key()
        return bool(key)

    # -------------------------------------------------------------------------
    # AI Assistance Operations (Always requires human review)
    # -------------------------------------------------------------------------

    def assist(self, request: AIAssistRequest) -> AIAssistResponse:
        """Execute AI assistance query with normalized Unicode output."""
        if not self._ai_provider:
            raise RuntimeError("No AI provider registered in application context.")
        if not self._ai_provider.is_configured() and not self.is_ai_available():
            raise RuntimeError(
                "AI provider API key is not configured. Add an API key in Settings/Vault."
            )

        # Normalize prompt text before dispatching
        clean_text = normalize_multilingual_text(request.text)
        normalized_request = AIAssistRequest(
            operation=request.operation,
            text=clean_text,
            target_language=request.target_language,
            tone=request.tone,
            reference_hashtags=request.reference_hashtags,
        )
        response = self._ai_provider.generate(normalized_request)

        # Ensure returned suggested text is NFC normalized
        return AIAssistResponse(
            operation=response.operation,
            original_text=clean_text,
            suggested_text=normalize_multilingual_text(response.suggested_text),
            language=response.language,
            suggested_hashtags=tuple(
                normalize_multilingual_text(t) for t in response.suggested_hashtags
            ),
            variants=tuple(normalize_multilingual_text(v) for v in response.variants),
            explanation=response.explanation,
            model_name=response.model_name,
            created_at=response.created_at,
        )

    # -------------------------------------------------------------------------
    # Unicode-Safe Template & Hashtag Helpers
    # -------------------------------------------------------------------------

    def render_template_safely(
        self,
        template: CaptionTemplate,
        variables: dict[str, str],
    ) -> str:
        """Render a caption template with Unicode NFC normalization."""
        clean_vars = {k: normalize_multilingual_text(v) for k, v in variables.items()}
        rendered = template.render(clean_vars)
        return normalize_multilingual_text(rendered)

    def assemble_post_copy(
        self,
        caption: str,
        hashtag_sets: Sequence[HashtagSet] = (),
        custom_tags: Sequence[str] = (),
    ) -> str:
        """Safely combine caption and hashtag sets with NFC normalization."""
        clean_caption = normalize_multilingual_text(caption)
        all_tags: list[str] = []

        for hset in hashtag_sets:
            for tag in hset.hashtags:
                norm_tag = normalize_multilingual_text(tag)
                if norm_tag and norm_tag not in all_tags:
                    all_tags.append(norm_tag)

        for ctag in custom_tags:
            cleaned = normalize_multilingual_text(ctag)
            if cleaned:
                if not cleaned.startswith("#"):
                    cleaned = f"#{cleaned}"
                if cleaned not in all_tags:
                    all_tags.append(cleaned)

        if not all_tags:
            return clean_caption

        tags_block = " ".join(all_tags)
        if not clean_caption:
            return tags_block
        return f"{clean_caption}\n\n{tags_block}"
