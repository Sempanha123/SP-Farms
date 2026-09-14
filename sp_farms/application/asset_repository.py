from collections.abc import Sequence
from typing import Protocol

from sp_farms.domain.assets import Group, Page


class AssetRepository(Protocol):
    """Abstraction for persisting and querying authorized Pages and Groups."""

    def save_page(self, page: Page) -> None:
        """Upsert a Page entity."""
        ...

    def get_page(self, id: str) -> Page | None:
        """Fetch Page by local database ID."""
        ...

    def get_page_by_meta_id(self, account_id: str, page_id: str) -> Page | None:
        """Fetch Page by account and Meta Page ID."""
        ...

    def list_pages_by_account(self, account_id: str) -> list[Page]:
        """List all Pages authorized for an account."""
        ...

    def delete_page(self, id: str) -> None:
        """Remove Page record."""
        ...

    def save_group(self, group: Group) -> None:
        """Upsert a Group entity."""
        ...

    def get_group(self, id: str) -> Group | None:
        """Fetch Group by local database ID."""
        ...

    def get_group_by_meta_id(self, account_id: str, group_id: str) -> Group | None:
        """Fetch Group by account and Meta Group ID."""
        ...

    def list_groups_by_account(self, account_id: str) -> list[Group]:
        """List all Groups associated with an account."""
        ...

    def delete_group(self, id: str) -> None:
        """Remove Group record."""
        ...

    def mark_missing_pages_stale(self, account_id: str, active_page_ids: Sequence[str]) -> int:
        """Mark pages no longer returned by the Meta API as STALE or REVOKED."""
        ...

    def mark_missing_groups_stale(self, account_id: str, active_group_ids: Sequence[str]) -> int:
        """Mark groups no longer returned by the Meta API as STALE or REVOKED."""
        ...
