# Meta Graph API Integration

## Overview

SP-Farms provides a dedicated integration boundary for official Meta Graph API operations. The architecture strictly decouples the user interface and business logic from low-level HTTP transport protocols, rate limits, and authentication mechanics.

All token management is backed by the operating system keyring (`KeyringVault` using Windows Credential Manager on Windows 11). Plaintext tokens are never stored in SQLite or logged.

## Configuration

Official Meta integration credentials may be configured via environment variables or Windows Credential Manager:

```env
# In .env or Windows environment:
SP_FARMS_META_APP_ID=123456789012345
SP_FARMS_META_APP_SECRET=your_app_secret_here
SP_FARMS_META_REDIRECT_URI=https://localhost/oauth/callback
SP_FARMS_META_API_VERSION=v21.0
```

When `SP_FARMS_META_APP_ID` or `SP_FARMS_META_APP_SECRET` are omitted, SP-Farms automatically defaults to `FakeMetaApiClient`. This provides full offline development and automated testing support without requiring active Meta developer accounts or live network calls.

## Architecture

1. **Domain (`sp_farms.domain.meta`)**:
   - `MetaScopeSet`: Immutable set representation of requested and granted permissions (`pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `email`, etc.).
   - `MetaTokenMetadata`: Inspected token properties including application ID, user identity, validity status, and expiration timestamps.
   - `MetaRateLimitInfo`: Standardized parsing of Meta's `X-App-Usage` and `X-Page-Usage` headers (call count percentage, CPU usage percentage, time limits, and estimated recovery time).
   - `MetaApiError`: Typed hierarchy covering `MetaAuthError`, `MetaPermissionError`, `MetaRateLimitError`, `MetaNotFoundError`, and `MetaTransientError`.

2. **Application Service (`sp_farms.application.meta_service.MetaIntegrationService`)**:
   - Generates compliant OAuth 2.0 authorization dialog URLs.
   - Orchestrates code exchange, short-to-long-lived token upgrades (60-day longevity), and debug token inspection.
   - Stores tokens as `SecretType.ACCESS_TOKEN` in the OS keyring vault using random GUID references.
   - Evaluates token health and expiration warnings (defaulting to 7-day alert window).

3. **Infrastructure (`sp_farms.infrastructure.meta`)**:
   - `MetaHttpClient`: Production HTTP client based on `httpx.Client` with automatic exponential backoff, rate-limit header tracking, and request redaction.
   - `FakeMetaApiClient`: Deterministic test double supporting simulated errors, expired tokens, custom permissions, and call inspection.
   - `map_meta_error`: Error taxonomy mapping Graph API error codes (e.g. 190, 4, 17, 32, 200-299) to domain exceptions.

## Security & Privacy Rules

- **Tokens Never Logged**: All HTTP debug logs automatically redact `access_token`, `client_secret`, `input_token`, `fb_exchange_token`, and `code`.
- **Zero Plaintext Storage**: Access tokens are stored exclusively in the OS vault; only non-sensitive metadata (token type, scopes, expiration date, and secret reference UUIDs) reside in SQLite.
- **Authorized Operations Only**: No scraping, fingerprint spoofing, or automated account creation is supported or implemented.
