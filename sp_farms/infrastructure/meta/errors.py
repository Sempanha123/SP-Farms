import contextlib
from typing import Any

from sp_farms.domain.meta import (
    MetaApiError,
    MetaAuthError,
    MetaErrorCode,
    MetaNotFoundError,
    MetaPermissionError,
    MetaRateLimitError,
    MetaTransientError,
)


def map_meta_error(
    status_code: int,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> MetaApiError:
    """Map raw Meta Graph API HTTP response and error payload to domain exception."""
    error_data = (payload or {}).get("error", {})
    message = error_data.get("message") or f"Meta Graph API error with HTTP {status_code}"
    code_val = error_data.get("code")
    subcode = error_data.get("error_subcode")
    retry_after: float | None = None

    if headers:
        raw_retry = headers.get("retry-after") or headers.get("Retry-After")
        if raw_retry:
            with contextlib.suppress(ValueError):
                retry_after = float(raw_retry)

    # 1. Rate Limit Errors (Error codes 4, 17, 32, 613, or HTTP 429)
    if status_code == 429 or code_val in (4, 17, 32, 613):
        return MetaRateLimitError(
            message=message,
            code=MetaErrorCode.RATE_LIMIT_EXCEEDED,
            status_code=status_code,
            subcode=subcode,
            retry_after_seconds=retry_after or 60.0,
            raw_error=error_data,
        )

    # 2. Authentication / Token Expiration (Error code 190 or HTTP 401)
    if status_code == 401 or code_val == 190:
        err_code = MetaErrorCode.EXPIRED_TOKEN if subcode == 463 else MetaErrorCode.INVALID_OAUTH
        return MetaAuthError(
            message=message,
            code=err_code,
            status_code=status_code,
            subcode=subcode,
            retry_after_seconds=retry_after,
            raw_error=error_data,
        )

    # 3. Permissions Errors (Codes 200..299 or HTTP 403)
    if status_code == 403 or (code_val is not None and 200 <= code_val <= 299):
        return MetaPermissionError(
            message=message,
            code=MetaErrorCode.PERMISSION_DENIED,
            status_code=status_code,
            subcode=subcode,
            retry_after_seconds=retry_after,
            raw_error=error_data,
        )

    # 4. Not Found (Code 100 with subcode 33, or HTTP 404)
    if status_code == 404 or (code_val == 100 and subcode == 33):
        return MetaNotFoundError(
            message=message,
            code=MetaErrorCode.ASSET_NOT_FOUND,
            status_code=status_code,
            subcode=subcode,
            retry_after_seconds=retry_after,
            raw_error=error_data,
        )

    # 5. Transient Server Errors (Codes 1, 2, or HTTP 5xx)
    if status_code >= 500 or code_val in (1, 2):
        return MetaTransientError(
            message=message,
            code=MetaErrorCode.TEMPORARY_SERVICE_ERROR,
            status_code=status_code,
            subcode=subcode,
            retry_after_seconds=retry_after or 5.0,
            raw_error=error_data,
        )

    # Default unknown API error
    return MetaApiError(
        message=message,
        code=MetaErrorCode.UNKNOWN_ERROR,
        status_code=status_code,
        subcode=subcode,
        retry_after_seconds=retry_after,
        raw_error=error_data,
    )
