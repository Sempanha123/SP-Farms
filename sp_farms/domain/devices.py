from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class DeviceState(StrEnum):
    ONLINE = "device"
    OFFLINE = "offline"
    UNAUTHORIZED = "unauthorized"
    BOOTLOADER = "bootloader"
    AUTHORIZING = "authorizing"
    CONNECTING = "connecting"
    UNKNOWN = "unknown"

    @classmethod
    def from_adb_status(cls, status: str) -> "DeviceState":
        raw = status.strip().lower()
        for state in cls:
            if state.value == raw:
                return state
        return cls.UNKNOWN


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    serial: str
    state: DeviceState
    model: str | None = None
    android_version: str | None = None
    sdk_version: int | None = None
    resolution: tuple[int, int] | None = None
    last_heartbeat: datetime | None = None

    @property
    def is_ready(self) -> bool:
        return self.state is DeviceState.ONLINE

    @property
    def display_name(self) -> str:
        if self.model:
            return f"{self.model} ({self.serial})"
        return self.serial

    @property
    def resolution_str(self) -> str:
        if self.resolution:
            return f"{self.resolution[0]}x{self.resolution[1]}"
        return "Unknown"
