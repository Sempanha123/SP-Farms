from pathlib import Path

import pytest

from sp_farms.application.providers import (
    ProviderInstanceNotFoundError,
)
from sp_farms.domain.devices import DeviceState
from sp_farms.domain.providers import (
    ConnectionTransport,
    DeviceProviderType,
)
from sp_farms.infrastructure.adb.fake import FakeAdbAdapter, SimulatedDevice
from sp_farms.infrastructure.providers.physical.fake import FakePhysicalProvider
from sp_farms.infrastructure.providers.physical.parser import (
    classify_transport,
    parse_battery_status,
)
from sp_farms.infrastructure.providers.physical.provider import PhysicalAndroidProvider
from sp_farms.infrastructure.providers.troubleshooting import get_default_troubleshooting_guidance


def test_classify_transport() -> None:
    assert classify_transport("192.168.1.50:5555") is ConnectionTransport.WIFI
    assert classify_transport("10.0.0.12:5555") is ConnectionTransport.WIFI
    assert classify_transport("emulator-5554") is ConnectionTransport.EMULATOR
    assert classify_transport("127.0.0.1:16384") is ConnectionTransport.EMULATOR
    assert classify_transport("RFCW10ABCDE") is ConnectionTransport.USB
    assert classify_transport("ZY224K7M3N") is ConnectionTransport.USB
    assert classify_transport("") is ConnectionTransport.UNKNOWN


def test_parse_battery_status() -> None:
    dumpsys_sample = """Current Battery Service state:
  AC powered: false
  USB powered: true
  Wireless powered: false
  Max charging current: 500000
  Max charging voltage: 5000000
  Charge counter: 2840000
  status: 2
  health: 2
  present: true
  level: 85
  scale: 100
  voltage: 4120
  temperature: 280
  technology: Li-ion
"""
    level, is_charging = parse_battery_status(dumpsys_sample)
    assert level == 85
    assert is_charging is True

    unplugged_sample = """Current Battery Service state:
  AC powered: false
  USB powered: false
  Wireless powered: false
  level: 42
"""
    level, is_charging = parse_battery_status(unplugged_sample)
    assert level == 42
    assert is_charging is False


def test_troubleshooting_guidance() -> None:
    unauth = get_default_troubleshooting_guidance(DeviceState.UNAUTHORIZED)
    assert "Unauthorized" in unauth.title
    assert any("Allow USB debugging" in step for step in unauth.steps)

    offline = get_default_troubleshooting_guidance(DeviceState.OFFLINE)
    assert "Offline" in offline.title
    assert any("USB cable" in step for step in offline.steps)

    online = get_default_troubleshooting_guidance(DeviceState.ONLINE)
    assert "Ready" in online.title


def test_fake_physical_provider(tmp_path: Path) -> None:
    provider = FakePhysicalProvider()
    assert provider.provider_type is DeviceProviderType.PHYSICAL
    assert provider.is_available()

    caps = provider.capabilities
    assert not caps.can_start_stop
    assert caps.can_restart
    assert caps.can_install_apk
    assert caps.can_take_screenshot

    instances = provider.list_instances()
    assert len(instances) == 2
    assert instances[0].adb_serial == "RFCT123456X"
    assert instances[0].is_running

    # Metadata
    meta = provider.get_metadata(0)
    assert meta.model == "Galaxy S22"
    assert meta.battery_level == 88

    # Start/stop raises for physical
    with pytest.raises(RuntimeError, match="cannot be started remotely"):
        provider.start_instance(0)
    with pytest.raises(RuntimeError, match="cannot be powered off remotely"):
        provider.stop_instance(0)

    # App launch & screenshot
    provider.launch_app(0, "com.facebook.katana")
    shot_path = tmp_path / "shot.png"
    provider.take_screenshot(0, shot_path)
    assert shot_path.exists()

    # APK installation
    apk_file = tmp_path / "app.apk"
    apk_file.write_bytes(b"PK-fake-apk")
    provider.install_apk(0, apk_file)

    # Missing APK
    with pytest.raises(FileNotFoundError):
        provider.install_apk(0, tmp_path / "missing.apk")

    # Diagnostics
    diag = provider.diagnostics()
    assert diag["provider"] == "physical"
    assert diag["devices_total"] == 2
    assert diag["transport_usb"] == 1
    assert diag["transport_wifi"] == 1


def test_physical_provider_with_fake_adb(tmp_path: Path) -> None:
    fake_adb = FakeAdbAdapter()
    usb_dev = SimulatedDevice(
        serial="USB123456",
        state=DeviceState.ONLINE,
        model="Pixel 6",
        properties={
            "ro.product.manufacturer": "Google",
            "ro.product.brand": "google",
            "ro.product.model": "Pixel 6",
            "ro.build.version.release": "13",
            "ro.build.version.sdk": "33",
        },
        resolution=(1080, 2400),
    )
    # Also add an emulator device that should be filtered out from physical list
    emu_dev = SimulatedDevice(
        serial="emulator-5554",
        state=DeviceState.ONLINE,
        model="LDPlayer",
    )
    fake_adb.add_device(usb_dev)
    fake_adb.add_device(emu_dev)

    provider = PhysicalAndroidProvider(adb_port=fake_adb)
    assert provider.is_available()

    # Only physical devices should be listed
    instances = provider.list_instances()
    assert len(instances) == 1
    assert instances[0].adb_serial == "USB123456"
    assert instances[0].name == "Pixel 6"

    # Screenshot
    shot = tmp_path / "pixel_snap.png"
    provider.take_screenshot("USB123456", shot)
    assert shot.exists()

    # Logs
    logs = provider.collect_logs("USB123456", lines=20)
    assert "Logcat output" in logs

    # Reboot
    provider.restart_instance("USB123456")

    # App launch
    provider.launch_app("USB123456", "com.facebook.katana")

    # Metadata
    meta = provider.get_metadata("USB123456")
    assert meta.manufacturer == "Google"
    assert meta.model == "Pixel 6"
    assert meta.android_version == "13"
    assert meta.sdk_version == 33
    assert meta.transport is ConnectionTransport.USB

    # Diagnostics
    diag = provider.diagnostics()
    assert diag["devices_total"] == 1
    assert diag["devices_online"] == 1
    assert diag["transport_usb"] == 1
    assert diag["transport_wifi"] == 0


def test_physical_provider_errors_and_troubleshooting(tmp_path: Path) -> None:
    fake_adb = FakeAdbAdapter()
    unauth_dev = SimulatedDevice(
        serial="UNAUTH_USB",
        state=DeviceState.UNAUTHORIZED,
    )
    fake_adb.add_device(unauth_dev)

    provider = PhysicalAndroidProvider(adb_port=fake_adb)

    # Health check
    health = provider.health_check("UNAUTH_USB")
    assert health is not None
    assert health.state is DeviceState.UNAUTHORIZED

    # Troubleshooting
    guide = provider.get_troubleshooting("UNAUTH_USB")
    assert guide.state is DeviceState.UNAUTHORIZED
    assert "Unauthorized" in guide.title

    # Unknown device raises
    with pytest.raises(ProviderInstanceNotFoundError):
        provider.get_metadata("NON_EXISTENT")

    # Start/stop raise
    with pytest.raises(RuntimeError):
        provider.start_instance("UNAUTH_USB")
    with pytest.raises(RuntimeError):
        provider.stop_instance("UNAUTH_USB")
