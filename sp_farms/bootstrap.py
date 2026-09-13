from sp_farms.application.context import ApplicationContext
from sp_farms.infrastructure.clock import SystemClock


def create_application() -> ApplicationContext:
    return ApplicationContext(clock=SystemClock())
