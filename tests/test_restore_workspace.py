from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sp_farms.application.account_service import AccountService
from sp_farms.application.device_service import DeviceService
from sp_farms.application.restore_workspace_service import RestoreWorkspaceService
from sp_farms.domain.accounts import PreferredApp, SecurityState
from sp_farms.domain.device_restore import (
    FACEBOOK_LITE_PACKAGE,
    FACEBOOK_PACKAGE,
    BindingStatus,
)
from sp_farms.domain.providers import DeviceProviderType
from sp_farms.infrastructure.adb.fake import FakeAdbAdapter, SimulatedDevice
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyAccountRepository,
    SqlAlchemyDeviceProfileRepository,
    run_migrations,
)
from sp_farms.infrastructure.providers.ldplayer import FakeLdPlayerProvider
from sp_farms.infrastructure.providers.mumu import FakeMuMuProvider
from sp_farms.infrastructure.providers.physical import FakePhysicalProvider

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


RestoreEnv = tuple[
    RestoreWorkspaceService,
    AccountService,
    FakeAdbAdapter,
    FakeLdPlayerProvider,
    FakePhysicalProvider,
    Database,
]


@pytest.fixture
def restore_env(tmp_path: Path) -> Generator[RestoreEnv, None, None]:
    database = Database(tmp_path / "restore_test.db")
    run_migrations(database, MIGRATIONS)
    clock = FixedClock()
    account_service = AccountService(
        database.unit_of_work,
        SqlAlchemyAccountRepository,
        clock,
    )

    adb = FakeAdbAdapter()
    adb.add_device(
        SimulatedDevice(
            serial="emulator-5554",
            installed_packages={"com.facebook.katana", "com.android.chrome"},
        )
    )
    adb.add_device(
        SimulatedDevice(
            serial="127.0.0.1:16384",
            installed_packages={"com.facebook.lite", "com.android.chrome"},
        )
    )
    adb.add_device(
        SimulatedDevice(
            serial="PHYSICAL-USB-01",
            installed_packages={"com.android.chrome"},
        )
    )

    ldplayer = FakeLdPlayerProvider()
    mumu = FakeMuMuProvider()
    physical = FakePhysicalProvider()

    device_service = DeviceService(
        (ldplayer, mumu, physical),
        database.unit_of_work,
        SqlAlchemyDeviceProfileRepository,
        tmp_path / "artifacts",
    )

    service = RestoreWorkspaceService(
        database.unit_of_work,
        SqlAlchemyDeviceProfileRepository,
        account_service,
        device_service,
        adb,
        clock,
        providers=(ldplayer, mumu, physical),
    )

    yield service, account_service, adb, ldplayer, physical, database
    database.close()


def test_binding_persistence_and_retrieval(restore_env: RestoreEnv) -> None:
    service, account_service, _, _, _, _ = restore_env
    account = account_service.create_account("Alice", "alice-100", "alice@example.test")

    binding = service.bind_device(
        account_id=account.id,
        provider=DeviceProviderType.LDPLAYER,
        external_id="0",
        preferred_app=PreferredApp.FACEBOOK,
    )

    assert binding.account_id == account.id
    assert binding.preferred_app == PreferredApp.FACEBOOK
    assert binding.status == BindingStatus.ACTIVE

    retrieved = service.get_binding(account.id)
    assert retrieved is not None
    assert retrieved.device_profile_id == binding.device_profile_id
    assert retrieved.preferred_app == PreferredApp.FACEBOOK

    profile = service.get_profile(binding.device_profile_id)
    assert profile is not None
    assert profile.provider == DeviceProviderType.LDPLAYER
    assert profile.external_id == "0"
    assert profile.adb_serial == "emulator-5554"


def test_restore_successful_workflow(restore_env: RestoreEnv) -> None:
    service, account_service, adb, _, _, _ = restore_env
    account = account_service.create_account("Bob", "bob-200", "bob@example.test")
    service.bind_device(
        account_id=account.id,
        provider=DeviceProviderType.LDPLAYER,
        external_id="0",
        preferred_app=PreferredApp.FACEBOOK,
    )

    result = service.restore_workspace(account.id)

    assert result.success is True
    assert result.status == "restored"
    assert result.target_package == FACEBOOK_PACKAGE
    assert result.device_name != ""
    assert result.reauth_required is False

    # Check that heartbeat and last_used were updated
    binding = service.get_binding(account.id)
    assert binding is not None
    assert binding.last_used_at == NOW

    profile = service.get_profile(binding.device_profile_id)
    assert profile is not None
    assert profile.last_heartbeat == NOW


def test_restore_starts_offline_emulator(restore_env: RestoreEnv) -> None:
    service, account_service, adb, ldplayer, _, _ = restore_env
    account = account_service.create_account("Charlie", "charlie-300", "charlie@example.test")
    service.bind_device(
        account_id=account.id,
        provider=DeviceProviderType.LDPLAYER,
        external_id="1",
        preferred_app=PreferredApp.BROWSER,
    )

    # LDPlayer instance 1 is initially stopped/offline
    assert not ldplayer.list_instances()[1].is_running

    # Add package to simulated device when it starts
    adb.add_device(
        SimulatedDevice(
            serial="emulator-5556",
            installed_packages={"com.android.chrome"},
        )
    )

    result = service.restore_workspace(account.id)

    assert result.success is True
    assert ldplayer.list_instances()[1].is_running is True


def test_restore_offline_physical_device_fails_gracefully(restore_env: RestoreEnv) -> None:
    service, account_service, adb, _, physical, _ = restore_env
    account = account_service.create_account("Dana", "dana-400", "dana@example.test")
    service.bind_device(
        account_id=account.id,
        provider=DeviceProviderType.PHYSICAL,
        external_id="PHYSICAL-USB-01",
        preferred_app=PreferredApp.BROWSER,
    )

    # Disconnect physical device from ADB
    adb.remove_device("PHYSICAL-USB-01")

    result = service.restore_workspace(account.id)

    assert result.success is False
    assert result.status in ("device_offline", "adb_unreachable")
    assert "offline" in result.message.lower() or "not reachable" in result.message.lower()


def test_restore_missing_app_reports_failure(restore_env: RestoreEnv) -> None:
    service, account_service, adb, _, _, _ = restore_env
    account = account_service.create_account("Evan", "evan-500", "evan@example.test")
    # emulator-5554 has katana and chrome, but not facebook lite
    service.bind_device(
        account_id=account.id,
        provider=DeviceProviderType.LDPLAYER,
        external_id="0",
        preferred_app=PreferredApp.FACEBOOK_LITE,
    )

    result = service.restore_workspace(account.id)

    assert result.success is False
    assert result.status == "missing_app"
    assert result.target_package == FACEBOOK_LITE_PACKAGE
    assert "not installed" in result.message


def test_restore_requests_reauth_on_review_or_compromised(restore_env: RestoreEnv) -> None:
    from dataclasses import replace

    service, account_service, _, _, _, _ = restore_env
    account = account_service.create_account("Fiona", "fiona-600", "fiona@example.test")
    service.bind_device(
        account_id=account.id,
        provider=DeviceProviderType.LDPLAYER,
        external_id="0",
        preferred_app=PreferredApp.FACEBOOK,
    )

    # Set security state to review required
    updated = replace(account, security_state=SecurityState.REVIEW_REQUIRED)
    account_service.save_account(updated)

    result = service.restore_workspace(account.id)

    assert result.success is True
    assert result.reauth_required is True
    assert "re-authenticate" in result.message.lower()
