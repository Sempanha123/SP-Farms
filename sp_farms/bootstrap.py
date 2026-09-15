import logging
from pathlib import Path

from sp_farms import __version__
from sp_farms.application.account_exchange_service import AccountExchangeService
from sp_farms.application.account_onboarding_service import AccountOnboardingService
from sp_farms.application.account_service import AccountService
from sp_farms.application.analytics_service import AnalyticsService
from sp_farms.application.approval_service import ApprovalService
from sp_farms.application.asset_sync_service import AssetSyncService
from sp_farms.application.audit_service import AuditService
from sp_farms.application.automation.appium_session_manager import AppiumSessionManager
from sp_farms.application.automation.job_handler import AppiumJobExecutor
from sp_farms.application.automation_builder import AutomationBuilderService
from sp_farms.application.backup_restore_service import BackupRestoreService
from sp_farms.application.campaign_service import CampaignService
from sp_farms.application.caption_ai_service import CaptionAIService
from sp_farms.application.composer_service import ComposerService
from sp_farms.application.content_service import ContentService
from sp_farms.application.context import ApplicationContext
from sp_farms.application.crash_recovery_service import CrashRecoveryService
from sp_farms.application.device_analytics_service import DeviceAnalyticsService
from sp_farms.application.device_pool_service import DevicePoolService
from sp_farms.application.device_service import DeviceService
from sp_farms.application.health_service import HealthService
from sp_farms.application.hybrid_publishing_service import HybridPublishingService
from sp_farms.application.i18n_service import I18nService
from sp_farms.application.job_service import JobService
from sp_farms.application.licensing_service import LicensingService
from sp_farms.application.maintenance_service import MaintenanceService
from sp_farms.application.media_prep_job import MediaPrepJobHandler
from sp_farms.application.media_prep_service import MediaPreparationService
from sp_farms.application.meta_client import MetaClientPort
from sp_farms.application.meta_service import MetaIntegrationService
from sp_farms.application.network_service import NetworkService
from sp_farms.application.plugin_service import (
    PluginService,
    SampleAnalyticsExporterPlugin,
    SampleNotificationPlugin,
)
from sp_farms.application.publishing_service import PublishingService
from sp_farms.application.qa_profile_service import QAProfileService
from sp_farms.application.restore_workspace_service import RestoreWorkspaceService
from sp_farms.application.scheduler_service import SchedulerService
from sp_farms.application.secret_service import SecretService
from sp_farms.application.security_service import SecurityService
from sp_farms.application.selection_context_service import SelectionContextService
from sp_farms.application.snapshot_service import SnapshotService
from sp_farms.application.update_service import UpdateService
from sp_farms.application.worker import FakeStressJobHandler, WorkerSupervisor
from sp_farms.domain.meta import MetaOAuthConfig
from sp_farms.infrastructure.adb import SubprocessAdbClient
from sp_farms.infrastructure.appium.fake_driver import FakeAppiumDriver
from sp_farms.infrastructure.assets_repository import SqlAlchemyAssetRepository
from sp_farms.infrastructure.clock import SystemClock
from sp_farms.infrastructure.config import load_config
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyAccountRepository,
    SqlAlchemyAnalyticsRepository,
    SqlAlchemyApprovalRepository,
    SqlAlchemyAuditRepository,
    SqlAlchemyAutomationPresetRepository,
    SqlAlchemyCampaignRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyDeviceAnalyticsRepository,
    SqlAlchemyDevicePoolRepository,
    SqlAlchemyDeviceProfileRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyPublishRepository,
    SqlAlchemyQAProfileRepository,
    SqlAlchemySchedulerRepository,
    SqlAlchemySecretRepository,
    run_migrations,
)
from sp_farms.infrastructure.diagnostics import create_diagnostics_bundle
from sp_farms.infrastructure.fake_ai_provider import FakeMultilingualAIProvider
from sp_farms.infrastructure.logging import configure_logging
from sp_farms.infrastructure.meta.analytics_adapter import FakeAnalyticsAdapter
from sp_farms.infrastructure.meta.client import MetaHttpClient
from sp_farms.infrastructure.meta.fake_client import FakeMetaApiClient
from sp_farms.infrastructure.meta.publishing_adapter import FakePublishingAdapter
from sp_farms.infrastructure.providers.ldplayer import LdPlayerProvider
from sp_farms.infrastructure.providers.mumu import MuMuProvider
from sp_farms.infrastructure.providers.physical import PhysicalAndroidProvider
from sp_farms.infrastructure.qa_bridge import AdbQAProfileReloadBridge
from sp_farms.infrastructure.vault import KeyringVault


