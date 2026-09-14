from pathlib import Path

from sp_farms.application.account_exchange_service import AccountExchangeService
from sp_farms.application.account_onboarding_service import AccountOnboardingService
from sp_farms.application.account_service import AccountService
from sp_farms.application.asset_sync_service import AssetSyncService
from sp_farms.application.audit_service import AuditService
from sp_farms.application.campaign_service import CampaignService
from sp_farms.application.caption_ai_service import CaptionAIService
from sp_farms.application.composer_service import ComposerService
from sp_farms.application.content_service import ContentService
from sp_farms.application.context import ApplicationContext
from sp_farms.application.device_pool_service import DevicePoolService
from sp_farms.application.device_service import DeviceService
from sp_farms.application.job_service import JobService
from sp_farms.application.media_prep_job import MediaPrepJobHandler
from sp_farms.application.media_prep_service import MediaPreparationService
from sp_farms.application.meta_client import MetaClientPort
from sp_farms.application.meta_service import MetaIntegrationService
from sp_farms.application.qa_profile_service import QAProfileService
from sp_farms.application.restore_workspace_service import RestoreWorkspaceService
from sp_farms.application.scheduler_service import SchedulerService
from sp_farms.application.secret_service import SecretService
from sp_farms.application.security_service import SecurityService
from sp_farms.application.snapshot_service import SnapshotService
from sp_farms.application.worker import FakeStressJobHandler, WorkerSupervisor
from sp_farms.domain.meta import MetaOAuthConfig
from sp_farms.infrastructure.adb import SubprocessAdbClient
from sp_farms.infrastructure.assets_repository import SqlAlchemyAssetRepository
from sp_farms.infrastructure.clock import SystemClock
from sp_farms.infrastructure.config import load_config
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyAccountRepository,
    SqlAlchemyAuditRepository,
    SqlAlchemyCampaignRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyDevicePoolRepository,
    SqlAlchemyDeviceProfileRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyQAProfileRepository,
    SqlAlchemySchedulerRepository,
    SqlAlchemySecretRepository,
    run_migrations,
)
from sp_farms.infrastructure.fake_ai_provider import FakeMultilingualAIProvider
from sp_farms.infrastructure.logging import configure_logging
from sp_farms.infrastructure.meta.client import MetaHttpClient
from sp_farms.infrastructure.meta.fake_client import FakeMetaApiClient
from sp_farms.infrastructure.providers.ldplayer import LdPlayerProvider
from sp_farms.infrastructure.providers.mumu import MuMuProvider
from sp_farms.infrastructure.providers.physical import PhysicalAndroidProvider
from sp_farms.infrastructure.qa_bridge import AdbQAProfileReloadBridge
from sp_farms.infrastructure.vault import KeyringVault


def create_application(config_path: Path | None = None) -> ApplicationContext:
    config = load_config(config_path)
    log_handler = configure_logging(config)
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
    restore_workspace_service = RestoreWorkspaceService(
        database.unit_of_work,
        SqlAlchemyDeviceProfileRepository,
        account_service,
        device_service,
        adb,
        clock,
        providers=(ldplayer, mumu, physical),
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
    )
    context.add_shutdown_hook(log_handler.close)
    context.add_shutdown_hook(database.close)
    context.add_shutdown_hook(supervisor.stop)
    return context
