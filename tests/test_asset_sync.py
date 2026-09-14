from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from sp_farms.application.asset_sync_service import AssetSyncService
from sp_farms.application.ports import Clock
from sp_farms.application.secret_service import SecretService
from sp_farms.application.vault import Vault
from sp_farms.domain.accounts import Account
from sp_farms.domain.assets import (
    AssetHealthState,
    AssetPermission,
    Group,
    Page,
)
from sp_farms.domain.meta import MetaErrorCode, MetaRateLimitError
from sp_farms.domain.secrets import SecretType
from sp_farms.infrastructure.assets_repository import SqlAlchemyAssetRepository
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyAccountRepository,
    SqlAlchemySecretRepository,
    run_migrations,
)
from sp_farms.infrastructure.meta.fake_client import FakeMetaApiClient


class MemoryVault(Vault):
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def store(self, key: str, secret: str) -> None:
        self._store[key] = secret

    def retrieve(self, key: str) -> str | None:
        return self._store.get(key)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


class FixedClock(Clock):
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, td: timedelta) -> None:
        self._now = self._now + td


@pytest.fixture
def test_db(tmp_path: Any) -> Database:
    db_path = tmp_path / "test_assets.db"
    db = Database(db_path)
    from pathlib import Path

    migrations_path = Path(__file__).resolve().parents[1] / "migrations"
    run_migrations(db, migrations_path)
    return db


@pytest.fixture
def secret_service() -> SecretService:
    return SecretService(MemoryVault())


def test_asset_domain_eligibility_and_stale() -> None:
    now = datetime.now(UTC)
    # Page with MANAGE task -> publishing eligible
    p1 = Page(
        id=str(uuid4()),
        account_id="acc-1",
        page_id="p-101",
        name="Main Page",
        tasks=("MANAGE", "ANALYZE"),
        can_publish=True,
        health=AssetHealthState.HEALTHY,
        last_synced_at=now,
    )
    assert p1.is_publishing_eligible()
    assert not p1.is_stale()
    assert p1.has_task(AssetPermission.MANAGE)
    assert not p1.has_task(AssetPermission.MODERATE)

    # Page with only ANALYZE task -> not publishing eligible
    p2 = Page(
        id=str(uuid4()),
        account_id="acc-1",
        page_id="p-102",
        name="Readonly Page",
        tasks=("ANALYZE",),
        can_publish=True,
        health=AssetHealthState.HEALTHY,
        last_synced_at=now - timedelta(hours=30),
    )
    assert not p2.is_publishing_eligible()
    assert p2.is_stale(threshold_hours=24)

    # Group roles & eligibility
    g1 = Group(
        id=str(uuid4()),
        account_id="acc-1",
        group_id="g-201",
        name="Admin Group",
        role="ADMIN",
        health=AssetHealthState.HEALTHY,
        last_synced_at=now,
    )
    assert g1.is_admin()
    assert g1.is_moderator()
    assert g1.is_posting_eligible()

    g2 = Group(
        id=str(uuid4()),
        account_id="acc-1",
        group_id="g-202",
        name="Restricted Group",
        role="MEMBER",
        can_post=False,
        health=AssetHealthState.RESTRICTED,
        last_synced_at=None,
    )
    assert not g2.is_admin()
    assert not g2.is_posting_eligible()
    assert g2.is_stale()


