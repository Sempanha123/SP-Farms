"""UI tests for ContextActionDialog."""

import pytest
from PySide6.QtWidgets import QApplication

from sp_farms.app.context_action_dialog import ContextActionDialog
from sp_farms.domain.selection_context import (
    ResolvedTarget,
    SelectionContext,
    SelectionSource,
    TargetCapability,
    TargetType,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_context_action_dialog_initialization(qapp):
    target = ResolvedTarget(
        target_id="acc-test-1",
        target_type=TargetType.ACCOUNT,
        display_name="Test Store Account",
        owning_account_id="acc-test-1",
        owning_account_name="Test Store Account",
        bound_device_id="dev-profile-1",
        bound_device_provider="ldplayer",
        preferred_app="facebook",
        auth_state="ready",
        health_status="healthy",
        capabilities=TargetCapability(can_restore=True, can_post_feed=True, can_backup=True),
    )

    ctx = SelectionContext(
        source_module=SelectionSource.ACCOUNTS,
        selected_account_ids=("acc-test-1",),
        resolved_targets=(target,),
        inferred_account_ids=("acc-test-1",),
        inferred_device_ids=("dev-profile-1",),
    )

    dialog = ContextActionDialog(context=ctx)
    assert dialog.title_label.text() == ctx.summary_header
    assert "Using: Account: Test Store Account" in dialog.using_summary_label.text()
    assert dialog.tabs.count() > 0

    # Ensure buttons exist
    assert dialog.run_btn is not None
    assert dialog.run_and_close_btn is not None
    assert dialog.save_preset_btn is not None
    assert dialog.dry_run_btn is not None
    dialog.close()


def test_context_action_dialog_page_context(qapp):
    target = ResolvedTarget(
        target_id="page-99",
        target_type=TargetType.PAGE,
        display_name="SP Auto Cambodia",
        owning_account_id="acc-owner-99",
        owning_account_name="Master Account 99",
        bound_device_id="dev-profile-2",
        bound_device_provider="mumu",
        preferred_app="facebook",
        auth_state="ready",
        health_status="healthy",
        capabilities=TargetCapability(can_post_feed=True, can_reply_comments=True),
    )

    ctx = SelectionContext(
        source_module=SelectionSource.PAGES,
        selected_page_ids=("page-99",),
        resolved_targets=(target,),
        inferred_account_ids=("acc-owner-99",),
        inferred_device_ids=("dev-profile-2",),
    )

    dialog = ContextActionDialog(context=ctx)
    assert "Page: SP Auto Cambodia" in dialog.using_summary_label.text()
    assert "Account: Master Account 99" in dialog.using_summary_label.text()

    tab_labels = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
    assert "Overview" in tab_labels
    assert "Connected Account" in tab_labels
    assert "Post Feed" in tab_labels
    dialog.close()
