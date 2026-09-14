"""Tests for Phase 35: Approval Queue and human-in-the-loop review."""

import tempfile
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from sp_farms.app.approval_workspace import (
    ApprovalDecisionDialog,
    ApprovalRequestTableModel,
    ApprovalWorkspace,
)
from sp_farms.application.approval_service import ApprovalService
from sp_farms.application.audit_service import AuditService
from sp_farms.application.job_service import JobService
from sp_farms.domain.approvals import (
    ApprovalActionType,
    ApprovalPolicyRule,
    ApprovalRequest,
    ApprovalStatus,
)
from sp_farms.domain.jobs import JobState
from sp_farms.infrastructure.clock import SystemClock
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyApprovalRepository,
    SqlAlchemyAuditRepository,
    SqlAlchemyJobRepository,
    run_migrations,
)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app  # type: ignore[return-value]


@pytest.fixture
def test_db() -> Generator[Database, None, None]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_approvals.db"
        db = Database(db_path)
        migrations_path = Path(__file__).resolve().parents[1] / "migrations"
        run_migrations(db, migrations_path)
        try:
            yield db
        finally:
            db.close()


@pytest.fixture
def audit_service(test_db: Database) -> AuditService:
    return AuditService(
        unit_of_work=test_db.unit_of_work,
        audit_repository_factory=SqlAlchemyAuditRepository,
        clock=SystemClock(),
    )


@pytest.fixture
def job_service(test_db: Database) -> JobService:
    return JobService(
        unit_of_work=test_db.unit_of_work,
        repository_factory=SqlAlchemyJobRepository,
        clock=SystemClock(),
    )


@pytest.fixture
def approval_service(
    test_db: Database, audit_service: AuditService, job_service: JobService
) -> ApprovalService:
    return ApprovalService(
        unit_of_work=test_db.unit_of_work,
        approval_repo_factory=SqlAlchemyApprovalRepository,  # type: ignore[arg-type]
        clock=SystemClock(),
        audit_service=audit_service,
        job_service=job_service,
    )


def test_approval_domain_and_policy_matching() -> None:
    """Test domain state transitions and policy rule matching."""
    # Policy rule
    rule = ApprovalPolicyRule(
        id="rule-publish-page",
        action_type=ApprovalActionType.PUBLISH_POST,
        target_pattern="dest-page-*",
    )
    assert rule.matches(ApprovalActionType.PUBLISH_POST, "dest-page-1") is True
    assert rule.matches(ApprovalActionType.PUBLISH_POST, "dest-profile-1") is False
    assert rule.matches(ApprovalActionType.DELETE_ASSET, "dest-page-1") is False

    # Request lifecycle
    req = ApprovalRequest.create(
        action_type=ApprovalActionType.PUBLISH_POST,
        target_id="dest-page-1",
        target_name="Marketing Page",
        summary="Publish black friday announcement",
        expires_in_hours=24,
    )
    assert req.status == ApprovalStatus.PENDING
    assert req.expires_at is not None

    # Approve
    approved = req.approve(reviewer="Alice", notes="Looks great!")
    assert approved.status == ApprovalStatus.APPROVED
    assert approved.reviewed_by == "Alice"
    assert approved.review_notes == "Looks great!"
    assert approved.decided_at is not None

    # Cannot re-approve approved request
    with pytest.raises(ValueError, match="Cannot approve request"):
        approved.approve(reviewer="Bob")

    # Reject
    rejected = req.reject(reviewer="Charlie", notes="Typo in image")
    assert rejected.status == ApprovalStatus.REJECTED
    assert rejected.reviewed_by == "Charlie"


