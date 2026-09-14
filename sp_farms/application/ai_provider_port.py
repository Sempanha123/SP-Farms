from typing import Protocol

from sp_farms.domain.caption_ai import AIAssistRequest, AIAssistResponse


class AIProviderPort(Protocol):
    """Port for multilingual AI assistant operations."""

    def is_configured(self) -> bool:
        """Check if provider has active API credentials or is available."""
        ...

    def generate(self, request: AIAssistRequest) -> AIAssistResponse:
        """Generate writing assistance, translation, or suggestions."""
        ...
