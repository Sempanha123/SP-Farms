import urllib.parse
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sp_farms.application.meta_client import MetaClientPort
from sp_farms.domain.meta import (
    MetaAuthError,
    MetaErrorCode,
    MetaOAuthTokenResponse,
    MetaRateLimitError,
    MetaRateLimitInfo,
    MetaScopeSet,
    MetaTokenMetadata,
    MetaTokenType,
    MetaTransientError,
)


class FakeMetaApiClient(MetaClientPort):
    """Controllable fake Meta API client for unit and integration tests."""

    def __init__(
        self,
        app_id: str = "123456789012345",
        app_secret: str = "fake_app_secret_abc123",
        redirect_uri: str = "https://localhost/oauth/callback",
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.redirect_uri = redirect_uri

        # Test hooks and simulated states
        self.simulated_rate_limit: MetaRateLimitInfo | None = None
        self.simulated_transient_failures_remaining: int = 0
        self.simulated_auth_expired: bool = False
        self.simulated_invalid_code: bool = False
        self.simulated_scopes = MetaScopeSet.from_string(
            "public_profile,email,pages_show_list,pages_read_engagement"
        )
        self.simulated_user_id: str = "fb-user-999"
        self.simulated_user_name: str = "Test Operator"
        self.simulated_user_email: str = "operator@spfarms.local"
        self.simulated_pages: list[dict[str, Any]] = [
            {
                "id": "page-101",
                "name": "SP Farms Official",
                "access_token": "EAA_fake_page_token_101",
                "category": "Agriculture",
                "tasks": ["MANAGE", "CREATE_CONTENT", "MODERATE"],
            }
        ]

        # Call inspection history
        self.recorded_calls: list[dict[str, Any]] = []

    def get_authorization_url(self, state: str, scopes: MetaScopeSet) -> str:
        params = {
            "client_id": self.app_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": scopes.to_string(),
            "response_type": "code",
        }
        encoded = urllib.parse.urlencode(params)
        return f"https://www.facebook.com/v21.0/dialog/oauth?{encoded}"

    def exchange_code_for_token(
        self, code: str, redirect_uri: str | None = None
    ) -> MetaOAuthTokenResponse:
        self.recorded_calls.append({"method": "exchange_code_for_token", "code_len": len(code)})
        if self.simulated_invalid_code or code == "invalid_code":
            raise MetaAuthError(
                "Invalid verification code format or expired.",
                code=MetaErrorCode.INVALID_OAUTH,
                status_code=400,
            )
        if self.simulated_rate_limit and self.simulated_rate_limit.is_throttled:
            raise MetaRateLimitError(
                "Application request limit reached.",
                code=MetaErrorCode.RATE_LIMIT_EXCEEDED,
                status_code=429,
                retry_after_seconds=60.0,
            )
        return MetaOAuthTokenResponse(
            access_token=f"EAA_fake_short_token_{code}",
            token_type="bearer",
            expires_in=7200,  # 2 hours
            granted_scopes=self.simulated_scopes,
        )

    def exchange_for_long_lived_token(self, short_lived_token: str) -> MetaOAuthTokenResponse:
        self.recorded_calls.append({"method": "exchange_for_long_lived_token"})
        if self.simulated_transient_failures_remaining > 0:
            self.simulated_transient_failures_remaining -= 1
            raise MetaTransientError(
                "Temporary Meta server outage.",
                code=MetaErrorCode.TEMPORARY_SERVICE_ERROR,
                status_code=500,
            )
        return MetaOAuthTokenResponse(
            access_token=f"EAA_long_lived_{short_lived_token}",
            token_type="bearer",
            expires_in=5184000,  # 60 days
            granted_scopes=self.simulated_scopes,
        )

    def inspect_token(self, token: str) -> MetaTokenMetadata:
        self.recorded_calls.append({"method": "inspect_token"})
        now = datetime.now(UTC)

        if self.simulated_auth_expired or "expired" in token.lower():
            return MetaTokenMetadata(
                app_id=self.app_id,
                token_type=MetaTokenType.USER,
                scopes=self.simulated_scopes,
                user_id=self.simulated_user_id,
                issued_at=now - timedelta(days=90),
                expires_at=now - timedelta(days=30),
                is_valid=False,
                raw_debug_info={
                    "error": {"code": 190, "subcode": 463, "message": "Session expired"}
                },
            )

        return MetaTokenMetadata(
            app_id=self.app_id,
            token_type=MetaTokenType.USER,
            scopes=self.simulated_scopes,
            user_id=self.simulated_user_id,
            issued_at=now,
            expires_at=now + timedelta(days=60),
            is_valid=True,
            raw_debug_info={"type": "USER", "is_valid": True},
        )

    def get_user_profile(
        self, token: str, fields: Sequence[str] | None = None
    ) -> dict[str, Any]:
        self.recorded_calls.append({"method": "get_user_profile"})
        if self.simulated_auth_expired or "expired" in token.lower():
            raise MetaAuthError(
                "Session has expired.",
                code=MetaErrorCode.EXPIRED_TOKEN,
                status_code=401,
            )
        return {
            "id": self.simulated_user_id,
            "name": self.simulated_user_name,
            "email": self.simulated_user_email,
        }

    def get_accounts_pages(self, token: str) -> list[dict[str, Any]]:
        self.recorded_calls.append({"method": "get_accounts_pages"})
        if self.simulated_auth_expired or "expired" in token.lower():
            raise MetaAuthError(
                "Session has expired.",
                code=MetaErrorCode.EXPIRED_TOKEN,
                status_code=401,
            )
        return list(self.simulated_pages)

    def get_rate_limit_info(self) -> MetaRateLimitInfo:
        return self.simulated_rate_limit or MetaRateLimitInfo()
