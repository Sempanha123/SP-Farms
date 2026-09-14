from datetime import UTC, datetime
from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from sp_farms.app.asset_workspace import PagesGroupsWorkspace
from sp_farms.domain.accounts import (
    Account,
    AccountStatus,
    PermissionState,
    PreferredApp,
    SecurityState,
)
from sp_farms.domain.assets import AssetHealthState, AssetPermission, Group, Page


def _get_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    assert isinstance(app, QApplication)
    return app


def test_pages_groups_workspace_init_and_filtering() -> None:
    _get_qapp()

    # Mock domain objects
    now = datetime.now(UTC)
    p1 = Page(
        id="p-1",
        account_id="acc-1",
        page_id="meta-p-1",
        name="Tech Innovators Page",
        category="Science & Tech",
        tasks=(AssetPermission.CREATE_CONTENT.value, AssetPermission.MANAGE.value),
        followers_count=1250,
        likes_count=980,
        health=AssetHealthState.HEALTHY,
        last_synced_at=now,
    )
    p2 = Page(
        id="p-2",
        account_id="acc-1",
        page_id="meta-p-2",
        name="Gaming Zone Archived",
        category="Entertainment",
        tasks=(AssetPermission.MODERATE.value,),
        followers_count=45,
        likes_count=30,
        health=AssetHealthState.STALE,
        last_synced_at=now,
    )

    g1 = Group(
        id="g-1",
        account_id="acc-1",
        group_id="meta-g-1",
        name="React Native Cambodia",
        privacy="CLOSED",
        role="ADMIN",
        member_count=3400,
        health=AssetHealthState.HEALTHY,
        last_synced_at=now,
    )
    g2 = Group(
        id="g-2",
        account_id="acc-2",
        group_id="meta-g-2",
        name="Crypto Discussion",
        privacy="PUBLIC",
        role="MEMBER",
        member_count=850,
        health=AssetHealthState.STALE,
        last_synced_at=now,
    )

    acc1 = Account(
        id="acc-1",
        display_name="Primary Operator",
        first_name="Primary",
        last_name="Operator",
        platform_uid="fb-101",
        primary_email="prim@test.com",
        phone="+1234567890",
        country="US",
        locale="en_US",
        timezone="UTC",
        status=AccountStatus.ACTIVE,
        two_factor_enabled=True,
        preferred_app=PreferredApp.FACEBOOK,
        permission_state=PermissionState.COMPLETE,
        security_state=SecurityState.SECURE,
    )
    acc2 = Account(
        id="acc-2",
        display_name="Secondary Worker",
        first_name="Secondary",
        last_name="Worker",
        platform_uid="fb-102",
        primary_email="sec@test.com",
        phone="+1234567891",
        country="US",
        locale="en_US",
        timezone="UTC",
        status=AccountStatus.ACTIVE,
        two_factor_enabled=True,
        preferred_app=PreferredApp.FACEBOOK,
        permission_state=PermissionState.COMPLETE,
        security_state=SecurityState.SECURE,
    )

    mock_sync_service = MagicMock()
    mock_sync_service.list_all_pages.return_value = [p1, p2]
    mock_sync_service.list_all_groups.return_value = [g1, g2]

    mock_account_service = MagicMock()
    mock_account_service.list_accounts.return_value = [acc1, acc2]

    workspace = PagesGroupsWorkspace(
        sync_service=mock_sync_service,
        account_service=mock_account_service,
    )
    workspace.refresh()

    # Initial state on Pages tab
    assert workspace.tab_widget.currentIndex() == 0
    assert workspace.pages_proxy.rowCount() == 2
    assert workspace.pages_metrics.value_labels[0].text() == "2"
    assert workspace.pages_metrics.value_labels[1].text() == "1"  # p1 is publishing eligible
    assert workspace.pages_metrics.value_labels[3].text() == "1"  # p2 is stale

    # Search filter on Pages
    workspace.search_input.setText("Gaming")
    assert workspace.pages_proxy.rowCount() == 1
    idx = workspace.pages_proxy.index(0, 0)
    assert workspace.pages_proxy.data(idx, Qt.ItemDataRole.DisplayRole) == "Gaming Zone Archived"

    workspace.search_input.clear()
    assert workspace.pages_proxy.rowCount() == 2

    # Eligibility filter
    workspace.filter_combo.setCurrentText("Publishing Eligible")
    assert workspace.pages_proxy.rowCount() == 1
    idx = workspace.pages_proxy.index(0, 0)
    assert workspace.pages_proxy.data(idx, Qt.ItemDataRole.DisplayRole) == "Tech Innovators Page"

    # Switch to Groups tab
    workspace.set_tab("Groups")
    assert workspace.tab_widget.currentIndex() == 1
    assert workspace.groups_proxy.rowCount() == 2
    assert workspace.groups_metrics.value_labels[0].text() == "2"
    assert workspace.groups_metrics.value_labels[1].text() == "1"  # g1 is posting eligible (ADMIN)
    assert workspace.groups_metrics.value_labels[3].text() == "1"  # g1 is admin

    # Role filter on Groups
    workspace.filter_combo.setCurrentText("Admin Only")
    assert workspace.groups_proxy.rowCount() == 1
    idx_g = workspace.groups_proxy.index(0, 0)
    assert (
        workspace.groups_proxy.data(idx_g, Qt.ItemDataRole.DisplayRole) == "React Native Cambodia"
    )


def test_asset_inspector_display_and_actions() -> None:
    _get_qapp()

    now = datetime.now(UTC)
    page = Page(
        id="p-1",
        account_id="acc-1",
        page_id="meta-p-1",
        name="Inspector Test Page",
        category="Community",
        tasks=(AssetPermission.CREATE_CONTENT.value,),
        followers_count=5000,
        likes_count=4500,
        health=AssetHealthState.HEALTHY,
        last_synced_at=now,
    )

    mock_sync_service = MagicMock()
    mock_sync_service.list_all_pages.return_value = [page]
    mock_sync_service.list_all_groups.return_value = []

    mock_account_service = MagicMock()
    mock_account_service.list_accounts.return_value = []

    workspace = PagesGroupsWorkspace(
        sync_service=mock_sync_service,
        account_service=mock_account_service,
    )
    workspace.refresh()

    # Select page row
    workspace.pages_table.selectRow(0)
    assert workspace.inspector.title_label.text() == "Inspector Test Page"
    assert workspace.inspector.id_label.text() == "ID: meta-p-1"
    assert workspace.inspector.eligibility_chip.text() == "Eligible"

    # Test shortcut route signals
    route_target: list[str] = []
    workspace.inspector.route_requested.connect(route_target.append)

    workspace.inspector.recent_content_btn.click()
    assert route_target == ["Content"]

    workspace.inspector.content_queue_btn.click()
    assert route_target == ["Content", "Automation"]

    workspace.inspector.analytics_btn.click()
    assert route_target == ["Content", "Automation", "Analytics"]
