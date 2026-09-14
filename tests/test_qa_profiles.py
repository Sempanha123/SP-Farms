from collections.abc import Generator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sp_farms.application.qa_profile_service import RESTRICTED_MESSAGE, QAProfileService
from sp_farms.domain.qa_profiles import QAProfile
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyQAProfileRepository,
    run_migrations,
)
from sp_farms.infrastructure.qa_bridge import FakeQAProfileReloadBridge

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
NOW = datetime(2026, 9, 1, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


@pytest.fixture
def qa_service(
    tmp_path: Path,
) -> Generator[tuple[QAProfileService, Database, FakeQAProfileReloadBridge], None, None]:
    database = Database(tmp_path / "qa.db")
    run_migrations(database, MIGRATIONS)
    bridge = FakeQAProfileReloadBridge()
    service = QAProfileService(
        database.unit_of_work,
        SqlAlchemyQAProfileRepository,
        bridge,
        FixedClock(),
    )
    yield service, database, bridge
    database.close()


def test_profile_schema_json_round_trip_and_validation() -> None:
    profile = replace(
        QAProfile.create("Pixel compatibility", NOW),
        manufacturer="Google",
        model="Pixel 8",
        test_android_id="fixture-android-id",
        latitude=12.3,
        longitude=45.6,
    )

    restored = QAProfile.from_json(profile.to_json())

    assert restored == profile
    assert restored.to_dict()["schema_version"] == 1
    with pytest.raises(ValueError, match="Unsupported"):
        QAProfile.from_json('{"schema_version": 99, "profile": {}}')
    with pytest.raises(ValueError, match="Unknown"):
        QAProfile.from_json(
            '{"schema_version": 1, "profile": {"id": "1", '
            '"profile_name": "x", "actual_android_id": "bad"}}'
        )


def test_crud_clone_randomize_and_assignment_persist(
    qa_service: tuple[QAProfileService, Database, FakeQAProfileReloadBridge],
) -> None:
    service, _database, _bridge = qa_service
    profile = service.create_profile("Base")
    clone = service.clone_profile(profile.id, "Base Copy")
    randomized = service.randomize_compatibility_fields(clone.id, seed=1)
    service.assign("ldplayer", "0", randomized.id)

    assert randomized.id != profile.id
    assert randomized.manufacturer
    assert service.get_assignment("ldplayer", "0").profile_id == randomized.id  # type: ignore[union-attr]
    assert len(service.list_profiles()) == 2

    service.delete_profile(profile.id)
    assert [item.profile_name for item in service.list_profiles()] == ["Base Copy"]


def test_restricted_and_non_allowlisted_targets_are_refused(
    qa_service: tuple[QAProfileService, Database, FakeQAProfileReloadBridge],
) -> None:
    service, _database, bridge = qa_service
    profile = service.create_profile("Authorized fixture")

    with pytest.raises(ValueError, match="restricted"):
        service.allow_target("com.facebook.katana", "Facebook", "Not owned")

    blocked = service.push(
        "emulator-5554",
        "ldplayer",
        "0",
        profile.id,
        "com.example.notallowed",
    )
    assert not blocked.is_success
    assert blocked.error.message == RESTRICTED_MESSAGE
    assert bridge.history == []


def test_authorized_push_reload_verify_and_restore(
    qa_service: tuple[QAProfileService, Database, FakeQAProfileReloadBridge],
) -> None:
    service, _database, bridge = qa_service
    profile = service.create_profile("Owned app fixture")
    service.allow_target("com.example.ownedapp", "Owned App", "Internal application")

    pushed = service.push(
        "emulator-5554",
        "ldplayer",
        "0",
        profile.id,
        "com.example.ownedapp",
        reload_profile=True,
    )
    verified = service.verify("emulator-5554", "ldplayer", "0", "com.example.ownedapp")
    restored = service.restore("emulator-5554", "ldplayer", "0", "com.example.ownedapp")

    assert pushed.is_success and pushed.value.loaded
    assert verified.is_success and verified.value.profile_id == profile.id
    assert restored.is_success and not restored.value.loaded
    assert [operation for operation, _serial in bridge.history] == [
        "push",
        "reload",
        "verify",
        "restore",
    ]
