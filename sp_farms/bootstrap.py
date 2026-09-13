from pathlib import Path

from sp_farms.application.context import ApplicationContext
from sp_farms.infrastructure.clock import SystemClock
from sp_farms.infrastructure.config import load_config
from sp_farms.infrastructure.logging import configure_logging


def create_application(config_path: Path | None = None) -> ApplicationContext:
    config = load_config(config_path)
    log_handler = configure_logging(config)
    context = ApplicationContext(clock=SystemClock())
    context.add_shutdown_hook(log_handler.close)
    return context
