from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class DeviceProviderType(StrEnum):
    LDPLAYER = "ldplayer"
    MUMU = "mumu"
    PHYSICAL = "physical"
    GENERIC_ADB = "generic_adb"


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    provider_type: DeviceProviderType
    can_start_stop: bool = True
    can_restart: bool = True
    can_take_screenshot: bool = True
    can_launch_apps: bool = True
    can_collect_logs: bool = True
    can_create_instances: bool = False
    can_clone_instances: bool = False


@dataclass(frozen=True, slots=True)
class EmulatorInstance:
    index: int
    name: str
    adb_serial: str
    is_running: bool
    pid: int | None = None
    vbox_pid: int | None = None
    resolution: tuple[int, int] | None = None
    dpi: int | None = None
    install_path: Path | None = None

    @property
    def display_name(self) -> str:
        return f"{self.name} [#{self.index}]"

    @property
    def resolution_str(self) -> str:
        if self.resolution:
            return f"{self.resolution[0]}x{self.resolution[1]}"
        return "Unknown"
