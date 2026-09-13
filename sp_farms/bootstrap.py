from pathlib import Path

from sp_farms.application.context import ApplicationContext
from sp_farms.infrastructure.clock import SystemClock
from sp_farms.infrastructure.config import load_config
from sp_farms.infrastructure.database import Database, run_migrations
from sp_farms.infrastructure.logging import configure_logging


def create_application(config_path: Path | None = None) -> ApplicationContext:
    config = load_config(config_path)
    log_handler = configure_logging(config)
    database = Database(config.database_path)
    migrations_path = Path(__file__).resolve().parents[1] / "migrations"
    run_migrations(database, migrations_path)
    context = ApplicationContext(clock=SystemClock(), unit_of_work=database.unit_of_work)
    context.add_shutdown_hook(log_handler.close)
    context.add_shutdown_hook(database.close)
    return context
