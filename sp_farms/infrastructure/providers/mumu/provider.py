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
from sp_farms.infrastructure.providers.mumu.locator import find_mumu_executable
from sp_farms.infrastructure.providers.mumu.parser import (
    map_mumu_serial,
    parse_mumu_instances,
)

logger = logging.getLogger(__name__)


class MuMuProvider(DeviceProviderPort):
    def __init__(
        self,
        executable_path: Path | str | None = None,
        adb_port: AdbPort | None = None,
    ) -> None:
        self._custom_path = Path(executable_path) if executable_path else None
        self._adb_port = adb_port

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

    def resolve_executable(self) -> Path:
        exe = find_mumu_executable(self._custom_path)
        if exe is None or not exe.is_file():
            raise ProviderExecutableNotFoundError(
                "MuMu executable (MuMuManager.exe) was not found. "
                "Please verify MuMu is installed or specify the path in settings."
            )
        return exe

    def is_available(self) -> bool:
        try:
            self.resolve_executable()
            return True
        except ProviderExecutableNotFoundError:
            return False

    def _run_manager_command(
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
                cmd_str = " ".join(args)
                raise ProviderError(
                    f"MuMu command '{cmd_str}' failed with code {result.returncode}: {err_msg}"
                )
            return result.stdout
        except subprocess.TimeoutExpired as exc:
            cmd_str = " ".join(args)
            raise ProviderOperationTimeoutError(
                f"MuMu command '{cmd_str}' timed out after {timeout}s"
            ) from exc
        except FileNotFoundError as exc:
            raise ProviderExecutableNotFoundError(f"MuMu executable not found at {exe}") from exc

    def list_instances(self) -> Sequence[EmulatorInstance]:
        exe = self.resolve_executable()
        try:
            # Try JSON api output
            output = self._run_manager_command(["api", "-v", "all"], timeout=15.0)
        except ProviderError:
            # Fallback to info -v all
            output = self._run_manager_command(["info", "-v", "all"], timeout=15.0)
        return parse_mumu_instances(output, install_path=exe.parent)

    def _resolve_index(self, index_or_name: int | str) -> int:
        if isinstance(index_or_name, int):
            return index_or_name
        if index_or_name.isdigit():
            return int(index_or_name)

        instances = self.list_instances()
        for inst in instances:
            if inst.name == index_or_name:
                return inst.index

        raise ProviderInstanceNotFoundError(
            f"MuMu instance '{index_or_name}' not found. Please check existing instances."
        )

    def start_instance(self, index_or_name: int | str, timeout: float = 60.0) -> None:
        index = self._resolve_index(index_or_name)
        self._run_manager_command(
            ["api", "-v", str(index), "launch_player"],
            timeout=timeout,
        )

    def stop_instance(self, index_or_name: int | str, timeout: float = 30.0) -> None:
        index = self._resolve_index(index_or_name)
        self._run_manager_command(
            ["api", "-v", str(index), "close_player"],
            timeout=timeout,
        )

    def restart_instance(self, index_or_name: int | str, timeout: float = 60.0) -> None:
        index = self._resolve_index(index_or_name)
        try:
            self._run_manager_command(
                ["api", "-v", str(index), "restart_player"],
                timeout=timeout,
            )
        except ProviderError:
            self.stop_instance(index, timeout=timeout / 2)
            self.start_instance(index, timeout=timeout / 2)

    def get_adb_serial(self, index: int) -> str:
        return map_mumu_serial(index)

    def launch_app(self, index_or_name: int | str, package_name: str) -> None:
        index = self._resolve_index(index_or_name)
        self._run_manager_command(
            ["api", "-v", str(index), "launch_app", "-pkg", package_name],
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

        raise ProviderError(
            "Screenshot requires an active ADB port connection to the MuMu instance"
        )

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
                logger.warning("Failed to collect logcat via ADB for %s: %s", serial, exc)
                return f"[Error collecting logs: {exc}]"

        return ""

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

    def diagnostics(self) -> dict[str, object]:
        try:
            exe = self.resolve_executable()
            available = True
            exe_str = str(exe)
        except ProviderExecutableNotFoundError:
            available = False
            exe_str = None

        running_count = 0
        total_count = 0
        if available:
            try:
                instances = self.list_instances()
                total_count = len(instances)
                running_count = sum(1 for i in instances if i.is_running)
            except Exception as exc:
                logger.warning("Failed to collect MuMu diagnostics: %s", exc)

        return {
            "provider": self.provider_type.value,
            "available": available,
            "executable": exe_str,
            "instances_total": total_count,
            "instances_running": running_count,
            "adb_connected": self._adb_port is not None,
        }