def test_fake_meta_sync_and_persistence(test_db: Database, secret_service: SecretService) -> None:
    now = datetime.now(UTC)
    clock = FixedClock(now)
    fake_client = FakeMetaApiClient()

    # Pre-seed account with an access token in vault
    acc = Account.create(
        display_name="Asset Sync Tester",
        platform_uid="fb-uid-tester",
        primary_email="tester@spfarms.local",
        now=now,
    )
    with test_db.unit_of_work() as uow:
        SqlAlchemyAccountRepository(uow).save_account(acc)
        uow.commit()
    account_id = acc.id

    # Create token reference in secret repository
    secret_ref = secret_service.create_reference(
        secret_type=SecretType.ACCESS_TOKEN,
        owner_id=account_id,
        value="EAA_valid_sync_token",
    )
    with test_db.unit_of_work() as uow:
        SqlAlchemySecretRepository(uow).save(secret_ref)
        uow.commit()

    service = AssetSyncService(
        unit_of_work=test_db.unit_of_work,
        asset_repository_factory=SqlAlchemyAssetRepository,
        meta_client=fake_client,
        secret_service=secret_service,
        secret_repository_factory=SqlAlchemySecretRepository,
        clock=clock,
    )

    # 1. First synchronization
    result = service.sync_account_assets(account_id)
    assert result.is_successful
    assert result.synced_pages_count == 1
    assert result.synced_groups_count == 1
    assert result.stale_pages_count == 0

    pages = service.list_account_pages(account_id)
    assert len(pages) == 1
    page = pages[0]
    assert page.page_id == "page-101"
    assert page.name == "SP Farms Official"
    assert page.is_publishing_eligible()
    assert page.access_token_ref is not None  # Vaulted page access token

    groups = service.list_account_groups(account_id)
    assert len(groups) == 1
    group = groups[0]
    assert group.group_id == "group-202"
    assert group.name == "SP Farms Community"
    assert group.is_admin()

    # 2. Incremental update: Meta client adds a page and updates followers
    fake_client.simulated_pages.append(
        {
            "id": "page-102",
            "name": "SP Farms Livestock",
            "category": "Farming",
            "tasks": ["MODERATE"],
            "fan_count": 300,
            "followers_count": 350,
        }
    )
    fake_client.simulated_pages[0]["followers_count"] = 1500

    result2 = service.sync_account_assets(account_id)
    assert result2.is_successful
    assert result2.synced_pages_count == 2
    assert result2.stale_pages_count == 0

    pages2 = service.list_account_pages(account_id)
    assert len(pages2) == 2
    p1 = next(p for p in pages2 if p.page_id == "page-101")
    assert p1.followers_count == 1500
    p2 = next(p for p in pages2 if p.page_id == "page-102")
    assert p2.name == "SP Farms Livestock"
    assert not p2.is_publishing_eligible()

    eligible_pages = service.get_publishing_eligible_pages(account_id)
    assert len(eligible_pages) == 1
    assert eligible_pages[0].page_id == "page-101"


def test_asset_stale_and_removal_detection(
    test_db: Database, secret_service: SecretService
) -> None:
    now = datetime.now(UTC)
    clock = FixedClock(now)
    fake_client = FakeMetaApiClient()

    acc = Account.create(
        display_name="Stale Test Account",
        platform_uid="fb-uid-stale",
        primary_email="stale@spfarms.local",
        now=now,
    )
    with test_db.unit_of_work() as uow:
        SqlAlchemyAccountRepository(uow).save_account(acc)
        uow.commit()
    account_id = acc.id

    service = AssetSyncService(
        unit_of_work=test_db.unit_of_work,
        asset_repository_factory=SqlAlchemyAssetRepository,
        meta_client=fake_client,
        secret_service=secret_service,
        secret_repository_factory=SqlAlchemySecretRepository,
        clock=clock,
    )

    # Initial sync with page-101 and group-202
    service.sync_account_assets(account_id, access_token="mock_token")
    assert len(service.list_account_pages(account_id)) == 1
    assert len(service.list_account_groups(account_id)) == 1

    # Meta client removes page-101 (e.g. admin access revoked on Facebook)
    fake_client.simulated_pages = []
    result = service.sync_account_assets(account_id, access_token="mock_token")
    assert result.is_successful
    assert result.synced_pages_count == 0
    assert result.stale_pages_count == 1

    pages = service.list_account_pages(account_id)
    assert len(pages) == 1
    assert pages[0].health == AssetHealthState.STALE
    assert not pages[0].is_publishing_eligible()


def test_partial_api_failure_handling(
    test_db: Database, secret_service: SecretService, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)
    clock = FixedClock(now)
    fake_client = FakeMetaApiClient()

    acc = Account.create(
        display_name="Error Test Account",
        platform_uid="fb-uid-error",
        primary_email="error@spfarms.local",
        now=now,
    )
    with test_db.unit_of_work() as uow:
        SqlAlchemyAccountRepository(uow).save_account(acc)
        uow.commit()
    account_id = acc.id

    # Make get_user_groups fail with Rate Limit error while pages succeed
    def mock_failing_groups(token: str) -> list[dict[str, Any]]:
        raise MetaRateLimitError(
            "User request rate limit exceeded",
            code=MetaErrorCode.RATE_LIMIT_EXCEEDED,
            status_code=429,
            retry_after_seconds=60.0,
        )

    monkeypatch.setattr(fake_client, "get_user_groups", mock_failing_groups)

    service = AssetSyncService(
        unit_of_work=test_db.unit_of_work,
        asset_repository_factory=SqlAlchemyAssetRepository,
        meta_client=fake_client,
        secret_service=secret_service,
        secret_repository_factory=SqlAlchemySecretRepository,
        clock=clock,
    )

    result = service.sync_account_assets(account_id, access_token="mock_token")
    assert not result.is_successful
    assert result.has_partial_failure
    assert result.synced_pages_count == 1
    assert result.synced_groups_count == 0
    assert len(result.errors) == 1
    assert "User request rate limit exceeded" in result.errors[0]

    # Pages were still committed and accessible
    pages = service.list_account_pages(account_id)
    assert len(pages) == 1
    assert pages[0].page_id == "page-101"
