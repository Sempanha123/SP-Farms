"""Domain models for official publishing attempts, error classification, and results."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sp_farms.domain.composer import PostType, PublishDestinationType


class PublishStatus(StrEnum):
    PENDING = "pending"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    RETRYING = "retrying"


class PublishMethod(StrEnum):
    API = "api"
    APPIUM = "appium"


class PublishExecutionStrategy(StrEnum):
    API_ONLY = "api_only"
    APPIUM_ONLY = "appium_only"
    HYBRID_AUTO = "hybrid_auto"


def is_api_supported_destination(
    destination_type: PublishDestinationType, post_type: PostType
) -> bool:
    """Return True if Meta Graph API supports direct posting for this destination and post type."""
    # Graph API does NOT support personal profile publishing or certain groups
    if destination_type in (PublishDestinationType.ACCOUNT_PROFILE,):
        return False
    # Stories on groups are also not supported via Graph API
    return not (destination_type == PublishDestinationType.GROUP and post_type == PostType.STORY)


class PublishErrorCode(StrEnum):
    RATE_LIMITED = "RATE_LIMITED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    MEDIA_UPLOAD_FAILED = "MEDIA_UPLOAD_FAILED"
    NETWORK_ERROR = "NETWORK_ERROR"
    DUPLICATE_POST = "DUPLICATE_POST"
    UNKNOWN = "UNKNOWN"

    @property
    def is_retryable(self) -> bool:
        return self in (
            PublishErrorCode.RATE_LIMITED,
            PublishErrorCode.NETWORK_ERROR,
            PublishErrorCode.MEDIA_UPLOAD_FAILED,
        )


@dataclass(frozen=True, slots=True)
class PublishAttempt:
    """Audit and state tracking entity for an individual publishing attempt."""

    id: str
    destination_type: PublishDestinationType
    destination_id: str
    destination_name: str
    post_type: PostType
    payload: Mapping[str, Any]
    status: PublishStatus = PublishStatus.PENDING
    method_used: PublishMethod = PublishMethod.API
    scheduled_item_id: str | None = None
    campaign_id: str | None = None
    job_id: str | None = None
    external_post_id: str | None = None
    error_code: PublishErrorCode | None = None
    error_message: str | None = None
    is_retryable: bool = False
    retry_count: int = 0
    duration_ms: int = 0
    idempotency_key: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        destination_type: PublishDestinationType,
        destination_id: str,
        destination_name: str,
        post_type: PostType,
        payload: Mapping[str, Any],
        method_used: PublishMethod = PublishMethod.API,
        scheduled_item_id: str | None = None,
        campaign_id: str | None = None,
        job_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> "PublishAttempt":
        now = datetime.now(UTC)
        return cls(
            id=str(uuid4()),
            destination_type=destination_type,
            destination_id=destination_id,
            destination_name=destination_name,
            post_type=post_type,
            payload=dict(payload),
            status=PublishStatus.PENDING,
            method_used=method_used,
            scheduled_item_id=scheduled_item_id,
            campaign_id=campaign_id,
            job_id=job_id,
            idempotency_key=idempotency_key or str(uuid4()),
            created_at=now,
            updated_at=now,
        )

    def mark_published(
        self, external_post_id: str, duration_ms: int = 0, method_used: PublishMethod | None = None
    ) -> "PublishAttempt":
        now = datetime.now(UTC)
        return PublishAttempt(
            id=self.id,
            destination_type=self.destination_type,
            destination_id=self.destination_id,
            destination_name=self.destination_name,
            post_type=self.post_type,
            payload=self.payload,
            status=PublishStatus.PUBLISHED,
            method_used=method_used or self.method_used,
            scheduled_item_id=self.scheduled_item_id,
            campaign_id=self.campaign_id,
            job_id=self.job_id,
            external_post_id=external_post_id,
            error_code=None,
            error_message=None,
            is_retryable=False,
            retry_count=self.retry_count,
            duration_ms=duration_ms,
            idempotency_key=self.idempotency_key,
            created_at=self.created_at,
            updated_at=now,
        )

    def mark_failed(
        self,
        error_code: PublishErrorCode,
        error_message: str,
        duration_ms: int = 0,
        is_retrying: bool = False,
        method_used: PublishMethod | None = None,
    ) -> "PublishAttempt":
        now = datetime.now(UTC)
        return PublishAttempt(
            id=self.id,
            destination_type=self.destination_type,
            destination_id=self.destination_id,
            destination_name=self.destination_name,
            post_type=self.post_type,
            payload=self.payload,
            status=PublishStatus.RETRYING if is_retrying else PublishStatus.FAILED,
            method_used=method_used or self.method_used,
            scheduled_item_id=self.scheduled_item_id,
            campaign_id=self.campaign_id,
            job_id=self.job_id,
            external_post_id=None,
            error_code=error_code,
            error_message=error_message,
            is_retryable=error_code.is_retryable,
            retry_count=self.retry_count + (1 if is_retrying else 0),
            duration_ms=duration_ms,
            idempotency_key=self.idempotency_key,
            created_at=self.created_at,
            updated_at=now,
        )
