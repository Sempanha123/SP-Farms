import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sp_farms.application.adb import AdbCommandResult
from sp_farms.application.providers import (
    ProviderError,
    ProviderExecutableNotFoundError,
    ProviderInstanceNotFoundError,
    ProviderOperationTimeoutError,
)
from sp_farms.domain.devices import DeviceState
from sp_farms.domain.providers import DeviceProviderType
from sp_farms.infrastructure.adb.fake import FakeAdbAdapter, SimulatedDevice
from sp_farms.infrastructure.providers.ldplayer.fake import FakeLdPlayerProvider
from sp_farms.infrastructure.providers.ldplayer.locator import find_ldplayer_executable
from sp_farms.infrastructure.providers.ldplayer.parser import (
    map_ldplayer_serial,
    parse_ldplayer_list,
)
from sp_farms.infrastructure.providers.ldplayer.provider import LdPlayerProvider


def test_map_ldplayer_serial() -> None:
    assert map_ldplayer_serial(0) == "emulator-5554"
    assert map_ldplayer_serial(1) == "emulator-5556"
    assert map_ldplayer_serial(2) == "emulator-5558"
    assert map_ldplayer_serial(5) == "emulator-5564"


def test_parse_ldplayer_list() -> None:
    raw_output = """0,LDPlayer-0,123456,123457,1,4012,4013,1080,1920,480
1,LDPlayer-1,0,0,0,0,0,720,1280,320
2,Farm-Account-3,0,0,-1,0,0
invalid line
"""
    instances = parse_ldplayer_list(raw_output)
    assert len(instances) == 3

    inst0 = instances[0]
    assert inst0.index == 0
    assert inst0.name == "LDPlayer-0"
    assert inst0.adb_serial == "emulator-5554"
    assert inst0.is_running is True
    assert inst0.pid == 4012
    assert inst0.vbox_pid == 4013
    assert inst0.resolution == (1080, 1920)
    assert inst0.dpi == 480
    assert inst0.display_name == "LDPlayer-0 [#0]"
    assert inst0.resolution_str == "1080x1920"

    inst1 = instances[1]
    assert inst1.index == 1
    assert inst1.name == "LDPlayer-1"
    assert inst1.adb_serial == "emulator-5556"
    assert inst1.is_running is False
    assert inst1.pid is None
    assert inst1.resolution == (720, 1280)
    assert inst1.dpi == 320

    inst2 = instances[2]
    assert inst2.index == 2
    assert inst2.name == "Farm-Account-3"
    assert inst2.adb_serial == "emulator-5558"
    assert inst2.is_running is False
    assert inst2.resolution is None
    assert inst2.resolution_str == "Unknown"


def test_fake_ldplayer_provider_lifecycle() -> None:
    provider = FakeLdPlayerProvider()
    assert provider.provider_type == DeviceProviderType.LDPLAYER
    assert provider.is_available()

    caps = provider.capabilities
    assert caps.can_start_stop
    assert caps.can_restart
    assert caps.can_take_screenshot
    assert caps.can_launch_apps

    instances = provider.list_instances()
    assert len(instances) == 2
    assert instances[0].is_running
    assert not instances[1].is_running

    # Start instance 1
    provider.start_instance(1)
    instances = provider.list_instances()
    inst1 = next(i for i in instances if i.index == 1)
    assert inst1.is_running

    # Stop instance 0
    provider.stop_instance("LDPlayer-0")
    instances = provider.list_instances()
    inst0 = next(i for i in instances if i.index == 0)
    assert not inst0.is_running

    # Restart instance 1
    provider.restart_instance(1)
    inst1_after = next(i for i in provider.list_instances() if i.index == 1)
    assert inst1_after.is_running


def test_fake_ldplayer_provider_apps_screenshot_logs(tmp_path: Path) -> None:
    provider = FakeLdPlayerProvider()

    # Launch app on running instance
    provider.launch_app(0, "com.facebook.katana")

    # Launch app on stopped instance raises
    with pytest.raises(RuntimeError, match="instance is not running"):
        provider.launch_app(1, "com.facebook.katana")

    # Screenshot
    shot_path = tmp_path / "screen.png"
    provider.take_screenshot(0, shot_path)
    assert shot_path.exists()
    assert shot_path.stat().st_size > 0

    # Logs
    logs = provider.collect_logs(0, lines=50)
    assert "[FakeLogcat]" in logs

    # Health check
    health_running = provider.health_check(0)
    assert health_running is not None
    assert health_running.state == DeviceState.ONLINE

    health_stopped = provider.health_check(1)
    assert health_stopped is not None
    assert health_stopped.state == DeviceState.OFFLINE


