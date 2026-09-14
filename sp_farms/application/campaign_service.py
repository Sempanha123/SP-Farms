"""Campaign management orchestrator service."""

import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sp_farms.application.campaign_repository import CampaignRepositoryPort
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.campaigns import (
    ApprovalPolicy,
    Campaign,
    CampaignReportSummary,
    CampaignStatus,
    CampaignTarget,
    RetryPolicy,
    SchedulePolicy,
    SchedulePolicyType,
    TargetStatus,
)
from sp_farms.domain.composer import PostType, PublishDestinationType
from sp_farms.domain.result import AppError, Result

if TYPE_CHECKING:
    from sp_farms.application.content_service import ContentService

logger = logging.getLogger(__name__)


class CampaignService:
    def __init__(
        self,
        unit_of_work: Callable[[], UnitOfWork],
        campaign_repo_factory: Callable[[UnitOfWork], CampaignRepositoryPort],
        content_service: "ContentService | None" = None,
    ) -> None:
        self._uow = unit_of_work
        self._repo_factory = campaign_repo_factory
        self._content_service = content_service

    def create_campaign(
        self,
        title: str,
        post_type: PostType = PostType.FEED,
        caption: str = "",
        content_item_id: str | None = None,
        media_asset_ids: Sequence[str] = (),
        schedule_policy: SchedulePolicy | None = None,
        approval_policy: ApprovalPolicy = ApprovalPolicy.MANUAL,
        retry_policy: RetryPolicy | None = None,
        tags: Sequence[str] = (),
        notes: str = "",
        target_specs: Sequence[tuple[PublishDestinationType, str, str]] = (),  # (type, id, name)
    ) -> Result[Campaign]:
        if not title.strip():
            return Result.failure(
                AppError(code="INVALID_ARGUMENT", message="Campaign title cannot be empty")
            )

        campaign = Campaign.create(
            title=title,
            post_type=post_type,
            caption=caption,
            content_item_id=content_item_id,
            media_asset_ids=media_asset_ids,
            schedule_policy=schedule_policy,
            approval_policy=approval_policy,
            retry_policy=retry_policy,
            tags=tags,
            notes=notes,
        )

        targets = [
            CampaignTarget.create(
                campaign_id=campaign.id,
                destination_type=dtype,
                destination_id=did,
                destination_name=dname,
            )
            for dtype, did, dname in target_specs
        ]

        campaign_with_targets = Campaign(
            id=campaign.id,
            title=campaign.title,
            content_item_id=campaign.content_item_id,
            post_type=campaign.post_type,
            caption=campaign.caption,
            media_asset_ids=campaign.media_asset_ids,
            status=campaign.status,
            schedule_policy=campaign.schedule_policy,
            approval_policy=campaign.approval_policy,
            retry_policy=campaign.retry_policy,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
            targets=tuple(targets),
            tags=campaign.tags,
            notes=campaign.notes,
            archived_at=campaign.archived_at,
        )

        with self._uow() as uow:
            repo = self._repo_factory(uow)
            saved = repo.save_campaign(campaign_with_targets)
            uow.commit()

        return Result.success(saved)

    def get_campaign(self, campaign_id: str) -> Campaign | None:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            return repo.get_campaign(campaign_id)

    def list_campaigns(
        self,
        status: CampaignStatus | None = None,
        search: str | None = None,
        include_archived: bool = False,
    ) -> Sequence[Campaign]:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            return repo.list_campaigns(
                status=status,
                search=search,
                include_archived=include_archived,
            )

    def add_target(
        self,
        campaign_id: str,
        destination_type: PublishDestinationType,
        destination_id: str,
        destination_name: str,
        scheduled_at: datetime | None = None,
    ) -> Result[CampaignTarget]:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            campaign = repo.get_campaign(campaign_id)
            if campaign is None:
                return Result.failure(
                    AppError(
                        code="NOT_FOUND",
                        message=f"Campaign {campaign_id} not found",
                    )
                )

            target = CampaignTarget.create(
                campaign_id=campaign_id,
                destination_type=destination_type,
                destination_id=destination_id,
                destination_name=destination_name,
                scheduled_at=scheduled_at,
            )
            saved_target = repo.save_target(target)
            uow.commit()
            return Result.success(saved_target)

    def remove_target(self, target_id: str) -> Result[bool]:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            deleted = repo.delete_target(target_id)
            uow.commit()
            return Result.success(deleted)

    def update_campaign_status(
        self,
        campaign_id: str,
        new_status: CampaignStatus,
    ) -> Result[Campaign]:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            campaign = repo.get_campaign(campaign_id)
            if campaign is None:
                return Result.failure(
                    AppError(
                        code="NOT_FOUND",
                        message=f"Campaign {campaign_id} not found",
                    )
                )

            updated = Campaign(
                id=campaign.id,
                title=campaign.title,
                content_item_id=campaign.content_item_id,
                post_type=campaign.post_type,
                caption=campaign.caption,
                media_asset_ids=campaign.media_asset_ids,
                status=new_status,
                schedule_policy=campaign.schedule_policy,
                approval_policy=campaign.approval_policy,
                retry_policy=campaign.retry_policy,
                created_at=campaign.created_at,
                updated_at=datetime.now(UTC),
                targets=campaign.targets,
                tags=campaign.tags,
                notes=campaign.notes,
                archived_at=campaign.archived_at
                if new_status != CampaignStatus.ARCHIVED
                else datetime.now(UTC),
            )
            saved = repo.save_campaign(updated)
            uow.commit()
            return Result.success(saved)

    def approve_campaign(self, campaign_id: str) -> Result[Campaign]:
        """Approve a campaign waiting for operator review."""
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            campaign = repo.get_campaign(campaign_id)
            if campaign is None:
                return Result.failure(
                    AppError(
                        code="NOT_FOUND",
                        message=f"Campaign {campaign_id} not found",
                    )
                )

            if campaign.schedule_policy.policy_type != SchedulePolicyType.IMMEDIATE:
                next_status = CampaignStatus.SCHEDULED
            else:
                next_status = CampaignStatus.READY

            updated = Campaign(
                id=campaign.id,
                title=campaign.title,
                content_item_id=campaign.content_item_id,
                post_type=campaign.post_type,
                caption=campaign.caption,
                media_asset_ids=campaign.media_asset_ids,
                status=next_status,
                schedule_policy=campaign.schedule_policy,
                approval_policy=campaign.approval_policy,
                retry_policy=campaign.retry_policy,
                created_at=campaign.created_at,
                updated_at=datetime.now(UTC),
                targets=campaign.targets,
                tags=campaign.tags,
                notes=campaign.notes,
                archived_at=campaign.archived_at,
            )
            saved = repo.save_campaign(updated)
            uow.commit()
            return Result.success(saved)

    def pause_campaign(self, campaign_id: str) -> Result[Campaign]:
        """Pause a running or scheduled campaign."""
        return self.update_campaign_status(campaign_id, CampaignStatus.PAUSED)

    def resume_campaign(self, campaign_id: str) -> Result[Campaign]:
        """Resume a paused campaign."""
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            campaign = repo.get_campaign(campaign_id)
            if campaign is None:
                return Result.failure(
                    AppError(
                        code="NOT_FOUND",
                        message=f"Campaign {campaign_id} not found",
                    )
                )

            # Determine appropriate resumed status
            resumed_status = campaign.evaluate_status_transition()
            if resumed_status == CampaignStatus.PAUSED:
                resumed_status = CampaignStatus.READY

            updated = Campaign(
                id=campaign.id,
                title=campaign.title,
                content_item_id=campaign.content_item_id,
                post_type=campaign.post_type,
                caption=campaign.caption,
                media_asset_ids=campaign.media_asset_ids,
                status=resumed_status,
                schedule_policy=campaign.schedule_policy,
                approval_policy=campaign.approval_policy,
                retry_policy=campaign.retry_policy,
                created_at=campaign.created_at,
                updated_at=datetime.now(UTC),
                targets=campaign.targets,
                tags=campaign.tags,
                notes=campaign.notes,
                archived_at=campaign.archived_at,
            )
            saved = repo.save_campaign(updated)
            uow.commit()
            return Result.success(saved)

    def update_target_status(
        self,
        target_id: str,
        status: TargetStatus,
        error_message: str | None = None,
        published_post_id: str | None = None,
        increment_attempt: bool = False,
    ) -> Result[CampaignTarget]:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            target = repo.get_target(target_id)
            if target is None:
                return Result.failure(
                    AppError(
                        code="NOT_FOUND",
                        message=f"Target {target_id} not found",
                    )
                )

            new_attempt = target.attempt_count + 1 if increment_attempt else target.attempt_count
            now = datetime.now(UTC)

            executed_at=(
                now
                if status in (TargetStatus.SUCCESS, TargetStatus.FAILED)
                else target.executed_at
            )
            updated_target = CampaignTarget(
                id=target.id,
                campaign_id=target.campaign_id,
                destination_type=target.destination_type,
                destination_id=target.destination_id,
                destination_name=target.destination_name,
                status=status,
                attempt_count=new_attempt,
                published_post_id=published_post_id or target.published_post_id,
                error_message=error_message,
                executed_at=executed_at,
                scheduled_at=target.scheduled_at,
            )
            saved_target = repo.save_target(updated_target)

            # Check if campaign overall status should transition
            campaign = repo.get_campaign(target.campaign_id)
            if campaign is not None:
                new_c_status = campaign.evaluate_status_transition()
                if new_c_status != campaign.status:
                    updated_c = Campaign(
                        id=campaign.id,
                        title=campaign.title,
                        content_item_id=campaign.content_item_id,
                        post_type=campaign.post_type,
                        caption=campaign.caption,
                        media_asset_ids=campaign.media_asset_ids,
                        status=new_c_status,
                        schedule_policy=campaign.schedule_policy,
                        approval_policy=campaign.approval_policy,
                        retry_policy=campaign.retry_policy,
                        created_at=campaign.created_at,
                        updated_at=now,
                        targets=campaign.targets,
                        tags=campaign.tags,
                        notes=campaign.notes,
                        archived_at=campaign.archived_at,
                    )
                    repo.save_campaign(updated_c)

            uow.commit()
            return Result.success(saved_target)

    def get_campaign_summary(self, campaign_id: str) -> CampaignReportSummary | None:
        campaign = self.get_campaign(campaign_id)
        if campaign is None:
            return None
        return campaign.generate_summary()
