from collections.abc import Callable, Sequence
from pathlib import Path
from re import sub
from uuid import uuid4

from sp_farms.application.device_profiles import DeviceProfileRepository
from sp_farms.application.providers import DeviceProviderPort, ProviderError
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.device_management import DeviceProfile, ManagedDevice
from sp_farms.domain.devices import DeviceState
from sp_farms.domain.providers import DeviceProviderType


class DeviceService:
    def __init__(
        self,
        providers: Sequence[DeviceProviderPort],
        unit_of_work: Callable[[], UnitOfWork] | None = None,
        repository_factory: Callable[[UnitOfWork], DeviceProfileRepository] | None = None,
        artifact_directory: Path | None = None,
    ) -> None:
        self._providers = {provider.provider_type: provider for provider in providers}
        self._unit_of_work = unit_of_work
        self._repository_factory = repository_factory
        self._artifact_directory = artifact_directory

    def discover(self) -> tuple[ManagedDevice, ...]:
        profiles = self._profiles()
        devices: list[ManagedDevice] = []
        for provider in self._providers.values():
            try:
                if not provider.is_available():
                    continue
                instances = provider.list_instances()
            except (ProviderError, OSError):
                continue
            for instance in instances:
                external_id = instance.adb_serial
                profile = profiles.get((provider.provider_type, external_id))
                devices.append(
                    ManagedDevice(
                        provider=provider.provider_type,
                        external_id=external_id,
                        selector=(
                            external_id
                            if provider.provider_type is DeviceProviderType.PHYSICAL
                            else instance.index
                        ),
                        name=instance.name,
                        adb_serial=instance.adb_serial,
                        state=(
                            instance.state
                            or (DeviceState.ONLINE if instance.is_running else DeviceState.OFFLINE)
                        ),
                        capabilities=provider.capabilities,
                        alias=profile.alias if profile else "",
                        notes=profile.notes if profile else "",
                        android_version=instance.android_version,
                        network_state=instance.network_state,
                        resolution=instance.resolution,
                        last_heartbeat=instance.last_heartbeat,
                    )
                )
        return tuple(devices)

    def start(self, devices: Sequence[ManagedDevice]) -> None:
        for device in devices:
            self._provider(device).start_instance(device.selector)

    def stop(self, devices: Sequence[ManagedDevice]) -> None:
        for device in devices:
            self._provider(device).stop_instance(device.selector)

    def restart(self, devices: Sequence[ManagedDevice]) -> None:
        for device in devices:
            self._provider(device).restart_instance(device.selector)

    def launch_app(self, devices: Sequence[ManagedDevice], package_name: str) -> None:
        package_name = package_name.strip()
        if not package_name:
            raise ValueError("Package name is required")
        for device in devices:
            self._provider(device).launch_app(device.selector, package_name)

    def take_screenshot(self, device: ManagedDevice) -> Path:
        directory = self._artifacts("screenshots")
        identity = self._safe_id(device.external_id)
        filename = f"{device.provider.value}-{identity}-{uuid4().hex[:8]}.png"
        return self._provider(device).take_screenshot(device.selector, directory / filename)

    def collect_logs(self, device: ManagedDevice, lines: int = 200) -> Path:
        directory = self._artifacts("logs")
        identity = self._safe_id(device.external_id)
        filename = f"{device.provider.value}-{identity}-{uuid4().hex[:8]}.log"
        destination = directory / filename
        destination.write_text(
            self._provider(device).collect_logs(device.selector, lines),
            encoding="utf-8",
        )
        return destination

    def save_profile(self, device: ManagedDevice, alias: str, notes: str) -> None:
        if self._unit_of_work is None or self._repository_factory is None:
            raise RuntimeError("Device profile persistence is unavailable")
        profile = DeviceProfile(
            provider=device.provider,
            external_id=device.external_id,
            alias=alias.strip(),
            notes=notes.strip(),
        )
        with self._unit_of_work() as unit:
            self._repository_factory(unit).save(profile)
            unit.commit()

    def _profiles(self) -> dict[tuple[DeviceProviderType, str], DeviceProfile]:
        if self._unit_of_work is None or self._repository_factory is None:
            return {}
        with self._unit_of_work() as unit:
            profiles = self._repository_factory(unit).list_all()
        return {(profile.provider, profile.external_id): profile for profile in profiles}

    def _artifacts(self, kind: str) -> Path:
        if self._artifact_directory is None:
            raise RuntimeError("Device artifact storage is unavailable")
        directory = self._artifact_directory / kind
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @staticmethod
    def _safe_id(value: str) -> str:
        return sub(r"[^A-Za-z0-9_.-]+", "_", value)

    def _provider(self, device: ManagedDevice) -> DeviceProviderPort:
        return self._providers[device.provider]
