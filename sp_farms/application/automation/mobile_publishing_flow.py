"""Automated mobile publishing workflow for Facebook Android app via Appium 2."""

import logging
import time

from sp_farms.application.automation.mobile_driver import MobileDriver
from sp_farms.domain.composer import PostType, PublishDestinationType
from sp_farms.infrastructure.appium.page_objects.facebook_screen import (
    FB_PACKAGE,
    FacebookHomeScreen,
)

logger = logging.getLogger(__name__)


def publish_post_via_mobile_app(
    driver: MobileDriver,
    destination_type: PublishDestinationType,
    destination_id: str,
    post_type: PostType,
    caption: str,
    media_paths: list[str] | None = None,
    timeout_seconds: float = 30.0,
) -> str:
    """Execute mobile UI automation flow to publish post on Android Facebook app.

    Returns synthetic or captured post identifier.
    """
    driver.check_cancelled()
    logger.info(
        "Starting mobile Facebook publishing flow for dest_type=%s, dest_id=%s, post_type=%s",
        destination_type.value,
        destination_id,
        post_type.value,
    )

    # 1. Launch Facebook App
    driver.open_app(FB_PACKAGE)
    home = FacebookHomeScreen(driver)
    home.wait_for_screen(timeout_seconds=min(10.0, timeout_seconds))

    driver.check_cancelled()

    # 2. Open Composer
    composer = home.open_composer()

    # 3. Enter Caption
    if caption:
        composer.set_post_text(caption)

    driver.check_cancelled()

    # 4. Submit Post
    composer.submit_post()

    # Allow slight settle time
    time.sleep(1.0)
    driver.check_cancelled()

    post_ref = f"appium-post-{int(time.time())}"
    logger.info("Mobile publishing completed successfully. Generated ref: %s", post_ref)
    return post_ref
