"""Job handler and automation runner integrating Appium 2.

Integrates with WorkerSupervisor and DevicePoolService.
"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sp_farms.application.automation.appium_session_manager import AppiumSessionManager
from sp_farms.application.automation.mobile_driver import MobileDriver
from sp_farms.application.device_pool_service import DevicePoolService
from sp_farms.application.worker import JobExecutionContext
from sp_farms.domain.automation import AutomationDevice, UiAutomator2Capabilities

logger = logging.getLogger(__name__)


class AppiumJobExecutor:
    """Executes automation workflows on reserved devices using Appium 2 with cleanup on release."""

    def __init__(
        self,
        session_manager: AppiumSessionManager,
        device_pool_service: DevicePoolService,
        artifacts_dir: Path | str = "artifacts/automation",
    ) -> None:
        self.session_manager = session_manager
        self.device_pool_service = device_pool_service
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def execute_with_device(
        self,
        context: JobExecutionContext,
        account_id: str,
        device_key: str,
        action: Callable[[MobileDriver, JobExecutionContext], Any],
        package: str | None = None,
        activity: str | None = None,
    ) -> Any:
        """Reserve device lock, initialize Appium session, run action, and cleanup."""
        context.check_cancelled()
        context.record_progress(5)

        lock = self.device_pool_service.acquire_device_lock(
            account_id=account_id,
            device_key=device_key,
            job_id=context.job.id,
            ttl_seconds=600,
        )
        if not lock:
            raise RuntimeError(
                f"Could not acquire device lock for account {account_id} on {device_key}"
            )

        provider, ext_id = (
            device_key.split(":", 1) if ":" in device_key else ("physical", device_key)
        )
        device = AutomationDevice(
            device_id=device_key,
            udid=ext_id,
            provider=provider,
            name=f"Device-{device_key}",
        )

        caps = UiAutomator2Capabilities(
            udid=device.udid,
            device_name=device.name,
            app_package=package,
            app_activity=activity,
        )

        try:
            context.check_cancelled()
            context.record_progress(15)
            logger.info(
                "Starting Appium session for job=%s on device=%s", context.job.id, device_key
            )
            self.session_manager.start_session(
                device=device,
                capabilities_override=caps,
                job_id=context.job.id,
            )

            driver = self.session_manager.get_mobile_driver(
                device_id=device_key,
                cancellation_token=context.cancellation_token,
            )
            driver._artifacts_dir = self.artifacts_dir

            context.check_cancelled()
            context.record_progress(30)
            logger.info("Executing Appium action in worker thread for job=%s", context.job.id)
            result = action(driver, context)

            context.record_progress(95)
            return result
        except Exception as e:
            logger.error("Error executing Appium automation job=%s: %s", context.job.id, e)
            try:
                if driver:
                    driver.save_screenshot(self.artifacts_dir / f"failure_job_{context.job.id}.png")
            except Exception as ss_err:
                logger.warning("Could not save failure screenshot: %s", ss_err)
            raise
        finally:
            logger.info(
                "Tearing down Appium session and releasing device lock for device=%s", device_key
            )
            try:
                self.session_manager.end_session(device_key)
            except Exception as e:
                logger.warning("Failed to end Appium session for %s: %s", device_key, e)
            try:
                self.device_pool_service.release_device_lock(account_id)
            except Exception as e:
                logger.warning("Failed to release device lock for %s: %s", account_id, e)
