from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

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
    remote_files: dict[str, str] = field(default_factory=dict)
    qa_bridge_loaded: bool = False
    installed_packages: set[str] = field(
        default_factory=lambda: {
            "com.facebook.katana",
            "com.facebook.lite",
            "com.android.chrome",
            "com.android.browser",
        }
    )


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

        if args and args[0] == "push" and serial is not None:
            if len(args) != 3:
                raise AdbCommandError("Invalid push arguments", returncode=1)
            self._devices[serial].remote_files[str(args[2])] = Path(args[1]).read_text(
                encoding="utf-8"
            )
            return AdbCommandResult(stdout="1 file pushed\n", stderr="", returncode=0)

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

        if command.startswith("pm list packages"):
            parts = command.strip().split()
            filter_pkg = parts[3] if len(parts) >= 4 else ""
            matches = [pkg for pkg in dev.installed_packages if not filter_pkg or filter_pkg in pkg]
            return "".join(f"package:{pkg}\n" for pkg in sorted(matches))

        if command.startswith("setprop "):
            parts = command.split(" ", 2)
            if len(parts) == 3:
                dev.properties[parts[1]] = parts[2]
            return ""

        if command.startswith("mkdir -p ") or command.startswith("chmod 600 "):
            return ""

        if command.startswith("test -f ") and command.endswith(" && echo OK"):
            path = command.removeprefix("test -f ").removesuffix(" && echo OK")
            return "OK\n" if path in dev.remote_files else ""

        if command.startswith("am broadcast -a "):
            profile = dev.remote_files.get("/data/local/tmp/sp_farms_qa/profile.json")
            if profile is not None:
                from json import dumps, loads

                document = loads(profile)
                dev.qa_bridge_loaded = True
                dev.remote_files["/data/local/tmp/sp_farms_qa/status.json"] = dumps(
                    {
                        "bridge_version": 1,
                        "loaded": True,
                        "profile_id": document["profile"]["id"],
                        "target_package": document["target_package"],
                    }
                )
            return "Broadcast completed: result=0\n"

        if command.startswith("cat "):
            return dev.remote_files.get(command.removeprefix("cat "), "")

        if command.startswith("rm -f "):
            path = command.removeprefix("rm -f ")
            dev.remote_files.pop(path, None)
            dev.remote_files.pop("/data/local/tmp/sp_farms_qa/status.json", None)
            dev.qa_bridge_loaded = False
            return ""

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
