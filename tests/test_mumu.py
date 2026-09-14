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
from sp_farms.infrastructure.providers.mumu.fake import FakeMuMuProvider
from sp_farms.infrastructure.providers.mumu.locator import find_mumu_executable
from sp_farms.infrastructure.providers.mumu.parser import (
    map_mumu_serial,
    parse_mumu_instances,
)
from sp_farms.infrastructure.providers.mumu.provider import MuMuProvider


def test_map_mumu_serial() -> None:
    assert map_mumu_serial(0) == "127.0.0.1:16384"
    assert map_mumu_serial(1) == "127.0.0.1:16416"
    assert map_mumu_serial(2) == "127.0.0.1:16448"
    assert map_mumu_serial(0, custom_port=7555) == "127.0.0.1:7555"


def test_parse_mumu_instances_json() -> None:
    json_output = """
    [
        {
            "index": 0,
            "name": "MuMuPlayer-12.0",
            "is_running": true,
            "pid": 6012,
            "width": 1080,
            "height": 1920,
            "dpi": 480
        },
        {
            "index": 1,
            "name": "MuMuPlayer-Test",
            "is_running": false,
            "adb_port": 16416
        }
    ]
    """
    instances = parse_mumu_instances(json_output)
    assert len(instances) == 2

    inst0 = instances[0]
    assert inst0.index == 0
    assert inst0.name == "MuMuPlayer-12.0"
    assert inst0.adb_serial == "127.0.0.1:16384"
    assert inst0.is_running is True
    assert inst0.pid == 6012
    assert inst0.resolution == (1080, 1920)
    assert inst0.dpi == 480

    inst1 = instances[1]
    assert inst1.index == 1
    assert inst1.name == "MuMuPlayer-Test"
    assert inst1.adb_serial == "127.0.0.1:16416"
    assert inst1.is_running is False
    assert inst1.pid is None


def test_parse_mumu_instances_tabular() -> None:
    tabular_output = """# Comment line
0,MuMu-Main,running,16384
1,MuMu-Worker,stopped,16416
"""
    instances = parse_mumu_instances(tabular_output)
    assert len(instances) == 2
    assert instances[0].index == 0
    assert instances[0].name == "MuMu-Main"
    assert instances[0].is_running is True
    assert instances[0].adb_serial == "127.0.0.1:16384"

    assert instances[1].index == 1
    assert instances[1].name == "MuMu-Worker"
    assert instances[1].is_running is False
    assert instances[1].adb_serial == "127.0.0.1:16416"


def test_fake_mumu_provider_lifecycle() -> None:
    provider = FakeMuMuProvider()
    assert provider.provider_type == DeviceProviderType.MUMU
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
    inst1 = next(i for i in provider.list_instances() if i.index == 1)
    assert inst1.is_running

    # Stop instance 0
    provider.stop_instance("MuMuPlayer-0")
    inst0 = next(i for i in provider.list_instances() if i.index == 0)
    assert not inst0.is_running

    # Restart instance 1
    provider.restart_instance(1)
    inst1_after = next(i for i in provider.list_instances() if i.index == 1)
    assert inst1_after.is_running

    # Diagnostics
    diag = provider.diagnostics()
    assert diag["provider"] == "mumu"
    assert diag["installed"] is True
    assert diag["instances_total"] == 2


def test_fake_mumu_provider_app_screenshot_logs(tmp_path: Path) -> None:
    provider = FakeMuMuProvider()
    provider.launch_app(0, "com.facebook.katana")

    with pytest.raises(RuntimeError, match="MuMu instance is not running"):
        provider.launch_app(1, "com.facebook.katana")

    # Screenshot
    shot = tmp_path / "mumu_snap.png"
    provider.take_screenshot(0, shot)
    assert shot.exists()
    assert shot.stat().st_size > 0

    # Logs
    logs = provider.collect_logs(0, lines=30)
    assert "[MuMuLogcat]" in logs

    # Health check
    health_0 = provider.health_check(0)
    assert health_0 is not None
    assert health_0.state == DeviceState.ONLINE

    health_1 = provider.health_check(1)
    assert health_1 is not None
    assert health_1.state == DeviceState.OFFLINE


