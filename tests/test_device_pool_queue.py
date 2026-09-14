from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sp_farms.application.account_service import AccountService
from sp_farms.application.device_pool_service import DevicePoolService
from sp_farms.application.device_service import DeviceService
from sp_farms.application.restore_workspace_service import RestoreWorkspaceService
from sp_farms.domain.accounts import PreferredApp
from sp_farms.domain.device_pool import SchedulingPolicy
from sp_farms.domain.providers import DeviceProviderType
from sp_farms.infrastructure.adb.fake import FakeAdbAdapter, SimulatedDevice
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyAccountRepository,
    SqlAlchemyDevicePoolRepository,
    SqlAlchemyDeviceProfileRepository,
    run_migrations,
)
from sp_farms.infrastructure.providers.ldplayer import FakeLdPlayerProvider
from sp_farms.infrastructure.providers.mumu import FakeMuMuProvider
from sp_farms.infrastructure.providers.physical import FakePhysicalProvider

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)


class MutableClock:
    def __init__(self, current: datetime = NOW) -> None:
        self.current = current

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)


PoolEnv = tuple[
    DevicePoolService,
    RestoreWorkspaceService,
    AccountService,
    MutableClock,
    Database,
]


@pytest.fixture
def pool_env(tmp_path: Path) -> Generator[PoolEnv, None, None]:
    database = Database(tmp_path / "pool_test.db")
    run_migrations(database, MIGRATIONS)
    clock = MutableClock()
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

    restore_service = RestoreWorkspaceService(
        database.unit_of_work,
        SqlAlchemyDeviceProfileRepository,
        account_service,
        device_service,
        adb,
        clock,
        providers=(ldplayer, mumu, physical),
    )

    pool_service = DevicePoolService(
        database.unit_of_work,
        SqlAlchemyDevicePoolRepository,
        SqlAlchemyAccountRepository,
        SqlAlchemyDeviceProfileRepository,
        device_service,
        restore_service,
        clock,
    )

    yield pool_service, restore_service, account_service, clock, database
    database.close()


def test_device_pool_discovery_and_availability(pool_env: PoolEnv) -> None:
    pool_service, _, _, _, _ = pool_env
    devices = pool_service.list_pool_devices()
    assert len(devices) == 6
    avail = pool_service.get_available_devices()
    assert len(avail) == 4


def test_atomic_device_lock_and_conflict_prevention(pool_env: PoolEnv) -> None:
    pool_service, _, accounts, _, _ = pool_env
    acct1 = accounts.create_account("User One", "uid-1", "user1@example.com")
    acct2 = accounts.create_account("User Two", "uid-2", "user2@example.com")

    lock1 = pool_service.acquire_device_lock(acct1.id, "ldplayer:emulator-5554", ttl_seconds=60)
    assert lock1 is not None
    assert lock1.account_id == acct1.id

    # Second account cannot acquire the same device while active
    lock2 = pool_service.acquire_device_lock(acct2.id, "ldplayer:emulator-5554", ttl_seconds=60)
    assert lock2 is None

    # Release lock
    released = pool_service.release_device_lock(acct1.id)
    assert released is True

    # Now second account can acquire
    lock2_again = pool_service.acquire_device_lock(
        acct2.id, "ldplayer:emulator-5554", ttl_seconds=60
    )
    assert lock2_again is not None
    assert lock2_again.account_id == acct2.id


def test_stale_lock_recovery(pool_env: PoolEnv) -> None:
    pool_service, _, accounts, clock, _ = pool_env
    acct = accounts.create_account("Stale User", "uid-stale", "stale@example.com")

    lock = pool_service.acquire_device_lock(acct.id, "ldplayer:emulator-5554", ttl_seconds=30)
    assert lock is not None

    # Advance clock past TTL
    clock.advance(35)
    recovered = pool_service.recover_stale_locks()
    assert recovered == 1

    # Device is now available again
    acct2 = accounts.create_account("Fresh User", "uid-fresh", "fresh@example.com")
    lock2 = pool_service.acquire_device_lock(acct2.id, "ldplayer:emulator-5554", ttl_seconds=60)
    assert lock2 is not None


def test_scheduling_policies(pool_env: PoolEnv) -> None:
    pool_service, restore_service, accounts, _, _ = pool_env
    acct = accounts.create_account("Test Policy User", "uid-policy", "policy@example.com")
    avail = pool_service.get_available_devices()

    # 1. Round Robin
    d1 = pool_service.select_device_for_account(acct.id, SchedulingPolicy.ROUND_ROBIN, avail)
    d2 = pool_service.select_device_for_account(acct.id, SchedulingPolicy.ROUND_ROBIN, avail)
    assert d1 != d2

    # 2. Bound Device First
    restore_service.bind_device(
        acct.id,
        DeviceProviderType.MUMU,
        "127.0.0.1:16384",
        PreferredApp.FACEBOOK_LITE,
    )
    d_bound = pool_service.select_device_for_account(
        acct.id, SchedulingPolicy.BOUND_DEVICE_FIRST, avail
    )
    assert d_bound is not None
    assert d_bound.provider == "mumu"

    # 3. Preferred Provider
    d_pref = pool_service.select_device_for_account(
        acct.id,
        SchedulingPolicy.PREFERRED_PROVIDER,
        avail,
        preferred_provider_order=("physical", "ldplayer"),
    )
    assert d_pref is not None
    assert d_pref.provider == "physical"


def test_queue_and_next_account_dispatch(pool_env: PoolEnv) -> None:
    pool_service, _, accounts, _, _ = pool_env
    acct_a = accounts.create_account("Account A", "uid-a", "a@example.com")
    acct_b = accounts.create_account("Account B", "uid-b", "b@example.com")

    items = pool_service.enqueue_restore([acct_a.id, acct_b.id], priority=10)
    assert len(items) == 2

    res1 = pool_service.dispatch_next()
    assert res1 is not None
    assert res1.success is True

    # Account A is now holding a device lock
    # When Account A is released, Account B is automatically restored
    rel, next_res = pool_service.release_device_and_restore_next(acct_a.id)
    assert rel is True
    assert next_res is not None
    assert next_res.success is True
    assert next_res.account_id == acct_b.id
