"""Automated tests for HybridPublishingService combining Meta Graph API with Appium 2 fallback."""

from unittest.mock import MagicMock

import pytest

from sp_farms.application.automation.appium_session_manager import AppiumSessionManager
from sp_farms.application.automation.job_handler import AppiumJobExecutor
from sp_farms.application.hybrid_publishing_service import HybridPublishingService
from sp_farms.application.publishing_service import PublishingService
from sp_farms.application.worker import CancellationToken
from sp_farms.domain.composer import PostType, PublishDestinationType
from sp_farms.domain.publishing import (
    PublishAttempt,
    PublishErrorCode,
    PublishExecutionStrategy,
    PublishMethod,
    PublishStatus,
)
from sp_farms.infrastructure.appium.fake_driver import FakeAppiumDriver


class InMemoryPublishRepo:
    def __init__(self):
        self.items: dict[str, PublishAttempt] = {}

    def save(self, attempt: PublishAttempt) -> None:
        self.items[attempt.id] = attempt

    def get(self, attempt_id: str) -> PublishAttempt | None:
        return self.items.get(attempt_id)

    def get_by_idempotency_key(self, key: str) -> PublishAttempt | None:
        for a in self.items.values():
            if a.idempotency_key == key:
                return a
        return None


@pytest.fixture
def repo():
    return InMemoryPublishRepo()


@pytest.fixture
def fake_driver():
    return FakeAppiumDriver()


@pytest.fixture
def session_manager(fake_driver):
    return AppiumSessionManager(driver_port=fake_driver)


@pytest.fixture
def appium_executor(session_manager):
    pool = MagicMock()
    pool.acquire_device_lock.return_value = MagicMock()
    pool.release_device_lock.return_value = True
    return AppiumJobExecutor(
        session_manager=session_manager,
        device_pool_service=pool,
    )


@pytest.fixture
def fake_api_publisher():
    from sp_farms.infrastructure.meta.publishing_adapter import FakePublishingAdapter

    adapter = FakePublishingAdapter()
    adapter.custom_post_id = "fb_api_post_123"
    return adapter


@pytest.fixture
def publishing_service(fake_api_publisher, repo):
    return PublishingService(
        publishing_port=fake_api_publisher,
        repository_factory=lambda: repo,
    )


@pytest.fixture
def hybrid_service(publishing_service, appium_executor):
    return HybridPublishingService(
        publishing_service=publishing_service,
        appium_executor=appium_executor,
    )


def test_hybrid_uses_api_when_supported(hybrid_service, fake_api_publisher):
    result = hybrid_service.execute_publish(
        destination_type=PublishDestinationType.PAGE,
        destination_id="page-101",
        destination_name="My Cool Page",
        post_type=PostType.FEED,
        payload={"message": "Official Page update"},
        access_token="valid_token",
        strategy=PublishExecutionStrategy.HYBRID_AUTO,
    )

    assert result.status == PublishStatus.PUBLISHED
    assert result.method_used == PublishMethod.API
    assert result.external_post_id == "fb_api_post_123"
    assert len(fake_api_publisher.published_feed_calls) == 1


def test_hybrid_routes_to_appium_when_destination_unsupported_by_api(
    hybrid_service, fake_api_publisher
):
    # Personal profile is not supported by official Meta Graph API
    ctx = MagicMock()
    ctx.job.id = "job-hybrid-1"
    ctx.cancellation_token = CancellationToken()

    result = hybrid_service.execute_publish(
        destination_type=PublishDestinationType.ACCOUNT_PROFILE,
        destination_id="profile-user-1",
        destination_name="Personal Profile",
        post_type=PostType.FEED,
        payload={"caption": "Personal update via Android UI"},
        account_id="acc-personal-1",
        device_key="ldplayer:emulator-5554",
        strategy=PublishExecutionStrategy.HYBRID_AUTO,
        execution_context=ctx,
    )

    assert result.status == PublishStatus.PUBLISHED
    assert result.method_used == PublishMethod.APPIUM
    assert result.external_post_id.startswith("appium-post-")
    assert len(fake_api_publisher.published_feed_calls) == 0


def test_hybrid_fallback_to_appium_on_api_permission_denied(hybrid_service, fake_api_publisher):
    # API fails with permission error
    fake_api_publisher.simulated_permission_denied = True

    ctx = MagicMock()
    ctx.job.id = "job-fallback-1"
    ctx.cancellation_token = CancellationToken()

    result = hybrid_service.execute_publish(
        destination_type=PublishDestinationType.PAGE,
        destination_id="page-restricted",
        destination_name="Restricted Page",
        post_type=PostType.FEED,
        payload={"message": "Trying API then fallback"},
        access_token="unauthorized_token",
        account_id="acc-page-admin",
        device_key="ldplayer:emulator-5554",
        strategy=PublishExecutionStrategy.HYBRID_AUTO,
        execution_context=ctx,
    )

    # Must fall back to Appium and succeed
    assert result.status == PublishStatus.PUBLISHED
    assert result.method_used == PublishMethod.APPIUM
    assert result.external_post_id.startswith("appium-post-")


def test_hybrid_respects_api_only_strategy(hybrid_service, fake_api_publisher):
    fake_api_publisher.simulated_permission_denied = True

    result = hybrid_service.execute_publish(
        destination_type=PublishDestinationType.PAGE,
        destination_id="page-101",
        destination_name="Page",
        post_type=PostType.FEED,
        payload={"message": "Strict API only"},
        access_token="invalid",
        strategy=PublishExecutionStrategy.API_ONLY,
    )

    # Should remain failed without Appium fallback
    assert result.status == PublishStatus.FAILED
    assert result.method_used == PublishMethod.API
    assert result.error_code == PublishErrorCode.PERMISSION_DENIED