def test_fake_mumu_errors() -> None:
    uninstalled = FakeMuMuProvider(is_installed=False)
    assert not uninstalled.is_available()
    with pytest.raises(ProviderExecutableNotFoundError):
        uninstalled.list_instances()

    provider = FakeMuMuProvider()
    with pytest.raises(ProviderInstanceNotFoundError):
        provider.start_instance("UnknownMuMu")

    timeout_provider = FakeMuMuProvider(timeout_on_start=True)
    with pytest.raises(ProviderOperationTimeoutError):
        timeout_provider.start_instance(0)


def test_mumu_locator(tmp_path: Path) -> None:
    custom_exe = tmp_path / "MuMuManager.exe"
    custom_exe.write_text("binary", encoding="utf-8")

    with patch("os.access", return_value=True):
        found = find_mumu_executable(custom_path=custom_exe)
        assert found == custom_exe.resolve()

        found_dir = find_mumu_executable(custom_path=tmp_path)
        assert found_dir == custom_exe.resolve()

        found_env = find_mumu_executable(environ={"SP_FARMS_MUMU_PATH": str(custom_exe)})
        assert found_env == custom_exe.resolve()


def test_mumu_provider_with_mocked_cli_and_adb(tmp_path: Path) -> None:
    fake_exe = tmp_path / "MuMuManager.exe"
    fake_exe.write_text("dummy", encoding="utf-8")

    fake_adb = FakeAdbAdapter()
    dev0 = SimulatedDevice(
        serial="127.0.0.1:16384",
        state=DeviceState.ONLINE,
        model="MuMuPlayer-12.0",
    )
    fake_adb.add_device(dev0)

    provider = MuMuProvider(executable_path=fake_exe, adb_port=fake_adb)

    sample_json = '[{"index": 0, "name": "MuMu-0", "is_running": true, "adb_port": 16384}]'

    def mock_run(cmd: list[str], **kwargs: object) -> MagicMock:
        if "api" in cmd and "all" in cmd:
            return MagicMock(returncode=0, stdout=sample_json, stderr="")
        return MagicMock(returncode=0, stdout="success", stderr="")

    with (
        patch("os.access", return_value=True),
        patch("subprocess.run", side_effect=mock_run),
    ):
        assert provider.is_available()
        instances = provider.list_instances()
        assert len(instances) == 1
        assert instances[0].name == "MuMu-0"
        assert instances[0].adb_serial == "127.0.0.1:16384"

        # Lifecycle operations
        provider.start_instance(0)
        provider.stop_instance(0)
        provider.restart_instance(0)
        provider.launch_app(0, "com.facebook.katana")

        # Health check
        health = provider.health_check(0)
        assert health is not None
        assert health.state == DeviceState.ONLINE
        assert health.serial == "127.0.0.1:16384"

        # Screenshot
        with patch.object(
            fake_adb,
            "run_command",
            return_value=AdbCommandResult(stdout="PNGMUMU", stderr="", returncode=0),
        ):
            screen_file = tmp_path / "snap.png"
            provider.take_screenshot(0, screen_file)
            assert screen_file.exists()

        # Diagnostics
        diag = provider.diagnostics()
        assert diag["provider"] == "mumu"
        assert diag["available"] is True
        assert diag["instances_total"] == 1
        assert diag["instances_running"] == 1


def test_mumu_provider_error_handling(tmp_path: Path) -> None:
    fake_exe = tmp_path / "MuMuManager.exe"
    fake_exe.write_text("dummy", encoding="utf-8")
    provider = MuMuProvider(executable_path=fake_exe)

    with (
        patch("os.access", return_value=True),
        patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="MuMuManager", timeout=5),
        ),
        pytest.raises(ProviderOperationTimeoutError),
    ):
        provider.list_instances()

    err_mock = MagicMock(returncode=1, stdout="", stderr="Internal manager failure")
    with (
        patch("os.access", return_value=True),
        patch("subprocess.run", return_value=err_mock),
        pytest.raises(ProviderError, match="Internal manager failure"),
    ):
        provider.start_instance(0)
