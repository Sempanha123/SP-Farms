"""Unit tests for SelectionContext domain and SelectionContextService."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from sp_farms.application.selection_context_service import SelectionContextService
from sp_farms.domain.accounts import Account, AccountStatus, PreferredApp
from sp_farms.domain.assets import AssetHealthState, AssetPermission, Page
from sp_farms.domain.device_management import DeviceProfile
from sp_farms.domain.device_restore import AccountDeviceBinding
from sp_farms.domain.providers import DeviceProviderType
from sp_farms.domain.selection_context import (
    ActionTabType,
    ResolvedTarget,
    SelectionContext,
    SelectionSource,
    TargetCapability,
    TargetType,
)


def test_selection_context_single_account():
    target = ResolvedTarget(
        target_id="acc-1",
        target_type=TargetType.ACCOUNT,
        display_name="Test Account 1",
        owning_account_id="acc-1",
        owning_account_name="Test Account 1",
        bound_device_id="dev-1",
        bound_device_provider="ldplayer",
        preferred_app="facebook",
        auth_state="ready",
        health_status="healthy",
        capabilities=TargetCapability(can_restore=True, can_post_feed=True),
    )

    ctx = SelectionContext(
        source_module=SelectionSource.ACCOUNTS,
        selected_account_ids=("acc-1",),
        resolved_targets=(target,),
        inferred_account_ids=("acc-1",),
        inferred_device_ids=("dev-1",),
    )

    assert not ctx.is_multi_select
    assert ctx.target_count == 1
    assert "Test Account 1" in ctx.summary_header
    assert "Using: Account: Test Account 1" in ctx.read_only_summary
    assert "Device: ldplayer:dev-1" in ctx.read_only_summary

    tabs = ctx.get_supported_tabs()
    assert ActionTabType.OVERVIEW in tabs
    assert ActionTabType.RESTORE in tabs
    assert ActionTabType.POST in tabs
    assert ActionTabType.QA_PROFILE_LAB not in tabs  # Restricted from production accounts


def test_selection_context_pages_resolution():
    target = ResolvedTarget(
        target_id="p-100",
        target_type=TargetType.PAGE,
        display_name="SP Cambo Shop",
        owning_account_id="acc-1",
        owning_account_name="Master Account",
        bound_device_id="dev-2",
        bound_device_provider="mumu",
        preferred_app="facebook",
        auth_state="ready",
        health_status="healthy",
        capabilities=TargetCapability(can_post_feed=True, can_reply_comments=True),
    )

    ctx = SelectionContext(
        source_module=SelectionSource.PAGES,
        selected_page_ids=("p-100",),
        resolved_targets=(target,),
        inferred_account_ids=("acc-1",),
        inferred_device_ids=("dev-2",),
    )

    assert "Page: SP Cambo Shop" in ctx.read_only_summary
    assert "Account: Master Account" in ctx.read_only_summary
    tabs = ctx.get_supported_tabs()
    assert ActionTabType.CONNECTED_ACCOUNT in tabs
    assert ActionTabType.POST in tabs
    assert ActionTabType.COMMENTS in tabs


def test_selection_context_service_resolution():
    mock_account_service = MagicMock()
    mock_restore_service = MagicMock()

    now = datetime.now(UTC)
    acc = Account.create("Retail Owner", "fb-12345", "owner@sp.com", now)
    mock_account_service.get_account.return_value = acc

    binding = AccountDeviceBinding(
        account_id=acc.id,
        device_profile_id="dev-profile-99",
        created_at=now,
    )
    mock_restore_service.get_binding.return_value = binding

    profile = DeviceProfile(
        id="dev-profile-99",
        friendly_name="LDPlayer Pixel 6",
        provider=DeviceProviderType.LDPLAYER,
        external_id="LD-01",
        created_at=now,
        updated_at=now,
    )
    mock_restore_service.get_profile.return_value = profile

    service = SelectionContextService(
        account_service=mock_account_service,
        restore_workspace_service=mock_restore_service,
    )

    ctx = service.resolve_context(
        source_module=SelectionSource.ACCOUNTS,
        account_ids=(acc.id,),
    )

    assert ctx.target_count == 1
    assert len(ctx.resolved_targets) == 1
    t = ctx.resolved_targets[0]
    assert t.target_id == acc.id
    assert t.display_name == "Retail Owner"
    assert t.bound_device_id == "dev-profile-99"
    assert t.bound_device_provider == "ldplayer"
    assert t.auth_state == "ready"
    assert t.capabilities.can_post_feed is True
    assert "can_restore" in ctx.common_capabilities


def test_selection_context_multi_capabilities():
    t1 = ResolvedTarget(
        target_id="acc-1",
        target_type=TargetType.ACCOUNT,
        display_name="Account 1",
        capabilities=TargetCapability(can_restore=True, can_post_feed=True, can_reply_comments=True),
    )
    t2 = ResolvedTarget(
        target_id="acc-2",
        target_type=TargetType.ACCOUNT,
        display_name="Account 2",
        capabilities=TargetCapability(can_restore=True, can_post_feed=False, can_reply_comments=True),
    )

    ctx = SelectionContext(
        source_module=SelectionSource.ACCOUNTS,
        selected_account_ids=("acc-1", "acc-2"),
        resolved_targets=(t1, t2),
        common_capabilities=("can_restore", "can_reply_comments"),
        mixed_capabilities=("can_post_feed",),
    )

    assert ctx.is_multi_select
    assert ctx.target_count == 2
    assert "2 Accounts selected" in ctx.summary_header
    assert "can_restore" in ctx.common_capabilities
    assert "can_post_feed" in ctx.mixed_capabilities
