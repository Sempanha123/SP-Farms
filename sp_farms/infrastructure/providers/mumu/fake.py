from collections.abc import Sequence
from pathlib import Path

from sp_farms.application.providers import (
    DeviceProviderPort,
    ProviderExecutableNotFoundError,
    ProviderInstanceNotFoundError,
    ProviderOperationTimeoutError,
)
from sp_farms.domain.devices import DeviceInfo, DeviceState
from sp_farms.domain.providers import (
    DeviceProviderType,
    EmulatorInstance,
    ProviderCapabilities,
    TroubleshootingGuidance,
)
from sp_farms.infrastructure.providers.mumu.parser import map_mumu_serial
from sp_farms.infrastructure.providers.troubleshooting import get_default_troubleshooting_guidance

_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f"
    b"\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class FakeMuMuProvider(DeviceProviderPort):
    def __init__(
        self,
        is_installed: bool = True,
        fail_on_start: bool = False,
        timeout_on_start: bool = False,
    ) -> None:
        self._installed = is_installed
        self._fail_on_start = fail_on_start
        self._timeout_on_start = timeout_on_start
        self._instances: dict[int, EmulatorInstance] = {}
        self._launched_apps: list[tuple[int, str]] = []

        # Default fixtures
        self.add_instance(0, "MuMuPlayer-0", is_running=True, resolution=(1080, 1920), dpi=480)
        self.add_instance(1, "MuMuPlayer-1", is_running=False, resolution=(720, 1280), dpi=320)

    @property
    def provider_type(self) -> DeviceProviderType:
        return DeviceProviderType.MUMU

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_type=DeviceProviderType.MUMU,
            can_start_stop=True,
            can_restart=True,
            can_take_screenshot=True,
            can_launch_apps=True,
            can_collect_logs=True,
            can_create_instances=False,
            can_clone_instances=False,
        )

    def is_available(self) -> bool:
        return self._installed

    def add_instance(
        self,
        index: int,
        name: str,
        is_running: bool = False,
        resolution: tuple[int, int] | None = None,
        dpi: int | None = None,
    ) -> EmulatorInstance:
        instance = EmulatorInstance(
            index=index,
            name=name,
            adb_serial=map_mumu_serial(index),
            is_running=is_running,
            pid=5000 + index if is_running else None,
            resolution=resolution,
            dpi=dpi,
        )
        self._instances[index] = instance
        return instance

    def _resolve_index(self, index_or_name: int | str) -> int:
        if isinstance(index_or_name, int):
            if index_or_name in self._instances:
                return index_or_name
            raise ProviderInstanceNotFoundError(
                f"MuMu instance with index {index_or_name} not found"
            )

        if index_or_name.isdigit():
            idx = int(index_or_name)
            if idx in self._instances:
                return idx

        for inst in self._instances.values():
            if inst.name == index_or_name:
                return inst.index

        raise ProviderInstanceNotFoundError(f"MuMu instance with name '{index_or_name}' not found")

    def list_instances(self) -> Sequence[EmulatorInstance]:
        if not self._installed:
            raise ProviderExecutableNotFoundError("MuMu CLI not found")
        return list(self._instances.values())

    def start_instance(self, index_or_name: int | str, timeout: float = 60.0) -> None:
        if not self._installed:
            raise ProviderExecutableNotFoundError("MuMu CLI not found")
        if self._timeout_on_start:
            raise ProviderOperationTimeoutError("Timeout starting MuMu instance")
        if self._fail_on_start:
            raise RuntimeError("Synthetic failure starting MuMu instance")

        idx = self._resolve_index(index_or_name)
        current = self._instances[idx]
        self._instances[idx] = EmulatorInstance(
            index=current.index,
            name=current.name,
            adb_serial=current.adb_serial,
            is_running=True,
            pid=5000 + idx,
            resolution=current.resolution,
            dpi=current.dpi,
        )

    def stop_instance(self, index_or_name: int | str, timeout: float = 30.0) -> None:
        if not self._installed:
            raise ProviderExecutableNotFoundError("MuMu CLI not found")
        idx = self._resolve_index(index_or_name)
        current = self._instances[idx]
        self._instances[idx] = EmulatorInstance(
            index=current.index,
            name=current.name,
            adb_serial=current.adb_serial,
            is_running=False,
            pid=None,
            resolution=current.resolution,
            dpi=current.dpi,
        )

    def restart_instance(self, index_or_name: int | str, timeout: float = 60.0) -> None:
        self.stop_instance(index_or_name, timeout=timeout)
        self.start_instance(index_or_name, timeout=timeout)

    def get_adb_serial(self, index: int) -> str:
        return map_mumu_serial(index)

    def launch_app(self, index_or_name: int | str, package_name: str) -> None:
        idx = self._resolve_index(index_or_name)
        inst = self._instances[idx]
        if not inst.is_running:
            raise RuntimeError(f"Cannot launch app '{package_name}': MuMu instance is not running")
        self._launched_apps.append((idx, package_name))

    def take_screenshot(self, index_or_name: int | str, destination: Path) -> Path:
        idx = self._resolve_index(index_or_name)
        inst = self._instances[idx]
        if not inst.is_running:
            raise RuntimeError("Cannot take screenshot: MuMu instance is not running")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_TINY_PNG)
        return destination

    def collect_logs(self, index_or_name: int | str, lines: int = 100) -> str:
        idx = self._resolve_index(index_or_name)
        inst = self._instances[idx]
        if not inst.is_running:
            return ""
        return f"[MuMuLogcat] Instance {inst.name} ({inst.adb_serial}) - {lines} lines collected\n"

    def health_check(self, index_or_name: int | str) -> DeviceInfo | None:
        idx = self._resolve_index(index_or_name)
        inst = self._instances[idx]
        state = DeviceState.ONLINE if inst.is_running else DeviceState.OFFLINE
        return DeviceInfo(
            serial=inst.adb_serial,
            state=state,
            model=inst.name,
            resolution=inst.resolution,
        )

    def install_apk(self, index_or_name: int | str, apk_path: Path) -> None:
        idx = self._resolve_index(index_or_name)
        inst = self._instances[idx]
        if not inst.is_running:
            raise RuntimeError("Cannot install APK: MuMu instance is not running")
        if not apk_path.exists():
            raise FileNotFoundError(f"APK not found at {apk_path}")

    def get_troubleshooting(self, index_or_name: int | str) -> TroubleshootingGuidance:
        idx = self._resolve_index(index_or_name)
        inst = self._instances[idx]
        state = DeviceState.ONLINE if inst.is_running else DeviceState.OFFLINE
        return get_default_troubleshooting_guidance(state)

    def diagnostics(self) -> dict[str, object]:
        return {
            "provider": self.provider_type.value,
            "installed": self._installed,
            "instances_total": len(self._instances),
            "instances_running": sum(1 for i in self._instances.values() if i.is_running),
        }
