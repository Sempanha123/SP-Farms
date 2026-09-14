from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sp_farms.application.ports import Clock
from sp_farms.application.unit_of_work import UnitOfWork

if TYPE_CHECKING:
    from sp_farms.application.account_exchange_service import AccountExchangeService
    from sp_farms.application.account_onboarding_service import AccountOnboardingService
    from sp_farms.application.account_service import AccountService
    from sp_farms.application.adb import AdbPort
    from sp_farms.application.asset_sync_service import AssetSyncService
    from sp_farms.application.audit_service import AuditService
    from sp_farms.application.composer_service import ComposerService
    from sp_farms.application.content_service import ContentService
    from sp_farms.application.device_pool_service import DevicePoolService
    from sp_farms.application.device_service import DeviceService
    from sp_farms.application.job_service import JobService
    from sp_farms.application.meta_client import MetaClientPort
    from sp_farms.application.meta_service import MetaIntegrationService
    from sp_farms.application.providers import DeviceProviderPort
    from sp_farms.application.qa_profile_service import QAProfileService
    from sp_farms.application.restore_workspace_service import RestoreWorkspaceService
    from sp_farms.application.security_service import SecurityService
    from sp_farms.application.snapshot_service import SnapshotService
    from sp_farms.application.worker import WorkerSupervisor

ShutdownHook = Callable[[], None]


@dataclass(slots=True)
class ApplicationContext:
    clock: Clock
    unit_of_work: Callable[[], UnitOfWork] | None = None
    job_service: "JobService | None" = None
    worker_supervisor: "WorkerSupervisor | None" = None
    adb: "AdbPort | None" = None
    ldplayer: "DeviceProviderPort | None" = None
    mumu: "DeviceProviderPort | None" = None
    physical: "DeviceProviderPort | None" = None
    device_service: "DeviceService | None" = None
    qa_profile_service: "QAProfileService | None" = None
    account_service: "AccountService | None" = None
    account_onboarding_service: "AccountOnboardingService | None" = None
    account_exchange_service: "AccountExchangeService | None" = None
    restore_workspace_service: "RestoreWorkspaceService | None" = None
    device_pool_service: "DevicePoolService | None" = None
    snapshot_service: "SnapshotService | None" = None
    meta_client: "MetaClientPort | None" = None
    meta_service: "MetaIntegrationService | None" = None
    asset_sync_service: "AssetSyncService | None" = None
    security_service: "SecurityService | None" = None
    audit_service: "AuditService | None" = None
    content_service: "ContentService | None" = None
    composer_service: "ComposerService | None" = None
    _shutdown_hooks: list[ShutdownHook] = field(default_factory=list)
    _closed: bool = False

    def add_shutdown_hook(self, hook: ShutdownHook) -> None:
        if self._closed:
            raise RuntimeError("Application context is closed")
        self._shutdown_hooks.append(hook)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for hook in reversed(self._shutdown_hooks):
            hook()
