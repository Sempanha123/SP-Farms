from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sp_farms.application.meta_client import MetaClientPort
from sp_farms.application.secret_service import SecretService
from sp_farms.domain.meta import (
    MetaAuthError,
    MetaPermission,
    MetaRateLimitInfo,
    MetaScopeSet,
    MetaTokenMetadata,
)
from sp_farms.domain.secrets import SecretReference, SecretType


class MetaIntegrationService:
    """Coordinates official Meta API authorization, token lifecycle, and vault storage."""

    def __init__(
        self,
        meta_client: MetaClientPort,
        secret_service: SecretService,
    ) -> None:
        self._client = meta_client
        self._secrets = secret_service

    def generate_authorization_url(
        self,
        state: str,
        scopes: Sequence[MetaPermission | str] | None = None,
    ) -> str:
        """Generate official OAuth consent URL for requested scopes."""
        if scopes is None:
            scope_set = MetaScopeSet(
                frozenset(
                    [
                        MetaPermission.PUBLIC_PROFILE.value,
                        MetaPermission.EMAIL.value,
                        MetaPermission.PAGES_SHOW_LIST.value,
                        MetaPermission.PAGES_READ_ENGAGEMENT.value,
                    ]
                )
            )
        else:
            perms = [s.value if isinstance(s, MetaPermission) else str(s) for s in scopes]
            scope_set = MetaScopeSet(frozenset(perms))

        return self._client.get_authorization_url(state=state, scopes=scope_set)

    def handle_oauth_callback(
        self,
        code: str,
        account_id: str,
        redirect_uri: str | None = None,
    ) -> tuple[SecretReference, MetaTokenMetadata]:
        """Exchange authorization code, upgrade to long-lived token, inspect, and vault it."""
        initial_token_res = self._client.exchange_code_for_token(code, redirect_uri=redirect_uri)
        raw_token = initial_token_res.access_token

        # Upgrade short-lived token (1-2 hours) to long-lived (60 days)
        try:
            long_lived_res = self._client.exchange_for_long_lived_token(raw_token)
            token_to_store = long_lived_res.access_token
        except Exception:
            # If long-lived exchange not supported (e.g. system user or test token), fallback
            token_to_store = raw_token

        # Inspect token to acquire authoritative expiry, permissions, and app identity
        metadata = self._client.inspect_token(token_to_store)
        if not metadata.is_valid:
            raise MetaAuthError("Acquired token failed debug inspection / is not valid.")

        # Vault the sensitive access token under SecretType.ACCESS_TOKEN
        secret_ref = self._secrets.create_reference(
            secret_type=SecretType.ACCESS_TOKEN,
            owner_id=account_id,
            value=token_to_store,
        )

        return secret_ref, metadata

    def get_token(self, secret_ref: SecretReference) -> str | None:
        """Safely reveal the raw access token from the OS keyring vault."""
        return self._secrets.reveal(secret_ref)

    def inspect_stored_token(self, secret_ref: SecretReference) -> MetaTokenMetadata:
        """Inspect a vaulted token and return current validity and permission metadata."""
        token = self._secrets.reveal(secret_ref)
        if not token:
            raise MetaAuthError("Access token could not be retrieved from secure vault.")
        return self._client.inspect_token(token)

    def is_token_near_expiration(
        self, metadata: MetaTokenMetadata, threshold_days: int = 7
    ) -> bool:
        """Check if token will expire within the given threshold."""
        if metadata.expires_at is None:
            return False
        now = datetime.now(UTC)
        return metadata.expires_at <= now + timedelta(days=threshold_days)

    def get_rate_limit_info(self) -> MetaRateLimitInfo:
        """Return the current rate limit usage indicators."""
        return self._client.get_rate_limit_info()

    def get_user_profile(self, secret_ref: SecretReference) -> dict[str, Any]:
        """Fetch profile information using the vaulted token."""
        token = self._secrets.reveal(secret_ref)
        if not token:
            raise MetaAuthError("Access token not found in vault.")
        return self._client.get_user_profile(token)

    def get_accounts_pages(self, secret_ref: SecretReference) -> list[dict[str, Any]]:
        """Fetch managed Facebook Pages authorized for this vaulted token."""
        token = self._secrets.reveal(secret_ref)
        if not token:
            raise MetaAuthError("Access token not found in vault.")
        return self._client.get_accounts_pages(token)
