from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from sp_farms.app.security_center import SecurityCenterWorkspace
from sp_farms.application.security_service import SecurityService
from sp_farms.domain.accounts import (
    Account,
    AccountStatus,
    PermissionState,
    PreferredApp,
    SecurityState,
)
from sp_farms.domain.meta import (
    MetaScopeSet,
    MetaTokenMetadata,
    MetaTokenType,
)
from sp_farms.domain.secrets import SecretReference, SecretType
from sp_farms.domain.security import (
    AuthState,
    SecurityEventCategory,
    TokenHealthState,
    calculate_security_score,
)


def _get_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    assert isinstance(app, QApplication)
    return app


def test_calculate_security_score() -> None:
    # Full secure
    assert (
        calculate_security_score(
            has_2fa=True,
            token_health=TokenHealthState.HEALTHY,
            session_stale=False,
            vault_synced=True,
            missing_scopes_count=0,
            auth_state=AuthState.AUTHENTICATED,
        )
        == 100
    )

    # Missing 2FA and stale session
    score = calculate_security_score(
        has_2fa=False,
        token_health=TokenHealthState.HEALTHY,
        session_stale=True,
        vault_synced=True,
        missing_scopes_count=0,
        auth_state=AuthState.AUTHENTICATED,
    )
    assert score == 60  # 100 - 25 - 15

    # Expired token and challenge required
    score_critical = calculate_security_score(
        has_2fa=True,
        token_health=TokenHealthState.EXPIRED,
        session_stale=False,
        vault_synced=True,
        missing_scopes_count=1,
        auth_state=AuthState.CHALLENGE_REQUIRED,
    )
    assert score_critical == 30  # 100 - 35 - 5 - 30


def test_security_service_audit_and_aggregation() -> None:
    now = datetime.now(UTC)

    # Setup accounts
    acc_secure = Account(
        id="acc-1",
        display_name="Alice Pro",
        first_name="Alice",
        last_name="Pro",
        platform_uid="10001",
        primary_email="alice@example.com",
        phone="+1234567890",
        country="US",
        locale="en_US",
        timezone="America/New_York",
        status=AccountStatus.ACTIVE,
        two_factor_enabled=True,
        preferred_app=PreferredApp.FACEBOOK,
        permission_state=PermissionState.COMPLETE,
        security_state=SecurityState.SECURE,
        last_verified_at=now - timedelta(days=2),
        notes="Secure test account",
        created_at=now,
        updated_at=now,
    )

    acc_warning = Account(
        id="acc-2",
        display_name="Bob Warn",
        first_name="Bob",
        last_name="Warn",
        platform_uid="10002",
        primary_email="bob@example.com",
        phone="+1234567891",
        country="US",
        locale="en_US",
        timezone="America/New_York",
        status=AccountStatus.ATTENTION,
        two_factor_enabled=False,
        preferred_app=PreferredApp.FACEBOOK,
        permission_state=PermissionState.LIMITED,
        security_state=SecurityState.REVIEW_REQUIRED,
        last_verified_at=now - timedelta(days=20),
        notes="Needs attention",
        created_at=now,
        updated_at=now,
    )

    mock_account_service = MagicMock()
    mock_account_service.list_accounts.return_value = [acc_secure, acc_warning]

    def _get_account(aid: str) -> Account:
        return acc_secure if aid == "acc-1" else acc_warning

    mock_account_service.get_account.side_effect = _get_account

    mock_secret_service = MagicMock()
    mock_secret_service.reveal.return_value = "EAAB..."  # Valid secret token

    token_ref = SecretReference(
        id="sec-ref-1",
        secret_type=SecretType.ACCESS_TOKEN,
        owner_id="acc-1",
        vault_ref="vault-1",
        created_at=now,
        updated_at=now,
    )
    mock_secret_repo = MagicMock()
    mock_secret_repo.list_by_owner_ids.side_effect = lambda aids: (
        [token_ref] if aids and "acc-1" in aids else []
    )

    def _secret_repo_factory(uow: Any = None) -> MagicMock:
        return mock_secret_repo

    mock_meta_service = MagicMock()
    mock_meta_service.inspect_stored_token.return_value = MetaTokenMetadata(
        app_id="app-1",
        token_type=MetaTokenType.USER,
        expires_at=now + timedelta(days=45),
        is_valid=True,
        scopes=MetaScopeSet.from_string(
            "public_profile,pages_show_list,pages_read_engagement,pages_manage_posts"
        ),
        user_id="10001",
    )
    mock_meta_service.generate_authorization_url.return_value = (
        "https://www.facebook.com/v21.0/dialog/oauth?client_id=123"
    )

    sec_service = SecurityService(
        account_service=mock_account_service,
        secret_service=mock_secret_service,
        secret_repository_factory=_secret_repo_factory,
        meta_service=mock_meta_service,
    )

    # Test audit Alice (Secure)
    audit_alice = sec_service.audit_account(acc_secure)
    assert audit_alice.security_score >= 80
    assert audit_alice.two_factor_enabled is True
    assert audit_alice.token_health == TokenHealthState.HEALTHY
    assert audit_alice.days_until_expiration in (44, 45)
    assert not audit_alice.session_stale
    assert audit_alice.vault_synced is True
    assert len(audit_alice.missing_scopes) == 0

    # Test audit Bob (Warning/Critical)
    audit_bob = sec_service.audit_account(acc_warning)
    assert audit_bob.security_score < 50
    assert audit_bob.two_factor_enabled is False
    assert audit_bob.session_stale is True
    assert audit_bob.auth_state == AuthState.CHALLENGE_REQUIRED
    assert len(audit_bob.warnings) >= 2
    assert len(audit_bob.remediation_steps) >= 2

    # Test system report aggregation
    report = sec_service.generate_system_report()
    assert report.total_accounts == 2
    assert report.secure_accounts == 1
    assert report.critical_accounts == 1
    assert report.missing_2fa_count == 1
    assert report.stale_sessions_count == 1
    assert report.vault_healthy is True

    # Test re-auth generation
    reauth = sec_service.generate_reauth_url_or_guidance("acc-1")
    assert reauth["status"] == "ready"
    assert "oauth" in reauth["oauth_url"]
    assert "checkpoint" in reauth["guidance"].lower()

    # Verify security events list
    events = sec_service.list_security_events()
    assert len(events) == 1
    assert events[0].category == SecurityEventCategory.AUTHENTICATION
    assert events[0].account_id == "acc-1"


