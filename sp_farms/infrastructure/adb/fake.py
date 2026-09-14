from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sp_farms.application.adb import (
    AdbCommandError,
    AdbCommandResult,
    AdbDeviceNotFoundError,
    AdbOfflineError,
    AdbPort,
    AdbTimeoutError,
    AdbUnauthorizedError,
)
from sp_farms.domain.devices import DeviceInfo, DeviceState


@dataclass
class SimulatedDevice:
    serial: str
    state: DeviceState = DeviceState.ONLINE
    model: str = "Pixel 6"
    android_version: str = "13"
    sdk_version: int = 33
    resolution: tuple[int, int] = (1080, 2400)
    properties: dict[str, str] = field(default_factory=dict)
    timeout_on_commands: bool = False
    fail_on_commands: bool = False


class FakeAdbAdapter(AdbPort):
    def __init__(self) -> None:
        self._devices: dict[str, SimulatedDevice] = {}
        self.command_history: list[tuple[Sequence[str], str | None]] = []

    def add_device(self, device: SimulatedDevice) -> None:
        self._devices[device.serial] = device

    def remove_device(self, serial: str) -> None:
        self._devices.pop(serial, None)

    def set_state(self, serial: str, state: DeviceState) -> None:
        if serial in self._devices:
            self._devices[serial].state = state

    def list_devices(self) -> Sequence[DeviceInfo]:
        results: list[DeviceInfo] = []
        for dev in self._devices.values():
            results.append(
                DeviceInfo(
                    serial=dev.serial,
                    state=dev.state,
                    model=dev.model,
                    android_version=dev.android_version,
                    sdk_version=dev.sdk_version,
                    resolution=dev.resolution,
                    last_heartbeat=datetime.now(UTC),
                )
            )
        return tuple(results)

    def run_command(
        self,
        args: Sequence[str],
        serial: str | None = None,
        timeout: float = 30.0,
    ) -> AdbCommandResult:
        self.command_history.append((args, serial))

        if serial is not None:
            dev = self._devices.get(serial)
            if dev is None:
                raise AdbDeviceNotFoundError(f"Device '{serial}' not found")
            if dev.timeout_on_commands:
                raise AdbTimeoutError(f"Command timed out on device '{serial}' after {timeout}s")
            if dev.state is DeviceState.UNAUTHORIZED:
                raise AdbUnauthorizedError(f"Device '{serial}' is unauthorized")
            if dev.state is DeviceState.OFFLINE:
                raise AdbOfflineError(f"Device '{serial}' is offline")
            if dev.fail_on_commands:
                raise AdbCommandError("Simulated execution failure", returncode=1, stderr="error")

        if args and args[0] == "devices":
            output_lines = ["List of devices attached"]
            for d in self._devices.values():
                model_str = d.model.replace(" ", "_")
                output_lines.append(f"{d.serial}\t{d.state.value} model:{model_str}")
            return AdbCommandResult(stdout="\n".join(output_lines) + "\n", stderr="", returncode=0)

        if args and args[0] == "logcat":
            return AdbCommandResult(
                stdout=f"[Logcat output for {serial}]\n", stderr="", returncode=0
            )

        return AdbCommandResult(stdout="OK\n", stderr="", returncode=0)

    def shell(
        self,
        serial: str,
        command: str,
        timeout: float = 30.0,
    ) -> str:
        dev = self._devices.get(serial)
        if dev is None:
            raise AdbDeviceNotFoundError(f"Device '{serial}' not found")
        if dev.timeout_on_commands:
            raise AdbTimeoutError(f"Shell timed out on device '{serial}' after {timeout}s")
        if dev.state is DeviceState.UNAUTHORIZED:
            raise AdbUnauthorizedError(f"Device '{serial}' is unauthorized")
        if dev.state is DeviceState.OFFLINE:
            raise AdbOfflineError(f"Device '{serial}' is offline")
        if dev.fail_on_commands:
            raise AdbCommandError("Simulated shell failure", returncode=1, stderr="error")

        if command.startswith("getprop "):
            prop = command.split(" ", 1)[1].strip()
            if prop == "ro.product.model":
                return dev.model + "\n"
            if prop == "ro.build.version.release":
                return dev.android_version + "\n"
            if prop == "ro.build.version.sdk":
                return str(dev.sdk_version) + "\n"
            return dev.properties.get(prop, "") + "\n"

        if command.strip() == "wm size":
            return f"Physical size: {dev.resolution[0]}x{dev.resolution[1]}\n"

        if command.strip() == "dumpsys battery":
            return (
                "Current Battery Service state:\n"
                "  AC powered: false\n"
                "  USB powered: true\n"
                "  level: 90\n"
            )

        if command.strip() == "echo 1":
            return "1\n"

        return ""

    def get_device_info(self, serial: str) -> DeviceInfo:
        dev = self._devices.get(serial)
        if dev is None:
            raise AdbDeviceNotFoundError(f"Device '{serial}' not found")
        return DeviceInfo(
            serial=dev.serial,
            state=dev.state,
            model=dev.model,
            android_version=dev.android_version,
            sdk_version=dev.sdk_version,
            resolution=dev.resolution,
            last_heartbeat=datetime.now(UTC),
        )

    def heartbeat(self, serial: str) -> bool:
        dev = self._devices.get(serial)
        return not (dev is None or dev.state is not DeviceState.ONLINE or dev.timeout_on_commands)