def create_application(config_path: Path | None = None) -> ApplicationContext:
    config = load_config(config_path)
    log_handler = configure_logging(config)

    # Crash recovery and safe mode evaluation
    marker_path = config.database_path.parent / ".startup_marker.json"
    crash_recovery_service = CrashRecoveryService(
        marker_path=marker_path,
        database_path=config.database_path,
    )
    safe_mode_state = crash_recovery_service.evaluate_startup()
    if safe_mode_state.safe_mode_active:
        logging.getLogger(__name__).warning("Booting in Safe Mode: %s", safe_mode_state.reason)
    crash_recovery_service.record_startup()

    database = Database(config.database_path)
    migrations_path = Path(__file__).resolve().parents[1] / "migrations"
    run_migrations(database, migrations_path)

    clock = SystemClock()
    job_service = JobService(database.unit_of_work, SqlAlchemyJobRepository, clock)
    job_service.recover_interrupted_jobs()

    supervisor = WorkerSupervisor(job_service=job_service, clock=clock)
    supervisor.register_handler("stress", FakeStressJobHandler())
    supervisor.register_handler("fake", FakeStressJobHandler())
    media_prep_service = MediaPreparationService(
        output_dir=config.database_path.parent / "content" / "prepared"
    )
    supervisor.register_handler("media_prep", MediaPrepJobHandler(media_prep_service))

    adb = SubprocessAdbClient(config.adb_path)
    ldplayer = LdPlayerProvider(config.ldplayer_path, adb_port=adb)
    mumu = MuMuProvider(config.mumu_path, adb_port=adb)
    physical = PhysicalAndroidProvider(adb_port=adb)
    device_service = DeviceService(
        (ldplayer, mumu, physical),
        database.unit_of_work,
        SqlAlchemyDeviceProfileRepository,
        config.database_path.parent / "device_artifacts",
    )
    qa_profile_service = QAProfileService(
        database.unit_of_work,
        SqlAlchemyQAProfileRepository,
        AdbQAProfileReloadBridge(adb),
        clock,
    )
    account_service = AccountService(
        database.unit_of_work,
        SqlAlchemyAccountRepository,
        clock,
    )
    account_onboarding_service = AccountOnboardingService(account_service)
    network_service = NetworkService(
        unit_of_work_factory=database.unit_of_work,
        adb=adb,
        clock=clock,
    )
    restore_workspace_service = RestoreWorkspaceService(
        database.unit_of_work,
        SqlAlchemyDeviceProfileRepository,
        account_service,
        device_service,
        adb,
        clock,
        providers=(ldplayer, mumu, physical),
        network_service=network_service,
    )
    device_pool_service = DevicePoolService(
        database.unit_of_work,
        SqlAlchemyDevicePoolRepository,
        SqlAlchemyAccountRepository,
        SqlAlchemyDeviceProfileRepository,
        device_service,
        restore_workspace_service,
        clock,
    )
    snapshot_service = SnapshotService(
        database.unit_of_work,
        SqlAlchemyDevicePoolRepository,
        SqlAlchemyAccountRepository,
        SqlAlchemyDeviceProfileRepository,
        config.database_path.parent / "backups",
        clock,
    )

    vault = KeyringVault()
    secret_service = SecretService(vault)
    account_exchange_service = AccountExchangeService(
        accounts=account_service,
        unit_of_work=database.unit_of_work,
        secrets=secret_service,
        secret_repository_factory=SqlAlchemySecretRepository,
    )

    meta_client: MetaClientPort
    if config.meta_app_id and config.meta_app_secret:
        oauth_cfg = MetaOAuthConfig(
            client_id=config.meta_app_id,
            client_secret=config.meta_app_secret,
            redirect_uri=config.meta_redirect_uri,
            graph_version=config.meta_api_version,
        )
        meta_client = MetaHttpClient(oauth_cfg)
    else:
        meta_client = FakeMetaApiClient(
            app_id=config.meta_app_id or "sp_farms_offline_app",
            redirect_uri=config.meta_redirect_uri,
        )

    meta_service = MetaIntegrationService(
        meta_client=meta_client,
        secret_service=secret_service,
    )

    asset_sync_service = AssetSyncService(
        unit_of_work=database.unit_of_work,
        asset_repository_factory=SqlAlchemyAssetRepository,
        meta_client=meta_client,
        secret_service=secret_service,
        secret_repository_factory=SqlAlchemySecretRepository,
        clock=clock,
    )

    security_service = SecurityService(
        account_service=account_service,
        secret_service=secret_service,
        unit_of_work=database.unit_of_work,
        secret_repository_factory=SqlAlchemySecretRepository,
        meta_service=meta_service,
        clock=clock,
    )

    audit_service = AuditService(
        unit_of_work=database.unit_of_work,
        audit_repository_factory=SqlAlchemyAuditRepository,
        clock=clock,
        job_service=job_service,
    )

    content_service = ContentService(
        unit_of_work=database.unit_of_work,
        content_repository_factory=SqlAlchemyContentRepository,
        clock=clock,
        storage_dir=config.database_path.parent / "content",
    )

    composer_service = ComposerService(
        unit_of_work=database.unit_of_work,
        content_repo_factory=SqlAlchemyContentRepository,
        asset_repo_factory=SqlAlchemyAssetRepository,
        clock=clock,
    )

    fake_ai_provider = FakeMultilingualAIProvider(configured=True)
    caption_ai_service = CaptionAIService(
        unit_of_work=database.unit_of_work,
        content_repo_factory=SqlAlchemyContentRepository,
        secret_service=secret_service,
        secret_repo_factory=SqlAlchemySecretRepository,
        ai_provider=fake_ai_provider,
    )

    campaign_service = CampaignService(
        unit_of_work=database.unit_of_work,
        campaign_repo_factory=SqlAlchemyCampaignRepository,
        content_service=content_service,
    )

    scheduler_service = SchedulerService(
        unit_of_work=database.unit_of_work,
        scheduler_repo_factory=SqlAlchemySchedulerRepository,
        clock=clock,
    )

    approval_service = ApprovalService(
        unit_of_work=database.unit_of_work,
        approval_repo_factory=SqlAlchemyApprovalRepository,
        clock=clock,
        audit_service=audit_service,
        job_service=job_service,
    )

    fake_publisher = FakePublishingAdapter()
    publishing_service = PublishingService(
        publishing_port=fake_publisher,
        unit_of_work=database.unit_of_work,
        publish_repo_factory=SqlAlchemyPublishRepository,
        audit_service=audit_service,
        schedule_service=scheduler_service,
        campaign_service=campaign_service,
        job_service=job_service,
    )

    appium_session = AppiumSessionManager(driver_port=FakeAppiumDriver())
    appium_executor = AppiumJobExecutor(
        session_manager=appium_session,
        device_pool_service=device_pool_service,
    )

    hybrid_publishing_service = HybridPublishingService(
        publishing_service=publishing_service,
        appium_executor=appium_executor,
        device_pool_service=device_pool_service,
        audit_service=audit_service,
    )

    fake_analytics_adapter = FakeAnalyticsAdapter()
    analytics_service = AnalyticsService(
        analytics_port=fake_analytics_adapter,
        unit_of_work=database.unit_of_work,
        analytics_repo_factory=SqlAlchemyAnalyticsRepository,
        publish_repo_factory=SqlAlchemyPublishRepository,
        audit_service=audit_service,
    )

    device_analytics_service = DeviceAnalyticsService(
        unit_of_work=database.unit_of_work,
        repo_factory=SqlAlchemyDeviceAnalyticsRepository,
        clock=clock,
    )

    backup_restore_service = BackupRestoreService(
        database_path=config.database_path,
        settings_path=config.database_path.parent / "settings.json",
        workspace_dir=config.database_path.parent,
        backup_dir=config.database_path.parent / "backups",
        vault=vault,
        clock=clock,
    )

    licensing_service = LicensingService()
    i18n_service = I18nService()
    update_service = UpdateService(current_version=__version__)

    def _probe_adb() -> tuple[bool, str]:
        avail = bool(adb.adb_path and adb.adb_path.exists())
        return avail, "ADB ready" if avail else "ADB not found"

    def _probe_ldplayer() -> tuple[bool, str]:
        try:
            ldplayer.resolve_executable()
            return True, "LDPlayer detected"
        except Exception:
            return False, "LDPlayer not found"

    def _probe_mumu() -> tuple[bool, str]:
        try:
            mumu.resolve_executable()
            return True, "MuMu detected"
        except Exception:
            return False, "MuMu not found"

    health_service = HealthService(
        config=config,
        vault_probe=lambda: True,
        adb_probe=_probe_adb,
        ldplayer_probe=_probe_ldplayer,
        mumu_probe=_probe_mumu,
        physical_probe=lambda: (True, f"{len(physical.list_instances())} physical device(s)"),
        scheduler_probe=lambda: (True, "Scheduler operational"),
        workers_probe=lambda: (
            supervisor.is_running,
            "Worker supervisor active" if supervisor.is_running else "Worker supervisor idle",
        ),
        export_bundle_handler=lambda dest, summary: create_diagnostics_bundle(
            destination=dest,
            config=config,
            health_summary=summary,
        ),
    )

    plugins_dir = config.database_path.parent / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)
    plugin_service = PluginService(plugins_dir=plugins_dir)
    # Register reference built-in plugins
    plugin_service.register_instance(SampleAnalyticsExporterPlugin())
    plugin_service.register_instance(SampleNotificationPlugin())
    plugin_service.discover_and_load_all()

    uow = database.unit_of_work()
    automation_preset_repo = SqlAlchemyAutomationPresetRepository(uow)
    automation_builder_service = AutomationBuilderService(
        repository=automation_preset_repo,
        audit_service=audit_service,
        job_service=job_service,
    )
    with uow:
        automation_builder_service.initialize_built_in_presets_if_missing()

    selection_context_service = SelectionContextService(
        account_service=account_service,
        restore_workspace_service=restore_workspace_service,
        asset_repository_factory=SqlAlchemyAssetRepository,
        unit_of_work_factory=database.unit_of_work,
        device_service=device_service,
    )

    maintenance_service = MaintenanceService(
        account_service=account_service,
        security_service=security_service,
        secret_service=secret_service,
        adb=adb,
    )

    context = ApplicationContext(
        clock=clock,
        unit_of_work=database.unit_of_work,
        job_service=job_service,
        worker_supervisor=supervisor,
        adb=adb,
        ldplayer=ldplayer,
        mumu=mumu,
        physical=physical,
        device_service=device_service,
        qa_profile_service=qa_profile_service,
        account_service=account_service,
        account_onboarding_service=account_onboarding_service,
        account_exchange_service=account_exchange_service,
        restore_workspace_service=restore_workspace_service,
        device_pool_service=device_pool_service,
        snapshot_service=snapshot_service,
        meta_client=meta_client,
        meta_service=meta_service,
        asset_sync_service=asset_sync_service,
        security_service=security_service,
        audit_service=audit_service,
        content_service=content_service,
        composer_service=composer_service,
        caption_ai_service=caption_ai_service,
        campaign_service=campaign_service,
        scheduler_service=scheduler_service,
        approval_service=approval_service,
        publishing_service=publishing_service,
        hybrid_publishing_service=hybrid_publishing_service,
        analytics_service=analytics_service,
        device_analytics_service=device_analytics_service,
        backup_restore_service=backup_restore_service,
        plugin_service=plugin_service,
        licensing_service=licensing_service,
        i18n_service=i18n_service,
        crash_recovery_service=crash_recovery_service,
        health_service=health_service,
        update_service=update_service,
        automation_builder_service=automation_builder_service,
        selection_context_service=selection_context_service,
        network_service=network_service,
        maintenance_service=maintenance_service,
    )
    context.add_shutdown_hook(crash_recovery_service.record_clean_shutdown)
    context.add_shutdown_hook(log_handler.close)
    context.add_shutdown_hook(database.close)
    context.add_shutdown_hook(supervisor.stop)
    return context
