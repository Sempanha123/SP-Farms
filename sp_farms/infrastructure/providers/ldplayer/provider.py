import logging
import subprocess
from collections.abc import Sequence
from pathlib import Path

from sp_farms.application.adb import (
    AdbCommandError,
    AdbDeviceNotFoundError,
    AdbOfflineError,
    AdbPort,
    AdbTimeoutError,
    AdbUnauthorizedError,
)
from sp_farms.application.providers import (
    DeviceProviderPort,
    ProviderError,
    ProviderExecutableNotFoundError,
    ProviderInstanceNotFoundError,
    ProviderOperationTimeoutError,
)
from sp_farms.domain.devices import DeviceInfo, DeviceState
from sp_farms.domain.providers import DeviceProviderType, EmulatorInstance, ProviderCapabilities
from sp_farms.infrastructure.providers.ldplayer.locator import find_ldplayer_executable
from sp_farms.infrastructure.providers.ldplayer.parser import (
    map_ldplayer_serial,
    parse_ldplayer_list,
)

logger = logging.getLogger(__name__)


class LdPlayerProvider(DeviceProviderPort):
    def __init__(
        self,
        executable_path: Path | str | None = None,
        adb_port: AdbPort | None = None,
    ) -> None:
        self._custom_path = Path(executable_path) if executable_path else None
        self._adb_port = adb_port

    @property
    def provider_type(self) -> DeviceProviderType:
        return DeviceProviderType.LDPLAYER

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_type=DeviceProviderType.LDPLAYER,
            can_start_stop=True,
            can_restart=True,
            can_take_screenshot=True,
            can_launch_apps=True,
            can_collect_logs=True,
            can_create_instances=True,
            can_clone_instances=True,
        )

    def resolve_executable(self) -> Path:
        exe = find_ldplayer_executable(self._custom_path)
        if exe is None or not exe.is_file():
            raise ProviderExecutableNotFoundError(
                "LDPlayer executable (ldconsole.exe / dnconsole.exe) was not found. "
                "Please verify LDPlayer is installed or specify the path in settings."
            )
        return exe

    def is_available(self) -> bool:
        try:
            self.resolve_executable()
            return True
        except ProviderExecutableNotFoundError:
            return False

    def _run_console_command(
        self,
        args: Sequence[str],
        timeout: float = 30.0,
    ) -> str:
        exe = self.resolve_executable()
        cmd = [str(exe), *args]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if result.returncode != 0:
                err_msg = (result.stderr or result.stdout or "").strip()
                cmd_name = " ".join(args)
                raise ProviderError(
                    f"LDPlayer command '{cmd_name}' failed with code {result.returncode}: {err_msg}"
                )
            return result.stdout
        except subprocess.TimeoutExpired as exc:
            raise ProviderOperationTimeoutError(
                f"LDPlayer command '{' '.join(args)}' timed out after {timeout}s"
            ) from exc
        except FileNotFoundError as exc:
            raise ProviderExecutableNotFoundError(
                f"LDPlayer executable not found at {exe}"
            ) from exc

    def list_instances(self) -> Sequence[EmulatorInstance]:
        exe = self.resolve_executable()
        output = self._run_console_command(["list2"], timeout=15.0)
        return parse_ldplayer_list(output, install_path=exe.parent)

    def _resolve_index(self, index_or_name: int | str) -> int:
        if isinstance(index_or_name, int):
            return index_or_name
        if index_or_name.isdigit():
            return int(index_or_name)

        # Look up by name
        instances = self.list_instances()
        for inst in instances:
            if inst.name == index_or_name:
                return inst.index

        raise ProviderInstanceNotFoundError(
            f"LDPlayer instance '{index_or_name}' not found. Please check existing instances."
        )

    def start_instance(self, index_or_name: int | str, timeout: float = 60.0) -> None:
        index = self._resolve_index(index_or_name)
        self._run_console_command(["launch", "--index", str(index)], timeout=timeout)

    def stop_instance(self, index_or_name: int | str, timeout: float = 30.0) -> None:
        index = self._resolve_index(index_or_name)
        self._run_console_command(["quit", "--index", str(index)], timeout=timeout)

    def restart_instance(self, index_or_name: int | str, timeout: float = 60.0) -> None:
        index = self._resolve_index(index_or_name)
        self._run_console_command(["reboot", "--index", str(index)], timeout=timeout)

    def get_adb_serial(self, index: int) -> str:
        return map_ldplayer_serial(index)

    def launch_app(self, index_or_name: int | str, package_name: str) -> None:
        index = self._resolve_index(index_or_name)
        self._run_console_command(
            ["runapp", "--index", str(index), "--packagename", package_name],
            timeout=15.0,
        )

    def take_screenshot(self, index_or_name: int | str, destination: Path) -> Path:
        index = self._resolve_index(index_or_name)
        serial = self.get_adb_serial(index)

        destination.parent.mkdir(parents=True, exist_ok=True)
        if self._adb_port is not None:
            res = self._adb_port.run_command(
                ["exec-out", "screencap", "-p"],
                serial=serial,
                timeout=15.0,
            )
            destination.write_bytes(res.stdout.encode("latin1"))
            return destination

        # Fallback via ldconsole adb command if adb_port is not provided
        self._run_console_command(
            ["adb", "--index", str(index), "--command", "shell screencap -p /sdcard/sp_snap.png"],
            timeout=15.0,
        )
        self._run_console_command(
            ["adb", "--index", str(index), "--command", f"pull /sdcard/sp_snap.png {destination}"],
            timeout=15.0,
        )
        return destination

    def collect_logs(self, index_or_name: int | str, lines: int = 100) -> str:
        index = self._resolve_index(index_or_name)
        serial = self.get_adb_serial(index)
        if self._adb_port is not None:
            try:
                res = self._adb_port.run_command(
                    ["logcat", "-d", "-t", str(lines)],
                    serial=serial,
                    timeout=15.0,
                )
                return res.stdout
            except (
                AdbCommandError,
                AdbTimeoutError,
                AdbOfflineError,
                AdbUnauthorizedError,
                AdbDeviceNotFoundError,
            ) as exc:
                logger.warning(
                    "Failed to collect logcat via ADB for %s: %s",
                    serial,
                    exc,
                )
                return f"[Error collecting logs: {exc}]"

        return self._run_console_command(
            ["adb", "--index", str(index), "--command", f"logcat -d -t {lines}"],
            timeout=15.0,
        )

    def health_check(self, index_or_name: int | str) -> DeviceInfo | None:
        index = self._resolve_index(index_or_name)
        serial = self.get_adb_serial(index)
        if self._adb_port is not None:
            try:
                return self._adb_port.get_device_info(serial)
            except (AdbOfflineError, AdbDeviceNotFoundError):
                return DeviceInfo(serial=serial, state=DeviceState.OFFLINE)
            except AdbUnauthorizedError:
                return DeviceInfo(serial=serial, state=DeviceState.UNAUTHORIZED)
            except Exception as exc:
                logger.warning("Health check for %s failed: %s", serial, exc)
                return DeviceInfo(serial=serial, state=DeviceState.UNKNOWN)

        # If no ADB port, check if instance is running in list2
        instances = self.list_instances()
        for inst in instances:
            if inst.index == index:
                state = DeviceState.ONLINE if inst.is_running else DeviceState.OFFLINE
                return DeviceInfo(
                    serial=serial,
                    state=state,
                    model=inst.name,
                    resolution=inst.resolution,
                )
        return None
