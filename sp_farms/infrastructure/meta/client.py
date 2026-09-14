import time
import urllib.parse
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import httpx

from sp_farms.application.meta_client import MetaClientPort
from sp_farms.domain.meta import (
    MetaApiError,
    MetaOAuthConfig,
    MetaOAuthTokenResponse,
    MetaRateLimitInfo,
    MetaScopeSet,
    MetaTokenMetadata,
    MetaTokenType,
)
from sp_farms.infrastructure.logging import get_logger
from sp_farms.infrastructure.meta.errors import map_meta_error

logger = get_logger("meta.client")


class MetaHttpClient(MetaClientPort):
    """Production Meta Graph API client utilizing httpx with retry and rate limit tracking."""

    def __init__(
        self,
        config: MetaOAuthConfig,
        http_client: httpx.Client | None = None,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        self._config = config
        self._client = http_client or httpx.Client(timeout=30.0)
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._rate_limit_info = MetaRateLimitInfo()

    @property
    def config(self) -> MetaOAuthConfig:
        return self._config

    def get_authorization_url(self, state: str, scopes: MetaScopeSet) -> str:
        """Construct the official OAuth 2.0 authorization dialog URL."""
        params = {
            "client_id": self._config.client_id,
            "redirect_uri": self._config.redirect_uri,
            "state": state,
            "scope": scopes.to_string(),
            "response_type": "code",
        }
        encoded_params = urllib.parse.urlencode(params)
        base = self._config.dialog_base_url.rstrip("/")
        version = self._config.graph_version.strip("/")
        return f"{base}/{version}/dialog/oauth?{encoded_params}"

    def exchange_code_for_token(
        self, code: str, redirect_uri: str | None = None
    ) -> MetaOAuthTokenResponse:
        """Exchange an OAuth authorization code for an access token."""
        url = self._build_graph_url("oauth/access_token")
        params = {
            "client_id": self._config.client_id,
            "redirect_uri": redirect_uri or self._config.redirect_uri,
            "client_secret": self._config.client_secret,
            "code": code,
        }
        data = self._request("GET", url, params=params)
        access_token = data.get("access_token", "")
        expires_in = data.get("expires_in")
        return MetaOAuthTokenResponse(
            access_token=access_token,
            token_type=data.get("token_type", "bearer"),
            expires_in=int(expires_in) if expires_in is not None else None,
        )

    def exchange_for_long_lived_token(self, short_lived_token: str) -> MetaOAuthTokenResponse:
        """Exchange a short-lived user access token for a 60-day long-lived token."""
        url = self._build_graph_url("oauth/access_token")
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self._config.client_id,
            "client_secret": self._config.client_secret,
            "fb_exchange_token": short_lived_token,
        }
        data = self._request("GET", url, params=params)
        access_token = data.get("access_token", "")
        expires_in = data.get("expires_in")
        return MetaOAuthTokenResponse(
            access_token=access_token,
            token_type=data.get("token_type", "bearer"),
            expires_in=int(expires_in) if expires_in is not None else None,
        )

    def inspect_token(self, token: str) -> MetaTokenMetadata:
        """Inspect and validate access token metadata via debug_token endpoint."""
        url = self._build_graph_url("debug_token")
        app_token = f"{self._config.client_id}|{self._config.client_secret}"
        params = {
            "input_token": token,
            "access_token": app_token,
        }
        res = self._request("GET", url, params=params)
        data = res.get("data", {})

        raw_type = str(data.get("type", "user")).lower()
        try:
            token_type = MetaTokenType(raw_type)
        except ValueError:
            token_type = MetaTokenType.USER

        issued_ts = data.get("issued_at")
        expires_ts = data.get("expires_at")

        issued_at = (
            datetime.fromtimestamp(issued_ts, UTC)
            if issued_ts and issued_ts > 0
            else None
        )
        expires_at = (
            datetime.fromtimestamp(expires_ts, UTC)
            if expires_ts and expires_ts > 0
            else None
        )

        scopes = MetaScopeSet(frozenset(data.get("scopes", [])))

        return MetaTokenMetadata(
            app_id=str(data.get("app_id", self._config.client_id)),
            token_type=token_type,
            scopes=scopes,
            user_id=str(data.get("user_id")) if data.get("user_id") else None,
            issued_at=issued_at,
            expires_at=expires_at,
            is_valid=bool(data.get("is_valid", False)),
            raw_debug_info=data,
        )

    def get_user_profile(
        self, token: str, fields: Sequence[str] | None = None
    ) -> dict[str, Any]:
        """Fetch basic authorized profile information for /me."""
        field_list = fields or ("id", "name", "email")
        url = self._build_graph_url("me")
        headers = {"Authorization": f"Bearer {token}"}
        params = {"fields": ",".join(field_list)}
        data = self._request("GET", url, headers=headers, params=params)
        return data

    def get_accounts_pages(self, token: str) -> list[dict[str, Any]]:
        """Fetch managed Facebook Pages authorized for the token."""
        url = self._build_graph_url("me/accounts")
        headers = {"Authorization": f"Bearer {token}"}
        params = {"fields": "id,name,access_token,category,tasks,verification_status"}
        data = self._request("GET", url, headers=headers, params=params)
        pages = data.get("data", [])
        if isinstance(pages, list):
            return [p for p in pages if isinstance(p, dict)]
        return []

    def get_rate_limit_info(self) -> MetaRateLimitInfo:
        """Return the most recently observed rate limit usage metrics."""
        return self._rate_limit_info

    def _build_graph_url(self, path: str) -> str:
        base = self._config.base_url.rstrip("/")
        version = self._config.graph_version.strip("/")
        endpoint = path.lstrip("/")
        return f"{base}/{version}/{endpoint}"

    def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        req_headers = dict(headers or {})
        req_headers.setdefault("User-Agent", "SP-Farms-Desktop/1.0")

        # Sanitize log statements to never leak credentials or tokens
        safe_params = dict(params or {})
        for secret_key in (
            "client_secret", "code", "input_token", "fb_exchange_token", "access_token"
        ):
            if secret_key in safe_params:
                safe_params[secret_key] = "[REDACTED]"

        logger.debug("Meta API %s %s params=%s", method, url, safe_params)

        last_exc: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                response = self._client.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=req_headers,
                    json=json_body,
                )

                # Record rate limit headers if present
                resp_headers_dict = dict(response.headers)
                rate_info = MetaRateLimitInfo.from_headers(resp_headers_dict)
                if rate_info.call_count > 0 or rate_info.total_cpu_time > 0:
                    self._rate_limit_info = rate_info

                if response.is_success:
                    result = response.json()
                    if isinstance(result, dict):
                        return result
                    return {"result": result}

                # HTTP error status: parse error payload
                try:
                    payload = response.json()
                except Exception:
                    payload = {"error": {"message": response.text}}

                err = map_meta_error(
                    status_code=response.status_code,
                    payload=payload if isinstance(payload, dict) else {},
                    headers=resp_headers_dict,
                )

                # Transient server or rate-limit retry
                if (
                    response.status_code in (429, 500, 502, 503, 504)
                    and attempt < self._max_retries - 1
                ):
                    sleep_time = err.retry_after_seconds or (self._backoff_factor * (2**attempt))
                    logger.warning(
                        "Meta API HTTP %d transient error, retrying in %.2fs (attempt %d/%d)",
                        response.status_code,
                        sleep_time,
                        attempt + 1,
                        self._max_retries,
                    )
                    time.sleep(sleep_time)
                    continue

                raise err

            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < self._max_retries - 1:
                    sleep_time = self._backoff_factor * (2**attempt)
                    logger.warning(
                        "Meta API transport error: %s, retrying in %.2fs",
                        exc.__class__.__name__,
                        sleep_time,
                    )
                    time.sleep(sleep_time)
                    continue
                raise MetaApiError(
                    f"Meta network transport failed: {exc.__class__.__name__}",
                    raw_error={"exception": str(exc)},
                ) from exc

        if last_exc:
            raise MetaApiError(f"Meta request failed after retries: {last_exc}")
        raise MetaApiError("Meta request failed unexpectedly.")
