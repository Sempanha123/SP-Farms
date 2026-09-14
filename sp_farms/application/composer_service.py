import contextlib
import difflib
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sp_farms.application.ports import Clock
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.composer import (
    DraftPost,
    DuplicateWarning,
    PostType,
    PublishDestination,
    PublishDestinationType,
    ValidationIssue,
    validate_draft_post,
)
from sp_farms.domain.content import ContentItem, ContentStatus

if TYPE_CHECKING:
    from sp_farms.application.asset_repository import AssetRepository
    from sp_farms.application.content_repository import ContentRepositoryPort

logger = logging.getLogger(__name__)


class ComposerService:
    """Orchestrates draft post/reel composition, validation, and deduplication."""

    def __init__(
        self,
        unit_of_work: Callable[[], UnitOfWork],
        content_repo_factory: Callable[[UnitOfWork], "ContentRepositoryPort"],
        asset_repo_factory: Callable[[UnitOfWork], "AssetRepository"] | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._content_repo_factory = content_repo_factory
        self._asset_repo_factory = asset_repo_factory
        self._clock = clock

    def get_authorized_destinations(self) -> list[PublishDestination]:
        """Fetch all eligible publishing destinations (Pages and Groups)."""
        destinations: list[PublishDestination] = []
        if not self._asset_repo_factory:
            return destinations

        with self._uow() as uow:
            repo = self._asset_repo_factory(uow)
            pages = repo.list_all_pages()
            for p in pages:
                # Must be eligible to publish
                destinations.append(
                    PublishDestination(
                        id=f"page_{p.id}",
                        name=f"📄 {p.name}",
                        destination_type=PublishDestinationType.PAGE,
                        account_id=p.account_id,
                        native_id=p.page_id,
                        can_publish_reels=True,
                        can_publish_stories=True,
                        supports_first_comment=True,
                        supports_location=True,
                    )
                )

            groups = repo.list_all_groups()
            for g in groups:
                destinations.append(
                    PublishDestination(
                        id=f"group_{g.id}",
                        name=f"👥 {g.name}",
                        destination_type=PublishDestinationType.GROUP,
                        account_id=g.account_id,
                        native_id=g.group_id,
                        can_publish_reels=False,
                        can_publish_stories=False,
                        supports_first_comment=False,
                        supports_location=False,
                    )
                )

        return destinations

    def validate_draft(
        self,
        draft: DraftPost,
    ) -> list[ValidationIssue]:
        """Validate draft content and destination capabilities."""
        media_types: dict[str, str] = {}
        if draft.media_asset_ids:
            with self._uow() as uow:
                repo = self._content_repo_factory(uow)
                for mid in draft.media_asset_ids:
                    asset = repo.get_asset(mid)
                    if asset:
                        media_types[mid] = asset.media_type.value

        return validate_draft_post(draft, media_types_by_id=media_types)

    def check_duplicate(
        self,
        caption: str,
        threshold: float = 0.85,
    ) -> DuplicateWarning:
        """Detect near-duplicate captions against existing content items."""
        clean_target = caption.strip().lower()
        if not clean_target or len(clean_target) < 10:
            return DuplicateWarning(is_duplicate=False)

        with self._uow() as uow:
            repo = self._content_repo_factory(uow)
            items = repo.list_content_items(limit=100)

            for item in items:
                existing_text = item.body.strip().lower()
                if not existing_text:
                    continue

                if existing_text == clean_target:
                    return DuplicateWarning(
                        is_duplicate=True,
                        similarity_score=1.0,
                        matched_id=item.id,
                        reason=f"Exact duplicate of existing item '{item.title}'",
                    )

                ratio = difflib.SequenceMatcher(None, clean_target, existing_text).ratio()
                if ratio >= threshold:
                    return DuplicateWarning(
                        is_duplicate=True,
                        similarity_score=round(ratio, 2),
                        matched_id=item.id,
                        reason=f"High similarity ({int(ratio * 100)}%) with item '{item.title}'",
                    )

        return DuplicateWarning(is_duplicate=False)

    def save_draft(self, draft: DraftPost) -> ContentItem:
        """Persist draft post into ContentItem storage."""
        now = self._clock.now() if self._clock else datetime.now(UTC)

        metadata_dict = {
            "post_type": draft.post_type.value,
            "destination_id": draft.destination.id if draft.destination else None,
            "destination_name": draft.destination.name if draft.destination else None,
            "destination_type": (
                draft.destination.destination_type.value if draft.destination else None
            ),
            "thumbnail_asset_id": draft.thumbnail_asset_id,
            "location_name": draft.location_name,
            "first_comment": draft.first_comment,
            "scheduled_at": draft.scheduled_at.isoformat() if draft.scheduled_at else None,
            "requires_approval": draft.requires_approval,
        }

        # Store in tags or folder
        tags = [f"type:{draft.post_type.value}"]
        if draft.requires_approval:
            tags.append("needs_approval")

        # Encode metadata inside item
        item = ContentItem(
            id=draft.id,
            title=draft.title,
            body=draft.caption,
            media_asset_ids=draft.media_asset_ids,
            hashtag_set_ids=(),
            caption_template_id=None,
            status=ContentStatus.DRAFT,
            folder=json.dumps(metadata_dict),  # Pack composer metadata
            tags=tuple(tags),
            is_favorite=False,
            is_archived=False,
            created_at=now,
            updated_at=now,
        )

        with self._uow() as uow:
            repo = self._content_repo_factory(uow)
            repo.add_content_item(item)
            uow.commit()

        return item

    def load_draft(self, draft_id: str) -> DraftPost | None:
        """Load and reconstruct DraftPost from ContentItem storage."""
        with self._uow() as uow:
            repo = self._content_repo_factory(uow)
            item = repo.get_content_item(draft_id)
            if not item:
                return None

            meta = {}
            with contextlib.suppress(Exception):
                meta = json.loads(item.folder)

            dest = None
            if meta.get("destination_id"):
                dest = PublishDestination(
                    id=meta["destination_id"],
                    name=meta.get("destination_name", "Destination"),
                    destination_type=PublishDestinationType(
                        meta.get("destination_type", "page")
                    ),
                    account_id="",
                    native_id="",
                )

            post_type_str = meta.get("post_type", "feed")
            try:
                p_type = PostType(post_type_str)
            except ValueError:
                p_type = PostType.FEED

            sched_dt = None
            if meta.get("scheduled_at"):
                with contextlib.suppress(Exception):
                    sched_dt = datetime.fromisoformat(meta["scheduled_at"])

            return DraftPost(
                id=item.id,
                title=item.title,
                post_type=p_type,
                destination=dest,
                caption=item.body,
                media_asset_ids=item.media_asset_ids,
                thumbnail_asset_id=meta.get("thumbnail_asset_id"),
                location_name=meta.get("location_name"),
                first_comment=meta.get("first_comment"),
                scheduled_at=sched_dt,
                requires_approval=bool(meta.get("requires_approval", False)),
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
