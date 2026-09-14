"""Automated test suite for Appium 2 UiAutomator2 integration layer."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sp_farms.application.automation.appium_session_manager import AppiumSessionManager
from sp_farms.application.automation.job_handler import AppiumJobExecutor
from sp_farms.application.automation.mobile_driver import MobileDriver
from sp_farms.application.worker import CancellationToken, JobCancelledError
from sp_farms.domain.automation import (
    AppState,
    AutomationDevice,
    AutomationTimeoutError,
    By,
    UiAutomator2Capabilities,
)
from sp_farms.infrastructure.appium.fake_driver import FakeAppiumDriver
from sp_farms.infrastructure.appium.page_objects.facebook_screen import (
    FacebookComposerScreen,
    FacebookHomeScreen,
)
from sp_farms.infrastructure.appium.server_manager import (
    AppiumServerHealth,
    AppiumServerManager,
    ServerHealthState,
)


@pytest.fixture
def fake_driver() -> FakeAppiumDriver:
    return FakeAppiumDriver()


@pytest.fixture
def session_manager(fake_driver: FakeAppiumDriver) -> AppiumSessionManager:
    return AppiumSessionManager(driver_port=fake_driver, server_url="http://127.0.0.1:4723")


def test_appium_session_creation_and_teardown(session_manager: AppiumSessionManager, fake_driver: FakeAppiumDriver):
    device = AutomationDevice(
        device_id="ldplayer:emulator-5554",
        udid="emulator-5554",
        provider="ldplayer",
        name="LDPlayer-1",
    )

    session = session_manager.start_session(device)
    assert session.session_id.startswith("fake-session-")
    assert session.device_id == "ldplayer:emulator-5554"
    assert session.system_port >= 8200
    assert fake_driver.is_session_alive(session.session_id)

    # Teardown
    session_manager.end_session(device.device_id)
    assert not fake_driver.is_session_alive(session.session_id)
    assert session_manager.get_session(device.device_id) is None


def test_mobile_driver_basic_actions(fake_driver: FakeAppiumDriver, tmp_path: Path):
    session_id = fake_driver.create_session("http://127.0.0.1:4723", UiAutomator2Capabilities())
    driver = MobileDriver(driver_port=fake_driver, session_id=session_id, artifacts_dir=tmp_path)

    # Open app
    driver.open_app("com.facebook.katana")
    assert driver.query_app_state("com.facebook.katana") == AppState.RUNNING_IN_FOREGROUND

    # Inspect current screen
    pkg, act = driver.inspect_current_screen()
    assert pkg == "com.facebook.katana"

    # Type & clear text
    driver.type_text(By.ID, "fake_input", "Hello Appium")
    assert driver.get_text(By.ID, "fake_input") == "Hello Appium"

    driver.clear(By.ID, "fake_input")
    assert driver.get_text(By.ID, "fake_input") == ""

    # Swipe & Scroll
    driver.swipe(100, 500, 100, 100)
    driver.scroll(direction="down")

    # Screenshot
    ss_path = driver.save_screenshot(tmp_path / "test_screen.png")
    assert ss_path.exists()
    assert len(ss_path.read_bytes()) > 0


def test_mobile_driver_cancellation(fake_driver: FakeAppiumDriver):
    session_id = fake_driver.create_session("http://127.0.0.1:4723", UiAutomator2Capabilities())
    token = CancellationToken()
    driver = MobileDriver(driver_port=fake_driver, session_id=session_id, cancellation_token=token)

    token.cancel()
    with pytest.raises(JobCancelledError):
        driver.open_app("com.facebook.katana")


def test_facebook_page_object_flow(fake_driver: FakeAppiumDriver):
    session_id = fake_driver.create_session("http://127.0.0.1:4723", UiAutomator2Capabilities())
    driver = MobileDriver(driver_port=fake_driver, session_id=session_id)

    home = FacebookHomeScreen(driver)
    assert home.is_screen_active()

    composer = home.open_composer()
    assert composer.is_screen_active()
    composer.set_post_text("Test Post Content")
    composer.submit_post()


def test_appium_server_manager_health(monkeypatch):
    mgr = AppiumServerManager(server_url="http://127.0.0.1:4723")

    # Mock successful response
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {
        "value": {
            "ready": True,
            "message": "The server is ready",
            "build": {"version": "2.5.0"},
        }
    }

    mock_client = MagicMock()
    mock_client.get.return_value = mock_res
    mock_client.__enter__.return_value = mock_client

    monkeypatch.setattr("httpx.Client", lambda *args, **kwargs: mock_client)

    health = mgr.check_health()
    assert health.state == ServerHealthState.ONLINE
    assert health.ready is True
    assert health.version == "2.5.0"


def test_appium_job_executor(session_manager: AppiumSessionManager, fake_driver: FakeAppiumDriver, tmp_path: Path):
    mock_pool_service = MagicMock()
    mock_pool_service.acquire_device_lock.return_value = MagicMock()
    mock_pool_service.release_device_lock.return_value = True

    executor = AppiumJobExecutor(
        session_manager=session_manager,
        device_pool_service=mock_pool_service,
        artifacts_dir=tmp_path,
    )

    mock_context = MagicMock()
    mock_context.job.id = "job-999"
    mock_context.cancellation_token = CancellationToken()

    action_called = False

    def sample_action(driver: MobileDriver, ctx):
        nonlocal action_called
        action_called = True
        driver.open_app("com.facebook.katana")

    executor.execute_with_device(
        context=mock_context,
        account_id="acc-123",
        device_key="ldplayer:emulator-5554",
        action=sample_action,
    )

    assert action_called is True
    mock_pool_service.acquire_device_lock.assert_called_once()
    mock_pool_service.release_device_lock.assert_called_once_with("acc-123")
    # Session must be closed after execution
    assert session_manager.get_session("ldplayer:emulator-5554") is None
