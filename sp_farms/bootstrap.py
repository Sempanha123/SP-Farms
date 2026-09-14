from pathlib import Path

from sp_farms.application.context import ApplicationContext
from sp_farms.application.job_service import JobService
from sp_farms.application.worker import FakeStressJobHandler, WorkerSupervisor
from sp_farms.infrastructure.adb import SubprocessAdbClient
from sp_farms.infrastructure.clock import SystemClock
from sp_farms.infrastructure.config import load_config
from sp_farms.infrastructure.database import Database, SqlAlchemyJobRepository, run_migrations
from sp_farms.infrastructure.logging import configure_logging
from sp_farms.infrastructure.providers.ldplayer import LdPlayerProvider
from sp_farms.infrastructure.providers.mumu import MuMuProvider


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

    adb = SubprocessAdbClient(config.adb_path)
    ldplayer = LdPlayerProvider(config.ldplayer_path, adb_port=adb)
    mumu = MuMuProvider(config.mumu_path, adb_port=adb)

    context = ApplicationContext(
        clock=clock,
        unit_of_work=database.unit_of_work,
        job_service=job_service,
        worker_supervisor=supervisor,
        adb=adb,
        ldplayer=ldplayer,
        mumu=mumu,
    )
    context.add_shutdown_hook(log_handler.close)
    context.add_shutdown_hook(database.close)
    context.add_shutdown_hook(supervisor.stop)
    return context
