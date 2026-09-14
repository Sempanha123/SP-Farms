"""Application service orchestrating post performance metrics tracking and sync."""

import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from uuid import uuid4

from sp_farms.application.analytics_port import AnalyticsPort
from sp_farms.application.analytics_repository import AnalyticsRepositoryPort
from sp_farms.application.audit_service import AuditService
from sp_farms.application.publish_repository import PublishRepositoryPort
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.analytics import AggregatedMetrics, PostAnalyticsSnapshot
from sp_farms.domain.audit import AuditResult
from sp_farms.domain.composer import PostType
from sp_farms.domain.publishing import PublishStatus

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Synchronizes and aggregates engagement metrics across published posts."""

    def __init__(
        self,
        analytics_port: AnalyticsPort,
        unit_of_work: Callable[[], UnitOfWork] | None = None,
        analytics_repo_factory: Callable[[UnitOfWork], AnalyticsRepositoryPort] | None = None,
        publish_repo_factory: Callable[[UnitOfWork], PublishRepositoryPort] | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        self._port = analytics_port
        self._uow = unit_of_work
        self._analytics_repo_factory = analytics_repo_factory
        self._publish_repo_factory = publish_repo_factory
        self._audit_service = audit_service

    def sync_post_metrics(
        self,
        external_post_id: str,
        access_token: str,
        account_id: str,
        destination_id: str,
        destination_name: str,
        post_type: PostType = PostType.FEED,
        publish_attempt_id: str | None = None,
    ) -> PostAnalyticsSnapshot:
        """Fetch latest metrics for an individual post and record a snapshot."""
        data = self._port.fetch_post_metrics(external_post_id, access_token)
        snapshot = PostAnalyticsSnapshot(
            id=str(uuid4()),
            external_post_id=external_post_id,
            account_id=account_id,
            destination_id=destination_id,
            destination_name=destination_name,
            post_type=post_type,
            publish_attempt_id=publish_attempt_id,
            likes_count=int(data.get("likes_count", data.get("likes", 0))),
            comments_count=int(data.get("comments_count", data.get("comments", 0))),
            shares_count=int(data.get("shares_count", data.get("shares", 0))),
            views_count=int(data.get("views_count", data.get("views", 0))),
            impressions_count=int(data.get("impressions_count", data.get("impressions", 0))),
            reach_count=int(data.get("reach_count", data.get("reach", 0))),
            synced_at=datetime.now(UTC),
        )

        if self._uow and self._analytics_repo_factory:
            with self._uow() as uow:
                repo = self._analytics_repo_factory(uow)
                repo.save_snapshot(snapshot)
                uow.commit()

        if self._audit_service:
            self._audit_service.record_event(
                action="analytics.sync.post",
                target_id=external_post_id,
                result=AuditResult.SUCCESS,
                details={
                    "snapshot_id": snapshot.id,
                    "external_post_id": external_post_id,
                    "likes": snapshot.likes_count,
                    "comments": snapshot.comments_count,
                    "shares": snapshot.shares_count,
                    "reach": snapshot.reach_count,
                },
            )

        return snapshot

    def sync_recent_published_posts(
        self,
        token_resolver: Callable[[str], str],
        limit: int = 50,
    ) -> list[PostAnalyticsSnapshot]:
        """Automatically sync performance metrics for recently published attempts."""
        if not (self._uow and self._publish_repo_factory):
            return []

        published_attempts = []
        with self._uow() as uow:
            p_repo = self._publish_repo_factory(uow)
            published_attempts = list(p_repo.list_recent(limit=limit, status=PublishStatus.PUBLISHED))

        snapshots = []
        for attempt in published_attempts:
            if not attempt.external_post_id:
                continue
            token = token_resolver(attempt.destination_id)
            if not token:
                continue
            try:
                snap = self.sync_post_metrics(
                    external_post_id=attempt.external_post_id,
                    access_token=token,
                    account_id="acc-default",
                    destination_id=attempt.destination_id,
                    destination_name=attempt.destination_name,
                    post_type=attempt.post_type,
                    publish_attempt_id=attempt.id,
                )
                snapshots.append(snap)
            except Exception as e:
                logger.warning("Failed syncing metrics for post %s: %s", attempt.external_post_id, e)

        return snapshots

    def get_summary(
        self,
        destination_id: str | None = None,
        account_id: str | None = None,
        since: datetime | None = None,
    ) -> AggregatedMetrics:
        """Get aggregate metrics across all tracked posts."""
        if not (self._uow and self._analytics_repo_factory):
            return AggregatedMetrics()

        with self._uow() as uow:
            repo = self._analytics_repo_factory(uow)
            return repo.get_aggregated_metrics(
                destination_id=destination_id,
                account_id=account_id,
                since=since,
            )

    def list_recent_snapshots(
        self,
        destination_id: str | None = None,
        account_id: str | None = None,
        post_type: PostType | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> Sequence[PostAnalyticsSnapshot]:
        if not (self._uow and self._analytics_repo_factory):
            return ()

        with self._uow() as uow:
            repo = self._analytics_repo_factory(uow)
            return repo.list_snapshots(
                destination_id=destination_id,
                account_id=account_id,
                post_type=post_type,
                since=since,
                limit=limit,
            )