def test_approval_service_lifecycle_and_audit(
    approval_service: ApprovalService, audit_service: AuditService
) -> None:
    """Test creating requests, approving, and verifying audit logging."""
    res = approval_service.request_approval(
        action_type=ApprovalActionType.CAMPAIGN_EXECUTION,
        target_id="camp-123",
        target_name="Spring Campaign",
        summary="Authorize launch of 15 scheduled posts",
        requested_by="SchedulerBot",
    )
    assert res.is_success
    req = res.value

    # Inbox listing
    inbox = approval_service.list_inbox(status=ApprovalStatus.PENDING)
    assert any(r.id == req.id for r in inbox)

    # Approve
    app_res = approval_service.approve_request(
        req.id, reviewer="SeniorOperator", notes="Authorized"
    )
    assert app_res.is_success
    assert app_res.value.status == ApprovalStatus.APPROVED

    # Check audit event
    events = audit_service.list_events(target_id="camp-123")
    assert len(events) >= 2  # requested + approved
    assert any(e.action == "approval.approved" and e.initiator == "SeniorOperator" for e in events)


def test_stale_request_expiration(approval_service: ApprovalService) -> None:
    """Test automatic expiration of requests whose deadline has passed."""
    # Create request with 0 hours expiration (instant expire)
    res = approval_service.request_approval(
        action_type=ApprovalActionType.CREDENTIAL_ROTATION,
        target_id="acc-999",
        target_name="Backup Account",
        summary="Rotate passwords",
        expires_in_hours=0,
    )
    assert res.is_success
    req = res.value

    # Force expiration time to the past
    with approval_service._uow() as uow:
        repo = approval_service._repo_factory(uow)
        saved = repo.get_request(req.id)
        assert saved is not None
        past_req = ApprovalRequest(
            id=saved.id,
            action_type=saved.action_type,
            target_id=saved.target_id,
            target_name=saved.target_name,
            summary=saved.summary,
            payload=saved.payload,
            campaign_id=saved.campaign_id,
            job_id=saved.job_id,
            status=ApprovalStatus.PENDING,
            requested_by=saved.requested_by,
            reviewed_by=saved.reviewed_by,
            review_notes=saved.review_notes,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
            decided_at=None,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )
        repo.save_request(past_req)
        uow.commit()

    expired = approval_service.expire_stale_requests()
    assert len(expired) >= 1
    assert any(r.id == req.id and r.status == ApprovalStatus.EXPIRED for r in expired)


def test_approval_job_integration(
    approval_service: ApprovalService, job_service: JobService
) -> None:
    """Test that approving a request resumes the linked job, and rejecting cancels it."""
    # 1. Create a job
    job, _ = job_service.create_job(
        job_type="media_prep",
        target_type="device",
        target_id="dev-1",
    )
    assert job.id is not None

    # 2. Request approval linked to job
    res = approval_service.request_approval(
        action_type=ApprovalActionType.PUBLISH_POST,
        target_id="post-1",
        target_name="Viral Reel",
        summary="Confirm video publishing",
        job_id=job.id,
    )
    assert res.is_success

    # 3. Reject with job cancellation
    rej_res = approval_service.reject_request(
        res.value.id, reviewer="Admin", notes="Not approved", cancel_job=True
    )
    assert rej_res.is_success

    # Verify job status cancelled
    updated_job = job_service.get_job(job.id)
    assert updated_job is not None
    assert updated_job.state == JobState.CANCELLED


def test_approval_workspace_ui(qapp: QApplication, approval_service: ApprovalService) -> None:
    """Test PySide6 ApprovalWorkspace UI components, tables, and dialogs."""
    res = approval_service.request_approval(
        action_type=ApprovalActionType.DEVICE_WIPE,
        target_id="dev-001",
        target_name="Emulator Device #1",
        summary="Wipe test data on emulator",
    )
    assert res.is_success
    req = res.value

    workspace = ApprovalWorkspace(approval_service)
    assert workspace.table_model.rowCount() >= 1

    # Inspector panel
    workspace.inspector.set_request(req)
    assert "Device Wipe" in workspace.inspector.title_label.text()
    assert workspace.inspector.approve_btn.isEnabled() is True

    # Table model tests
    model = ApprovalRequestTableModel()
    model.set_requests([req])
    assert model.rowCount() == 1
    assert model.columnCount() == 7
    assert model.get_request(0) == req

    # Decision dialogs
    approve_dlg = ApprovalDecisionDialog(req, "Approve")
    assert approve_dlg.get_reviewer() == "Operator"

    reject_dlg = ApprovalDecisionDialog(req, "Reject")
    assert reject_dlg.get_reviewer() == "Operator"
