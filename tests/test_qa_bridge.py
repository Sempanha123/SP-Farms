from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from sp_farms.domain.devices import DeviceState
from sp_farms.domain.qa_profiles import QAProfile
from sp_farms.infrastructure.adb.fake import FakeAdbAdapter, SimulatedDevice
from sp_farms.infrastructure.qa_bridge import (
    REMOTE_PROFILE_PATH,
    AdbQAProfileReloadBridge,
)

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def test_adb_bridge_pushes_with_arguments_permissions_and_cleanup(tmp_path: Path) -> None:
    adb = FakeAdbAdapter()
    device = SimulatedDevice("emulator-5554", DeviceState.ONLINE)
    adb.add_device(device)
    profile = replace(QAProfile.create("Fixture", NOW), manufacturer="Google")
    bridge = AdbQAProfileReloadBridge(adb, tmp_path)

    result = bridge.push("emulator-5554", profile, "com.example.ownedapp")

    assert result.is_success
    push_args, serial = next(item for item in adb.command_history if item[0][0] == "push")
    assert serial == "emulator-5554"
    assert push_args[2] == REMOTE_PROFILE_PATH
    assert REMOTE_PROFILE_PATH in device.remote_files
    assert list(tmp_path.iterdir()) == []


def test_adb_bridge_reload_verify_and_restore() -> None:
    adb = FakeAdbAdapter()
    device = SimulatedDevice("emulator-5554")
    adb.add_device(device)
    profile = QAProfile.create("Fixture", NOW)
    bridge = AdbQAProfileReloadBridge(adb)

    assert bridge.push("emulator-5554", profile, "com.example.ownedapp").is_success
    assert bridge.reload("emulator-5554").is_success
    verified = bridge.verify("emulator-5554")
    assert verified.is_success and verified.value.profile_id == profile.id
    assert bridge.restore("emulator-5554").is_success
    assert REMOTE_PROFILE_PATH not in device.remote_files


def test_adb_bridge_cleans_temporary_file_on_failure(tmp_path: Path) -> None:
    adb = FakeAdbAdapter()
    adb.add_device(SimulatedDevice("offline", state=DeviceState.OFFLINE))
    bridge = AdbQAProfileReloadBridge(adb, tmp_path)

    result = bridge.push(
        "offline",
        QAProfile.create("Fixture", NOW),
        "com.example.ownedapp",
    )

    assert not result.is_success
    assert result.error.code == "qa.push_failed"
    assert list(tmp_path.iterdir()) == []
