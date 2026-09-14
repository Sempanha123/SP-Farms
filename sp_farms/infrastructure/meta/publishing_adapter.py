"""Official and fake publishing adapters for Meta Graph API."""

import time
from typing import Any
from uuid import uuid4

import httpx

from sp_farms.application.publishing_port import PublishingPort, PublishResponse
from sp_farms.domain.meta import (
    MetaApiError,
    MetaAuthError,
    MetaErrorCode,
    MetaOAuthConfig,
    MetaPermissionError,
    MetaRateLimitError,
    MetaRateLimitInfo,
    MetaTransientError,
)
from sp_farms.domain.publishing import PublishErrorCode
from sp_farms.infrastructure.logging import get_logger
from sp_farms.infrastructure.meta.errors import map_meta_error

logger = get_logger("meta.publishing")


def map_exception_to_publish_error(exc: Exception) -> tuple[PublishErrorCode, str]:
    """Map Meta API exceptions or standard network exceptions to domain PublishErrorCode."""
    if isinstance(exc, MetaRateLimitError):
        return PublishErrorCode.RATE_LIMITED, str(exc)
    if isinstance(exc, MetaAuthError):
        return PublishErrorCode.TOKEN_EXPIRED, str(exc)
    if isinstance(exc, MetaPermissionError):
        return PublishErrorCode.PERMISSION_DENIED, str(exc)
    if isinstance(exc, MetaTransientError):
        return PublishErrorCode.NETWORK_ERROR, str(exc)
    if isinstance(exc, httpx.TransportError | httpx.TimeoutException):
        return PublishErrorCode.NETWORK_ERROR, str(exc)
    if isinstance(exc, MetaApiError):
        if exc.code in (
            MetaErrorCode.PARAM_ERROR,
            MetaErrorCode.GRAPH_METHOD_NOT_SUPPORTED,
        ):
            return PublishErrorCode.INVALID_PAYLOAD, str(exc)
        if exc.code == MetaErrorCode.DUPLICATE_POST:
            return PublishErrorCode.DUPLICATE_POST, str(exc)
        return PublishErrorCode.UNKNOWN, str(exc)
    return PublishErrorCode.UNKNOWN, str(exc)


