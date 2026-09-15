"""Hybrid publishing service combining Meta Graph API and Appium 2 Android UI automation."""

import logging
import time
from collections.abc import Mapping
from typing import Any

from sp_farms.application.audit_service import AuditService
from sp_farms.application.automation.job_handler import AppiumJobExecutor
from sp_farms.application.automation.mobile_driver import MobileDriver
from sp_farms.application.automation.mobile_publishing_flow import publish_post_via_mobile_app
from sp_farms.application.device_pool_service import DevicePoolService
from sp_farms.application.publishing_service import PublishingService
from sp_farms.application.worker import JobExecutionContext
from sp_farms.domain.audit import AuditResult
from sp_farms.domain.composer import PostType, PublishDestinationType
from sp_farms.domain.publishing import (
    PublishAttempt,
    PublishErrorCode,
    PublishExecutionStrategy,
    PublishMethod,
    PublishStatus,
    is_api_supported_destination,
)

logger = logging.getLogger(__name__)


class HybridPublishingService:
    """Orchestrates hybrid publishing using Meta Graph API with Appium fallback."""

    def __init__(
        self,
        publishing_service: PublishingService,
        appium_executor: AppiumJobExecutor | None = None,
        device_pool_service: DevicePoolService | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        self.publishing_service = publishing_service
        self.appium_executor = appium_executor
        self.device_pool_service = device_pool_service
        self.audit_service = audit_service

    def execute_publish(
        self,
        destination_type: PublishDestinationType,
        destination_id: str,
        destination_name: str,
        post_type: PostType,
        payload: Mapping[str, Any],
        access_token: str = "",
        account_id: str = "acc-default",
        device_key: str = "physical:default",
        strategy: PublishExecutionStrategy = PublishExecutionStrategy.HYBRID_AUTO,
        scheduled_item_id: str | None = None,
        campaign_id: str | None = None,
        job_id: str | None = None,
        idempotency_key: str | None = None,
        execution_context: JobExecutionContext | None = None,
        initiator: str = "operator",
    ) -> PublishAttempt:
        """Execute publishing using selected strategy (API, Appium, or Hybrid)."""
        caption = str(payload.get("caption", payload.get("message", "")))
        api_supported = is_api_supported_destination(destination_type, post_type)

        # 1. Direct Appium path
        if strategy == PublishExecutionStrategy.APPIUM_ONLY or (
            strategy == PublishExecutionStrategy.HYBRID_AUTO and not api_supported
        ):
            reason = (
                "Destination or format not supported by Meta Graph API"
                if not api_supported
                else "Appium only strategy requested"
            )
            logger.info("Publishing directly via Appium Android UI automation: %s", reason)
            return self._publish_via_appium(
                destination_type=destination_type,
                destination_id=destination_id,
                destination_name=destination_name,
                post_type=post_type,
                payload=payload,
                caption=caption,
                account_id=account_id,
                device_key=device_key,
                scheduled_item_id=scheduled_item_id,
                campaign_id=campaign_id,
                job_id=job_id,
                idempotency_key=idempotency_key,
                execution_context=execution_context,
                initiator=initiator,
                fallback_reason=reason,
            )

        # 2. Try API First
        attempt = self.publishing_service.execute_publish(
            destination_type=destination_type,
            destination_id=destination_id,
            destination_name=destination_name,
            access_token=access_token,
            post_type=post_type,
            payload=payload,
            scheduled_item_id=scheduled_item_id,
            campaign_id=campaign_id,
            job_id=job_id,
            idempotency_key=idempotency_key,
            initiator=initiator,
        )

        # If API succeeded or strategy is strictly API_ONLY, return as-is
        if (
            attempt.status == PublishStatus.PUBLISHED
            or strategy == PublishExecutionStrategy.API_ONLY
        ):
            return attempt

        # 3. Hybrid Fallback: If API failed due to permission denial or unsupported payload
        if strategy == PublishExecutionStrategy.HYBRID_AUTO and attempt.error_code in (
            PublishErrorCode.PERMISSION_DENIED,
            PublishErrorCode.INVALID_PAYLOAD,
            PublishErrorCode.UNKNOWN,
        ):
            fallback_reason = (
                f"Graph API returned {attempt.error_code.value}: {attempt.error_message}. "
                "Falling back to Appium automation."
            )
            logger.warning(fallback_reason)

            if self.audit_service:
                self.audit_service.record_event(
                    initiator=initiator,
                    action="publish.hybrid.fallback_to_appium",
                    target_type="publish_attempt",
                    target_id=attempt.id,
                    result=AuditResult.WARNING,
                    details={
                        "original_attempt_id": attempt.id,
                        "destination_id": destination_id,
                        "reason": fallback_reason,
                    },
                )

            return self._publish_via_appium(
                destination_type=destination_type,
                destination_id=destination_id,
                destination_name=destination_name,
                post_type=post_type,
                payload=payload,
                caption=caption,
                account_id=account_id,
                device_key=device_key,
                scheduled_item_id=scheduled_item_id,
                campaign_id=campaign_id,
                job_id=job_id,
                idempotency_key=f"{idempotency_key or attempt.id}_appium_fallback",
                execution_context=execution_context,
                initiator=initiator,
                fallback_reason=fallback_reason,
            )

        return attempt

    def _publish_via_appium(
        self,
        destination_type: PublishDestinationType,
        destination_id: str,
        destination_name: str,
        post_type: PostType,
        payload: Mapping[str, Any],
        caption: str,
        account_id: str,
        device_key: str,
        scheduled_item_id: str | None,
        campaign_id: str | None,
        job_id: str | None,
        idempotency_key: str | None,
        execution_context: JobExecutionContext | None,
        initiator: str,
        fallback_reason: str,
    ) -> PublishAttempt:
        """Execute Android mobile publishing action via Appium executor."""
        attempt = PublishAttempt.create(
            destination_type=destination_type,
            destination_id=destination_id,
            destination_name=destination_name,
            post_type=post_type,
            payload=payload,
            method_used=PublishMethod.APPIUM,
            scheduled_item_id=scheduled_item_id,
            campaign_id=campaign_id,
            job_id=job_id,
            idempotency_key=idempotency_key,
        )

        start_time = time.monotonic()

        if not self.appium_executor:
            err_msg = "Appium executor is not configured for mobile automation fallback"
            logger.error(err_msg)
            failed_attempt = attempt.mark_failed(
                error_code=PublishErrorCode.UNKNOWN,
                error_message=err_msg,
                method_used=PublishMethod.APPIUM,
            )
            self.publishing_service._save_attempt(failed_attempt)
            return failed_attempt

        def _action(driver: MobileDriver, ctx: JobExecutionContext | None) -> str:
            return publish_post_via_mobile_app(
                driver=driver,
                destination_type=destination_type,
                destination_id=destination_id,
                post_type=post_type,
                caption=caption,
            )

        try:
            if execution_context:
                post_ref = self.appium_executor.execute_with_device(
                    context=execution_context,
                    account_id=account_id,
                    device_key=device_key,
                    action=_action,
                )
            else:
                # Direct device run if outside worker supervisor context
                driver = self.appium_executor.session_manager.get_mobile_driver(device_key)
                post_ref = _action(driver, None)

            duration_ms = int((time.monotonic() - start_time) * 1000)
            published_attempt = attempt.mark_published(
                external_post_id=post_ref,
                duration_ms=duration_ms,
                method_used=PublishMethod.APPIUM,
            )
            self.publishing_service._save_attempt(published_attempt)

            if self.audit_service:
                self.audit_service.record_event(
                    initiator=initiator,
                    action="publish.appium.success",
                    target_type="publish_attempt",
                    target_id=published_attempt.id,
                    result=AuditResult.SUCCESS,
                    details={
                        "attempt_id": published_attempt.id,
                        "destination_id": destination_id,
                        "destination_name": destination_name,
                        "method": "appium",
                        "post_ref": post_ref,
                        "fallback_reason": fallback_reason,
                    },
                )

            return published_attempt

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            err_msg = f"Appium automation failure: {e}"
            logger.error(err_msg)
            failed_attempt = attempt.mark_failed(
                error_code=PublishErrorCode.UNKNOWN,
                error_message=err_msg,
                duration_ms=duration_ms,
                method_used=PublishMethod.APPIUM,
            )
            self.publishing_service._save_attempt(failed_attempt)
            return failed_attempt
