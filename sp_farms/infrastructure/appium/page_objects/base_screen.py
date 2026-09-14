"""Base Page Object class for Android screens."""

import logging
from typing import Any

from sp_farms.application.automation.mobile_driver import MobileDriver
from sp_farms.domain.automation import By, ElementRef

logger = logging.getLogger(__name__)


class BaseScreen:
    """Base class for Android screen/page objects."""

    def __init__(self, driver: MobileDriver) -> None:
        self.driver = driver

    def is_screen_active(self, timeout_seconds: float = 5.0) -> bool:
        """Override to provide validation that this screen is currently active."""
        raise NotImplementedError

    def wait_for_screen(self, timeout_seconds: float = 10.0) -> bool:
        """Poll until this screen is active."""
        try:
            return self.is_screen_active(timeout_seconds=timeout_seconds)
        except Exception as e:
            logger.debug("Screen %s not active: %s", self.__class__.__name__, e)
            return False
