import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sp_farms.application.adb import (
    AdbCommandError,
    AdbDeviceNotFoundError,
    AdbExecutableNotFoundError,
    AdbOfflineError,
    AdbTimeoutError,
    AdbUnauthorizedError,
)
from sp_farms.domain.devices import DeviceState
from sp_farms.infrastructure.adb.client import SubprocessAdbClient
from sp_farms.infrastructure.adb.fake import FakeAdbAdapter, SimulatedDevice
from sp_farms.infrastructure.adb.locator import find_adb_executable
from sp_farms.infrastructure.adb.parser import (
    parse_android_version,
    parse_devices_output,
    parse_resolution,
    parse_sdk_version,
)


def test_parse_devices_output() -> None:
    sample_output = """* daemon not running; starting now at tcp:5037
* daemon started successfully
List of devices attached
emulator-5554	device product:sdk_gphone64 model:sdk_gphone64 device:emu64a transport_id:1
192.168.1.100:5555	unauthorized transport_id:2
XYZ1234567	offline transport_id:3
PIXEL7_PRO	device model:Pixel_7_Pro transport_id:4

"""
    devices = parse_devices_output(sample_output)
    assert len(devices) == 4

    # Device 1: online emulator
    assert devices[0].serial == "emulator-5554"
    assert devices[0].state is DeviceState.ONLINE
    assert devices[0].model == "sdk gphone64"

    # Device 2: unauthorized
    assert devices[1].serial == "192.168.1.100:5555"
    assert devices[1].state is DeviceState.UNAUTHORIZED

    # Device 3: offline
    assert devices[2].serial == "XYZ1234567"
    assert devices[2].state is DeviceState.OFFLINE

    # Device 4: physical pixel with model name
    assert devices[3].serial == "PIXEL7_PRO"
    assert devices[3].state is DeviceState.ONLINE
    assert devices[3].model == "Pixel 7 Pro"


def test_parse_properties_and_metrics() -> None:
    assert parse_android_version("14\n") == "14"
    assert parse_android_version("") is None

    assert parse_sdk_version("34\n") == 34
    assert parse_sdk_version("invalid\n") is None

    assert parse_resolution("Physical size: 1080x2400\n") == (1080, 2400)
    assert parse_resolution("Override size: 720x1600\n") == (720, 1600)
    assert parse_resolution("No size reported") is None


def test_fake_adb_adapter_simulated_devices() -> None:
    adapter = FakeAdbAdapter()
    dev1 = SimulatedDevice(
        serial="dev-1",
        state=DeviceState.ONLINE,
        model="Galaxy S22",
        android_version="12",
        sdk_version=31,
        resolution=(1080, 2340),
    )
    dev2 = SimulatedDevice(
        serial="dev-2",
        state=DeviceState.UNAUTHORIZED,
    )
    adapter.add_device(dev1)
    adapter.add_device(dev2)

    devices = adapter.list_devices()
    assert len(devices) == 2
    assert devices[0].serial == "dev-1"
    assert devices[0].is_ready
    assert devices[0].display_name == "Galaxy S22 (dev-1)"
    assert devices[0].resolution_str == "1080x2340"

    # Unauthorized device
    assert not devices[1].is_ready

    # Shell execution on online device
    model = adapter.shell("dev-1", "getprop ro.product.model")
    assert model.strip() == "Galaxy S22"

    size = adapter.shell("dev-1", "wm size")
    assert "1080x2340" in size

    # Heartbeat
    assert adapter.heartbeat("dev-1")
    assert not adapter.heartbeat("dev-2")  # unauthorized fails heartbeat


def test_fake_adb_adapter_errors() -> None:
    adapter = FakeAdbAdapter()
    dev_timeout = SimulatedDevice(serial="dev-timeout", timeout_on_commands=True)
    dev_unauth = SimulatedDevice(serial="dev-unauth", state=DeviceState.UNAUTHORIZED)
    dev_offline = SimulatedDevice(serial="dev-offline", state=DeviceState.OFFLINE)
    dev_fail = SimulatedDevice(serial="dev-fail", fail_on_commands=True)

    adapter.add_device(dev_timeout)
    adapter.add_device(dev_unauth)
    adapter.add_device(dev_offline)
    adapter.add_device(dev_fail)

    with pytest.raises(AdbTimeoutError):
        adapter.shell("dev-timeout", "echo test")

    with pytest.raises(AdbUnauthorizedError):
        adapter.shell("dev-unauth", "echo test")

    with pytest.raises(AdbOfflineError):
        adapter.shell("dev-offline", "echo test")

    with pytest.raises(AdbCommandError):
        adapter.shell("dev-fail", "echo test")

    with pytest.raises(AdbDeviceNotFoundError):
        adapter.shell("non-existent-device", "echo test")


def test_subprocess_adb_client_timeout_and_error_mapping() -> None:
    fake_exe = Path("C:/fake/adb.exe")
    client = SubprocessAdbClient(fake_exe)

    with patch.object(Path, "exists", return_value=True):
        # 1. TimeoutExpired mapping
        with (
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="adb", timeout=5.0)),
            pytest.raises(AdbTimeoutError),
        ):
            client.run_command(["devices"], timeout=5.0)

        # 2. FileNotFoundError mapping
        with (
            patch("subprocess.run", side_effect=FileNotFoundError("not found")),
            pytest.raises(AdbExecutableNotFoundError),
        ):
            client.run_command(["devices"])

        # 3. Unauthorized stderr mapping
        mock_unauth = MagicMock(returncode=1, stdout="", stderr="error: device unauthorized.")
        with (
            patch("subprocess.run", return_value=mock_unauth),
            pytest.raises(AdbUnauthorizedError),
        ):
            client.run_command(["shell", "echo"], serial="dev-1")

        # 4. Offline stderr mapping
        mock_offline = MagicMock(returncode=1, stdout="", stderr="error: device offline")
        with (
            patch("subprocess.run", return_value=mock_offline),
            pytest.raises(AdbOfflineError),
        ):
            client.run_command(["shell", "echo"], serial="dev-1")

        # 5. Device not found mapping
        mock_not_found = MagicMock(returncode=1, stdout="", stderr="error: device 'xyz' not found")
        with (
            patch("subprocess.run", return_value=mock_not_found),
            pytest.raises(AdbDeviceNotFoundError),
        ):
            client.run_command(["shell", "echo"], serial="xyz")

        # 6. Generic command error
        mock_err = MagicMock(returncode=127, stdout="", stderr="/system/bin/sh: foo: not found")
        with (
            patch("subprocess.run", return_value=mock_err),
            pytest.raises(AdbCommandError) as exc_info,
        ):
            client.run_command(["shell", "foo"], serial="dev-1")
        assert exc_info.value.returncode == 127


def test_locator_precedence(tmp_path: Path) -> None:
    custom_adb = tmp_path / "custom_adb.exe"
    custom_adb.write_text("dummy", encoding="utf-8")

    env_adb = tmp_path / "env_adb.exe"
    env_adb.write_text("dummy", encoding="utf-8")

    # Custom path has highest precedence
    with patch("os.access", return_value=True):
        found = find_adb_executable(
            custom_path=custom_adb,
            environ={"SP_FARMS_ADB_PATH": str(env_adb)},
        )
        assert found == custom_adb.resolve()

        # Env variable precedence when custom is None
        found_env = find_adb_executable(environ={"SP_FARMS_ADB_PATH": str(env_adb)})
        assert found_env == env_adb.resolve()