def test_fake_ldplayer_errors() -> None:
    uninstalled = FakeLdPlayerProvider(is_installed=False)
    assert not uninstalled.is_available()
    with pytest.raises(ProviderExecutableNotFoundError):
        uninstalled.list_instances()

    provider = FakeLdPlayerProvider()
    with pytest.raises(ProviderInstanceNotFoundError):
        provider.start_instance("NonExistentInstance")

    timeout_provider = FakeLdPlayerProvider(timeout_on_start=True)
    with pytest.raises(ProviderOperationTimeoutError):
        timeout_provider.start_instance(0)


def test_ldplayer_locator(tmp_path: Path) -> None:
    custom_exe = tmp_path / "ldconsole.exe"
    custom_exe.write_text("binary", encoding="utf-8")

    with patch("os.access", return_value=True):
        found = find_ldplayer_executable(custom_path=custom_exe)
        assert found == custom_exe.resolve()

        # From directory path
        found_dir = find_ldplayer_executable(custom_path=tmp_path)
        assert found_dir == custom_exe.resolve()

        # From environment variable
        found_env = find_ldplayer_executable(environ={"SP_FARMS_LDPLAYER_PATH": str(custom_exe)})
        assert found_env == custom_exe.resolve()


def test_ldplayer_provider_with_mocked_cli_and_adb(tmp_path: Path) -> None:
    fake_exe = tmp_path / "ldconsole.exe"
    fake_exe.write_text("dummy", encoding="utf-8")

    fake_adb = FakeAdbAdapter()
    dev0 = SimulatedDevice(
        serial="emulator-5554",
        state=DeviceState.ONLINE,
        model="LDPlayer-0",
    )
    fake_adb.add_device(dev0)

    provider = LdPlayerProvider(executable_path=fake_exe, adb_port=fake_adb)

    # Mock subprocess.run for CLI list2 and launch commands
    list_stdout = "0,LDPlayer-0,111,222,1,100,200,900,1600,320\n"

    def mock_run(cmd: list[str], **kwargs: object) -> MagicMock:
        if "list2" in cmd:
            return MagicMock(returncode=0, stdout=list_stdout, stderr="")
        if "launch" in cmd or "quit" in cmd or "reboot" in cmd or "runapp" in cmd:
            return MagicMock(returncode=0, stdout="OK", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    with (
        patch("os.access", return_value=True),
        patch("subprocess.run", side_effect=mock_run),
    ):
        assert provider.is_available()
        instances = provider.list_instances()
        assert len(instances) == 1
        assert instances[0].name == "LDPlayer-0"
        assert instances[0].adb_serial == "emulator-5554"

        # Start, stop, restart, runapp
        provider.start_instance(0)
        provider.stop_instance(0)
        provider.restart_instance("LDPlayer-0")
        provider.launch_app(0, "com.facebook.katana")

        # Health check via ADB
        health = provider.health_check(0)
        assert health is not None
        assert health.state == DeviceState.ONLINE
        assert health.serial == "emulator-5554"

        # Screenshot via ADB
        with patch.object(
            fake_adb,
            "run_command",
            return_value=AdbCommandResult(stdout="PNGDATA", stderr="", returncode=0),
        ):
            screen_file = tmp_path / "snap.png"
            provider.take_screenshot(0, screen_file)
            assert screen_file.exists()


def test_ldplayer_provider_error_handling(tmp_path: Path) -> None:
    fake_exe = tmp_path / "ldconsole.exe"
    fake_exe.write_text("dummy", encoding="utf-8")
    provider = LdPlayerProvider(executable_path=fake_exe)

    with (
        patch("os.access", return_value=True),
        patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ldconsole", timeout=5)),
        pytest.raises(ProviderOperationTimeoutError),
    ):
        provider.list_instances()

    err_mock = MagicMock(returncode=1, stdout="", stderr="Instance already running")
    with (
        patch("os.access", return_value=True),
        patch("subprocess.run", return_value=err_mock),
        pytest.raises(ProviderError, match="Instance already running"),
    ):
        provider.start_instance(0)
