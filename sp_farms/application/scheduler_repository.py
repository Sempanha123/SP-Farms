"""Port definition for scheduled items repository."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from sp_farms.domain.scheduler import ScheduledItem, ScheduledItemStatus


class ScheduledItemRepositoryPort(Protocol):
    def save_item(self, item: ScheduledItem) -> ScheduledItem: ...
    def get_item(self, item_id: str) -> ScheduledItem | None: ...
    def list_items(
        self,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        destination_id: str | None = None,
        status: ScheduledItemStatus | None = None,
        limit: int = 200,
    ) -> Sequence[ScheduledItem]: ...
    def delete_item(self, item_id: str) -> bool: ...
    def list_due_items(self, now: datetime, limit: int = 50) -> Sequence[ScheduledItem]: ...
    def list_missed_items(
        self, now: datetime, grace_period_minutes: int = 15
    ) -> Sequence[ScheduledItem]: ...
