"""High-level mobile driver providing reliable Android UI actions and explicit waits."""

import logging
import time
from pathlib import Path
from typing import Any

from sp_farms.application.appium_port import AppiumDriverPort
from sp_farms.application.worker import CancellationToken
from sp_farms.domain.automation import (
    AppState,
    AutomationError,
    AutomationTimeoutError,
    By,
    ElementNotFoundError,
    ElementRef,
)

logger = logging.getLogger(__name__)


class MobileDriver:
    """High-level ergonomic wrapper over low-level Appium 2 UiAutomator2 port."""

    def __init__(
        self,
        driver_port: AppiumDriverPort,
        session_id: str,
        cancellation_token: CancellationToken | None = None,
        artifacts_dir: Path | None = None,
    ) -> None:
        self._port = driver_port
        self.session_id = session_id
        self._token = cancellation_token
        self._artifacts_dir = artifacts_dir

    def check_cancelled(self) -> None:
        if self._token and self._token.is_cancelled:
            self._token.raise_if_cancelled()

    def open_app(self, package: str, activity: str | None = None) -> None:
        self.check_cancelled()
        logger.info("Opening app package=%s activity=%s", package, activity)
        self._port.activate_app(self.session_id, package)

    def close_app(self, package: str) -> bool:
        self.check_cancelled()
        return self._port.terminate_app(self.session_id, package)

    def query_app_state(self, package: str) -> AppState:
        self.check_cancelled()
        return self._port.query_app_state(self.session_id, package)

    def inspect_current_screen(self) -> tuple[str, str]:
        self.check_cancelled()
        pkg = self._port.get_current_package(self.session_id)
        act = self._port.get_current_activity(self.session_id)
        return pkg, act

    def get_page_source(self) -> str:
        self.check_cancelled()
        return self._port.get_page_source(self.session_id)

    def take_screenshot(self) -> bytes:
        return self._port.take_screenshot(self.session_id)

    def save_screenshot(self, target_path: Path | str) -> Path:
        p = Path(target_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        raw_bytes = self.take_screenshot()
        p.write_bytes(raw_bytes)
        logger.info("Saved automation screenshot to %s", p)
        return p

    def wait_for_element(
        self,
        by: By,
        value: str,
        timeout_seconds: float = 10.0,
        poll_interval_seconds: float = 0.5,
    ) -> ElementRef:
        """Poll until element is present and displayed or timeout occurs."""
        end_time = time.monotonic() + timeout_seconds
        last_err: Exception | None = None

        while time.monotonic() < end_time:
            self.check_cancelled()
            try:
                elem = self._port.find_element(self.session_id, by, value)
                if self._port.is_element_displayed(self.session_id, elem.element_id):
                    return elem
            except Exception as e:
                last_err = e
            time.sleep(poll_interval_seconds)

        self._capture_failure_screenshot("wait_for_element_failed")
        raise AutomationTimeoutError(
            f"Timed out after {timeout_seconds}s waiting for element by {by.value}='{value}'",
            details={"by": by.value, "value": value, "last_error": str(last_err)},
        )

    def wait_for_element_disappear(
        self,
        by: By,
        value: str,
        timeout_seconds: float = 10.0,
        poll_interval_seconds: float = 0.5,
    ) -> bool:
        """Poll until element is absent or no longer displayed."""
        end_time = time.monotonic() + timeout_seconds
        while time.monotonic() < end_time:
            self.check_cancelled()
            try:
                elem = self._port.find_element(self.session_id, by, value)
                if not self._port.is_element_displayed(self.session_id, elem.element_id):
                    return True
            except Exception:
                return True
            time.sleep(poll_interval_seconds)
        return False

    def tap(
        self,
        by: By,
        value: str,
        timeout_seconds: float = 10.0,
        retries: int = 2,
    ) -> None:
        """Wait for element and click it with automatic retry on transient failures."""
        for attempt in range(retries + 1):
            self.check_cancelled()
            try:
                elem = self.wait_for_element(by, value, timeout_seconds=timeout_seconds)
                self._port.click(self.session_id, elem.element_id)
                logger.debug("Tapped element %s='%s'", by.value, value)
                return
            except Exception as e:
                if attempt < retries:
                    logger.warning(
                        "Transient failure tapping %s='%s' (attempt %d/%d): %s",
                        by.value,
                        value,
                        attempt + 1,
                        retries,
                        e,
                    )
                    time.sleep(0.5)
                    continue
                self._capture_failure_screenshot(f"tap_failed_{by.value}")
                raise

    def tap_coordinates(self, x: int, y: int) -> None:
        self.check_cancelled()
        self._port.tap_coordinates(self.session_id, x, y)

    def type_text(
        self,
        by: By,
        value: str,
        text: str,
        clear_first: bool = True,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.check_cancelled()
        elem = self.wait_for_element(by, value, timeout_seconds=timeout_seconds)
        if clear_first:
            self._port.clear_text(self.session_id, elem.element_id)
        self._port.type_text(self.session_id, elem.element_id, text)
        logger.debug("Typed text into %s='%s'", by.value, value)

    def clear(self, by: By, value: str, timeout_seconds: float = 10.0) -> None:
        self.check_cancelled()
        elem = self.wait_for_element(by, value, timeout_seconds=timeout_seconds)
        self._port.clear_text(self.session_id, elem.element_id)

    def get_text(self, by: By, value: str, timeout_seconds: float = 10.0) -> str:
        self.check_cancelled()
        elem = self.wait_for_element(by, value, timeout_seconds=timeout_seconds)
        return self._port.get_element_text(self.session_id, elem.element_id)

    def swipe(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int = 800,
    ) -> None:
        self.check_cancelled()
        self._port.swipe(self.session_id, start_x, start_y, end_x, end_y, duration_ms)

    def scroll(
        self,
        direction: str = "down",
        percent: float = 0.5,
        center_x: int = 540,
        center_y: int = 960,
    ) -> None:
        self.check_cancelled()
        distance = int(center_y * percent)
        if direction.lower() == "down":
            self.swipe(center_x, center_y + (distance // 2), center_x, center_y - (distance // 2))
        else:
            self.swipe(center_x, center_y - (distance // 2), center_x, center_y + (distance // 2))

    def back(self) -> None:
        self.check_cancelled()
        self._port.press_back(self.session_id)

    def _capture_failure_screenshot(self, label: str) -> Path | None:
        if not self._artifacts_dir:
            return None
        try:
            ts = int(time.time())
            path = self._artifacts_dir / f"fail_{label}_{ts}.png"
            return self.save_screenshot(path)
        except Exception as e:
            logger.warning("Failed to capture failure screenshot: %s", e)
            return None