def test_security_center_workspace_ui() -> None:
    _get_qapp()

    now = datetime.now(UTC)
    acc = Account(
        id="acc-10",
        display_name="Dev Farm Account",
        first_name="Dev",
        last_name="Farm",
        primary_email="dev@example.com",
        phone="+1234567899",
        country="US",
        locale="en_US",
        timezone="America/New_York",
        status=AccountStatus.ACTIVE,
        two_factor_enabled=True,
        preferred_app=PreferredApp.FACEBOOK,
        permission_state=PermissionState.COMPLETE,
        security_state=SecurityState.SECURE,
        platform_uid="10010",
        last_verified_at=now,
        created_at=now,
        updated_at=now,
    )

    mock_account_service = MagicMock()
    mock_account_service.list_accounts.return_value = [acc]
    mock_account_service.get_account.return_value = acc

    sec_service = SecurityService(account_service=mock_account_service)

    workspace = SecurityCenterWorkspace(security_service=sec_service)
    workspace.refresh()

    # Check metrics bar populated
    assert workspace.metrics_bar.value_labels[0].text() == "1"

    # Check table row
    assert workspace.proxy.rowCount() == 1
    idx = workspace.proxy.index(0, 0)
    assert workspace.proxy.data(idx, Qt.ItemDataRole.DisplayRole) == "Dev Farm Account"

    # Select row and check inspector
    workspace.table.selectRow(0)
    assert workspace.inspector.title_label.text() == "Dev Farm Account"
    assert workspace.inspector.uid_label.text() == "UID: 10010"
    assert "100" in workspace.inspector.score_chip.text()
    assert workspace.inspector.two_fa_label.text() == "Enabled (2FA)"

    # Test search filter
    workspace.search_input.setText("Unknown")
    assert workspace.proxy.rowCount() == 0
    workspace.search_input.setText("Dev Farm")
    assert workspace.proxy.rowCount() == 1

    # Test filter combo
    workspace.filter_combo.setCurrentText("Missing 2FA")
    assert workspace.proxy.rowCount() == 0
    workspace.filter_combo.setCurrentText("All")
    assert workspace.proxy.rowCount() == 1
