from collections.abc import Callable
from typing import TYPE_CHECKING
from uuid import uuid4

from sp_farms.application.asset_repository import AssetRepository
from sp_farms.application.meta_client import MetaClientPort
from sp_farms.application.ports import Clock
from sp_farms.application.secret_service import SecretService
from sp_farms.application.secrets import SecretRepository
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.assets import AssetHealthState, Group, Page, SyncResult
from sp_farms.domain.meta import MetaApiError
from sp_farms.domain.secrets import SecretType
from sp_farms.infrastructure.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("assets.sync")


class AssetSyncService:
    """Synchronizes authorized Facebook Pages and Groups for managed accounts."""

    def __init__(
        self,
        unit_of_work: Callable[[], UnitOfWork],
        asset_repository_factory: Callable[[UnitOfWork], AssetRepository],
        meta_client: MetaClientPort,
        secret_service: SecretService,
        secret_repository_factory: Callable[[UnitOfWork], SecretRepository],
        clock: Clock,
    ) -> None:
        self._uow = unit_of_work
        self._asset_repo_factory = asset_repository_factory
        self._client = meta_client
        self._secrets = secret_service
        self._secret_repo_factory = secret_repository_factory
        self._clock = clock

    def sync_account_assets(
        self,
        account_id: str,
        access_token: str | None = None,
    ) -> SyncResult:
        """Fetch latest Pages and Groups for account, update status, and track stale assets."""
        token = access_token or self._resolve_account_token(account_id)
        if not token:
            return SyncResult(
                account_id=account_id,
                errors=("No authorized Meta access token found for account.",),
            )

        errors: list[str] = []
        synced_pages = 0
        synced_groups = 0
        stale_pages = 0
        stale_groups = 0
        now = self._clock.now()

        # 1. Synchronize Facebook Pages
        try:
            raw_pages = self._client.get_accounts_pages(token)
            with self._uow() as uow:
                repo = self._asset_repo_factory(uow)
                active_page_ids: list[str] = []

                for item in raw_pages:
                    meta_page_id = str(item.get("id", ""))
                    if not meta_page_id:
                        continue
                    active_page_ids.append(meta_page_id)

                    raw_tasks = item.get("tasks", [])
                    tasks_tuple = tuple(str(t) for t in raw_tasks)
                    can_publish = "MANAGE" in tasks_tuple or "CREATE_CONTENT" in tasks_tuple

                    existing_page = repo.get_page_by_meta_id(account_id, meta_page_id)
                    page_token = item.get("access_token")
                    token_ref = existing_page.access_token_ref if existing_page else None

                    # If page provides its own page token, vault it
                    if page_token:
                        secret_ref = self._secrets.create_reference(
                            secret_type=SecretType.ACCESS_TOKEN,
                            owner_id=f"page:{meta_page_id}",
                            value=page_token,
                        )
                        sec_repo = self._secret_repo_factory(uow)
                        sec_repo.save(secret_ref)
                        token_ref = secret_ref.id

                    page_entity = Page(
                        id=existing_page.id if existing_page else str(uuid4()),
                        account_id=account_id,
                        page_id=meta_page_id,
                        name=str(item.get("name", "Unnamed Page")),
                        category=item.get("category"),
                        tasks=tasks_tuple,
                        access_token_ref=token_ref,
                        can_publish=can_publish,
                        followers_count=int(item.get("followers_count", 0)),
                        likes_count=int(item.get("fan_count", 0)),
                        link=item.get("link"),
                        health=AssetHealthState.HEALTHY,
                        last_synced_at=now,
                        created_at=existing_page.created_at if existing_page else now,
                        updated_at=now,
                    )
                    repo.save_page(page_entity)
                    synced_pages += 1

                stale_pages = repo.mark_missing_pages_stale(account_id, active_page_ids)
                uow.commit()

        except MetaApiError as exc:
            logger.error("Failed to sync Pages for account %s: %s", account_id, exc)
            errors.append(f"Pages sync error: {exc.message}")
        except Exception as exc:
            logger.error("Unexpected failure syncing Pages for account %s: %s", account_id, exc)
            errors.append(f"Pages sync error: {exc}")

        # 2. Synchronize Facebook Groups
        try:
            raw_groups = self._client.get_user_groups(token)
            with self._uow() as uow:
                repo = self._asset_repo_factory(uow)
                active_group_ids: list[str] = []

                for item in raw_groups:
                    meta_group_id = str(item.get("id", ""))
                    if not meta_group_id:
                        continue
                    active_group_ids.append(meta_group_id)

                    is_admin = bool(item.get("administrator", False))
                    role = "ADMIN" if is_admin else "MEMBER"
                    privacy = str(item.get("privacy", "PUBLIC"))

                    existing_group = repo.get_group_by_meta_id(account_id, meta_group_id)
                    group_entity = Group(
                        id=existing_group.id if existing_group else str(uuid4()),
                        account_id=account_id,
                        group_id=meta_group_id,
                        name=str(item.get("name", "Unnamed Group")),
                        privacy=privacy,
                        role=role,
                        member_count=int(item.get("member_count", 0)),
                        can_post=True,
                        health=AssetHealthState.HEALTHY,
                        last_synced_at=now,
                        created_at=existing_group.created_at if existing_group else now,
                        updated_at=now,
                    )
                    repo.save_group(group_entity)
                    synced_groups += 1

                stale_groups = repo.mark_missing_groups_stale(account_id, active_group_ids)
                uow.commit()

        except MetaApiError as exc:
            logger.error("Failed to sync Groups for account %s: %s", account_id, exc)
            errors.append(f"Groups sync error: {exc.message}")
        except Exception as exc:
            logger.error("Unexpected failure syncing Groups for account %s: %s", account_id, exc)
            errors.append(f"Groups sync error: {exc}")

        return SyncResult(
            account_id=account_id,
            synced_pages_count=synced_pages,
            synced_groups_count=synced_groups,
            stale_pages_count=stale_pages,
            stale_groups_count=stale_groups,
            errors=tuple(errors),
        )

    def list_account_pages(self, account_id: str) -> list[Page]:
        """List all Pages for account."""
        with self._uow() as uow:
            repo = self._asset_repo_factory(uow)
            return repo.list_pages_by_account(account_id)

    def list_account_groups(self, account_id: str) -> list[Group]:
        """List all Groups for account."""
        with self._uow() as uow:
            repo = self._asset_repo_factory(uow)
            return repo.list_groups_by_account(account_id)

    def get_publishing_eligible_pages(self, account_id: str) -> list[Page]:
        """Return all healthy pages with publishing privileges."""
        pages = self.list_account_pages(account_id)
        return [p for p in pages if p.is_publishing_eligible()]

    def get_publishing_eligible_groups(self, account_id: str) -> list[Group]:
        """Return all healthy groups where account can post."""
        groups = self.list_account_groups(account_id)
        return [g for g in groups if g.is_posting_eligible()]

    def _resolve_account_token(self, account_id: str) -> str | None:
        """Query secret repository for the account's Meta access token and reveal it from vault."""
        with self._uow() as uow:
            sec_repo = self._secret_repo_factory(uow)
            refs = sec_repo.list_by_owner_ids([account_id])
            token_refs = [r for r in refs if r.secret_type == SecretType.ACCESS_TOKEN]
            if not token_refs:
                return None
            # Use most recently updated token
            latest_ref = max(token_refs, key=lambda r: r.updated_at)
            return self._secrets.reveal(latest_ref)
