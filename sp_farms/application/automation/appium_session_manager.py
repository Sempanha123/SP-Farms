"""Session manager and lifecycle coordinator for isolated Appium 2 device sessions."""

import logging
import threading
from typing import Final

from sp_farms.application.appium_port import AppiumDriverPort
from sp_farms.application.automation.mobile_driver import MobileDriver
from sp_farms.application.worker import CancellationToken
from sp_farms.domain.automation import (
    AppiumSessionInfo,
    AppiumSessionState,
    AutomationDevice,
    UiAutomator2Capabilities,
)

logger = logging.getLogger(__name__)

# Base port allocation range for UiAutomator2 system ports (8200..8299)
DEFAULT_SYSTEM_PORT_START: Final[int] = 8200


class AppiumSessionManager:
    """Manages active Appium 2 sessions mapped to reserved devices."""

    def __init__(
        self,
        driver_port: AppiumDriverPort,
        server_url: str = "http://127.0.0.1:4723",
        system_port_base: int = DEFAULT_SYSTEM_PORT_START,
    ) -> None:
        self.driver_port = driver_port
        self.server_url = server_url
        self.system_port_base = system_port_base
        self._sessions: dict[str, AppiumSessionInfo] = {}  # device_id -> session_info
        self._lock = threading.RLock()
        self._port_counter = 0

    def _allocate_system_port(self) -> int:
        with self._lock:
            port = self.system_port_base + (self._port_counter % 100)
            self._port_counter += 1
            return port

    def get_session(self, device_id: str) -> AppiumSessionInfo | None:
        with self._lock:
            return self._sessions.get(device_id)

    def get_all_sessions(self) -> list[AppiumSessionInfo]:
        with self._lock:
            return list(self._sessions.values())

    def start_session(
        self,
        device: AutomationDevice,
        capabilities_override: UiAutomator2Capabilities | None = None,
        job_id: str | None = None,
    ) -> AppiumSessionInfo:
        """Create and register an isolated Appium session for a reserved device."""
        with self._lock:
            existing = self._sessions.get(device.device_id)
            if existing and existing.state in (AppiumSessionState.ACTIVE, AppiumSessionState.BUSY):
                logger.info(
                    "Reusing existing active session %s for device %s",
                    existing.session_id,
                    device.device_id,
                )
                return existing

            system_port = self._allocate_system_port()
            caps = capabilities_override or UiAutomator2Capabilities(
                udid=device.udid,
                device_name=device.name,
                system_port=system_port,
            )

            logger.info(
                "Initializing Appium session for device %s on systemPort=%d",
                device.device_id,
                system_port,
            )
            self._sessions[device.device_id] = AppiumSessionInfo(
                session_id="",
                device_id=device.device_id,
                udid=device.udid,
                state=AppiumSessionState.CONNECTING,
                server_url=self.server_url,
                system_port=system_port,
                active_job_id=job_id,
            )

        try:
            session_id = self.driver_port.create_session(self.server_url, caps)
            with self._lock:
                session_info = AppiumSessionInfo(
                    session_id=session_id,
                    device_id=device.device_id,
                    udid=device.udid,
                    state=AppiumSessionState.ACTIVE if not job_id else AppiumSessionState.BUSY,
                    server_url=self.server_url,
                    system_port=system_port,
                    active_job_id=job_id,
                    capabilities=caps,
                )
                self._sessions[device.device_id] = session_info
                logger.info(
                    "Appium session %s established for device %s", session_id, device.device_id
                )
                return session_info
        except Exception as e:
            logger.error("Failed to start Appium session for device %s: %s", device.device_id, e)
            with self._lock:
                self._sessions[device.device_id] = AppiumSessionInfo(
                    session_id="",
                    device_id=device.device_id,
                    udid=device.udid,
                    state=AppiumSessionState.ERROR,
                    server_url=self.server_url,
                    system_port=system_port,
                    error_message=str(e),
                )
            raise

    def get_mobile_driver(
        self,
        device_id: str,
        cancellation_token: CancellationToken | None = None,
    ) -> MobileDriver:
        """Obtain a MobileDriver helper for an active session."""
        with self._lock:
            session = self._sessions.get(device_id)
            if (
                not session
                or not session.session_id
                or session.state not in (AppiumSessionState.ACTIVE, AppiumSessionState.BUSY)
            ):
                raise ValueError(f"No active Appium session for device {device_id}")
            return MobileDriver(
                driver_port=self.driver_port,
                session_id=session.session_id,
                cancellation_token=cancellation_token,
            )

    def end_session(self, device_id: str) -> None:
        """Teardown Appium session and free associated device resources."""
        with self._lock:
            session = self._sessions.pop(device_id, None)
            if not session or not session.session_id:
                return

        logger.info("Terminating Appium session %s for device %s", session.session_id, device_id)
        try:
            self.driver_port.delete_session(session.session_id)
        except Exception as e:
            logger.warning("Error deleting Appium session %s: %s", session.session_id, e)

    def close_all(self) -> None:
        """Cleanup all open sessions."""
        with self._lock:
            device_ids = list(self._sessions.keys())
        for dev_id in device_ids:
            self.end_session(dev_id)
