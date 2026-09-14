"""Manages local or remote Appium 2 server discovery, health checks, and lifecycle."""

import contextlib
import json
import logging
import subprocess
import time
from dataclasses import dataclass
from enum import StrEnum

import httpx

logger = logging.getLogger(__name__)


class ServerHealthState(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class AppiumServerHealth:
    url: str
    state: ServerHealthState
    version: str | None = None
    ready: bool = False
    message: str | None = None
    latency_ms: float = 0.0


class AppiumServerManager:
    """Monitors and manages Appium 2 server instances."""

    def __init__(
        self,
        server_url: str = "http://127.0.0.1:4723",
        client_timeout_seconds: float = 5.0,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.timeout = client_timeout_seconds
        self._process: subprocess.Popen[str] | None = None

    def check_health(self) -> AppiumServerHealth:
        """Query Appium 2 /status endpoint."""
        start_time = time.monotonic()
        target_url = f"{self.server_url}/status"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(target_url)
                latency = (time.monotonic() - start_time) * 1000.0

                if res.status_code == 200:
                    data = res.json().get("value", {})
                    ready = bool(data.get("ready", True))
                    version = data.get("build", {}).get("version")
                    msg = data.get("message", "Server ready")
                    return AppiumServerHealth(
                        url=self.server_url,
                        state=ServerHealthState.ONLINE if ready else ServerHealthState.DEGRADED,
                        version=version,
                        ready=ready,
                        message=msg,
                        latency_ms=round(latency, 2),
                    )
                return AppiumServerHealth(
                    url=self.server_url,
                    state=ServerHealthState.DEGRADED,
                    ready=False,
                    message=f"HTTP {res.status_code}: {res.text}",
                    latency_ms=round(latency, 2),
                )
        except httpx.ConnectError:
            return AppiumServerHealth(
                url=self.server_url,
                state=ServerHealthState.OFFLINE,
                ready=False,
                message="Cannot connect to Appium server",
            )
        except Exception as e:
            return AppiumServerHealth(
                url=self.server_url,
                state=ServerHealthState.OFFLINE,
                ready=False,
                message=str(e),
            )

    def is_uiautomator2_installed(self) -> bool:
        """Check whether uiautomator2 driver is installed via `appium driver list`."""
        try:
            res = subprocess.run(
                ["appium", "driver", "list", "--json"],
                capture_output=True,
                text=True,
                check=False,
                shell=True,
            )
            if res.returncode != 0:
                return False
            data = json.loads(res.stdout)
            return "uiautomator2" in data and bool(data["uiautomator2"].get("installed"))
        except Exception:
            return False

    def start_local_server(
        self,
        port: int = 4723,
        host: str = "127.0.0.1",
        base_path: str = "",
        wait_timeout_seconds: float = 15.0,
    ) -> bool:
        """Launch local appium process if not already running."""
        health = self.check_health()
        if health.state == ServerHealthState.ONLINE:
            logger.info("Appium server already online at %s", self.server_url)
            return True

        cmd = ["appium", "--port", str(port), "--address", host]
        if base_path:
            cmd.extend(["--base-path", base_path])

        logger.info("Launching Appium server: %s", " ".join(cmd))
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True,
            )
        except Exception as e:
            logger.error("Failed to start Appium server process: %s", e)
            return False

        end_time = time.monotonic() + wait_timeout_seconds
        while time.monotonic() < end_time:
            time.sleep(1.0)
            if self.check_health().state == ServerHealthState.ONLINE:
                logger.info("Appium server started successfully.")
                return True

        logger.warning("Appium server did not become healthy within %ss", wait_timeout_seconds)
        return False

    def stop_local_server(self) -> None:
        """Terminate local appium process if running."""
        if self._process:
            logger.info("Stopping Appium server process pid=%s", self._process.pid)
            try:
                self._process.terminate()
                self._process.wait(timeout=5.0)
            except Exception as e:
                logger.warning("Error stopping Appium server: %s", e)
                with contextlib.suppress(Exception):
                    self._process.kill()
            self._process = None
