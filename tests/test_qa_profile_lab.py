from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from sp_farms.app.qa_profile_lab import QAProfileLab
from sp_farms.application.device_service import DeviceService
from sp_farms.application.qa_profile_service import QAProfileService
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyQAProfileRepository,
    run_migrations,
)
from sp_farms.infrastructure.providers.ldplayer import FakeLdPlayerProvider
from sp_farms.infrastructure.qa_bridge import FakeQAProfileReloadBridge

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 9, 1, tzinfo=UTC)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    return app  # type: ignore[return-value]


def test_qa_profile_lab_smoke_and_restricted_target_error(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "qa-ui.db")
    try:
        run_migrations(database, MIGRATIONS)
        service = QAProfileService(
            database.unit_of_work,
            SqlAlchemyQAProfileRepository,
            FakeQAProfileReloadBridge(),
            FixedClock(),
        )
        service.create_profile("QA Pixel")
        view = QAProfileLab(service)
        view.set_devices(DeviceService((FakeLdPlayerProvider(),)).discover())

        assert view.profile_table.rowCount() == 1
        assert view.device_list.count() == 2
        view.package_input.setText("com.instagram.android")
        view.ownership_input.setText("not owned")
        view.allow_target_btn.click()
        assert "restricted" in view.bridge_status.text().lower()
        assert not view.grab().isNull()
    finally:
        database.close()
