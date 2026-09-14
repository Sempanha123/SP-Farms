from collections.abc import Sequence
from typing import Any, Protocol

from sp_farms.domain.meta import (
    MetaOAuthTokenResponse,
    MetaRateLimitInfo,
    MetaScopeSet,
    MetaTokenMetadata,
)


class MetaClientPort(Protocol):
    """Abstraction for official Meta Graph API client operations."""

    def get_authorization_url(self, state: str, scopes: MetaScopeSet) -> str:
        """Construct the official OAuth 2.0 authorization dialog URL."""
        ...

    def exchange_code_for_token(
        self, code: str, redirect_uri: str | None = None
    ) -> MetaOAuthTokenResponse:
        """Exchange an OAuth authorization code for an access token."""
        ...

    def exchange_for_long_lived_token(self, short_lived_token: str) -> MetaOAuthTokenResponse:
        """Exchange a short-lived user access token for a 60-day long-lived token."""
        ...

    def inspect_token(self, token: str) -> MetaTokenMetadata:
        """Inspect and validate access token metadata via debug_token endpoint."""
        ...

    def get_user_profile(
        self, token: str, fields: Sequence[str] | None = None
    ) -> dict[str, Any]:
        """Fetch basic authorized profile information for /me."""
        ...

    def get_accounts_pages(self, token: str) -> list[dict[str, Any]]:
        """Fetch managed Facebook Pages authorized for the token."""
        ...

    def get_rate_limit_info(self) -> MetaRateLimitInfo:
        """Return the most recently observed rate limit usage metrics."""
        ...
