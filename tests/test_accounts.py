from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from sp_farms.application.account_service import AccountService
from sp_farms.domain.accounts import (
    Account,
    AccountGender,
    AccountHealthState,
    AccountStatus,
    PermissionState,
    PreferredApp,
    SecurityState,
    calculate_account_health,
)
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyAccountRepository,
    run_migrations,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


@pytest.fixture
def accounts(tmp_path: Path) -> tuple[AccountService, Database]:
    database = Database(tmp_path / "accounts.db")
    run_migrations(database, MIGRATIONS)
    service = AccountService(
        database.unit_of_work,
        SqlAlchemyAccountRepository,
        FixedClock(),
    )
    yield service, database
    database.close()


def test_repository_round_trips_rich_metadata(
    accounts: tuple[AccountService, Database],
) -> None:
    service, _database = accounts
    category = service.create_category("Managed", "mint")
    account = service.create_account("Ada Account", "platform-001", "ada@example.test")
    account = service.save_account(
        replace(
            account,
            avatar_ref="avatar/ada.png",
            first_name="Ada",
            last_name="Lovelace",
            birthday=date(1990, 12, 10),
            gender=AccountGender.FEMALE,
            recovery_email="recovery@example.test",
            phone="+12025550123",
            country="US",
            locale="en_US",
            timezone="America/New_York",
            account_created_at=NOW,
            status=AccountStatus.ACTIVE,
            two_factor_enabled=True,
            category_id=category.id,
            notes="Operator-owned account",
            preferred_app=PreferredApp.FACEBOOK,
            last_login_at=NOW,
            last_verified_at=NOW,
            page_count=3,
            group_count=4,
            permission_state=PermissionState.COMPLETE,
            security_state=SecurityState.SECURE,
        )
    )

    restored = service.get_account(account.id)

    assert restored == account
    assert restored.birthday == date(1990, 12, 10)
    assert restored.category_id == category.id
    assert restored.page_count == 3


def test_category_tag_assignment_and_removal(
    accounts: tuple[AccountService, Database],
) -> None:
    service, _database = accounts
    account = service.create_account("Tagged", "platform-002", "tagged@example.test")
    first = service.create_tag("Priority", "amber")
    second = service.create_tag("Verified", "mint")

    tagged = service.set_tags(account.id, (first.id, second.id))
    assert set(tagged.tag_ids) == {first.id, second.id}

    reduced = service.set_tags(account.id, (second.id,))
    assert reduced.tag_ids == (second.id,)
    assert [tag.name for tag in service.list_tags()] == ["Priority", "Verified"]


def test_device_assignment_is_stable_and_reassigns_ownership(
    accounts: tuple[AccountService, Database],
) -> None:
    service, _database = accounts
    first = service.create_account("First", "platform-003", "first@example.test")
    second = service.create_account("Second", "platform-004", "second@example.test")

    service.assign_device(first.id, "ldplayer", "0")
    assigned = service.assign_device(second.id, "ldplayer", "0")

    assert assigned.assigned_device is not None
    assert assigned.assigned_device.external_id == "0"
    assert service.get_account(first.id).assigned_device is None


def test_health_rules_are_deterministic() -> None:
    account = replace(
        Account.create("Health", "platform-005", "health@example.test", NOW),
        first_name="Health",
        country="US",
        locale="en_US",
        two_factor_enabled=True,
        last_verified_at=NOW,
        permission_state=PermissionState.COMPLETE,
        security_state=SecurityState.SECURE,
    )
    healthy = calculate_account_health(account)
    attention = calculate_account_health(
        replace(account, status=AccountStatus.ATTENTION, two_factor_enabled=False)
    )
    critical = calculate_account_health(
        replace(account, security_state=SecurityState.COMPROMISED)
    )

    assert healthy.score == 95
    assert healthy.state is AccountHealthState.HEALTHY
    assert attention.state is AccountHealthState.ATTENTION
    assert critical.state is AccountHealthState.CRITICAL
    assert "Security state is compromised" in critical.reasons


def test_archive_excludes_active_listing_and_preserves_relations(
    accounts: tuple[AccountService, Database],
) -> None:
    service, _database = accounts
    account = service.create_account("Archive", "platform-006", "archive@example.test")
    tag = service.create_tag("Keep", "neutral")
    service.set_tags(account.id, (tag.id,))
    service.assign_device(account.id, "physical", "serial-1")

    archived = service.archive_account(account.id)

    assert archived.archived_at == NOW
    assert service.list_accounts() == ()
    included = service.list_accounts(include_archived=True)
    assert len(included) == 1
    assert included[0].tag_ids == (tag.id,)
    assert included[0].assigned_device is not None
