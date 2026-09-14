import json
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sp_farms.application.account_onboarding_service import AccountOnboardingService
from sp_farms.application.account_service import AccountService
from sp_farms.domain.account_onboarding import (
    AccountOnboardingRequest,
    OnboardingSource,
    mask_email,
    mask_phone,
)
from sp_farms.domain.accounts import PreferredApp
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyAccountRepository,
    run_migrations,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
NOW = datetime(2026, 9, 2, 12, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


@pytest.fixture
def onboarding(
    tmp_path: Path,
) -> Generator[tuple[AccountOnboardingService, AccountService, Database], None, None]:
    database = Database(tmp_path / "onboarding.db")
    run_migrations(database, MIGRATIONS)
    accounts = AccountService(
        database.unit_of_work,
        SqlAlchemyAccountRepository,
        FixedClock(),
    )
    yield AccountOnboardingService(accounts), accounts, database
    database.close()


def test_manual_onboarding_is_immediately_available(
    onboarding: tuple[AccountOnboardingService, AccountService, Database],
) -> None:
    service, accounts, _database = onboarding

    created = service.onboard(
        AccountOnboardingRequest(
            source=OnboardingSource.MANUAL,
            display_name="  Ada Account  ",
            platform_uid="fb-001",
            primary_email="ada@example.com",
            first_name="Ada",
            recovery_email="recovery@example.com",
            phone="+1 (202) 555-0123",
            country="US",
            locale="en_US",
            preferred_app=PreferredApp.FACEBOOK,
        )
    )

    assert created.display_name == "Ada Account"
    assert created.phone == "+12025550123"
    assert created.preferred_app is PreferredApp.FACEBOOK
    assert accounts.get_account(created.id) == created


def test_imports_strict_versioned_authorized_metadata(
    onboarding: tuple[AccountOnboardingService, AccountService, Database],
) -> None:
    service, _accounts, _database = onboarding
    payload = json.dumps(
        {
            "schema_version": 1,
            "source": "authorized_metadata_import",
            "account": {
                "display_name": "Imported",
                "platform_uid": "fb-002",
                "primary_email": "imported@example.com",
                "preferred_app": "facebook_lite",
                "birthday": "1990-05-20",
                "last_verified_at": "2026-09-01T12:00:00+00:00",
                "page_count": 2,
            },
        }
    )

    account = service.import_metadata(payload)

    assert account.birthday is not None
    assert account.birthday.isoformat() == "1990-05-20"
    assert account.preferred_app is PreferredApp.FACEBOOK_LITE
    assert account.page_count == 2


@pytest.mark.parametrize(
    "onboarding_request, error",
    [
        (
            AccountOnboardingRequest(OnboardingSource.MANUAL, "", "fb-003", "valid@example.com"),
            "Display name",
        ),
        (
            AccountOnboardingRequest(OnboardingSource.MANUAL, "Invalid", "fb-003", "not-email"),
            "valid email",
        ),
        (
            AccountOnboardingRequest(
                OnboardingSource.MANUAL,
                "Same email",
                "fb-003",
                "same@example.com",
                recovery_email="same@example.com",
            ),
            "differ",
        ),
        (
            AccountOnboardingRequest(
                OnboardingSource.MANUAL,
                "Invalid phone",
                "fb-003",
                "valid@example.com",
                phone="123",
            ),
            "Phone",
        ),
    ],
)
def test_validates_manual_metadata(
    onboarding: tuple[AccountOnboardingService, AccountService, Database],
    onboarding_request: AccountOnboardingRequest,
    error: str,
) -> None:
    service, _accounts, _database = onboarding

    with pytest.raises(ValueError, match=error):
        service.onboard(onboarding_request)


@pytest.mark.parametrize(
    "document, error",
    [
        (
            {"schema_version": 2, "account": {}},
            "Unsupported metadata schema version",
        ),
        (
            {
                "schema_version": 1,
                "account": {
                    "display_name": "Secret",
                    "platform_uid": "fb-004",
                    "primary_email": "secret@example.com",
                    "password": "never-store-this",
                },
            },
            "Secret-bearing field",
        ),
        (
            {
                "schema_version": 1,
                "account": {
                    "display_name": "Unknown",
                    "platform_uid": "fb-004",
                    "primary_email": "unknown@example.com",
                    "mystery": True,
                },
            },
            "Unknown account field",
        ),
    ],
)
def test_rejects_unsafe_or_unknown_import_fields(
    onboarding: tuple[AccountOnboardingService, AccountService, Database],
    document: dict[str, object],
    error: str,
) -> None:
    service, _accounts, _database = onboarding

    with pytest.raises(ValueError, match=error):
        service.import_metadata(json.dumps(document))


def test_export_contains_metadata_only_and_round_trips(
    onboarding: tuple[AccountOnboardingService, AccountService, Database],
) -> None:
    service, _accounts, _database = onboarding
    account = service.onboard(
        AccountOnboardingRequest(
            OnboardingSource.DEVELOPMENT_TEST,
            "Test Account",
            "test-001",
            "test@example.test",
        )
    )

    payload = service.export_metadata(account.id)
    document = json.loads(payload)

    assert document["schema_version"] == 1
    assert document["account"]["platform_uid"] == "test-001"
    assert all(term not in payload.casefold() for term in ("password", "cookie", "token"))


def test_masks_contact_details() -> None:
    assert mask_email("alice@example.com") == "a***@example.com"
    assert mask_phone("+1 (202) 555-0123") == "***0123"
    assert mask_phone("") == "—"
