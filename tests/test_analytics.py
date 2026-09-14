"""Automated tests for Analytics domain, SqlAlchemy repository, and AnalyticsService."""

from datetime import UTC, datetime, timedelta

import pytest

from sp_farms.application.analytics_service import AnalyticsService
from sp_farms.domain.analytics import AggregatedMetrics, PostAnalyticsSnapshot
from sp_farms.domain.composer import PostType
from sp_farms.domain.publishing import PublishAttempt, PublishMethod, PublishStatus
from sp_farms.infrastructure.database import (
    Base,
    Database,
    SqlAlchemyAnalyticsRepository,
    SqlAlchemyPublishRepository,
)
from sp_farms.infrastructure.meta.analytics_adapter import FakeAnalyticsAdapter


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_analytics.db"
    database = Database(db_path)
    Base.metadata.create_all(database.engine)
    return database


@pytest.fixture
def fake_adapter():
    adapter = FakeAnalyticsAdapter()
    adapter.set_metrics(
        external_post_id="fb_post_999",
        likes=150,
        comments=25,
        shares=10,
        views=800,
        impressions=2500,
        reach=1800,
    )
    return adapter


def test_analytics_snapshot_domain_metrics():
    snap = PostAnalyticsSnapshot(
        id="snap-1",
        external_post_id="post-100",
        account_id="acc-1",
        destination_id="page-1",
        destination_name="Farm Page",
        post_type=PostType.FEED,
        likes_count=100,
        comments_count=20,
        shares_count=5,
        reach_count=1000,
    )

    assert snap.total_interactions == 125
    # engagement_rate = (125 / 1000) * 100 = 12.5%
    assert snap.engagement_rate == 12.5


def test_analytics_repository_crud_and_aggregates(db):
    uow_factory = db.unit_of_work

    snap1 = PostAnalyticsSnapshot(
        id="snap-101",
        external_post_id="post-101",
        account_id="acc-1",
        destination_id="dest-page-1",
        destination_name="Page 1",
        post_type=PostType.FEED,
        likes_count=50,
        comments_count=10,
        shares_count=2,
        reach_count=500,
    )

    snap2 = PostAnalyticsSnapshot(
        id="snap-102",
        external_post_id="post-102",
        account_id="acc-1",
        destination_id="dest-page-1",
        destination_name="Page 1",
        post_type=PostType.REEL,
        likes_count=150,
        comments_count=30,
        shares_count=18,
        reach_count=1500,
    )

    with uow_factory() as uow:
        repo = SqlAlchemyAnalyticsRepository(uow)
        repo.save_snapshot(snap1)
        repo.save_snapshot(snap2)
        uow.commit()

    with uow_factory() as uow:
        repo = SqlAlchemyAnalyticsRepository(uow)
        fetched = repo.get_snapshot("snap-101")
        assert fetched is not None
        assert fetched.likes_count == 50

        latest = repo.get_latest_by_post("post-102")
        assert latest is not None
        assert latest.post_type == PostType.REEL

        all_snaps = repo.list_snapshots(destination_id="dest-page-1")
        assert len(all_snaps) == 2

        aggregates = repo.get_aggregated_metrics(destination_id="dest-page-1")
        assert aggregates.total_posts == 2
        assert aggregates.total_likes == 200
        assert aggregates.total_comments == 40
        assert aggregates.total_shares == 20
        assert aggregates.total_reach == 2000
        assert aggregates.total_interactions == 260
        # 260 / 2000 * 100 = 13.0%
        assert aggregates.average_engagement_rate == 13.0


def test_analytics_service_sync_post(db, fake_adapter):
    service = AnalyticsService(
        analytics_port=fake_adapter,
        unit_of_work=db.unit_of_work,
        analytics_repo_factory=lambda uow: SqlAlchemyAnalyticsRepository(uow),
    )

    snap = service.sync_post_metrics(
        external_post_id="fb_post_999",
        access_token="valid_token",
        account_id="acc-prod-1",
        destination_id="dest-page-999",
        destination_name="Production Page",
        post_type=PostType.FEED,
    )

    assert snap.external_post_id == "fb_post_999"
    assert snap.likes_count == 150
    assert snap.comments_count == 25
    assert snap.shares_count == 10
    assert snap.reach_count == 1800

    summary = service.get_summary(destination_id="dest-page-999")
    assert summary.total_posts == 1
    assert summary.total_likes == 150


def test_analytics_service_sync_recent_published_posts(db, fake_adapter):
    # Seed a published attempt
    attempt = PublishAttempt.create(
        destination_type=PostType.FEED,  # will be converted or saved
        destination_id="dest-page-auto",
        destination_name="Auto Page",
        post_type=PostType.FEED,
        payload={"caption": "Hello world"},
    ).mark_published(external_post_id="fb_post_999")

    with db.unit_of_work() as uow:
        p_repo = SqlAlchemyPublishRepository(uow)
        p_repo.save(attempt)
        uow.commit()

    service = AnalyticsService(
        analytics_port=fake_adapter,
        unit_of_work=db.unit_of_work,
        analytics_repo_factory=lambda uow: SqlAlchemyAnalyticsRepository(uow),
        publish_repo_factory=lambda uow: SqlAlchemyPublishRepository(uow),
    )

    synced = service.sync_recent_published_posts(
        token_resolver=lambda dest_id: "token_for_" + dest_id
    )

    assert len(synced) == 1
    assert synced[0].external_post_id == "fb_post_999"
    assert synced[0].likes_count == 150
