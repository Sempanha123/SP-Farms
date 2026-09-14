"""Application service orchestrating official Meta Graph API publishing execution."""

import time
from collections.abc import Callable, Mapping
from typing import Any

from sp_farms.application.audit_service import AuditService
from sp_farms.application.campaign_service import CampaignService
from sp_farms.application.job_service import JobService
from sp_farms.application.publish_repository import PublishRepositoryPort
from sp_farms.application.publishing_port import PublishingPort
from sp_farms.application.scheduler_service import SchedulerService
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.audit import AuditResult
from sp_farms.domain.campaigns import CampaignStatus, TargetStatus
from sp_farms.domain.composer import PostType, PublishDestinationType
from sp_farms.domain.publishing import PublishAttempt, PublishErrorCode, PublishStatus
from sp_farms.domain.scheduler import ScheduledItemStatus
from sp_farms.infrastructure.logging import get_logger
from sp_farms.infrastructure.meta.publishing_adapter import map_exception_to_publish_error

logger = get_logger("application.publishing_service")


class PublishingService:
    """Service that executes official post publishing with retry policies and state updates."""

    def __init__(
        self,
        publishing_port: PublishingPort,
        unit_of_work: Callable[[], UnitOfWork] | None = None,
        publish_repo_factory: Callable[[UnitOfWork], PublishRepositoryPort] | None = None,
        repository_factory: Callable[[], PublishRepositoryPort] | None = None,
        audit_service: AuditService | None = None,
        schedule_service: SchedulerService | None = None,
        campaign_service: CampaignService | None = None,
        job_service: JobService | None = None,
        backoff_base_seconds: float = 0.1,  # Low default for fast unit testing; configurable
    ) -> None:
        self._publisher = publishing_port
        self._uow = unit_of_work
        self._publish_repo_factory = publish_repo_factory
        self._repository_factory = repository_factory
        self._audit_service = audit_service
        self._schedule_service = schedule_service
        self._campaign_service = campaign_service
        self._job_service = job_service
        self._backoff_base_seconds = backoff_base_seconds

    def _get_existing(self, idempotency_key: str) -> PublishAttempt | None:
        if self._uow and self._publish_repo_factory:
            with self._uow() as uow:
                repo = self._publish_repo_factory(uow)
                return repo.get_by_idempotency_key(idempotency_key)
        elif self._repository_factory:
            return self._repository_factory().get_by_idempotency_key(idempotency_key)
        return None

    def _save_attempt(self, attempt: PublishAttempt) -> None:
        if self._uow and self._publish_repo_factory:
            with self._uow() as uow:
                repo = self._publish_repo_factory(uow)
                repo.save(attempt)
                uow.commit()
        elif self._repository_factory:
            self._repository_factory().save(attempt)

    def execute_publish(
        self,
        destination_type: PublishDestinationType,
        destination_id: str,
        destination_name: str,
        access_token: str,
        post_type: PostType,
        payload: Mapping[str, Any],
        scheduled_item_id: str | None = None,
        campaign_id: str | None = None,
        job_id: str | None = None,
        idempotency_key: str | None = None,
        max_retries: int = 3,
        initiator: str = "operator",
    ) -> PublishAttempt:
        """Execute a single publish attempt with rate limit protection and retry logic."""
        # 1. Check idempotency
        if idempotency_key:
            existing = self._get_existing(idempotency_key)
            if existing and existing.status == PublishStatus.PUBLISHED:
                logger.info(
                    "Publish attempt with idempotency key %s already published (%s)",
                    idempotency_key,
                    existing.external_post_id,
                )
                return existing

        # 2. Initialize attempt
        attempt = PublishAttempt.create(
            destination_type=destination_type,
            destination_id=destination_id,
            destination_name=destination_name,
            post_type=post_type,
            payload=payload,
            scheduled_item_id=scheduled_item_id,
            campaign_id=campaign_id,
            job_id=job_id,
            idempotency_key=idempotency_key,
        )
        self._save_attempt(attempt)

        start_time = time.monotonic()
        last_error_code: PublishErrorCode = PublishErrorCode.UNKNOWN
        last_error_msg: str = "Unknown error"

        # Update schedule item state to RUNNING if linked
        if scheduled_item_id and self._schedule_service:
            try:
                self._schedule_service.update_item_status(
                    scheduled_item_id, ScheduledItemStatus.RUNNING
                )
            except Exception as e:
                logger.warning("Failed to mark scheduled item as RUNNING: %s", e)

        # 3. Execution loop with retries
        for current_retry in range(max_retries + 1):
            try:
                post_id = self._call_adapter(
                    destination_type=destination_type,
                    destination_id=destination_id,
                    access_token=access_token,
                    post_type=post_type,
                    payload=payload,
                )

                # Success
                duration_ms = int((time.monotonic() - start_time) * 1000)
                attempt = attempt.mark_published(
                    external_post_id=post_id,
                    duration_ms=duration_ms,
                )
                self._save_attempt(attempt)

                self._record_audit(
                    action="publish.success",
                    target_id=attempt.id,
                    result=AuditResult.SUCCESS,
                    details={
                        "attempt_id": attempt.id,
                        "destination_id": destination_id,
                        "destination_name": destination_name,
                        "post_type": str(post_type),
                        "external_post_id": post_id,
                        "duration_ms": duration_ms,
                    },
                    initiator=initiator,
                )

                # Update linked schedule item
                if scheduled_item_id and self._schedule_service:
                    self._schedule_service.update_item_status(
                        scheduled_item_id, ScheduledItemStatus.COMPLETED
                    )

                return attempt

            except Exception as exc:
                err_code, err_msg = map_exception_to_publish_error(exc)
                last_error_code = err_code
                last_error_msg = err_msg
                duration_ms = int((time.monotonic() - start_time) * 1000)

                # Check if retryable and retries remaining
                if err_code.is_retryable and current_retry < max_retries:
                    attempt = attempt.mark_failed(
                        error_code=err_code,
                        error_message=f"[Retry {current_retry + 1}/{max_retries}] {err_msg}",
                        duration_ms=duration_ms,
                        is_retrying=True,
                    )
                    self._save_attempt(attempt)
                    sleep_time = self._backoff_base_seconds * (2**current_retry)
                    logger.warning(
                        "Publish retryable error %s on %s, sleeping %.2fs (attempt %d/%d)",
                        err_code,
                        destination_name,
                        sleep_time,
                        current_retry + 1,
                        max_retries,
                    )
                    time.sleep(sleep_time)
                    continue
                else:
                    # Terminal failure
                    break

        # 4. Terminal Failure Handling
        duration_ms = int((time.monotonic() - start_time) * 1000)
        attempt = attempt.mark_failed(
            error_code=last_error_code,
            error_message=last_error_msg,
            duration_ms=duration_ms,
            is_retrying=False,
        )
        self._save_attempt(attempt)

        self._record_audit(
            action="publish.failure",
            target_id=attempt.id,
            result=AuditResult.FAILURE,
            error_code=str(last_error_code),
            error_message=last_error_msg,
            details={
                "attempt_id": attempt.id,
                "destination_id": destination_id,
                "destination_name": destination_name,
                "post_type": str(post_type),
                "error_code": str(last_error_code),
                "error_message": last_error_msg,
                "duration_ms": duration_ms,
            },
            initiator=initiator,
        )

        if scheduled_item_id and self._schedule_service:
            self._schedule_service.update_item_status(
                scheduled_item_id,
                ScheduledItemStatus.FAILED,
                error_message=last_error_msg,
            )

        return attempt

    def execute_campaign_publishing(
        self,
        campaign_id: str,
        token_resolver: Callable[[PublishDestinationType, str], str | None],
        initiator: str = "operator",
    ) -> list[PublishAttempt]:
        """Publish all pending targets in a campaign and update campaign state."""
        if not self._campaign_service:
            raise RuntimeError("CampaignService not configured in PublishingService")

        campaign = self._campaign_service.get_campaign(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        self._campaign_service.update_campaign_status(campaign_id, CampaignStatus.RUNNING)

        attempts: list[PublishAttempt] = []
        target_results: dict[str, TargetStatus] = {}

        for target in campaign.targets:
            if target.status == TargetStatus.SUCCESS:
                target_results[target.destination_id] = TargetStatus.SUCCESS
                continue

            token = token_resolver(target.destination_type, target.destination_id)
            if not token:
                logger.error(
                    "No access token resolved for target %s (%s)",
                    target.destination_name,
                    target.destination_id,
                )
                attempt = PublishAttempt.create(
                    destination_type=target.destination_type,
                    destination_id=target.destination_id,
                    destination_name=target.destination_name,
                    post_type=campaign.post_type,
                    payload={"caption": campaign.caption},
                    campaign_id=campaign_id,
                ).mark_failed(
                    error_code=PublishErrorCode.TOKEN_EXPIRED,
                    error_message=f"Missing or expired access token for {target.destination_name}",
                )
                self._save_attempt(attempt)
                attempts.append(attempt)
                target_results[target.destination_id] = TargetStatus.FAILED
                self._campaign_service.update_target_status(
                    target.id,
                    TargetStatus.FAILED,
                    error_message=attempt.error_message,
                )
                continue

            payload = {
                "caption": campaign.caption,
                "media_asset_ids": list(campaign.media_asset_ids),
            }

            idempotency_key = f"campaign_{campaign_id}_{target.destination_id}"

            attempt = self.execute_publish(
                destination_type=target.destination_type,
                destination_id=target.destination_id,
                destination_name=target.destination_name,
                access_token=token,
                post_type=campaign.post_type,
                payload=payload,
                campaign_id=campaign_id,
                idempotency_key=idempotency_key,
                initiator=initiator,
            )
            attempts.append(attempt)

            if attempt.status == PublishStatus.PUBLISHED:
                target_results[target.destination_id] = TargetStatus.SUCCESS
                self._campaign_service.update_target_status(
                    target.id,
                    TargetStatus.SUCCESS,
                    published_post_id=attempt.external_post_id,
                )
            else:
                target_results[target.destination_id] = TargetStatus.FAILED
                self._campaign_service.update_target_status(
                    target.id,
                    TargetStatus.FAILED,
                    error_message=attempt.error_message,
                )

        # Update overall campaign state
        success_count = sum(1 for s in target_results.values() if s == TargetStatus.SUCCESS)
        total_count = len(campaign.targets)

        if success_count == total_count:
            self._campaign_service.update_campaign_status(campaign_id, CampaignStatus.COMPLETED)
        elif success_count > 0:
            self._campaign_service.update_campaign_status(
                campaign_id, CampaignStatus.PARTIALLY_COMPLETED
            )
        else:
            self._campaign_service.update_campaign_status(campaign_id, CampaignStatus.FAILED)

        return attempts

    def _call_adapter(
        self,
        destination_type: PublishDestinationType,
        destination_id: str,
        access_token: str,
        post_type: PostType,
        payload: Mapping[str, Any],
    ) -> str:
        """Call the appropriate publishing port method based on destination and post type."""
        caption = str(payload.get("caption", ""))
        link_url = payload.get("link_url")
        photo_bytes = payload.get("photo_bytes")
        photo_url = payload.get("photo_url")
        video_bytes = payload.get("video_bytes")
        video_url = payload.get("video_url")
        title = payload.get("title")

        if destination_type == PublishDestinationType.PAGE:
            if photo_bytes or photo_url:
                res = self._publisher.publish_page_photo(
                    page_id=destination_id,
                    access_token=access_token,
                    caption=caption,
                    photo_url=photo_url,
                    photo_bytes=photo_bytes,
                )
                return res.post_id or res.id
            elif post_type == PostType.REEL or video_bytes or video_url:
                res = self._publisher.publish_page_video(
                    page_id=destination_id,
                    access_token=access_token,
                    description=caption,
                    title=title,
                    video_url=video_url,
                    video_bytes=video_bytes,
                )
                return res.post_id or res.id
            else:
                res = self._publisher.publish_page_feed(
                    page_id=destination_id,
                    access_token=access_token,
                    message=caption,
                    link=link_url,
                )
                return res.post_id or res.id

        elif destination_type == PublishDestinationType.GROUP:
            res = self._publisher.publish_group_feed(
                group_id=destination_id,
                access_token=access_token,
                message=caption,
                link=link_url,
            )
            return res.post_id or res.id

        else:
            # For account_profile or other destinations
            res = self._publisher.publish_page_feed(
                page_id=destination_id,
                access_token=access_token,
                message=caption,
                link=link_url,
            )
            return res.post_id or res.id

    def _record_audit(
        self,
        action: str,
        target_id: str,
        result: AuditResult,
        details: Mapping[str, Any],
        error_code: str | None = None,
        error_message: str | None = None,
        initiator: str = "system",
    ) -> None:
        if self._audit_service:
            try:
                self._audit_service.record_event(
                    initiator=initiator,
                    action=action,
                    target_type="publish_attempt",
                    target_id=target_id,
                    result=result,
                    error_code=error_code,
                    error_message=error_message,
                    details=dict(details),
                )
            except Exception as e:
                logger.warning("Failed to record audit event for %s: %s", action, e)
