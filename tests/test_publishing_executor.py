"""Tests for Phase 36: Official Publishing Executor."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from sp_farms.application.audit_service import AuditService
from sp_farms.application.campaign_service import CampaignService
from sp_farms.application.ports import Clock
from sp_farms.application.publish_repository import PublishRepositoryPort
from sp_farms.application.publishing_service import PublishingService
from sp_farms.domain.campaigns import (
    ApprovalPolicy,
    Campaign,
    CampaignStatus,
    CampaignTarget,
    RetryPolicy,
    SchedulePolicy,
    TargetStatus,
)
from sp_farms.domain.composer import PostType, PublishDestinationType
from sp_farms.domain.publishing import (
    PublishAttempt,
    PublishErrorCode,
    PublishStatus,
)
from sp_farms.infrastructure.database import (
    Base,
    Database,
    SqlAlchemyAuditRepository,
    SqlAlchemyCampaignRepository,
    SqlAlchemyPublishRepository,
)
from sp_farms.infrastructure.meta.publishing_adapter import FakePublishingAdapter


class FixedClock(Clock):
    def __init__(self, now_dt: datetime | None = None) -> None:
        self._now = now_dt or datetime.now(UTC)

    def now(self) -> datetime:
        return self._now


class InMemoryPublishRepository(PublishRepositoryPort):
    def __init__(self) -> None:
        self._attempts: dict[str, PublishAttempt] = {}

    def save(self, attempt: PublishAttempt) -> None:
        self._attempts[attempt.id] = attempt

    def get(self, attempt_id: str) -> PublishAttempt | None:
        return self._attempts.get(attempt_id)

    def get_by_idempotency_key(self, key: str) -> PublishAttempt | None:
        for a in self._attempts.values():
            if a.idempotency_key == key:
                return a
        return None

    def list_recent(
        self,
        limit: int = 50,
        status: PublishStatus | None = None,
        destination_id: str | None = None,
        campaign_id: str | None = None,
    ) -> list[PublishAttempt]:
        results = list(self._attempts.values())
        if status:
            results = [r for r in results if r.status == status]
        if destination_id:
            results = [r for r in results if r.destination_id == destination_id]
        if campaign_id:
            results = [r for r in results if r.campaign_id == campaign_id]
        return results[:limit]


@pytest.fixture
def fake_adapter() -> FakePublishingAdapter:
    return FakePublishingAdapter()


@pytest.fixture
def in_memory_repo() -> InMemoryPublishRepository:
    return InMemoryPublishRepository()


def test_publish_page_feed_success(
    in_memory_repo: InMemoryPublishRepository, fake_adapter: FakePublishingAdapter
) -> None:
    service = PublishingService(
        repository_factory=lambda: in_memory_repo,
        publishing_port=fake_adapter,
        backoff_base_seconds=0.01,
    )

    attempt = service.execute_publish(
        destination_type=PublishDestinationType.PAGE,
        destination_id="page-101",
        destination_name="Main Farm Page",
        access_token="EAA_valid_page_token",
        post_type=PostType.FEED,
        payload={"caption": "Fresh harvest today! Check out our organic vegetables."},
    )

    assert attempt.status == PublishStatus.PUBLISHED
    assert attempt.external_post_id is not None
    assert attempt.external_post_id.startswith("page-101_")
    assert len(fake_adapter.published_feed_calls) == 1
    call = fake_adapter.published_feed_calls[0]
    assert call["page_id"] == "page-101"
    assert "Fresh harvest" in call["message"]


def test_publish_page_photo_success(
    in_memory_repo: InMemoryPublishRepository, fake_adapter: FakePublishingAdapter
) -> None:
    service = PublishingService(
        repository_factory=lambda: in_memory_repo,
        publishing_port=fake_adapter,
        backoff_base_seconds=0.01,
    )

    attempt = service.execute_publish(
        destination_type=PublishDestinationType.PAGE,
        destination_id="page-101",
        destination_name="Main Farm Page",
        access_token="EAA_valid_page_token",
        post_type=PostType.FEED,
        payload={
            "caption": "Photo of hydroponic lettuce",
            "photo_bytes": b"FAKE_JPEG_IMAGE_BYTES",
        },
    )

    assert attempt.status == PublishStatus.PUBLISHED
    assert attempt.external_post_id is not None
    assert len(fake_adapter.published_photo_calls) == 1
    call = fake_adapter.published_photo_calls[0]
    assert call["caption"] == "Photo of hydroponic lettuce"
    assert call["photo_bytes_len"] == len(b"FAKE_JPEG_IMAGE_BYTES")


def test_publish_group_feed_success(
    in_memory_repo: InMemoryPublishRepository, fake_adapter: FakePublishingAdapter
) -> None:
    service = PublishingService(
        repository_factory=lambda: in_memory_repo,
        publishing_port=fake_adapter,
        backoff_base_seconds=0.01,
    )

    attempt = service.execute_publish(
        destination_type=PublishDestinationType.GROUP,
        destination_id="group-202",
        destination_name="Local Farmers Group",
        access_token="EAA_valid_user_token",
        post_type=PostType.FEED,
        payload={"caption": "Weekly community market schedule announcement"},
    )

    assert attempt.status == PublishStatus.PUBLISHED
    assert len(fake_adapter.published_group_calls) == 1
    call = fake_adapter.published_group_calls[0]
    assert call["group_id"] == "group-202"


def test_publish_retryable_transient_error_recovers(
    in_memory_repo: InMemoryPublishRepository, fake_adapter: FakePublishingAdapter
) -> None:
    # Set 2 transient network failures, then succeeds on 3rd attempt
    fake_adapter.simulated_network_failures_remaining = 2

    service = PublishingService(
        repository_factory=lambda: in_memory_repo,
        publishing_port=fake_adapter,
        backoff_base_seconds=0.01,
    )

    attempt = service.execute_publish(
        destination_type=PublishDestinationType.PAGE,
        destination_id="page-101",
        destination_name="Main Farm Page",
        access_token="EAA_valid_token",
        post_type=PostType.FEED,
        payload={"caption": "Resilient post"},
        max_retries=3,
    )

    assert attempt.status == PublishStatus.PUBLISHED
    assert attempt.retry_count == 2
    assert attempt.external_post_id is not None


def test_publish_non_retryable_auth_error(
    in_memory_repo: InMemoryPublishRepository, fake_adapter: FakePublishingAdapter
) -> None:
    fake_adapter.simulated_auth_expired = True

    service = PublishingService(
        repository_factory=lambda: in_memory_repo,
        publishing_port=fake_adapter,
        backoff_base_seconds=0.01,
    )

    attempt = service.execute_publish(
        destination_type=PublishDestinationType.PAGE,
        destination_id="page-101",
        destination_name="Main Farm Page",
        access_token="EAA_expired_token",
        post_type=PostType.FEED,
        payload={"caption": "Should fail immediately"},
        max_retries=3,
    )

    assert attempt.status == PublishStatus.FAILED
    assert attempt.error_code == PublishErrorCode.TOKEN_EXPIRED
    assert attempt.is_retryable is False
    assert attempt.retry_count == 0


def test_publish_rate_limit_failure_exceeds_retries(
    in_memory_repo: InMemoryPublishRepository, fake_adapter: FakePublishingAdapter
) -> None:
    fake_adapter.simulated_rate_limit = True

    service = PublishingService(
        repository_factory=lambda: in_memory_repo,
        publishing_port=fake_adapter,
        backoff_base_seconds=0.01,
    )

    attempt = service.execute_publish(
        destination_type=PublishDestinationType.PAGE,
        destination_id="page-101",
        destination_name="Main Farm Page",
        access_token="EAA_token",
        post_type=PostType.FEED,
        payload={"caption": "Rate limited post"},
        max_retries=2,
    )

    assert attempt.status == PublishStatus.FAILED
    assert attempt.error_code == PublishErrorCode.RATE_LIMITED
    assert attempt.retry_count == 2
    assert attempt.is_retryable is True


def test_publish_idempotency_prevents_duplicate(
    in_memory_repo: InMemoryPublishRepository, fake_adapter: FakePublishingAdapter
) -> None:
    service = PublishingService(
        repository_factory=lambda: in_memory_repo,
        publishing_port=fake_adapter,
        backoff_base_seconds=0.01,
    )

    idempotency_key = "idemp-key-12345"

    attempt1 = service.execute_publish(
        destination_type=PublishDestinationType.PAGE,
        destination_id="page-101",
        destination_name="Main Farm Page",
        access_token="EAA_valid_token",
        post_type=PostType.FEED,
        payload={"caption": "Once only"},
        idempotency_key=idempotency_key,
    )

    assert attempt1.status == PublishStatus.PUBLISHED

    # Second call with same idempotency key returns existing attempt without calling adapter again
    attempt2 = service.execute_publish(
        destination_type=PublishDestinationType.PAGE,
        destination_id="page-101",
        destination_name="Main Farm Page",
        access_token="EAA_valid_token",
        post_type=PostType.FEED,
        payload={"caption": "Once only"},
        idempotency_key=idempotency_key,
    )

    assert attempt2.id == attempt1.id
    assert attempt2.external_post_id == attempt1.external_post_id
    assert len(fake_adapter.published_feed_calls) == 1


def test_campaign_publishing_partial_and_full(
    tmp_path: Any, fake_adapter: FakePublishingAdapter
) -> None:
    db = Database(tmp_path / "test_pub.db")
    Base.metadata.create_all(db.engine)
    clock = FixedClock()

    audit_service = AuditService(
        unit_of_work=db.unit_of_work,
        audit_repository_factory=lambda uow: SqlAlchemyAuditRepository(uow),
        clock=clock,
    )

    campaign_service = CampaignService(
        unit_of_work=db.unit_of_work,
        campaign_repo_factory=lambda uow: SqlAlchemyCampaignRepository(uow),
    )

    target_specs = [
        (PublishDestinationType.PAGE, "page-101", "Page One"),
        (PublishDestinationType.PAGE, "page-102", "Page Two"),
    ]

    res = campaign_service.create_campaign(
        title="Spring Harvest Campaign",
        post_type=PostType.FEED,
        caption="Multi-destination announcement",
        target_specs=target_specs,
    )
    assert res.is_success
    campaign = res.value

    service = PublishingService(
        unit_of_work=db.unit_of_work,
        publish_repo_factory=lambda uow: SqlAlchemyPublishRepository(uow),
        publishing_port=fake_adapter,
        campaign_service=campaign_service,
        audit_service=audit_service,
        backoff_base_seconds=0.01,
    )

    # 1. Successful campaign publish across both targets
    def token_resolver(dest_type: PublishDestinationType, dest_id: str) -> str | None:
        return f"token_for_{dest_id}"

    attempts = service.execute_campaign_publishing(campaign.id, token_resolver)

    assert len(attempts) == 2
    assert all(a.status == PublishStatus.PUBLISHED for a in attempts)

    updated_campaign = campaign_service.get_campaign(campaign.id)
    assert updated_campaign is not None
    assert updated_campaign.status == CampaignStatus.COMPLETED
    assert all(t.status == TargetStatus.SUCCESS for t in updated_campaign.targets)


def test_campaign_publishing_partial_failure(
    tmp_path: Any, fake_adapter: FakePublishingAdapter
) -> None:
    db = Database(tmp_path / "test_pub_partial.db")
    Base.metadata.create_all(db.engine)
    clock = FixedClock()

    audit_service = AuditService(
        unit_of_work=db.unit_of_work,
        audit_repository_factory=lambda uow: SqlAlchemyAuditRepository(uow),
        clock=clock,
    )
    campaign_service = CampaignService(
        unit_of_work=db.unit_of_work,
        campaign_repo_factory=lambda uow: SqlAlchemyCampaignRepository(uow),
    )

    target_specs = [
        (PublishDestinationType.PAGE, "page-good", "Good Page"),
        (PublishDestinationType.PAGE, "page-bad", "Bad Page (Missing Token)"),
    ]

    res = campaign_service.create_campaign(
        title="Partial Failure Test Campaign",
        caption="Test",
        post_type=PostType.FEED,
        target_specs=target_specs,
    )
    assert res.is_success
    campaign = res.value

    service = PublishingService(
        unit_of_work=db.unit_of_work,
        publish_repo_factory=lambda uow: SqlAlchemyPublishRepository(uow),
        publishing_port=fake_adapter,
        campaign_service=campaign_service,
        audit_service=audit_service,
        backoff_base_seconds=0.01,
    )

    def partial_token_resolver(dest_type: PublishDestinationType, dest_id: str) -> str | None:
        if dest_id == "page-good":
            return "valid_token"
        return None  # Missing token for page-bad

    attempts = service.execute_campaign_publishing(campaign.id, partial_token_resolver)

    assert len(attempts) == 2
    updated_campaign = campaign_service.get_campaign(campaign.id)
    assert updated_campaign is not None
    assert updated_campaign.status == CampaignStatus.PARTIALLY_COMPLETED

    targets_map = {t.destination_id: t for t in updated_campaign.targets}
    assert targets_map["page-good"].status == TargetStatus.SUCCESS
    assert targets_map["page-bad"].status == TargetStatus.FAILED
