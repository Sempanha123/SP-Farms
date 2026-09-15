"""Unit tests for Phase 55: Account Maintenance, Security, and 2FA Automation."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from sp_farms.application.maintenance_service import MaintenanceService
from sp_farms.domain.accounts import Account
from sp_farms.domain.maintenance import (
    MaintenanceStatus,
    MaintenanceTaskType,
)


def test_create_maintenance_action_approval_gate():
    service = MaintenanceService()
    action = service.create_action(
        account_id="acc-1",
        task_type=MaintenanceTaskType.PROFILE_AUDIT,
        requires_operator_approval=True,
    )

    assert action.account_id == "acc-1"
    assert action.task_type == MaintenanceTaskType.PROFILE_AUDIT
    assert action.status == MaintenanceStatus.PENDING
    assert action.requires_operator_approval is True


def test_maintenance_service_unapproved_execution_rejected():
    service = MaintenanceService()
    action = service.create_action(
        account_id="acc-1",
        task_type=MaintenanceTaskType.CACHE_PURGE,
        requires_operator_approval=True,
    )

    result = service.execute_action(action.id)
    assert result.success is False
    assert result.status == MaintenanceStatus.REJECTED
    assert "requires explicit operator approval" in result.summary


def test_maintenance_service_approved_execution_success():
    service = MaintenanceService()
    action = service.create_action(
        account_id="acc-1",
        task_type=MaintenanceTaskType.SESSION_HEALTH_CHECK,
        requires_operator_approval=True,
    )
    service.approve_action(action.id)

    result = service.execute_action(action.id)
    assert result.success is True
    assert result.status == MaintenanceStatus.COMPLETED
    assert "Session health verified" in result.summary


def test_maintenance_service_dry_run_simulation():
    service = MaintenanceService()
    action = service.create_action(
        account_id="acc-1",
        task_type=MaintenanceTaskType.PASSWORD_ROTATION_RECORD,
        requires_operator_approval=False,
        dry_run=True,
    )

    result = service.execute_action(action.id)
    assert result.success is True
    assert result.dry_run is True
    assert "Dry run simulation completed" in result.summary
    assert result.details.get("side_effects") == "none"


def test_maintenance_service_profile_audit():
    mock_acc_service = MagicMock()
    now = datetime.now(UTC)
    acc = Account.create("Store Owner", "fb-12345", "store@sp.com", now)
    mock_acc_service.get_account.return_value = acc

    service = MaintenanceService(account_service=mock_acc_service)
    action = service.create_action(
        account_id=acc.id,
        task_type=MaintenanceTaskType.PROFILE_AUDIT,
        requires_operator_approval=False,
    )

    result = service.execute_action(action.id)
    assert result.success is True
    assert "Store Owner" in result.summary


def test_maintenance_service_cache_purge_with_adb():
    mock_adb = MagicMock()
    service = MaintenanceService(adb=mock_adb)
    action = service.create_action(
        account_id="acc-1",
        task_type=MaintenanceTaskType.CACHE_PURGE,
        requires_operator_approval=False,
    )

    result = service.execute_action(action.id, adb_serial="emulator-5554")
    assert result.success is True
    mock_adb.shell.assert_called_with("emulator-5554", "pm trim-caches 200M")


def test_maintenance_service_totp_setup():
    service = MaintenanceService()
    action = service.create_action(
        account_id="acc-1",
        task_type=MaintenanceTaskType.TOTP_2FA_SETUP,
        requires_operator_approval=False,
    )

    result = service.execute_action(action.id)
    assert result.success is True
    assert result.details.get("algorithm") == "TOTP-SHA1"
    assert result.details.get("digits") == "6"
