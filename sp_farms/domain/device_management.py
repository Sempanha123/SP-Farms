from dataclasses import dataclass
from datetime import datetime

from sp_farms.domain.devices import DeviceState
from sp_farms.domain.providers import DeviceProviderType, ProviderCapabilities


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    provider: DeviceProviderType
    external_id: str
    alias: str = ""
    notes: str = ""


@dataclass(frozen=True, slots=True)
class ManagedDevice:
    provider: DeviceProviderType
    external_id: str
    selector: int | str
    name: str
    adb_serial: str
    state: DeviceState
    capabilities: ProviderCapabilities
    alias: str = ""
    notes: str = ""
    android_version: str | None = None
    assigned_account: str | None = None
    app_version: str | None = None
    cpu_usage: float | None = None
    ram_usage_mb: int | None = None
    network_state: str | None = None
    resolution: tuple[int, int] | None = None
    last_heartbeat: datetime | None = None

    @property
    def display_name(self) -> str:
        return self.alias or self.name

    @property
    def is_online(self) -> bool:
        return self.state is DeviceState.ONLINE
