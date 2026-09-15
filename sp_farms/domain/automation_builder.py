"""Domain models, step schemas, capability matrix, and presets for the Automation Builder."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class AutomationStepType(StrEnum):
    """Authorized automation function types for operator-owned social assets."""

    RESTORE_WORKSPACE = "restore_workspace"
    OPEN_PREFERRED_APP = "open_preferred_app"
    HEALTH_CHECK = "health_check"
    REFRESH_ASSETS = "refresh_assets"
    PUBLISH_TEXT = "publish_text"
    PUBLISH_IMAGE = "publish_image"
    PUBLISH_MULTI_IMAGE = "publish_multi_image"
    PUBLISH_VIDEO = "publish_video"
    PUBLISH_REEL = "publish_reel"
    PUBLISH_STORY = "publish_story"
    PUBLISH_LINK = "publish_link"
    SCHEDULE_CONTENT = "schedule_content"
    READ_COMMENTS = "read_comments"
    REPLY_COMMENTS = "reply_comments"
    MODERATE_COMMENTS = "moderate_comments"
    READ_INBOX = "read_inbox"
    REPLY_INBOX = "reply_inbox"
    ASSIGN_INBOX = "assign_inbox"
    ADD_INTERNAL_NOTE = "add_internal_note"
    MARK_RESOLVED = "mark_resolved"
    COLLECT_POST_ANALYTICS = "collect_post_analytics"
    COLLECT_REACTION_ANALYTICS = "collect_reaction_analytics"
    COLLECT_SHARE_VIEW_ANALYTICS = "collect_share_view_analytics"
    COLLECT_FOLLOWER_ANALYTICS = "collect_follower_analytics"
    BACKUP_WORKSPACE = "backup_workspace"
    RELEASE_DEVICE = "release_device"
    START_NEXT_ACCOUNT = "start_next_account"


# Explicitly forbidden step types to guarantee compliance with platform safety boundaries
FORBIDDEN_AUTOMATION_STEPS = frozenset(
    {
        "mass_reactions",
        "reaction_farming",
        "fake_reactions",
        "mass_likes",
        "mass_follows",
        "mass_shares",
        "unsolicited_bulk_messaging",
        "mass_comments",
        "captcha_bypass",
        "checkpoint_bypass",
        "fingerprint_spoofing",
    }
)


class CapabilitySupport(StrEnum):
    """Official platform capability tier for a step."""

    OFFICIALLY_SUPPORTED = "officially_supported"
    REQUIRES_OPERATOR_APPROVAL = "requires_operator_approval"
    CAPABILITY_GATED = "capability_gated"
    READ_ONLY_ANALYTICS = "read_only_analytics"


@dataclass(frozen=True, slots=True)
class StepCapabilityInfo:
    """Metadata regarding API capability, destination support, and safety boundaries."""

    step_type: AutomationStepType
    title: str
    description: str
    support_tier: CapabilitySupport
    supports_page: bool = True
    supports_group: bool = False
    supports_device: bool = False
    required_permissions: tuple[str, ...] = ()
    read_only: bool = False


CAPABILITY_MATRIX: dict[AutomationStepType, StepCapabilityInfo] = {
    AutomationStepType.RESTORE_WORKSPACE: StepCapabilityInfo(
        step_type=AutomationStepType.RESTORE_WORKSPACE,
        title="Restore Workspace",
        description="Safely restores operator workspace snapshot to assigned device.",
        support_tier=CapabilitySupport.OFFICIALLY_SUPPORTED,
        supports_device=True,
    ),
    AutomationStepType.OPEN_PREFERRED_APP: StepCapabilityInfo(
        step_type=AutomationStepType.OPEN_PREFERRED_APP,
        title="Open Preferred App",
        description="Launches Facebook/Business Suite on target device.",
        support_tier=CapabilitySupport.OFFICIALLY_SUPPORTED,
        supports_device=True,
    ),
    AutomationStepType.HEALTH_CHECK: StepCapabilityInfo(
        step_type=AutomationStepType.HEALTH_CHECK,
        title="Health Check",
        description="Validates account auth validity and device readiness.",
        support_tier=CapabilitySupport.OFFICIALLY_SUPPORTED,
        read_only=True,
    ),
    AutomationStepType.REFRESH_ASSETS: StepCapabilityInfo(
        step_type=AutomationStepType.REFRESH_ASSETS,
        title="Refresh Authorized Asset Data",
        description="Synchronizes operator Pages and authorized Groups.",
        support_tier=CapabilitySupport.OFFICIALLY_SUPPORTED,
        required_permissions=("pages_show_list",),
        read_only=True,
    ),
    AutomationStepType.PUBLISH_TEXT: StepCapabilityInfo(
        step_type=AutomationStepType.PUBLISH_TEXT,
        title="Publish Text Post",
        description="Publishes text post to authorized Pages or Groups.",
        support_tier=CapabilitySupport.OFFICIALLY_SUPPORTED,
        supports_page=True,
        supports_group=True,
        required_permissions=("pages_manage_posts",),
    ),
    AutomationStepType.PUBLISH_IMAGE: StepCapabilityInfo(
        step_type=AutomationStepType.PUBLISH_IMAGE,
        title="Publish Image Post",
        description="Publishes single image post to authorized Pages or Groups.",
        support_tier=CapabilitySupport.OFFICIALLY_SUPPORTED,
        supports_page=True,
        supports_group=True,
        required_permissions=("pages_manage_posts",),
    ),
    AutomationStepType.PUBLISH_MULTI_IMAGE: StepCapabilityInfo(
        step_type=AutomationStepType.PUBLISH_MULTI_IMAGE,
        title="Publish Multi-Image Post",
        description="Publishes carousel/album to authorized Page.",
        support_tier=CapabilitySupport.OFFICIALLY_SUPPORTED,
        supports_page=True,
        supports_group=False,
        required_permissions=("pages_manage_posts",),
    ),
    AutomationStepType.PUBLISH_VIDEO: StepCapabilityInfo(
        step_type=AutomationStepType.PUBLISH_VIDEO,
        title="Publish Video Post",
        description="Uploads and publishes video with caption and thumbnail.",
        support_tier=CapabilitySupport.OFFICIALLY_SUPPORTED,
        supports_page=True,
        supports_group=True,
        required_permissions=("pages_manage_posts",),
    ),
    AutomationStepType.PUBLISH_REEL: StepCapabilityInfo(
        step_type=AutomationStepType.PUBLISH_REEL,
        title="Publish Reel",
        description="Publishes 9:16 short-form reel video to authorized Page.",
        support_tier=CapabilitySupport.OFFICIALLY_SUPPORTED,
        supports_page=True,
        supports_group=False,
        required_permissions=("pages_manage_posts",),
    ),
    AutomationStepType.PUBLISH_STORY: StepCapabilityInfo(
        step_type=AutomationStepType.PUBLISH_STORY,
        title="Publish Story",
        description="Publishes ephemeral story where officially supported by Meta API.",
        support_tier=CapabilitySupport.CAPABILITY_GATED,
        supports_page=True,
        supports_group=False,
        required_permissions=("pages_manage_posts",),
    ),
    AutomationStepType.PUBLISH_LINK: StepCapabilityInfo(
        step_type=AutomationStepType.PUBLISH_LINK,
        title="Publish Link Post",
        description="Shares link with preview card to authorized destination.",
        support_tier=CapabilitySupport.OFFICIALLY_SUPPORTED,
        supports_page=True,
        supports_group=True,
        required_permissions=("pages_manage_posts",),
    ),
    AutomationStepType.SCHEDULE_CONTENT: StepCapabilityInfo(
        step_type=AutomationStepType.SCHEDULE_CONTENT,
        title="Schedule Content",
        description="Queues content for automated release within allowed window.",
        support_tier=CapabilitySupport.OFFICIALLY_SUPPORTED,
    ),
    AutomationStepType.READ_COMMENTS: StepCapabilityInfo(
        step_type=AutomationStepType.READ_COMMENTS,
        title="Read Comments",
        description="Fetches recent post comments for customer service.",
        support_tier=CapabilitySupport.READ_ONLY_ANALYTICS,
        read_only=True,
        required_permissions=("pages_read_user_content",),
    ),
    AutomationStepType.REPLY_COMMENTS: StepCapabilityInfo(
        step_type=AutomationStepType.REPLY_COMMENTS,
        title="Reply to Selected Comments",
        description="Sends operator-approved replies to filtered customer comments.",
        support_tier=CapabilitySupport.REQUIRES_OPERATOR_APPROVAL,
        required_permissions=("pages_manage_engagement",),
    ),
    AutomationStepType.MODERATE_COMMENTS: StepCapabilityInfo(
        step_type=AutomationStepType.MODERATE_COMMENTS,
        title="Moderate Comments",
        description="Hides or flags spam/profane comments using configured rules.",
        support_tier=CapabilitySupport.OFFICIALLY_SUPPORTED,
        required_permissions=("pages_manage_engagement",),
    ),
    AutomationStepType.READ_INBOX: StepCapabilityInfo(
        step_type=AutomationStepType.READ_INBOX,
        title="Read Inbox",
        description="Retrieves customer messages and inquiries.",
        support_tier=CapabilitySupport.READ_ONLY_ANALYTICS,
        read_only=True,
        required_permissions=("pages_messaging",),
    ),
    AutomationStepType.REPLY_INBOX: StepCapabilityInfo(
        step_type=AutomationStepType.REPLY_INBOX,
        title="Reply with Saved Reply",
        description="Sends operator-approved canned or AI-suggested response.",
        support_tier=CapabilitySupport.REQUIRES_OPERATOR_APPROVAL,
        required_permissions=("pages_messaging",),
    ),
    AutomationStepType.ASSIGN_INBOX: StepCapabilityInfo(
        step_type=AutomationStepType.ASSIGN_INBOX,
        title="Assign Inbox Item",
        description="Routes conversation to specific operator queue.",
        support_tier=CapabilitySupport.OFFICIALLY_SUPPORTED,
    ),
    AutomationStepType.ADD_INTERNAL_NOTE: StepCapabilityInfo(
        step_type=AutomationStepType.ADD_INTERNAL_NOTE,
        title="Add Internal Note",
        description="Attaches internal audit note to customer thread.",
        support_tier=CapabilitySupport.OFFICIALLY_SUPPORTED,
    ),
    AutomationStepType.MARK_RESOLVED: StepCapabilityInfo(
        step_type=AutomationStepType.MARK_RESOLVED,
        title="Mark Resolved",
        description="Updates customer support thread to resolved status.",
        support_tier=CapabilitySupport.OFFICIALLY_SUPPORTED,
    ),
    AutomationStepType.COLLECT_POST_ANALYTICS: StepCapabilityInfo(
        step_type=AutomationStepType.COLLECT_POST_ANALYTICS,
        title="Collect Post Analytics",
        description="Queries reach, impressions, and engagement metrics.",
        support_tier=CapabilitySupport.READ_ONLY_ANALYTICS,
        read_only=True,
        required_permissions=("pages_read_engagement",),
    ),
    AutomationStepType.COLLECT_REACTION_ANALYTICS: StepCapabilityInfo(
        step_type=AutomationStepType.COLLECT_REACTION_ANALYTICS,
        title="Reaction Analytics (Read-Only)",
        description=(
            "Collects reaction breakdown (Like, Love, Haha, Wow, Sad, Angry) for analytics only."
        ),
        support_tier=CapabilitySupport.READ_ONLY_ANALYTICS,
        read_only=True,
        required_permissions=("pages_read_engagement",),
    ),
    AutomationStepType.COLLECT_SHARE_VIEW_ANALYTICS: StepCapabilityInfo(
        step_type=AutomationStepType.COLLECT_SHARE_VIEW_ANALYTICS,
        title="Share & View Metrics",
        description="Queries shares, video views, and retention curves.",
        support_tier=CapabilitySupport.READ_ONLY_ANALYTICS,
        read_only=True,
        required_permissions=("pages_read_engagement",),
    ),
    AutomationStepType.COLLECT_FOLLOWER_ANALYTICS: StepCapabilityInfo(
        step_type=AutomationStepType.COLLECT_FOLLOWER_ANALYTICS,
        title="Follower & Growth Metrics",
        description="Tracks organic page fan and follower growth trends over time.",
        support_tier=CapabilitySupport.READ_ONLY_ANALYTICS,
        read_only=True,
        required_permissions=("pages_read_engagement",),
    ),
    AutomationStepType.BACKUP_WORKSPACE: StepCapabilityInfo(
        step_type=AutomationStepType.BACKUP_WORKSPACE,
        title="Backup Workspace",
        description="Creates lightweight encrypted .spws snapshot before device release.",
        support_tier=CapabilitySupport.OFFICIALLY_SUPPORTED,
        supports_device=True,
    ),
    AutomationStepType.RELEASE_DEVICE: StepCapabilityInfo(
        step_type=AutomationStepType.RELEASE_DEVICE,
        title="Release Device",
        description="Unlocks and cleans device lease in device pool.",
        support_tier=CapabilitySupport.OFFICIALLY_SUPPORTED,
        supports_device=True,
    ),
    AutomationStepType.START_NEXT_ACCOUNT: StepCapabilityInfo(
        step_type=AutomationStepType.START_NEXT_ACCOUNT,
        title="Start Next Account",
        description="Automatically dispatches next pending account in workflow queue.",
        support_tier=CapabilitySupport.OFFICIALLY_SUPPORTED,
    ),
}


@dataclass(frozen=True, slots=True)
class TargetSelectionRules:
    """Target selection and filtering configuration for workflow execution."""

    account_ids: tuple[str, ...] = ()
    account_category: str | None = None
    account_tags: tuple[str, ...] = ()
    only_healthy_accounts: bool = True
    only_accounts_with_device: bool = False
    only_valid_auth: bool = True

    # Device policies
    device_policy: str = "bound_first"  # bound_first, any_available, preferred_order
    provider_preference: tuple[str, ...] = ("ldplayer", "mumu", "physical")
    max_concurrent_devices: int = 4
    stop_device_after_release: bool = False

    # Destination policies
    destination_ids: tuple[str, ...] = ()
    destination_types: tuple[str, ...] = ("page",)  # page, group
    exclude_destination_ids: tuple[str, ...] = ()
    only_destinations_with_permissions: bool = True


@dataclass(frozen=True, slots=True)
class AutomationPresetStep:
    """A configured step within an automation workflow preset."""

    id: str
    preset_id: str
    step_type: AutomationStepType
    enabled: bool = True
    order: int = 0
    configuration: Mapping[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    continue_on_error: bool = False
    retry_policy: str = "no_retry"  # no_retry, once, up_to_3
    timeout_seconds: int = 120

    @property
    def capability_info(self) -> StepCapabilityInfo:
        return CAPABILITY_MATRIX[self.step_type]


@dataclass(frozen=True, slots=True)
class AutomationPreset:
    """A reusable automation workflow preset."""

    id: str
    name: str
    description: str
    target_rules: TargetSelectionRules = field(default_factory=TargetSelectionRules)
    steps: tuple[AutomationPresetStep, ...] = ()
    tags: tuple[str, ...] = ()
    is_built_in: bool = False
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class StepValidationResult:
    """Result of step configuration validation."""

    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def validate_step_config(
    step_type: AutomationStepType,
    config: Mapping[str, Any],
) -> StepValidationResult:
    """Validate step configuration against domain schema and platform safety rules."""
    errors: list[str] = []
    warnings: list[str] = []

    # Prohibited capabilities check
    if str(step_type) in FORBIDDEN_AUTOMATION_STEPS:
        return StepValidationResult(
            valid=False,
            errors=(
                f"Step type '{step_type}' is strictly prohibited by platform safety boundaries.",
            ),
        )

    # Check for forbidden reaction automation parameters
    if "reaction_type" in config and config.get("action") in ("give", "mass_react", "farm"):
        errors.append(
            "Automated reaction generation is prohibited. "
            "Only read-only reaction analytics are permitted."
        )

    if step_type == AutomationStepType.PUBLISH_TEXT:
        text = config.get("text", "")
        if not text and not config.get("caption_template_id"):
            errors.append("Publish Text step requires 'text' or 'caption_template_id'")
        if len(text) > 63206:
            errors.append("Post text exceeds platform character limit (63,206 chars)")

    elif step_type in (AutomationStepType.PUBLISH_IMAGE, AutomationStepType.PUBLISH_MULTI_IMAGE):
        media_paths = config.get("media_paths", [])
        if not media_paths and not config.get("media_pool_tag"):
            errors.append("Image publish step requires at least one media path or media pool tag")

    elif step_type == AutomationStepType.PUBLISH_VIDEO:
        video_path = config.get("video_path")
        media_pool_tag = config.get("media_pool_tag")
        if not video_path and not media_pool_tag:
            errors.append("Video publish step requires 'video_path' or 'media_pool_tag'")

    elif step_type == AutomationStepType.PUBLISH_REEL:
        video_path = config.get("video_path")
        media_pool_tag = config.get("media_pool_tag")
        if not video_path and not media_pool_tag:
            errors.append("Reel publish step requires 'video_path' or 'media_pool_tag'")
        aspect_ratio = config.get("aspect_ratio", "9:16")
        if aspect_ratio != "9:16":
            warnings.append("Reels are optimized for 9:16 vertical aspect ratio")

    elif step_type == AutomationStepType.PUBLISH_STORY:
        warnings.append(
            "Story publishing is capability-gated: "
            "only supported where Meta API officially permits."
        )

    elif step_type == AutomationStepType.REPLY_COMMENTS:
        if not config.get("reply_template") and not config.get("use_ai_suggestion"):
            errors.append("Comment reply step requires 'reply_template' or 'use_ai_suggestion'")
        max_replies = config.get("max_replies_per_run", 10)
        if max_replies > 50:
            warnings.append("High reply count may exceed hourly operator moderation thresholds")

    return StepValidationResult(
        valid=len(errors) == 0,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


@dataclass(frozen=True, slots=True)
class DryRunItem:
    """Individual planned action in a Dry Run execution plan."""

    step_order: int
    step_type: AutomationStepType
    title: str
    target_account: str
    target_destination: str
    expected_device: str
    requires_approval: bool
    summary: str
    capability_tier: CapabilitySupport
    is_read_only: bool


@dataclass(frozen=True, slots=True)
class DryRunReport:
    """Pre-flight Dry Run analysis ensuring zero side-effects."""

    preset_name: str
    target_accounts_count: int
    target_destinations_count: int
    expected_devices_count: int
    total_planned_steps: int
    estimated_jobs_count: int
    items: Sequence[DryRunItem]
    warnings: Sequence[str]
    is_safe_to_execute: bool
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def create_standard_preset(
    preset_key: str,
) -> AutomationPreset:
    """Factory creating the 5 standard built-in presets."""
    preset_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"spfarms.preset.{preset_key}"))

    if preset_key == "morning_publishing":
        steps: tuple[AutomationPresetStep, ...] = (
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.RESTORE_WORKSPACE,
                order=1,
                configuration={"clean_cache": False},
            ),
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.HEALTH_CHECK,
                order=2,
            ),
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.PUBLISH_IMAGE,
                order=3,
                configuration={
                    "caption": "Good morning! Fresh daily update.",
                    "media_pool_tag": "morning_pool",
                    "approval": True,
                },
                requires_approval=True,
            ),
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.PUBLISH_REEL,
                order=4,
                configuration={
                    "caption": "Daily highlights #spfarms",
                    "media_pool_tag": "morning_reels",
                    "approval": True,
                },
                requires_approval=True,
            ),
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.COLLECT_POST_ANALYTICS,
                order=5,
            ),
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.BACKUP_WORKSPACE,
                order=6,
            ),
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.RELEASE_DEVICE,
                order=7,
            ),
        )
        return AutomationPreset(
            id=preset_id,
            name="Morning Page Publishing",
            description=(
                "Daily morning cycle: restore, verify health, publish image & reel, "
                "collect insights, backup, release."
            ),
            tags=("publishing", "daily", "morning"),
            steps=steps,
            is_built_in=True,
        )

    if preset_key == "story_queue":
        steps = (
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.RESTORE_WORKSPACE,
                order=1,
            ),
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.PUBLISH_STORY,
                order=2,
                configuration={"media_type": "image", "approval": True},
                requires_approval=True,
            ),
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.BACKUP_WORKSPACE,
                order=3,
            ),
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.RELEASE_DEVICE,
                order=4,
            ),
        )
        return AutomationPreset(
            id=preset_id,
            name="Story Queue",
            description=(
                "Ephemeral story publishing where officially supported, "
                "with snapshot backup and device release."
            ),
            tags=("story", "ephemeral"),
            steps=steps,
            is_built_in=True,
        )

    if preset_key == "customer_support":
        steps = (
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.READ_INBOX,
                order=1,
            ),
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.READ_COMMENTS,
                order=2,
            ),
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.REPLY_INBOX,
                order=3,
                configuration={"max_replies_per_run": 5},
                requires_approval=True,
            ),
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.MARK_RESOLVED,
                order=4,
            ),
        )
        return AutomationPreset(
            id=preset_id,
            name="Customer Support & Inbox",
            description=(
                "Fetch incoming inquiries and comments, stage operator-approved "
                "canned replies, and mark resolved."
            ),
            tags=("support", "inbox", "moderation"),
            steps=steps,
            is_built_in=True,
        )

    if preset_key == "analytics_sweep":
        steps = (
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.COLLECT_POST_ANALYTICS,
                order=1,
            ),
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.COLLECT_REACTION_ANALYTICS,
                order=2,
            ),
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.COLLECT_SHARE_VIEW_ANALYTICS,
                order=3,
            ),
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=preset_id,
                step_type=AutomationStepType.COLLECT_FOLLOWER_ANALYTICS,
                order=4,
            ),
        )
        return AutomationPreset(
            id=preset_id,
            name="Analytics Sweep",
            description=(
                "Pure read-only sweep gathering post metrics, reaction counts, "
                "video views, and follower growth."
            ),
            tags=("analytics", "metrics", "read_only"),
            steps=steps,
            is_built_in=True,
        )

    # Content + Device Queue
    steps = (
        AutomationPresetStep(
            id=str(uuid.uuid4()),
            preset_id=preset_id,
            step_type=AutomationStepType.RESTORE_WORKSPACE,
            order=1,
        ),
        AutomationPresetStep(
            id=str(uuid.uuid4()),
            preset_id=preset_id,
            step_type=AutomationStepType.PUBLISH_IMAGE,
            order=2,
            configuration={"media_pool_tag": "approved_queue"},
            requires_approval=True,
        ),
        AutomationPresetStep(
            id=str(uuid.uuid4()),
            preset_id=preset_id,
            step_type=AutomationStepType.BACKUP_WORKSPACE,
            order=3,
        ),
        AutomationPresetStep(
            id=str(uuid.uuid4()),
            preset_id=preset_id,
            step_type=AutomationStepType.RELEASE_DEVICE,
            order=4,
        ),
        AutomationPresetStep(
            id=str(uuid.uuid4()),
            preset_id=preset_id,
            step_type=AutomationStepType.START_NEXT_ACCOUNT,
            order=5,
        ),
    )
    return AutomationPreset(
        id=preset_id,
        name="Content + Device Queue",
        description=(
            "Rotates through queued accounts on available devices, "
            "restores workspace, publishes, backups, and starts next."
        ),
        tags=("queue", "device_rotation"),
        steps=steps,
        is_built_in=True,
    )
