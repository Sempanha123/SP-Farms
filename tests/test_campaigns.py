"""Tests for Phase 33 Campaign Manager."""

import tempfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from sp_farms.app.campaign_workspace import (
    CampaignWorkspace,
)
from sp_farms.application.campaign_service import CampaignService
from sp_farms.domain.campaigns import (
    ApprovalPolicy,
    Campaign,
    CampaignStatus,
    CampaignTarget,
    TargetStatus,
)
from sp_farms.domain.composer import PostType, PublishDestinationType
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyCampaignRepository,
    run_migrations,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def test_db():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_campaigns.db"
        db = Database(db_path)
        migrations_path = Path(__file__).resolve().parents[1] / "migrations"
        run_migrations(db, migrations_path)
        try:
            yield db
        finally:
            db.close()


def test_campaign_status_transitions_and_aggregation():
    """Test campaign creation, status transitions, and target aggregation."""
    c = Campaign.create(
        title="Black Friday Sale",
        post_type=PostType.FEED,
        caption="Huge discounts today only! 🚀",
        approval_policy=ApprovalPolicy.MANUAL,
    )
    assert c.status == CampaignStatus.DRAFT

    # Add targets
    t1 = CampaignTarget.create(
        campaign_id=c.id,
        destination_type=PublishDestinationType.PAGE,
        destination_id="p1",
        destination_name="Main Brand Page",
    )
    t2 = CampaignTarget.create(
        campaign_id=c.id,
        destination_type=PublishDestinationType.GROUP,
        destination_id="g1",
        destination_name="VIP Deals Group",
    )

    c_with_targets = Campaign(
        id=c.id,
        title=c.title,
        content_item_id=c.content_item_id,
        post_type=c.post_type,
        caption=c.caption,
        media_asset_ids=c.media_asset_ids,
        status=c.status,
        schedule_policy=c.schedule_policy,
        approval_policy=c.approval_policy,
        retry_policy=c.retry_policy,
        created_at=c.created_at,
        updated_at=c.updated_at,
        targets=(t1, t2),
        tags=c.tags,
        notes=c.notes,
        archived_at=c.archived_at,
    )

    summary = c_with_targets.generate_summary()
    assert summary.total_targets == 2
    assert summary.pending_targets == 2
    assert summary.successful_targets == 0
    assert summary.completion_percentage == 0.0

    # Status transition when pending
    next_status = c_with_targets.evaluate_status_transition()
    assert next_status == CampaignStatus.DRAFT  # Still draft if draft

    # Test all success
    t1_done = CampaignTarget(
        id=t1.id,
        campaign_id=t1.campaign_id,
        destination_type=t1.destination_type,
        destination_id=t1.destination_id,
        destination_name=t1.destination_name,
        status=TargetStatus.SUCCESS,
        published_post_id="post_123",
    )
    t2_done = CampaignTarget(
        id=t2.id,
        campaign_id=t2.campaign_id,
        destination_type=t2.destination_type,
        destination_id=t2.destination_id,
        destination_name=t2.destination_name,
        status=TargetStatus.SUCCESS,
        published_post_id="post_456",
    )
    c_completed = Campaign(
        id=c.id,
        title=c.title,
        content_item_id=c.content_item_id,
        post_type=c.post_type,
        caption=c.caption,
        media_asset_ids=c.media_asset_ids,
        status=CampaignStatus.RUNNING,
        schedule_policy=c.schedule_policy,
        approval_policy=c.approval_policy,
        retry_policy=c.retry_policy,
        created_at=c.created_at,
        updated_at=c.updated_at,
        targets=(t1_done, t2_done),
        tags=c.tags,
        notes=c.notes,
        archived_at=c.archived_at,
    )
    summary_done = c_completed.generate_summary()
    assert summary_done.successful_targets == 2
    assert summary_done.completion_percentage == 100.0
    assert c_completed.evaluate_status_transition() == CampaignStatus.COMPLETED


