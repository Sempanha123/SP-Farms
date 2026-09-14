"""Page object for Facebook Android application screens and core interactions."""

import logging
from typing import Final

from sp_farms.domain.automation import By
from sp_farms.infrastructure.appium.page_objects.base_screen import BaseScreen

logger = logging.getLogger(__name__)

FB_PACKAGE: Final[str] = "com.facebook.katana"
FB_LITE_PACKAGE: Final[str] = "com.facebook.lite"


class FacebookHomeScreen(BaseScreen):
    """Encapsulates elements and actions on Facebook Android Home Feed."""

    NEWS_FEED_TAB = (By.ACCESSIBILITY_ID, "News Feed")
    CREATE_POST_BAR = (By.XPATH, "//*[@content-desc=\"What's on your mind?\" or @text=\"What's on your mind?\"]")
    NOTIFICATIONS_TAB = (By.ACCESSIBILITY_ID, "Notifications")
    MENU_TAB = (By.ACCESSIBILITY_ID, "Menu")
    PROFILE_TAB = (By.ACCESSIBILITY_ID, "Profile")

    def is_screen_active(self, timeout_seconds: float = 5.0) -> bool:
        try:
            self.driver.wait_for_element(*self.CREATE_POST_BAR, timeout_seconds=timeout_seconds)
            return True
        except Exception:
            return False

    def open_composer(self) -> "FacebookComposerScreen":
        logger.info("Opening Facebook Post Composer")
        self.driver.tap(*self.CREATE_POST_BAR)
        composer = FacebookComposerScreen(self.driver)
        composer.wait_for_screen(timeout_seconds=8.0)
        return composer


class FacebookComposerScreen(BaseScreen):
    """Encapsulates elements and actions on Facebook Post Creation screen."""

    STATUS_INPUT = (By.XPATH, "//android.widget.EditText")
    POST_BUTTON = (By.XPATH, "//*[@text='POST' or @text='Publish' or @content-desc='Post']")
    ADD_PHOTO_VIDEO = (By.XPATH, "//*[@content-desc='Photo/video' or @text='Photo/video']")
    AUDIENCE_SELECTOR = (By.XPATH, "//*[@content-desc='Audience' or @text='Public' or @text='Friends']")

    def is_screen_active(self, timeout_seconds: float = 5.0) -> bool:
        try:
            self.driver.wait_for_element(*self.STATUS_INPUT, timeout_seconds=timeout_seconds)
            return True
        except Exception:
            return False

    def set_post_text(self, text: str) -> None:
        logger.info("Setting post text in Facebook Composer")
        self.driver.type_text(*self.STATUS_INPUT, text=text, clear_first=True)

    def submit_post(self) -> None:
        logger.info("Submitting post via Facebook Composer")
        self.driver.tap(*self.POST_BUTTON)
