import time
from pathlib import Path

import pytest
from PySide6.QtCore import QItemSelectionModel, QSettings
from PySide6.QtWidgets import QApplication

from sp_farms.app.device_manager import DeviceManagerView, DeviceTableModel
from sp_farms.application.device_service import DeviceService
from sp_farms.domain.device_management import ManagedDevice
from sp_farms.domain.devices import DeviceState
from sp_farms.domain.providers import DeviceProviderType, ProviderCapabilities
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyDeviceProfileRepository,
    run_migrations,
)
from sp_farms.infrastructure.providers.ldplayer import FakeLdPlayerProvider
from sp_farms.infrastructure.providers.mumu import FakeMuMuProvider
from sp_farms.infrastructure.providers.physical import FakePhysicalProvider

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app  # type: ignore[return-value]


def settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def mixed_service() -> DeviceService:
    return DeviceService((FakeLdPlayerProvider(), FakeMuMuProvider(), FakePhysicalProvider()))


def test_discovery_aggregates_provider_mix_and_assignment_placeholder() -> None:
    devices = mixed_service().discover()

    assert len(devices) == 6
    assert {device.provider for device in devices} == {
        DeviceProviderType.LDPLAYER,
        DeviceProviderType.MUMU,
        DeviceProviderType.PHYSICAL,
    }
    physical = next(device for device in devices if device.provider is DeviceProviderType.PHYSICAL)
    assert physical.android_version in {"13", "14"}
    assert physical.network_state in {"usb", "wifi"}

    model = DeviceTableModel()
    model.set_devices(devices)
    assert model.data(model.index(0, 5)) == "Unassigned"


def test_action_enablement_uses_capabilities_and_online_state(
    qapp: QApplication, tmp_path: Path
) -> None:
    service = mixed_service()
    view = DeviceManagerView(service, settings(tmp_path))
    view.set_devices(service.discover())

    offline_emulator_row = next(
        row
        for row in range(view.model.rowCount())
        if (device := view.model.get_device(row)) is not None
        and device.provider is DeviceProviderType.LDPLAYER
        and not device.is_online
    )
    proxy_index = view.proxy_model.mapFromSource(view.model.index(offline_emulator_row, 0))
    view.table.selectRow(proxy_index.row())
    assert view.start_btn.isEnabled()
    assert not view.stop_btn.isEnabled()
    assert not view.launch_btn.isEnabled()

    physical_row = next(
        row
        for row in range(view.model.rowCount())
        if (device := view.model.get_device(row)) is not None
        and device.provider is DeviceProviderType.PHYSICAL
    )
    view.table.selectRow(view.proxy_model.mapFromSource(view.model.index(physical_row, 0)).row())
    assert not view.start_btn.isEnabled()
    assert not view.stop_btn.isEnabled()
    assert view.restart_btn.isEnabled()
    assert view.launch_btn.isEnabled()


def test_search_select_all_and_saved_filters(qapp: QApplication, tmp_path: Path) -> None:
    stored = settings(tmp_path)
    service = mixed_service()
    view = DeviceManagerView(service, stored)
    view.set_devices(service.discover())
    view.search_input.setText("Galaxy")
    assert view.proxy_model.rowCount() == 1

    view.preset_combo.setCurrentText("Samsung USB")
    view._save_preset()
    restored = DeviceManagerView(None, settings(tmp_path))
    preset_index = restored.preset_combo.findText("Samsung USB")
    restored._apply_preset(preset_index)
    assert restored.search_input.text() == "Galaxy"

    view.search_input.clear()
    view.select_all_btn.click()
    assert len(view.table.selectionModel().selectedRows()) == 6


def test_screenshot_and_logs_use_deterministic_artifact_directories(tmp_path: Path) -> None:
    service = DeviceService((FakeLdPlayerProvider(),), artifact_directory=tmp_path)
    device = next(item for item in service.discover() if item.is_online)

    screenshot = service.take_screenshot(device)
    logs = service.collect_logs(device)

    assert screenshot.parent == tmp_path / "screenshots"
    assert screenshot.read_bytes().startswith(b"\x89PNG")
    assert logs.parent == tmp_path / "logs"
    assert "logcat" in logs.read_text(encoding="utf-8").lower()


def test_profiles_persist_across_discovery(tmp_path: Path) -> None:
    database = Database(tmp_path / "devices.db")
    try:
        run_migrations(database, MIGRATIONS)
        service = DeviceService(
            (FakePhysicalProvider(),),
            database.unit_of_work,
            SqlAlchemyDeviceProfileRepository,
        )
        device = service.discover()[0]
        service.save_profile(device, "Front Desk", "Primary test handset")

        refreshed = service.discover()[0]
        assert refreshed.alias == "Front Desk"
        assert refreshed.notes == "Primary test handset"
    finally:
        database.close()


def test_large_device_list_performance(qapp: QApplication, tmp_path: Path) -> None:
    capabilities = ProviderCapabilities(DeviceProviderType.LDPLAYER)
    devices = [
        ManagedDevice(
            provider=DeviceProviderType.LDPLAYER,
            external_id=f"emulator-{5554 + i * 2}",
            selector=i,
            name=f"Device {i}",
            adb_serial=f"emulator-{5554 + i * 2}",
            state=DeviceState.ONLINE if i % 2 == 0 else DeviceState.OFFLINE,
            capabilities=capabilities,
            assigned_account=f"account-{i % 50}" if i % 3 == 0 else None,
        )
        for i in range(1500)
    ]
    view = DeviceManagerView(None, settings(tmp_path))
    started = time.perf_counter()
    view.set_devices(devices)
    assert time.perf_counter() - started < 1.0
    assert view.proxy_model.rowCount() == 1500

    started = time.perf_counter()
    view.state_filter.setCurrentText("Online")
    assert time.perf_counter() - started < 0.5
    assert view.proxy_model.rowCount() == 750

    selection = view.table.selectionModel()
    selection.select(
        view.proxy_model.index(0, 0),
        QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
    )
    assert view.restart_btn.isEnabled()
