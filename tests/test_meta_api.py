from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from sp_farms.application.meta_service import MetaIntegrationService
from sp_farms.application.secret_service import SecretService
from sp_farms.application.vault import Vault
from sp_farms.domain.meta import (
    MetaAuthError,
    MetaErrorCode,
    MetaOAuthConfig,
    MetaPermission,
    MetaPermissionError,
    MetaRateLimitError,
    MetaRateLimitInfo,
    MetaScopeSet,
    MetaTokenMetadata,
    MetaTokenType,
    MetaTransientError,
)
from sp_farms.domain.secrets import SecretType
from sp_farms.infrastructure.logging import redact
from sp_farms.infrastructure.meta.client import MetaHttpClient
from sp_farms.infrastructure.meta.errors import map_meta_error
from sp_farms.infrastructure.meta.fake_client import FakeMetaApiClient


class MemoryVault(Vault):
    """In-memory vault double for unit testing."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def store(self, key: str, secret: str) -> None:
        self._store[key] = secret

    def retrieve(self, key: str) -> str | None:
        return self._store.get(key)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


@pytest.fixture
def memory_vault() -> Vault:
    return MemoryVault()


@pytest.fixture
def secret_service(memory_vault: Vault) -> SecretService:
    return SecretService(memory_vault)


def test_meta_scope_set_parsing_and_subsets() -> None:
    # Comma-separated
    scopes1 = MetaScopeSet.from_string("public_profile, email, pages_show_list")
    assert len(scopes1.permissions) == 3
    assert scopes1.has_permission(MetaPermission.PUBLIC_PROFILE)
    assert scopes1.has_permission(MetaPermission.EMAIL)
    assert scopes1.has_permission("pages_show_list")
    assert not scopes1.has_permission(MetaPermission.PAGES_MANAGE_POSTS)

    # Whitespace-separated
    scopes2 = MetaScopeSet.from_string("email pages_show_list")
    assert scopes1.contains_all(scopes2)
    assert not scopes2.contains_all(scopes1)

    # Empty
    empty = MetaScopeSet.from_string("   ")
    assert len(empty.permissions) == 0
    assert scopes1.contains_all(empty)


def test_meta_token_metadata_expiration() -> None:
    now = datetime.now(UTC)
    scopes = MetaScopeSet.from_string("email")

    # Non-expired token
    valid_meta = MetaTokenMetadata(
        app_id="123",
        token_type=MetaTokenType.USER,
        scopes=scopes,
        expires_at=now + timedelta(days=30),
        is_valid=True,
    )
    assert not valid_meta.is_expired

    # Expired token
    expired_meta = MetaTokenMetadata(
        app_id="123",
        token_type=MetaTokenType.USER,
        scopes=scopes,
        expires_at=now - timedelta(hours=1),
        is_valid=True,
    )
    assert expired_meta.is_expired

    # Never expiring token (e.g. system user / page token)
    permanent_meta = MetaTokenMetadata(
        app_id="123",
        token_type=MetaTokenType.PAGE,
        scopes=scopes,
        expires_at=None,
        is_valid=True,
    )
    assert not permanent_meta.is_expired


def test_rate_limit_header_parsing() -> None:
    headers = {
        "x-app-usage": (
            '{"call_count": 85, "total_cpu_time": 40, '
            '"total_time": 20, "estimated_time_to_regain_access": 0}'
        )
    }
    info = MetaRateLimitInfo.from_headers(headers)
    assert info.call_count == 85
    assert info.total_cpu_time == 40
    assert not info.is_throttled

    # Throttled header
    throttled_headers = {
        "X-App-Usage": (
            '{"call_count": 105, "total_cpu_time": 95, '
            '"total_time": 100, "estimated_time_to_regain_access": 15}'
        )
    }
    throttled_info = MetaRateLimitInfo.from_headers(throttled_headers)
    assert throttled_info.is_throttled
    assert throttled_info.estimated_time_to_regain_access == 15


def test_error_mapping_taxonomy() -> None:
    # 1. Rate Limit Error
    err1 = map_meta_error(
        429,
        {"error": {"message": "Calls limit exceeded", "code": 4}},
        {"retry-after": "120"},
    )
    assert isinstance(err1, MetaRateLimitError)
    assert err1.code == MetaErrorCode.RATE_LIMIT_EXCEEDED
    assert err1.retry_after_seconds == 120.0

    # 2. Expired Token Error (code 190 subcode 463)
    err2 = map_meta_error(
        400,
        {
            "error": {
                "message": "Error validating access token: Session expired",
                "code": 190,
                "error_subcode": 463,
            }
        },
    )
    assert isinstance(err2, MetaAuthError)
    assert err2.code == MetaErrorCode.EXPIRED_TOKEN

    # 3. Missing Permission Error (code 200..299)
    err3 = map_meta_error(
        403,
        {"error": {"message": "Requires pages_read_engagement permission", "code": 200}},
    )
    assert isinstance(err3, MetaPermissionError)
    assert err3.code == MetaErrorCode.PERMISSION_DENIED

    # 4. Transient Error (500 or 503)
    err4 = map_meta_error(
        503,
        {"error": {"message": "Service Unavailable", "code": 2}},
    )
    assert isinstance(err4, MetaTransientError)
    assert err4.code == MetaErrorCode.TEMPORARY_SERVICE_ERROR


def test_fake_meta_oauth_flow_and_vault_storage(secret_service: SecretService) -> None:
    fake_client = FakeMetaApiClient(app_id="test_app_123")
    service = MetaIntegrationService(meta_client=fake_client, secret_service=secret_service)

    # 1. Generate Auth URL
    auth_url = service.generate_authorization_url(
        state="state_xyz",
        scopes=[MetaPermission.PUBLIC_PROFILE, MetaPermission.PAGES_SHOW_LIST],
    )
    assert "client_id=test_app_123" in auth_url
    assert "state=state_xyz" in auth_url
    assert "scope=pages_show_list%2Cpublic_profile" in auth_url

    # 2. Callback handling & vaulting
    account_id = str(uuid4())
    secret_ref, metadata = service.handle_oauth_callback(
        code="valid_auth_code_789",
        account_id=account_id,
    )
    assert secret_ref.secret_type == SecretType.ACCESS_TOKEN
    assert secret_ref.owner_id == account_id
    assert metadata.app_id == "test_app_123"
    assert metadata.is_valid is True
    assert not metadata.is_expired

    # 3. Secret retrieval from vault (plain token not stored on metadata or entity)
    revealed_token = service.get_token(secret_ref)
    assert revealed_token is not None
    assert "EAA_long_lived_" in revealed_token

    # 4. User profile & pages access
    profile = service.get_user_profile(secret_ref)
    assert profile["id"] == "fb-user-999"
    assert profile["name"] == "Test Operator"

    pages = service.get_accounts_pages(secret_ref)
    assert len(pages) == 1
    assert pages[0]["name"] == "SP Farms Official"


def test_fake_meta_oauth_error_cases(secret_service: SecretService) -> None:
    fake_client = FakeMetaApiClient(app_id="test_app_123")
    fake_client.simulated_invalid_code = True
    service = MetaIntegrationService(meta_client=fake_client, secret_service=secret_service)

    with pytest.raises(MetaAuthError, match="Invalid verification code"):
        service.handle_oauth_callback(code="bad_code", account_id="acc_1")


def test_token_never_logged_in_redaction() -> None:
    sensitive_token = "EAABwzLixnjYBO123456789SecretTokenABC"
    auth_header = f"Authorization: Bearer {sensitive_token}"

    redacted_header = redact(auth_header)
    assert sensitive_token not in redacted_header
    assert "[REDACTED]" in redacted_header

    # Test logger does not expose sensitive parameters in MetaHttpClient
    config = MetaOAuthConfig(
        client_id="app_123",
        client_secret="secret_abc",
        redirect_uri="https://localhost/callback",
    )

    class MockTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"access_token": sensitive_token, "token_type": "bearer"}
            )

    mock_http = httpx.Client(transport=MockTransport())
    client = MetaHttpClient(config, http_client=mock_http)

    res = client.exchange_code_for_token("auth_code_123")
    assert res.access_token == sensitive_token

    # Check that redact utility correctly catches secrets
    log_line = (
        "GET /oauth/access_token?client_secret=secret_abc"
        f"&code=auth_code_123&token={sensitive_token}"
    )
    assert sensitive_token not in redact(log_line)


def test_http_meta_client_transient_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    config = MetaOAuthConfig(
        client_id="app_123",
        client_secret="secret_abc",
        redirect_uri="https://localhost/callback",
    )

    call_count = 0

    class FailThenSucceedTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # 500 error on first attempt
                return httpx.Response(
                    500, json={"error": {"code": 1, "message": "Please retry later"}}
                )
            return httpx.Response(200, json={"id": "123", "name": "Success User"})

    # Speed up sleep during test
    import time

    monkeypatch.setattr(time, "sleep", lambda _sec: None)

    mock_client = httpx.Client(transport=FailThenSucceedTransport())
    client = MetaHttpClient(config, http_client=mock_client, max_retries=3, backoff_factor=0.01)

    profile = client.get_user_profile("EAA_test_token")
    assert profile["id"] == "123"
    assert call_count == 2
