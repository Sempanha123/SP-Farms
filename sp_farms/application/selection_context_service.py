"""Application service for resolving selection context and device bindings."""

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.assets import AssetHealthState, AssetPermission, Page
from sp_farms.domain.device_restore import AccountDeviceBinding
from sp_farms.domain.selection_context import (
    ResolvedTarget,
    SelectionContext,
    SelectionSource,
    TargetCapability,
    TargetType,
)

if TYPE_CHECKING:
    from sp_farms.application.account_service import AccountService
    from sp_farms.application.asset_repository import AssetRepository
    from sp_farms.application.device_service import DeviceService
    from sp_farms.application.restore_workspace_service import RestoreWorkspaceService


class SelectionContextService:
    """Resolves rich selection context across Accounts, Pages, and Devices."""

    def __init__(
        self,
        account_service: "AccountService",
        restore_workspace_service: "RestoreWorkspaceService | None" = None,
        asset_repository_factory: "Callable[[UnitOfWork], AssetRepository] | None" = None,
        unit_of_work_factory: "Callable[[], UnitOfWork] | None" = None,
        device_service: "DeviceService | None" = None,
    ) -> None:
        self._accounts = account_service
        self._restore_service = restore_workspace_service
        self._asset_repo_factory = asset_repository_factory
        self._uow_factory = unit_of_work_factory
        self._device_service = device_service

    def resolve_context(
        self,
        source_module: SelectionSource,
        account_ids: Sequence[str] = (),
        page_ids: Sequence[str] = (),
        device_ids: Sequence[str] = (),
        group_ids: Sequence[str] = (),
    ) -> SelectionContext:
        """Resolve selection context and infer target bindings."""
        resolved_targets: list[ResolvedTarget] = []
        inferred_accounts: set[str] = set()
        inferred_devices: set[str] = set()

        if source_module == SelectionSource.ACCOUNTS:
            for acc_id in account_ids:
                target = self._resolve_account_target(acc_id)
                if target:
                    resolved_targets.append(target)
                    inferred_accounts.add(target.target_id)
                    if target.bound_device_id:
                        inferred_devices.add(target.bound_device_id)

        elif source_module == SelectionSource.PAGES:
            for p_id in page_ids:
                target = self._resolve_page_target(p_id)
                if target:
                    resolved_targets.append(target)
                    if target.owning_account_id:
                        inferred_accounts.add(target.owning_account_id)
                    if target.bound_device_id:
                        inferred_devices.add(target.bound_device_id)

        elif source_module == SelectionSource.DEVICES:
            for d_id in device_ids:
                target = self._resolve_device_target(d_id)
                if target:
                    resolved_targets.append(target)
                    inferred_devices.add(target.target_id)
                    if target.owning_account_id:
                        inferred_accounts.add(target.owning_account_id)

        common_caps, mixed_caps = self._compute_capabilities(resolved_targets)

        return SelectionContext(
            source_module=source_module,
            selected_account_ids=tuple(account_ids),
            selected_page_ids=tuple(page_ids),
            selected_device_ids=tuple(device_ids),
            selected_group_ids=tuple(group_ids),
            resolved_targets=tuple(resolved_targets),
            inferred_account_ids=tuple(sorted(inferred_accounts)),
            inferred_device_ids=tuple(sorted(inferred_devices)),
            common_capabilities=tuple(sorted(common_caps)),
            mixed_capabilities=tuple(sorted(mixed_caps)),
        )

    def _resolve_account_target(self, account_id: str) -> ResolvedTarget | None:
        try:
            account = self._accounts.get_account(account_id)
        except Exception:
            return None

        binding: AccountDeviceBinding | None = None
        device_profile_id: str | None = None
        device_provider: str | None = None

        if self._restore_service:
            binding = self._restore_service.get_binding(account_id)
            if binding and binding.device_profile_id:
                device_profile_id = binding.device_profile_id
                prof = self._restore_service.get_profile(device_profile_id)
                if prof:
                    device_provider = prof.provider.value

        auth_state = "ready"
        if account.status.value in ("checkpoint", "suspended", "disabled"):
            auth_state = "needs_reauth"
        elif account.security_state.value == "critical":
            auth_state = "needs_reauth"

        capabilities = TargetCapability(
            can_restore=True,
            can_post_feed=True,
            can_post_video=True,
            can_post_reel=True,
            can_post_story=False,
            can_reply_comments=True,
            can_manage_inbox=True,
            can_collect_analytics=True,
            can_backup=True,
            can_manage_device=True,
            requires_approval=False,
        )

        return ResolvedTarget(
            target_id=account.id,
            target_type=TargetType.ACCOUNT,
            display_name=account.display_name,
            owning_account_id=account.id,
            owning_account_name=account.display_name,
            bound_device_id=device_profile_id,
            bound_device_provider=device_provider,
            preferred_app=account.preferred_app.value,
            auth_state=auth_state,
            health_status=account.status.value,
            capabilities=capabilities,
        )

    def _resolve_page_target(self, page_id: str) -> ResolvedTarget | None:
        page: Page | None = None
        if self._uow_factory and self._asset_repo_factory:
            with self._uow_factory() as uow:
                repo = self._asset_repo_factory(uow)
                page = repo.get_page(page_id)
                if page is None:
                    # Try finding by meta page_id
                    all_pages = repo.list_all_pages()
                    page = next((p for p in all_pages if p.page_id == page_id or p.id == page_id), None)

        if page is None:
            return None

        # Resolve owning account
        owning_acc = None
        bound_device_id = None
        bound_device_provider = None
        preferred_app = "facebook"
        auth_state = "ready"

        try:
            owning_acc = self._accounts.get_account(page.account_id)
            preferred_app = owning_acc.preferred_app.value
            if owning_acc.status.value in ("checkpoint", "suspended", "disabled"):
                auth_state = "needs_reauth"
        except Exception:
            pass

        if owning_acc and self._restore_service:
            binding = self._restore_service.get_binding(owning_acc.id)
            if binding and binding.device_profile_id:
                bound_device_id = binding.device_profile_id
                prof = self._restore_service.get_profile(bound_device_id)
                if prof:
                    bound_device_provider = prof.provider.value

        can_publish = page.is_publishing_eligible()
        can_moderate = page.has_task(AssetPermission.MODERATE) or page.has_task(AssetPermission.MANAGE)
        can_message = page.has_task(AssetPermission.MESSAGING) or page.has_task(AssetPermission.MANAGE)
        can_analyze = page.has_task(AssetPermission.ANALYZE) or page.has_task(AssetPermission.MANAGE)

        if page.health != AssetHealthState.HEALTHY:
            auth_state = "needs_reauth" if page.health == AssetHealthState.RESTRICTED else "degraded"

        capabilities = TargetCapability(
            can_restore=True,
            can_post_feed=can_publish,
            can_post_video=can_publish,
            can_post_reel=can_publish,
            can_post_story=False,  # Graph API restrictions
            can_reply_comments=can_moderate,
            can_manage_inbox=can_message,
            can_collect_analytics=can_analyze,
            can_backup=True,
            can_manage_device=True,
        )

        return ResolvedTarget(
            target_id=page.id,
            target_type=TargetType.PAGE,
            display_name=page.name,
            owning_account_id=page.account_id,
            owning_account_name=owning_acc.display_name if owning_acc else None,
            bound_device_id=bound_device_id,
            bound_device_provider=bound_device_provider,
            preferred_app=preferred_app,
            auth_state=auth_state,
            health_status=page.health.value,
            capabilities=capabilities,
        )

    def _resolve_device_target(self, device_id: str) -> ResolvedTarget | None:
        profile = None
        if self._restore_service:
            profile = self._restore_service.get_profile(device_id)

        display_name = profile.friendly_name if profile else device_id
        provider_name = profile.provider.value if profile else "unknown"

        # Check if any account is currently bound
        owning_acc_id = None
        owning_acc_name = None
        if profile and self._restore_service:
            bindings = []
            # Check bindings
            for acc in self._accounts.list_accounts():
                b = self._restore_service.get_binding(acc.id)
                if b and b.device_profile_id == profile.id:
                    owning_acc_id = acc.id
                    owning_acc_name = acc.display_name
                    break

        capabilities = TargetCapability(
            can_restore=True,
            can_post_feed=False,
            can_post_video=False,
            can_post_reel=False,
            can_post_story=False,
            can_reply_comments=False,
            can_manage_inbox=False,
            can_collect_analytics=False,
            can_backup=True,
            can_manage_device=True,
        )

        return ResolvedTarget(
            target_id=device_id,
            target_type=TargetType.DEVICE,
            display_name=display_name,
            owning_account_id=owning_acc_id,
            owning_account_name=owning_acc_name,
            bound_device_id=device_id,
            bound_device_provider=provider_name,
            preferred_app="facebook",
            auth_state="ready",
            health_status="healthy",
            capabilities=capabilities,
        )

    def _compute_capabilities(
        self, targets: Sequence[ResolvedTarget]
    ) -> tuple[set[str], set[str]]:
        if not targets:
            return set(), set()

        all_cap_names = (
            "can_restore",
            "can_post_feed",
            "can_post_video",
            "can_post_reel",
            "can_post_story",
            "can_reply_comments",
            "can_manage_inbox",
            "can_collect_analytics",
            "can_backup",
            "can_manage_device",
        )

        common: set[str] = set()
        mixed: set[str] = set()

        for cap_name in all_cap_names:
            vals = [getattr(t.capabilities, cap_name) for t in targets]
            if all(vals):
                common.add(cap_name)
            elif any(vals):
                mixed.add(cap_name)

        return common, mixed
