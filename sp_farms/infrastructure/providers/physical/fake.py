from collections.abc import Sequence
from pathlib import Path

from sp_farms.application.providers import (
    DeviceProviderPort,
    ProviderInstanceNotFoundError,
)
from sp_farms.domain.devices import DeviceInfo, DeviceState
from sp_farms.domain.providers import (
    ConnectionTransport,
    DeviceProviderType,
    EmulatorInstance,
    PhysicalDeviceMetadata,
    ProviderCapabilities,
    TroubleshootingGuidance,
)
from sp_farms.infrastructure.providers.troubleshooting import get_default_troubleshooting_guidance

_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f"
    b"\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class FakePhysicalProvider(DeviceProviderPort):
    def __init__(self) -> None:
        self._devices: dict[str, PhysicalDeviceMetadata] = {}
        self._states: dict[str, DeviceState] = {}
        self._installed_apks: list[tuple[str, Path]] = []
        self._launched_apps: list[tuple[str, str]] = []

        # Default fixtures: one USB Galaxy S22, one Wi-Fi Pixel 7 Pro
        self.add_device(
            PhysicalDeviceMetadata(
                serial="RFCT123456X",
                transport=ConnectionTransport.USB,
                manufacturer="Samsung",
                brand="Samsung",
                model="Galaxy S22",
                android_version="13",
                sdk_version=33,
                battery_level=88,
                battery_charging=True,
                resolution=(1080, 2340),
            ),
            state=DeviceState.ONLINE,
        )
        self.add_device(
            PhysicalDeviceMetadata(
                serial="192.168.1.150:5555",
                transport=ConnectionTransport.WIFI,
                manufacturer="Google",
                brand="Google",
                model="Pixel 7 Pro",
                android_version="14",
                sdk_version=34,
                battery_level=42,
                battery_charging=False,
                resolution=(1440, 3120),
            ),
            state=DeviceState.ONLINE,
        )

    @property
    def provider_type(self) -> DeviceProviderType:
        return DeviceProviderType.PHYSICAL

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_type=DeviceProviderType.PHYSICAL,
            can_start_stop=False,
            can_restart=True,
            can_take_screenshot=True,
            can_launch_apps=True,
            can_collect_logs=True,
            can_create_instances=False,
            can_clone_instances=False,
            can_install_apk=True,
        )

    def is_available(self) -> bool:
        return True

    def add_device(
        self,
        metadata: PhysicalDeviceMetadata,
        state: DeviceState = DeviceState.ONLINE,
    ) -> None:
        self._devices[metadata.serial] = metadata
        self._states[metadata.serial] = state

    def _resolve_serial(self, index_or_name: int | str) -> str:
        if isinstance(index_or_name, int):
            serials = list(self._devices.keys())
            if 0 <= index_or_name < len(serials):
                return serials[index_or_name]
            raise ProviderInstanceNotFoundError(f"Device index {index_or_name} not found")

        # Serial match
        if index_or_name in self._devices:
            return index_or_name

        # Model or display match
        for meta in self._devices.values():
            if meta.model == index_or_name:
                return meta.serial

        raise ProviderInstanceNotFoundError(f"Device '{index_or_name}' not found")

    def list_instances(self) -> Sequence[EmulatorInstance]:
        instances: list[EmulatorInstance] = []
        for idx, (serial, meta) in enumerate(self._devices.items()):
            state = self._states.get(serial, DeviceState.UNKNOWN)
            is_running = state is DeviceState.ONLINE
            instances.append(
                EmulatorInstance(
                    index=idx,
                    name=meta.model or serial,
                    adb_serial=serial,
                    is_running=is_running,
                    resolution=meta.resolution,
                )
            )
        return instances

    def start_instance(self, index_or_name: int | str, timeout: float = 60.0) -> None:
        raise RuntimeError("Physical devices cannot be started remotely via PC software")

    def stop_instance(self, index_or_name: int | str, timeout: float = 30.0) -> None:
        raise RuntimeError("Physical devices cannot be powered off remotely via PC software")

    def restart_instance(self, index_or_name: int | str, timeout: float = 60.0) -> None:
        serial = self._resolve_serial(index_or_name)
        if self._states.get(serial) is not DeviceState.ONLINE:
            raise RuntimeError(f"Cannot restart device {serial}: not online")

    def get_adb_serial(self, index: int) -> str:
        serials = list(self._devices.keys())
        if 0 <= index < len(serials):
            return serials[index]
        return f"unknown-physical-{index}"

    def launch_app(self, index_or_name: int | str, package_name: str) -> None:
        serial = self._resolve_serial(index_or_name)
        if self._states.get(serial) is not DeviceState.ONLINE:
            raise RuntimeError(f"Cannot launch app on {serial}: device not online")
        self._launched_apps.append((serial, package_name))

    def take_screenshot(self, index_or_name: int | str, destination: Path) -> Path:
        serial = self._resolve_serial(index_or_name)
        if self._states.get(serial) is not DeviceState.ONLINE:
            raise RuntimeError(f"Cannot take screenshot on {serial}: device not online")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_TINY_PNG)
        return destination

    def collect_logs(self, index_or_name: int | str, lines: int = 100) -> str:
        serial = self._resolve_serial(index_or_name)
        if self._states.get(serial) is not DeviceState.ONLINE:
            return ""
        return f"[PhysicalLogcat] Device {serial} - {lines} lines collected\n"

    def install_apk(self, index_or_name: int | str, apk_path: Path) -> None:
        serial = self._resolve_serial(index_or_name)
        if self._states.get(serial) is not DeviceState.ONLINE:
            raise RuntimeError(f"Cannot install APK on {serial}: device not online")
        if not apk_path.exists():
            raise FileNotFoundError(f"APK not found at {apk_path}")
        self._installed_apks.append((serial, apk_path))

    def health_check(self, index_or_name: int | str) -> DeviceInfo | None:
        serial = self._resolve_serial(index_or_name)
        meta = self._devices.get(serial)
        state = self._states.get(serial, DeviceState.UNKNOWN)
        return DeviceInfo(
            serial=serial,
            state=state,
            model=meta.model if meta else None,
            android_version=meta.android_version if meta else None,
            sdk_version=meta.sdk_version if meta else None,
            resolution=meta.resolution if meta else None,
        )

    def get_metadata(self, index_or_name: int | str) -> PhysicalDeviceMetadata:
        serial = self._resolve_serial(index_or_name)
        return self._devices[serial]

    def get_troubleshooting(self, index_or_name: int | str) -> TroubleshootingGuidance:
        serial = self._resolve_serial(index_or_name)
        state = self._states.get(serial, DeviceState.UNKNOWN)
        return get_default_troubleshooting_guidance(state)

    def diagnostics(self) -> dict[str, object]:
        usb_count = sum(1 for d in self._devices.values() if d.transport is ConnectionTransport.USB)
        wifi_count = sum(
            1 for d in self._devices.values() if d.transport is ConnectionTransport.WIFI
        )
        online_count = sum(1 for s in self._states.values() if s is DeviceState.ONLINE)
        return {
            "provider": self.provider_type.value,
            "devices_total": len(self._devices),
            "devices_online": online_count,
            "transport_usb": usb_count,
            "transport_wifi": wifi_count,
        }
