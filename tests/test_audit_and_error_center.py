import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from PySide6.QtWidgets import QApplication

from sp_farms.app.error_center import (
    ErrorCenterWorkspace,
)
from sp_farms.application.audit_service import AuditService
from sp_farms.domain.audit import (
    AuditEvent,
    AuditResult,
    AuditTargetType,
)
from sp_farms.domain.redaction import redact_data, redact_text
from sp_farms.domain.security import (
    SecurityEvent,
    SecurityEventCategory,
    SecuritySeverity,
)
from sp_farms.infrastructure.clock import SystemClock
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyAuditRepository,
    run_migrations,
)


@pytest.fixture
def temp_db() -> Generator[tuple[Database, Path], None, None]:
    temp_dir = TemporaryDirectory()
    db_path = Path(temp_dir.name) / "test_audit.db"
    db = Database(db_path)
    migrations_path = Path(__file__).resolve().parents[1] / "migrations"
    run_migrations(db, migrations_path)
    yield db, db_path
    db.close()
    temp_dir.cleanup()


@pytest.fixture
def audit_service(temp_db: tuple[Database, Path]) -> AuditService:
    db, _ = temp_db
    clock = SystemClock()
    return AuditService(
        unit_of_work=db.unit_of_work,
        audit_repository_factory=SqlAlchemyAuditRepository,
        clock=clock,
        job_service=None,
    )


def test_redaction_removes_sensitive_tokens_and_passwords() -> None:
    text = "Failed with token EAABwz1234567890abcdefghijklmn and password: MySuperSecretPassword123"
    cleaned = redact_text(text)
    assert "EAAB" not in cleaned
    assert "MySuperSecretPassword123" not in cleaned
    assert "[REDACTED]" in cleaned

    data = {
        "user": "operator1",
        "api_secret": "raw_secret_xyz",
        "nested": {
            "auth_header": (
                "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
                "eyJzdWIiOiIxMjM0NTY3ODkwIn0.do_not_leak"
            ),
            "safe_field": "public_data",
        },
    }
    scrubbed = redact_data(data)
    assert scrubbed["api_secret"] == "[REDACTED]"
    assert "do_not_leak" not in scrubbed["nested"]["auth_header"]
    assert scrubbed["nested"]["safe_field"] == "public_data"


def test_audit_event_creation_and_retrieval(audit_service: AuditService) -> None:
    event = audit_service.record_event(
        initiator="operator",
        action="account.create",
        target_type=AuditTargetType.ACCOUNT.value,
        target_id="acc_123",
        result=AuditResult.SUCCESS,
        details={"name": "Alice Cooper", "cookie": "secret_session_cookie"},
    )
    assert event.id is not None
    assert event.action == "account.create"
    assert event.details.get("cookie") == "[REDACTED]"

    retrieved = audit_service.get_event(event.id)
    assert retrieved is not None
    assert retrieved.target_id == "acc_123"
    assert retrieved.result == AuditResult.SUCCESS
    assert retrieved.details["cookie"] == "[REDACTED]"


def test_error_recording_and_diagnostics(audit_service: AuditService) -> None:
    err_event = audit_service.record_error(
        initiator="worker",
        action="device.connect",
        target_type=AuditTargetType.DEVICE.value,
        target_id="emulator-5554",
        error_code="DEVICE_OFFLINE",
        error_message="Adb connection timed out after 30s. Offline state detected.",
    )
    assert err_event.result == AuditResult.FAILURE
    assert err_event.error_code == "DEVICE_OFFLINE"

    diagnostics = audit_service.list_error_diagnostics()
    assert len(diagnostics) == 1
    diag = diagnostics[0]
    assert diag.error_code == "DEVICE_OFFLINE"
    assert "disconnected" in diag.friendly_summary.lower()
    assert diag.is_retryable is True
    assert "adb" in diag.safe_recovery_suggestion.lower()


def test_security_event_integration(audit_service: AuditService) -> None:
    sec_event = SecurityEvent(
        id="sec_001",
        category=SecurityEventCategory.AUTHENTICATION,
        severity=SecuritySeverity.HIGH,
        title="2FA Disabled",
        description="Account missing two-factor authentication key.",
        remediation="Configure 2FA in security settings.",
        created_at=datetime.now(UTC),
        account_id="acc_999",
    )
    audit = audit_service.record_security_event(sec_event)
    assert audit.action == "security.authentication"
    assert audit.result == AuditResult.WARNING
    assert audit.target_id == "acc_999"


def test_diagnostics_bundle_generation(audit_service: AuditService) -> None:
    msg = (
        "Graph API returned code 17: User request limit reached "
        "with secret token EAAB9876543210zyxwvutsrq"
    )
    err_event = audit_service.record_error(
        initiator="scheduler",
        action="publish.post",
        target_type="page",
        target_id="page_456",
        error_code="RATE_LIMIT_EXCEEDED",
        error_message=msg,
    )
    bundle_str = audit_service.generate_diagnostics_bundle(err_event.id)
    assert bundle_str is not None
    data = json.loads(bundle_str)
    assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "EAAB" not in bundle_str
    assert "[REDACTED]" in data["error"]["technical_details"]


def test_retention_policy_pruning(
    audit_service: AuditService, temp_db: tuple[Database, Path]
) -> None:
    # Add older record
    old_event = AuditEvent.create(
        id="old_ev",
        initiator="system",
        action="test.old",
        target_type="test",
        target_id="1",
        timestamp=datetime.now(UTC) - timedelta(days=45),
        result=AuditResult.SUCCESS,
    )
    db, _ = temp_db
    with db.unit_of_work() as uow:
        repo = SqlAlchemyAuditRepository(uow)
        repo.add(old_event)
        uow.commit()

    # Add fresh record
    audit_service.record_event(
        initiator="system",
        action="test.fresh",
        target_type="test",
        target_id="2",
        result=AuditResult.SUCCESS,
    )

    events_before = audit_service.list_events()
    assert len(events_before) == 2

    # Prune records older than 30 days
    pruned = audit_service.prune_audit_logs(retention_days=30)
    assert pruned == 1

    events_after = audit_service.list_events()
    assert any(e.id == "old_ev" for e in events_after) is False
    assert any(e.action == "test.fresh" for e in events_after) is True


def test_error_center_ui(audit_service: AuditService) -> None:
    _ = QApplication.instance() or QApplication([])

    audit_service.record_error(
        initiator="operator",
        action="account.restore",
        target_type="account",
        target_id="acc_001",
        error_code="AUTH_EXPIRED",
        error_message="Access token expired (code 190).",
        job_id="job_777",
    )

    ws = ErrorCenterWorkspace(audit_service)
    assert ws.tabs.count() == 3
    assert ws.error_table_model.rowCount() == 1
    assert ws.audit_model.rowCount() == 1

    # Test error selection
    ws.error_table.selectRow(0)
    assert ws.error_inspector._current_entry is not None
    assert ws.error_inspector._current_entry.error_code == "AUTH_EXPIRED"
    assert ws.error_inspector.open_target_button.isEnabled() is True
    assert "token has expired" in ws.error_inspector.summary_text.text().lower()

    # Test search filter
    ws.error_search.setText("non_existent_code")
    assert ws.error_proxy.rowCount() == 0
    ws.error_search.setText("")
    assert ws.error_proxy.rowCount() == 1