class OfficialMetaPublishingAdapter(PublishingPort):
    """Official publisher using Meta Graph API with rate limit monitoring and backoff."""

    def __init__(
        self,
        config: MetaOAuthConfig,
        http_client: httpx.Client | None = None,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        self._config = config
        self._client = http_client or httpx.Client(timeout=60.0)
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._rate_limit_info = MetaRateLimitInfo()

    @property
    def rate_limit_info(self) -> MetaRateLimitInfo:
        return self._rate_limit_info

    def publish_page_feed(
        self,
        page_id: str,
        access_token: str,
        message: str,
        link: str | None = None,
        published: bool = True,
    ) -> PublishResponse:
        url = self._build_url(f"{page_id}/feed")
        data: dict[str, Any] = {
            "message": message,
            "published": published,
        }
        if link:
            data["link"] = link
        res = self._post(url, access_token=access_token, data=data)
        return PublishResponse(
            id=str(res.get("id", "")),
            post_id=str(res.get("id", "")),
            raw_response=res,
        )

    def publish_page_photo(
        self,
        page_id: str,
        access_token: str,
        caption: str,
        photo_url: str | None = None,
        photo_bytes: bytes | None = None,
        published: bool = True,
    ) -> PublishResponse:
        url = self._build_url(f"{page_id}/photos")
        data: dict[str, Any] = {
            "caption": caption,
            "published": published,
        }
        files: dict[str, Any] | None = None
        if photo_url:
            data["url"] = photo_url
        elif photo_bytes:
            files = {"source": ("photo.jpg", photo_bytes, "image/jpeg")}
        else:
            raise MetaApiError(
                "Either photo_url or photo_bytes must be provided for photo publish."
            )

        res = self._post(url, access_token=access_token, data=data, files=files)
        return PublishResponse(
            id=str(res.get("id", "")),
            post_id=str(res.get("post_id", res.get("id", ""))),
            media_id=str(res.get("id", "")),
            raw_response=res,
        )

    def publish_page_video(
        self,
        page_id: str,
        access_token: str,
        description: str,
        title: str | None = None,
        video_url: str | None = None,
        video_bytes: bytes | None = None,
        published: bool = True,
    ) -> PublishResponse:
        url = self._build_url(f"{page_id}/videos")
        data: dict[str, Any] = {
            "description": description,
            "published": published,
        }
        if title:
            data["title"] = title

        files: dict[str, Any] | None = None
        if video_url:
            data["file_url"] = video_url
        elif video_bytes:
            files = {"source": ("video.mp4", video_bytes, "video/mp4")}
        else:
            raise MetaApiError(
                "Either video_url or video_bytes must be provided for video publish."
            )

        res = self._post(url, access_token=access_token, data=data, files=files)
        return PublishResponse(
            id=str(res.get("id", "")),
            post_id=str(res.get("id", "")),
            media_id=str(res.get("id", "")),
            raw_response=res,
        )

    def publish_group_feed(
        self,
        group_id: str,
        access_token: str,
        message: str,
        link: str | None = None,
    ) -> PublishResponse:
        url = self._build_url(f"{group_id}/feed")
        data: dict[str, Any] = {
            "message": message,
        }
        if link:
            data["link"] = link
        res = self._post(url, access_token=access_token, data=data)
        return PublishResponse(
            id=str(res.get("id", "")),
            post_id=str(res.get("id", "")),
            raw_response=res,
        )

    def _build_url(self, path: str) -> str:
        base = self._config.base_url.rstrip("/")
        version = self._config.graph_version.strip("/")
        return f"{base}/{version}/{path.lstrip('/')}"

    def _post(
        self,
        url: str,
        access_token: str,
        data: dict[str, Any],
        files: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "SP-Farms-Desktop/1.0",
        }
        last_exc: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                response = self._client.post(url, headers=headers, data=data, files=files)

                resp_headers_dict = dict(response.headers)
                rate_info = MetaRateLimitInfo.from_headers(resp_headers_dict)
                if rate_info.call_count > 0 or rate_info.total_cpu_time > 0:
                    self._rate_limit_info = rate_info

                if response.is_success:
                    result = response.json()
                    if isinstance(result, dict):
                        return result
                    return {"id": str(result)}

                try:
                    payload = response.json()
                except Exception:
                    payload = {"error": {"message": response.text}}

                err = map_meta_error(
                    status_code=response.status_code,
                    payload=payload if isinstance(payload, dict) else {},
                    headers=resp_headers_dict,
                )

                if (
                    response.status_code in (429, 500, 502, 503, 504)
                    and attempt < self._max_retries - 1
                ):
                    sleep_time = err.retry_after_seconds or (self._backoff_factor * (2**attempt))
                    logger.warning(
                        "Publish HTTP %d error, retrying in %.2fs (attempt %d/%d)",
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
                    time.sleep(sleep_time)
                    continue
                raise MetaApiError(f"Publish transport failed: {exc.__class__.__name__}") from exc

        if last_exc:
            raise MetaApiError(f"Publish request failed after retries: {last_exc}")
        raise MetaApiError("Publish request failed unexpectedly.")


class FakePublishingAdapter(PublishingPort):
    """Deterministic test adapter for official publishing operations."""

    def __init__(self) -> None:
        self.published_feed_calls: list[dict[str, Any]] = []
        self.published_photo_calls: list[dict[str, Any]] = []
        self.published_video_calls: list[dict[str, Any]] = []
        self.published_group_calls: list[dict[str, Any]] = []

        self.simulated_rate_limit: bool = False
        self.simulated_auth_expired: bool = False
        self.simulated_permission_denied: bool = False
        self.simulated_invalid_payload: bool = False
        self.simulated_network_failures_remaining: int = 0
        self.custom_post_id: str | None = None

    def publish_page_feed(
        self,
        page_id: str,
        access_token: str,
        message: str,
        link: str | None = None,
        published: bool = True,
    ) -> PublishResponse:
        self._check_simulated_errors()
        post_id = self.custom_post_id or f"{page_id}_{uuid4().hex[:10]}"
        record = {
            "page_id": page_id,
            "access_token": access_token,
            "message": message,
            "link": link,
            "published": published,
            "post_id": post_id,
        }
        self.published_feed_calls.append(record)
        return PublishResponse(
            id=post_id,
            post_id=post_id,
            raw_response={"id": post_id},
        )

    def publish_page_photo(
        self,
        page_id: str,
        access_token: str,
        caption: str,
        photo_url: str | None = None,
        photo_bytes: bytes | None = None,
        published: bool = True,
    ) -> PublishResponse:
        self._check_simulated_errors()
        photo_id = f"photo_{uuid4().hex[:10]}"
        post_id = self.custom_post_id or f"{page_id}_{photo_id}"
        record = {
            "page_id": page_id,
            "access_token": access_token,
            "caption": caption,
            "photo_url": photo_url,
            "photo_bytes_len": len(photo_bytes) if photo_bytes else 0,
            "published": published,
            "photo_id": photo_id,
            "post_id": post_id,
        }
        self.published_photo_calls.append(record)
        return PublishResponse(
            id=photo_id,
            post_id=post_id,
            media_id=photo_id,
            raw_response={"id": photo_id, "post_id": post_id},
        )

    def publish_page_video(
        self,
        page_id: str,
        access_token: str,
        description: str,
        title: str | None = None,
        video_url: str | None = None,
        video_bytes: bytes | None = None,
        published: bool = True,
    ) -> PublishResponse:
        self._check_simulated_errors()
        video_id = self.custom_post_id or f"vid_{uuid4().hex[:10]}"
        record = {
            "page_id": page_id,
            "access_token": access_token,
            "description": description,
            "title": title,
            "video_url": video_url,
            "video_bytes_len": len(video_bytes) if video_bytes else 0,
            "published": published,
            "video_id": video_id,
        }
        self.published_video_calls.append(record)
        return PublishResponse(
            id=video_id,
            post_id=video_id,
            media_id=video_id,
            raw_response={"id": video_id},
        )

    def publish_group_feed(
        self,
        group_id: str,
        access_token: str,
        message: str,
        link: str | None = None,
    ) -> PublishResponse:
        self._check_simulated_errors()
        post_id = self.custom_post_id or f"{group_id}_{uuid4().hex[:10]}"
        record = {
            "group_id": group_id,
            "access_token": access_token,
            "message": message,
            "link": link,
            "post_id": post_id,
        }
        self.published_group_calls.append(record)
        return PublishResponse(
            id=post_id,
            post_id=post_id,
            raw_response={"id": post_id},
        )

    def _check_simulated_errors(self) -> None:
        if self.simulated_rate_limit:
            raise MetaRateLimitError(
                "App rate limit exceeded.",
                code=MetaErrorCode.RATE_LIMIT_EXCEEDED,
                status_code=429,
                retry_after_seconds=30.0,
            )
        if self.simulated_auth_expired:
            raise MetaAuthError(
                "Access token has expired or is invalid.",
                code=MetaErrorCode.EXPIRED_TOKEN,
                status_code=401,
            )
        if self.simulated_permission_denied:
            raise MetaPermissionError(
                "(#200) Insufficient permissions to publish content.",
                code=MetaErrorCode.PERMISSION_DENIED,
                status_code=403,
            )
        if self.simulated_invalid_payload:
            raise MetaApiError(
                "Invalid parameters supplied for publishing.",
                code=MetaErrorCode.UNKNOWN_ERROR,
                status_code=400,
            )
        if self.simulated_network_failures_remaining > 0:
            self.simulated_network_failures_remaining -= 1
            raise MetaTransientError(
                "Transient connection failure to Meta Graph API.",
                code=MetaErrorCode.TEMPORARY_SERVICE_ERROR,
                status_code=503,
            )
