from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from sp_farms.domain.accounts import PreferredApp
from sp_farms.domain.devices import DeviceState
from sp_farms.domain.providers import DeviceProviderType, ProviderCapabilities


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    provider: DeviceProviderType
    external_id: str
    id: str = field(default_factory=lambda: str(uuid4()))
    friendly_name: str = ""
    emulator_instance: str = ""
    adb_serial: str = ""
    android_version: str = ""
    model: str = ""
    resolution: str = ""
    dpi: int | None = None
    language: str = ""
    locale: str = ""
    timezone: str = "UTC"
    keyboard_config: str = ""
    app_versions: dict[str, str] = field(default_factory=dict)
    preferred_app: PreferredApp = PreferredApp.BROWSER
    network_profile_ref: str | None = None
    last_heartbeat: datetime | None = None
    alias: str = ""
    notes: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def display_name(self) -> str:
        return self.friendly_name or self.alias or f"{self.provider.value}:{self.external_id}"


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
