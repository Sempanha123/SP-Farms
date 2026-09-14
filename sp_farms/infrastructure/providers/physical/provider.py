import logging
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
from sp_farms.infrastructure.providers.physical.parser import (
    classify_transport,
    parse_battery_status,
)
from sp_farms.infrastructure.providers.troubleshooting import get_default_troubleshooting_guidance

logger = logging.getLogger(__name__)


class PhysicalAndroidProvider(DeviceProviderPort):
    def __init__(self, adb_port: AdbPort) -> None:
        self._adb = adb_port

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

    def _is_physical(self, serial: str) -> bool:
        transport = classify_transport(serial)
        return transport in (ConnectionTransport.USB, ConnectionTransport.WIFI)

    def list_instances(self) -> Sequence[EmulatorInstance]:
        devices = self._adb.list_devices()
        instances: list[EmulatorInstance] = []
        idx = 0
        for dev in devices:
            if not self._is_physical(dev.serial):
                continue

            name = dev.model or dev.serial
            is_running = dev.state is DeviceState.ONLINE
            instances.append(
                EmulatorInstance(
                    index=idx,
                    name=name,
                    adb_serial=dev.serial,
                    is_running=is_running,
                    resolution=dev.resolution,
                )
            )
            idx += 1
        return instances

    def _resolve_serial(self, index_or_name: int | str) -> str:
        instances = self.list_instances()
        if isinstance(index_or_name, int):
            if 0 <= index_or_name < len(instances):
                return instances[index_or_name].adb_serial
            raise ProviderInstanceNotFoundError(f"Physical device index {index_or_name} not found")

        # Check by serial or name among physical devices
        for inst in instances:
            if inst.adb_serial == str(index_or_name) or inst.name == str(index_or_name):
                return inst.adb_serial

        raise ProviderInstanceNotFoundError(f"Physical device '{index_or_name}' not found")

    def start_instance(self, index_or_name: int | str, timeout: float = 60.0) -> None:
        raise RuntimeError("Physical Android devices cannot be powered on remotely via software")

    def stop_instance(self, index_or_name: int | str, timeout: float = 30.0) -> None:
        raise RuntimeError("Physical Android devices cannot be powered off remotely via software")

    def restart_instance(self, index_or_name: int | str, timeout: float = 60.0) -> None:
        serial = self._resolve_serial(index_or_name)
        try:
            self._adb.run_command(["reboot"], serial=serial, timeout=timeout)
        except Exception as exc:
            raise ProviderError(f"Failed to reboot device {serial}: {exc}") from exc

    def get_adb_serial(self, index: int) -> str:
        instances = self.list_instances()
        if 0 <= index < len(instances):
            return instances[index].adb_serial
        raise ProviderInstanceNotFoundError(f"Physical device index {index} not found")

    def launch_app(self, index_or_name: int | str, package_name: str) -> None:
        serial = self._resolve_serial(index_or_name)
        # Standard reliable launcher via monkey tool without needing exported activity name
        try:
            self._adb.run_command(
                [
                    "shell",
                    "monkey",
                    "-p",
                    package_name,
                    "-c",
                    "android.intent.category.LAUNCHER",
                    "1",
                ],
                serial=serial,
                timeout=15.0,
            )
        except Exception as exc:
            msg = f"Failed to launch app '{package_name}' on {serial}: {exc}"
            raise ProviderError(msg) from exc

    def take_screenshot(self, index_or_name: int | str, destination: Path) -> Path:
        serial = self._resolve_serial(index_or_name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            res = self._adb.run_command(
                ["exec-out", "screencap", "-p"],
                serial=serial,
                timeout=15.0,
            )
            destination.write_bytes(res.stdout.encode("latin1"))
            return destination
        except Exception as exc:
            raise ProviderError(f"Failed to take screenshot on {serial}: {exc}") from exc

    def collect_logs(self, index_or_name: int | str, lines: int = 100) -> str:
        serial = self._resolve_serial(index_or_name)
        try:
            res = self._adb.run_command(
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
            logger.warning("Failed to collect logcat for %s: %s", serial, exc)
            return f"[Error collecting logs: {exc}]"

    def install_apk(self, index_or_name: int | str, apk_path: Path) -> None:
        serial = self._resolve_serial(index_or_name)
        if not apk_path.is_file():
            raise FileNotFoundError(f"APK file not found at {apk_path}")
        try:
            self._adb.run_command(
                ["install", "-r", str(apk_path)],
                serial=serial,
                timeout=90.0,
            )
        except Exception as exc:
            msg = f"Failed to install APK {apk_path.name} on {serial}: {exc}"
            raise ProviderError(msg) from exc

    def health_check(self, index_or_name: int | str) -> DeviceInfo | None:
        serial = self._resolve_serial(index_or_name)
        try:
            return self._adb.get_device_info(serial)
        except (AdbOfflineError, AdbDeviceNotFoundError):
            return DeviceInfo(serial=serial, state=DeviceState.OFFLINE)
        except AdbUnauthorizedError:
            return DeviceInfo(serial=serial, state=DeviceState.UNAUTHORIZED)
        except Exception as exc:
            logger.warning("Health check for %s failed: %s", serial, exc)
            return DeviceInfo(serial=serial, state=DeviceState.UNKNOWN)

    def get_metadata(self, index_or_name: int | str) -> PhysicalDeviceMetadata:
        serial = self._resolve_serial(index_or_name)
        transport = classify_transport(serial)

        # Get props
        manufacturer: str | None = None
        brand: str | None = None
        model: str | None = None
        android_version: str | None = None
        sdk_version: int | None = None

        try:
            m_out = self._adb.shell(serial, "getprop ro.product.manufacturer", timeout=5.0).strip()
            manufacturer = m_out or None
            b_out = self._adb.shell(serial, "getprop ro.product.brand", timeout=5.0).strip()
            brand = b_out or None
            mod_out = self._adb.shell(serial, "getprop ro.product.model", timeout=5.0).strip()
            model = mod_out or None
            v_out = self._adb.shell(serial, "getprop ro.build.version.release", timeout=5.0).strip()
            android_version = v_out or None
            sdk_str = self._adb.shell(serial, "getprop ro.build.version.sdk", timeout=5.0).strip()
            if sdk_str and sdk_str.isdigit():
                sdk_version = int(sdk_str)
        except Exception as exc:
            logger.debug("Failed to read props for %s: %s", serial, exc)

        # Battery
        battery_level: int | None = None
        battery_charging: bool | None = None
        try:
            bat_out = self._adb.shell(serial, "dumpsys battery", timeout=5.0)
            battery_level, battery_charging = parse_battery_status(bat_out)
        except Exception as exc:
            logger.debug("Failed to read battery for %s: %s", serial, exc)

        # Resolution
        resolution: tuple[int, int] | None = None
        try:
            info = self._adb.get_device_info(serial)
            resolution = info.resolution
        except Exception:
            pass

        return PhysicalDeviceMetadata(
            serial=serial,
            transport=transport,
            manufacturer=manufacturer,
            brand=brand,
            model=model,
            android_version=android_version,
            sdk_version=sdk_version,
            battery_level=battery_level,
            battery_charging=battery_charging,
            resolution=resolution,
        )

    def get_troubleshooting(self, index_or_name: int | str) -> TroubleshootingGuidance:
        serial = self._resolve_serial(index_or_name)
        try:
            info = self._adb.get_device_info(serial)
            return get_default_troubleshooting_guidance(info.state)
        except (AdbOfflineError, AdbDeviceNotFoundError):
            return get_default_troubleshooting_guidance(DeviceState.OFFLINE)
        except AdbUnauthorizedError:
            return get_default_troubleshooting_guidance(DeviceState.UNAUTHORIZED)
        except Exception:
            return get_default_troubleshooting_guidance(DeviceState.UNKNOWN)

    def diagnostics(self) -> dict[str, object]:
        instances = self.list_instances()
        usb_count = 0
        wifi_count = 0
        online_count = 0
        for inst in instances:
            t = classify_transport(inst.adb_serial)
            if t is ConnectionTransport.USB:
                usb_count += 1
            elif t is ConnectionTransport.WIFI:
                wifi_count += 1
            if inst.is_running:
                online_count += 1

        return {
            "provider": self.provider_type.value,
            "devices_total": len(instances),
            "devices_online": online_count,
            "transport_usb": usb_count,
            "transport_wifi": wifi_count,
        }
