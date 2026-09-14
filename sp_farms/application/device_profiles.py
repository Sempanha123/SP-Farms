from collections.abc import Sequence
from typing import Protocol

from sp_farms.domain.device_management import DeviceProfile
from sp_farms.domain.providers import DeviceProviderType


class DeviceProfileRepository(Protocol):
    def get(self, provider: DeviceProviderType, external_id: str) -> DeviceProfile | None: ...

    def list_all(self) -> Sequence[DeviceProfile]: ...

    def save(self, profile: DeviceProfile) -> None: ...
