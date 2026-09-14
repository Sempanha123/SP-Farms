"""Domain entities and types for Appium 2 Android UI automation."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class AppiumSessionState(StrEnum):
    """Lifecycle state of an Appium UiAutomator2 session."""

    IDLE = "idle"
    CONNECTING = "connecting"
    ACTIVE = "active"
    BUSY = "busy"
    ERROR = "error"
    CLOSED = "closed"


class By(StrEnum):
    """Locator strategies supported by Appium UiAutomator2."""

    ID = "id"
    XPATH = "xpath"
    ACCESSIBILITY_ID = "accessibility id"
    CLASS_NAME = "class name"
    ANDROID_UIAUTOMATOR = "-android uiautomator"


class AppState(StrEnum):
    """Application running state on Android."""

    NOT_INSTALLED = "not_installed"
    NOT_RUNNING = "not_running"
    RUNNING_IN_BACKGROUND_SUSPENDED = "running_in_background_suspended"
    RUNNING_IN_BACKGROUND = "running_in_background"
    RUNNING_IN_FOREGROUND = "running_in_foreground"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ElementRef:
    """Reference to an element found in the Android UI hierarchy."""

    element_id: str
    by: By
    value: str
    bounds: tuple[int, int, int, int] | None = None  # (left, top, right, bottom)
    text: str = ""
    is_displayed: bool = True
    is_enabled: bool = True


@dataclass(frozen=True, slots=True)
class UiAutomator2Capabilities:
    """Typed capabilities for Appium 2 UiAutomator2 driver."""

    platform_name: str = "Android"
    automation_name: str = "UiAutomator2"
    device_name: str = "Android Device"
    udid: str = ""  # ADB serial
    app_package: str | None = None
    app_activity: str | None = None
    app_wait_activity: str | None = None
    app_wait_package: str | None = None
    no_reset: bool = True
    full_reset: bool = False
    new_command_timeout: int = 300
    auto_grant_permissions: bool = True
    system_port: int = 8200  # Unique port per device for UiAutomator2 server
    skip_unlock: bool = True
    skip_device_initialization: bool = False
    ignore_unimportant_views: bool = True
    disable_window_animation: bool = True
    extra_capabilities: Mapping[str, Any] = field(default_factory=dict)

    def to_w3c_payload(self) -> dict[str, Any]:
        """Generate W3C-compliant Appium 2 capability payload."""
        caps: dict[str, Any] = {
            "platformName": self.platform_name,
            "appium:automationName": self.automation_name,
            "appium:deviceName": self.device_name,
            "appium:udid": self.udid,
            "appium:noReset": self.no_reset,
            "appium:fullReset": self.full_reset,
            "appium:newCommandTimeout": self.new_command_timeout,
            "appium:autoGrantPermissions": self.auto_grant_permissions,
            "appium:systemPort": self.system_port,
            "appium:skipUnlock": self.skip_unlock,
            "appium:skipDeviceInitialization": self.skip_device_initialization,
            "appium:ignoreUnimportantViews": self.ignore_unimportant_views,
            "appium:disableWindowAnimation": self.disable_window_animation,
        }
        if self.app_package:
            caps["appium:appPackage"] = self.app_package
        if self.app_activity:
            caps["appium:appActivity"] = self.app_activity
        if self.app_wait_activity:
            caps["appium:appWaitActivity"] = self.app_wait_activity
        if self.app_wait_package:
            caps["appium:appWaitPackage"] = self.app_wait_package

        for k, v in self.extra_capabilities.items():
            if not k.startswith("appium:") and k != "platformName":
                caps[f"appium:{k}"] = v
            else:
                caps[k] = v

        return {"capabilities": {"alwaysMatch": caps}}


@dataclass(slots=True)
class AutomationDevice:
    """Device representation for automation binding."""

    device_id: str
    udid: str
    provider: str
    name: str = ""


@dataclass(slots=True)
class AppiumSessionInfo:
    """Runtime session state and metadata for an Appium session."""

    session_id: str
    device_id: str
    udid: str
    state: AppiumSessionState
    server_url: str
    system_port: int
    active_job_id: str | None = None
    capabilities: UiAutomator2Capabilities | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class AppiumSession:
    """Live Appium automation session bound to a specific device."""

    session_id: str
    device_key: str
    udid: str
    server_url: str
    system_port: int
    capabilities: UiAutomator2Capabilities
    state: AppiumSessionState = AppiumSessionState.ACTIVE
    current_package: str | None = None
    current_activity: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_heartbeat_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_error: str | None = None

    def refresh_heartbeat(self) -> None:
        self.last_heartbeat_at = datetime.now(UTC)


class AutomationError(Exception):
    """Base error for all Appium and UI automation failures."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class AppiumConnectionError(AutomationError):
    """Failed to reach or initialize Appium 2 server."""


class SessionNotCreatedError(AutomationError):
    """Appium server failed to create a new UiAutomator2 session."""


class ElementNotFoundError(AutomationError):
    """Element could not be found within the allotted wait time."""


class AutomationTimeoutError(AutomationError):
    """Automation action exceeded explicit timeout."""


class StaleElementReferenceError(AutomationError):
    """Referenced element is no longer attached to the UI hierarchy."""


class ScreenStateMismatchError(AutomationError):
    """Current activity or screen is not the expected target screen."""
