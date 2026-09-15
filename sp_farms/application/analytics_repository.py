"""Repository port for social media post analytics snapshots and aggregate metrics."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from sp_farms.domain.analytics import AggregatedMetrics, PostAnalyticsSnapshot
from sp_farms.domain.composer import PostType


class AnalyticsRepositoryPort(Protocol):
    """Port interface for persisting and querying post engagement analytics."""

    def save_snapshot(self, snapshot: PostAnalyticsSnapshot) -> None:
        """Persist or update an analytics snapshot."""
        ...

    def get_snapshot(self, snapshot_id: str) -> PostAnalyticsSnapshot | None:
        """Retrieve a snapshot by ID."""
        ...

    def get_latest_by_post(self, external_post_id: str) -> PostAnalyticsSnapshot | None:
        """Retrieve the latest metrics snapshot for a specific post."""
        ...

    def list_snapshots(
        self,
        destination_id: str | None = None,
        account_id: str | None = None,
        post_type: PostType | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> Sequence[PostAnalyticsSnapshot]:
        """List snapshots matching criteria ordered by synced_at desc."""
        ...

    def get_aggregated_metrics(
        self,
        destination_id: str | None = None,
        account_id: str | None = None,
        since: datetime | None = None,
    ) -> AggregatedMetrics:
        """Compute aggregated engagement totals across matching snapshots."""
        ...
