from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class PublishDestinationType(StrEnum):
    PAGE = "page"
    GROUP = "group"
    ACCOUNT_PROFILE = "account_profile"


class PostType(StrEnum):
    FEED = "feed"
    REEL = "reel"
    STORY = "story"


@dataclass(frozen=True, slots=True)
class PublishDestination:
    id: str
    name: str
    destination_type: PublishDestinationType
    account_id: str
    native_id: str
    can_publish_reels: bool = True
    can_publish_stories: bool = True
    supports_first_comment: bool = True
    supports_location: bool = True


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    field: str
    severity: str  # "error" | "warning"
    message: str


@dataclass(frozen=True, slots=True)
class DuplicateWarning:
    is_duplicate: bool
    similarity_score: float = 0.0
    matched_id: str | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class DraftPost:
    id: str
    title: str
    post_type: PostType
    destination: PublishDestination | None
    caption: str
    media_asset_ids: tuple[str, ...] = field(default_factory=tuple)
    thumbnail_asset_id: str | None = None
    location_name: str | None = None
    first_comment: str | None = None
    scheduled_at: datetime | None = None
    requires_approval: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        title: str,
        post_type: PostType = PostType.FEED,
        destination: PublishDestination | None = None,
        caption: str = "",
        media_asset_ids: Sequence[str] = (),
        thumbnail_asset_id: str | None = None,
        location_name: str | None = None,
        first_comment: str | None = None,
        scheduled_at: datetime | None = None,
        requires_approval: bool = False,
        draft_id: str | None = None,
    ) -> "DraftPost":
        now = datetime.now(UTC)
        return cls(
            id=draft_id or str(uuid4()),
            title=title.strip() or "Untitled Draft",
            post_type=post_type,
            destination=destination,
            caption=caption,
            media_asset_ids=tuple(media_asset_ids),
            thumbnail_asset_id=thumbnail_asset_id,
            location_name=location_name.strip() if location_name else None,
            first_comment=first_comment.strip() if first_comment else None,
            scheduled_at=scheduled_at,
            requires_approval=requires_approval,
            created_at=now,
            updated_at=now,
        )


def validate_draft_post(
    draft: DraftPost,
    media_types_by_id: dict[str, str] | None = None,
) -> list[ValidationIssue]:
    """Validate a draft post against destination capabilities and Meta posting rules."""
    issues: list[ValidationIssue] = []
    media_map = media_types_by_id or {}

    # 1. Title / Caption check
    if not draft.caption.strip() and not draft.media_asset_ids:
        issues.append(
            ValidationIssue(
                field="caption",
                severity="error",
                message="Post must contain text caption or at least one media asset.",
            )
        )

    # 2. Destination check
    if draft.destination is None:
        issues.append(
            ValidationIssue(
                field="destination",
                severity="error",
                message="Please select an authorized destination.",
            )
        )
    else:
        dest = draft.destination
        if draft.post_type == PostType.REEL and not dest.can_publish_reels:
            issues.append(
                ValidationIssue(
                    field="post_type",
                    severity="error",
                    message=f"Destination '{dest.name}' does not support Reel publishing.",
                )
            )
        if draft.post_type == PostType.STORY and not dest.can_publish_stories:
            issues.append(
                ValidationIssue(
                    field="post_type",
                    severity="error",
                    message=f"Destination '{dest.name}' does not support Story publishing.",
                )
            )
        if draft.first_comment and not dest.supports_first_comment:
            issues.append(
                ValidationIssue(
                    field="first_comment",
                    severity="error",
                    message=(
                        f"First comment is only supported on Pages, "
                        f"not {dest.destination_type.value}."
                    ),
                )
            )
        if draft.location_name and not dest.supports_location:
            issues.append(
                ValidationIssue(
                    field="location_name",
                    severity="warning",
                    message=f"Location tag may not be displayed on {dest.destination_type.value}.",
                )
            )

    # 3. Media requirements by post type
    if draft.post_type == PostType.REEL:
        if not draft.media_asset_ids:
            issues.append(
                ValidationIssue(
                    field="media",
                    severity="error",
                    message="Reels require exactly one video asset.",
                )
            )
        elif len(draft.media_asset_ids) > 1:
            issues.append(
                ValidationIssue(
                    field="media",
                    severity="error",
                    message="Reels cannot have multiple video assets.",
                )
            )
        else:
            asset_id = draft.media_asset_ids[0]
            m_type = media_map.get(asset_id, "").upper()
            if m_type and m_type != "VIDEO":
                issues.append(
                    ValidationIssue(
                        field="media",
                        severity="error",
                        message="Reel media must be a video file.",
                    )
                )

    if draft.post_type == PostType.STORY and not draft.media_asset_ids:
        issues.append(
            ValidationIssue(
                field="media",
                severity="error",
                message="Stories require media (image or video).",
            )
        )

    # 4. Schedule check
    if draft.scheduled_at:
        now = datetime.now(UTC)
        if draft.scheduled_at <= now:
            issues.append(
                ValidationIssue(
                    field="scheduled_at",
                    severity="error",
                    message="Schedule time must be in the future.",
                )
            )

    return issues
