"""Domain models for SelectionContext, TargetResolution, and Contextual Action Capabilities."""

from dataclasses import dataclass, field
from enum import StrEnum


class SelectionSource(StrEnum):
    ACCOUNTS = "accounts"
    PAGES = "pages"
    GROUPS = "groups"
    DEVICES = "devices"
    CAMPAIGNS = "campaigns"
    COMPOSER = "composer"


class TargetType(StrEnum):
    ACCOUNT = "account"
    PAGE = "page"
    GROUP = "group"
    DEVICE = "device"


class ActionTabType(StrEnum):
    OVERVIEW = "overview"
    RESTORE = "restore"
    CONTENT = "content"
    POST = "post"
    VIDEO = "video"
    REEL = "reel"
    STORY = "story"
    COMMENTS = "comments"
    INBOX = "inbox"
    ANALYTICS = "analytics"
    SCHEDULE = "schedule"
    BACKUP = "backup"
    DEVICE = "device"
    CONNECTED_ACCOUNT = "connected_account"
    ASSIGNED_ACCOUNT = "assigned_account"
    LAUNCH_APP = "launch_app"
    HEALTH = "health"
    SCREENSHOT = "screenshot"
    LOGS = "logs"
    RELEASE = "release"
    SECURITY = "security"
    NETWORK = "network"
    MAINTENANCE = "maintenance"
    QA_PROFILE_LAB = "qa_profile_lab"
    ADVANCED = "advanced"


@dataclass(frozen=True, slots=True)
class TargetCapability:
    """Capability flag for a resolved target."""

    can_restore: bool = True
    can_post_feed: bool = True
    can_post_video: bool = True
    can_post_reel: bool = True
    can_post_story: bool = False  # Gated by Meta API capability
    can_reply_comments: bool = True
    can_manage_inbox: bool = True
    can_collect_analytics: bool = True
    can_backup: bool = True
    can_manage_device: bool = True
    requires_approval: bool = False


@dataclass(frozen=True, slots=True)
class ResolvedTarget:
    """Fully resolved target with owning account and device bindings."""

    target_id: str
    target_type: TargetType
    display_name: str
    owning_account_id: str | None = None
    owning_account_name: str | None = None
    bound_device_id: str | None = None
    bound_device_provider: str | None = None
    preferred_app: str = "facebook"
    auth_state: str = "ready"  # ready | needs_reauth | unauthenticated
    health_status: str = "healthy"  # healthy | degraded | critical
    capabilities: TargetCapability = field(default_factory=TargetCapability)


@dataclass(frozen=True, slots=True)
class SelectionContext:
    """Rich selection context captured from UI tables or automation inputs."""

    source_module: SelectionSource
    selected_account_ids: tuple[str, ...] = ()
    selected_page_ids: tuple[str, ...] = ()
    selected_group_ids: tuple[str, ...] = ()
    selected_device_ids: tuple[str, ...] = ()
    resolved_targets: tuple[ResolvedTarget, ...] = ()
    inferred_account_ids: tuple[str, ...] = ()
    inferred_device_ids: tuple[str, ...] = ()
    common_capabilities: tuple[str, ...] = ()
    mixed_capabilities: tuple[str, ...] = ()

    @property
    def target_count(self) -> int:
        return len(self.resolved_targets)

    @property
    def is_multi_select(self) -> bool:
        return len(self.resolved_targets) > 1

    @property
    def primary_target(self) -> ResolvedTarget | None:
        return self.resolved_targets[0] if self.resolved_targets else None

    @property
    def summary_header(self) -> str:
        count = self.target_count
        if count == 0:
            return "No targets selected"
        if count == 1 and self.primary_target:
            t = self.primary_target
            return f"{t.target_type.value.capitalize()}: {t.display_name}"
        return f"{count} {self.source_module.value.capitalize()} selected (Batch Action)"

    @property
    def read_only_summary(self) -> str:
        """Compact read-only 'Using:' summary line for contextual tabs."""
        if not self.resolved_targets:
            return "Using: No active target context"
        if len(self.resolved_targets) == 1:
            t = self.resolved_targets[0]
            acc = (
                t.owning_account_name or t.display_name
                if t.target_type == TargetType.ACCOUNT
                else (t.owning_account_name or "Unknown")
            )
            page = t.display_name if t.target_type == TargetType.PAGE else "n/a"
            dev = f"{t.bound_device_provider or 'device'}:{t.bound_device_id or 'none'}"
            app_name = t.preferred_app.capitalize()
            auth_s = t.auth_state.capitalize()
            return (
                f"Using: Account: {acc} | Page: {page} | "
                f"Device: {dev} | App: {app_name} | State: {auth_s}"
            )
        num_targets = len(self.resolved_targets)
        num_accounts = len(self.inferred_account_ids)
        num_devices = len(self.inferred_device_ids)
        return (
            f"Using: {num_targets} targets across {num_accounts} accounts and {num_devices} devices"
        )

    def get_supported_tabs(self) -> tuple[ActionTabType, ...]:
        """Determine applicable tabs based on source module and target capabilities."""
        if self.source_module == SelectionSource.ACCOUNTS:
            return (
                ActionTabType.OVERVIEW,
                ActionTabType.RESTORE,
                ActionTabType.CONTENT,
                ActionTabType.POST,
                ActionTabType.VIDEO,
                ActionTabType.REEL,
                ActionTabType.STORY,
                ActionTabType.COMMENTS,
                ActionTabType.INBOX,
                ActionTabType.ANALYTICS,
                ActionTabType.BACKUP,
                ActionTabType.DEVICE,
                ActionTabType.NETWORK,
                ActionTabType.SECURITY,
                ActionTabType.MAINTENANCE,
                ActionTabType.ADVANCED,
            )
        if self.source_module == SelectionSource.PAGES:
            return (
                ActionTabType.OVERVIEW,
                ActionTabType.CONTENT,
                ActionTabType.POST,
                ActionTabType.VIDEO,
                ActionTabType.REEL,
                ActionTabType.STORY,
                ActionTabType.COMMENTS,
                ActionTabType.INBOX,
                ActionTabType.ANALYTICS,
                ActionTabType.SCHEDULE,
                ActionTabType.BACKUP,
                ActionTabType.CONNECTED_ACCOUNT,
                ActionTabType.DEVICE,
                ActionTabType.NETWORK,
                ActionTabType.ADVANCED,
            )
        if self.source_module == SelectionSource.DEVICES:
            return (
                ActionTabType.OVERVIEW,
                ActionTabType.ASSIGNED_ACCOUNT,
                ActionTabType.LAUNCH_APP,
                ActionTabType.HEALTH,
                ActionTabType.SCREENSHOT,
                ActionTabType.LOGS,
                ActionTabType.BACKUP,
                ActionTabType.RELEASE,
                ActionTabType.QA_PROFILE_LAB,
                ActionTabType.ADVANCED,
            )
        # Default fallback
        return (ActionTabType.OVERVIEW, ActionTabType.POST, ActionTabType.ADVANCED)