def test_partial_failure_and_retry_aggregation():
    """Test partial failure aggregation when one target succeeds and another fails."""
    t1 = CampaignTarget(
        id="t1",
        campaign_id="c1",
        destination_type=PublishDestinationType.PAGE,
        destination_id="p1",
        destination_name="Page A",
        status=TargetStatus.SUCCESS,
        published_post_id="post_1",
    )
    t2 = CampaignTarget(
        id="t2",
        campaign_id="c1",
        destination_type=PublishDestinationType.PAGE,
        destination_id="p2",
        destination_name="Page B",
        status=TargetStatus.FAILED,
        error_message="Meta API Error: Rate limit exceeded",
    )

    c = Campaign.create(
        title="Partial Campaign",
        targets=(t1, t2),
    )
    c_running = Campaign(
        id=c.id,
        title=c.title,
        content_item_id=c.content_item_id,
        post_type=c.post_type,
        caption=c.caption,
        media_asset_ids=c.media_asset_ids,
        status=CampaignStatus.RUNNING,
        schedule_policy=c.schedule_policy,
        approval_policy=c.approval_policy,
        retry_policy=c.retry_policy,
        created_at=c.created_at,
        updated_at=c.updated_at,
        targets=(t1, t2),
        tags=c.tags,
        notes=c.notes,
        archived_at=c.archived_at,
    )

    summary = c_running.generate_summary()
    assert summary.total_targets == 2
    assert summary.successful_targets == 1
    assert summary.failed_targets == 1
    assert summary.completion_percentage == 100.0
    assert c_running.evaluate_status_transition() == CampaignStatus.PARTIALLY_COMPLETED


def test_campaign_service_lifecycle_pause_resume(test_db):
    """Test campaign service orchestration including save, targets, approval, pause and resume."""
    svc = CampaignService(
        unit_of_work=test_db.unit_of_work,
        campaign_repo_factory=SqlAlchemyCampaignRepository,
    )

    # 1. Create campaign with targets
    res = svc.create_campaign(
        title="Holiday Promo 2026",
        post_type=PostType.FEED,
        caption="Merry Christmas!",
        target_specs=[
            (PublishDestinationType.PAGE, "page_1", "Official Page"),
            (PublishDestinationType.GROUP, "group_1", "Community Group"),
        ],
    )
    assert res.is_success
    campaign = res.value
    assert campaign.title == "Holiday Promo 2026"
    assert len(campaign.targets) == 2
    assert campaign.status == CampaignStatus.DRAFT

    # 2. Approve campaign
    appr_res = svc.approve_campaign(campaign.id)
    assert appr_res.is_success
    assert appr_res.value.status == CampaignStatus.READY

    # 3. Pause campaign
    pause_res = svc.pause_campaign(campaign.id)
    assert pause_res.is_success
    assert pause_res.value.status == CampaignStatus.PAUSED

    # 4. Resume campaign
    resume_res = svc.resume_campaign(campaign.id)
    assert resume_res.is_success
    assert resume_res.value.status == CampaignStatus.READY

    # 5. Update target status
    t_id = campaign.targets[0].id
    t_res = svc.update_target_status(
        t_id,
        TargetStatus.SUCCESS,
        published_post_id="meta_post_999",
    )
    assert t_res.is_success
    assert t_res.value.status == TargetStatus.SUCCESS
    assert t_res.value.published_post_id == "meta_post_999"

    # 6. Check summary
    summary = svc.get_campaign_summary(campaign.id)
    assert summary is not None
    assert summary.successful_targets == 1
    assert summary.pending_targets == 1
    assert summary.completion_percentage == 50.0


def test_campaign_workspace_ui(qapp, test_db):
    """Test CampaignWorkspace UI model and filtering."""
    svc = CampaignService(
        unit_of_work=test_db.unit_of_work,
        campaign_repo_factory=SqlAlchemyCampaignRepository,
    )

    svc.create_campaign(title="Alpha Launch")
    svc.create_campaign(title="Beta Testing")

    ws = CampaignWorkspace(svc)
    assert ws.campaign_model.rowCount() == 2

    # Filter search
    ws._on_search_changed("Alpha")
    assert ws.proxy_model.rowCount() == 1

    ws._on_search_changed("")
    assert ws.proxy_model.rowCount() == 2

    # Detail panel selection
    c = svc.list_campaigns()[0]
    ws.detail_panel.set_campaign(c)
    assert ws.detail_panel.title_label.text() == c.title
