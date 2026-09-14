import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from sp_farms.application.adb import (
    AdbCommandError,
    AdbCommandResult,
    AdbDeviceNotFoundError,
    AdbExecutableNotFoundError,
    AdbOfflineError,
    AdbPort,
    AdbTimeoutError,
    AdbUnauthorizedError,
)
from sp_farms.domain.devices import DeviceInfo, DeviceState
from sp_farms.infrastructure.adb.locator import find_adb_executable
from sp_farms.infrastructure.adb.parser import (
    parse_android_version,
    parse_devices_output,
    parse_resolution,
    parse_sdk_version,
)


class SubprocessAdbClient(AdbPort):
    def __init__(self, adb_path: Path | None = None) -> None:
        resolved = adb_path or find_adb_executable()
        self._adb_path = resolved

    @property
    def adb_path(self) -> Path | None:
        return self._adb_path

    def _ensure_executable(self) -> Path:
        if self._adb_path is None or not self._adb_path.exists():
            cand = find_adb_executable()
            if cand is None:
                raise AdbExecutableNotFoundError("ADB executable not found")
            self._adb_path = cand
        return self._adb_path

    def run_command(
        self,
        args: Sequence[str],
        serial: str | None = None,
        timeout: float = 30.0,
    ) -> AdbCommandResult:
        exe = self._ensure_executable()
        cmd: list[str] = [str(exe)]
        if serial:
            cmd.extend(["-s", serial])
        cmd.extend(args)

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            cmd_str = " ".join(cmd)
            raise AdbTimeoutError(f"ADB command timed out after {timeout}s: {cmd_str}") from exc
        except FileNotFoundError as exc:
            raise AdbExecutableNotFoundError(f"ADB executable not found at {exe}") from exc

        err = res.stderr.strip()
        low_err = err.lower()
        if "device unauthorized" in low_err or "unauthorized" in low_err:
            raise AdbUnauthorizedError(f"Device {serial or ''} unauthorized: {err}")
        if "device offline" in low_err:
            raise AdbOfflineError(f"Device {serial or ''} offline: {err}")
        if "device not found" in low_err or "device '" in low_err:
            raise AdbDeviceNotFoundError(f"Device {serial or ''} not found: {err}")

        if res.returncode != 0:
            raise AdbCommandError(
                f"ADB command failed ({res.returncode}): {err or res.stdout.strip()}",
                returncode=res.returncode,
                stderr=res.stderr,
            )

        return AdbCommandResult(
            stdout=res.stdout,
            stderr=res.stderr,
            returncode=res.returncode,
        )

    def shell(
        self,
        serial: str,
        command: str,
        timeout: float = 30.0,
    ) -> str:
        res = self.run_command(["shell", command], serial=serial, timeout=timeout)
        return res.stdout

    def list_devices(self) -> Sequence[DeviceInfo]:
        res = self.run_command(["devices", "-l"], timeout=10.0)
        return tuple(parse_devices_output(res.stdout))

    def get_device_info(self, serial: str) -> DeviceInfo:
        devices = self.list_devices()
        current_dev = next((d for d in devices if d.serial == serial), None)
        if current_dev is None:
            raise AdbDeviceNotFoundError(f"Device '{serial}' not found")

        if current_dev.state is not DeviceState.ONLINE:
            return current_dev

        try:
            model_raw = self.shell(serial, "getprop ro.product.model", timeout=5.0).strip()
            model = model_raw if model_raw else current_dev.model
        except Exception:
            model = current_dev.model

        try:
            version_out = self.shell(serial, "getprop ro.build.version.release", timeout=5.0)
            version = parse_android_version(version_out)
        except Exception:
            version = None

        try:
            sdk_out = self.shell(serial, "getprop ro.build.version.sdk", timeout=5.0)
            sdk = parse_sdk_version(sdk_out)
        except Exception:
            sdk = None

        try:
            size_out = self.shell(serial, "wm size", timeout=5.0)
            resolution = parse_resolution(size_out)
        except Exception:
            resolution = None

        return DeviceInfo(
            serial=serial,
            state=current_dev.state,
            model=model,
            android_version=version,
            sdk_version=sdk,
            resolution=resolution,
            last_heartbeat=datetime.now(UTC),
        )

    def heartbeat(self, serial: str) -> bool:
        try:
            out = self.shell(serial, "echo 1", timeout=3.0)
            return out.strip() == "1"
        except Exception:
            return False
