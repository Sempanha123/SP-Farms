from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class MetaPermission(StrEnum):
    PUBLIC_PROFILE = "public_profile"
    EMAIL = "email"
    PAGES_SHOW_LIST = "pages_show_list"
    PAGES_READ_ENGAGEMENT = "pages_read_engagement"
    PAGES_MANAGE_POSTS = "pages_manage_posts"
    PAGES_MANAGE_METADATA = "pages_manage_metadata"
    GROUPS_ACCESS_MEMBER_INFO = "groups_access_member_info"
    PUBLISH_VIDEO = "publish_video"
    BUSINESS_MANAGEMENT = "business_management"


class MetaTokenType(StrEnum):
    USER = "user"
    PAGE = "page"
    APP = "app"
    CLIENT = "client"


class MetaErrorCode(StrEnum):
    INVALID_OAUTH = "invalid_oauth"
    EXPIRED_TOKEN = "expired_token"
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    USER_RATE_LIMIT = "user_rate_limit"
    ASSET_NOT_FOUND = "asset_not_found"
    TEMPORARY_SERVICE_ERROR = "temporary_service_error"
    NETWORK_ERROR = "network_error"
    PARAM_ERROR = "param_error"
    GRAPH_METHOD_NOT_SUPPORTED = "graph_method_not_supported"
    DUPLICATE_POST = "duplicate_post"
    UNKNOWN_ERROR = "unknown_error"


@dataclass(frozen=True, slots=True)
class MetaScopeSet:
    permissions: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_string(cls, raw: str) -> "MetaScopeSet":
        if not raw.strip():
            return cls(frozenset())
        items = [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
        return cls(frozenset(items))

    def to_string(self) -> str:
        return ",".join(sorted(self.permissions))

    def has_permission(self, permission: str | MetaPermission) -> bool:
        perm_str = permission.value if isinstance(permission, MetaPermission) else permission
        return perm_str in self.permissions

    def contains_all(self, perms: "MetaScopeSet | set[str] | list[str]") -> bool:
        if isinstance(perms, MetaScopeSet):
            return perms.permissions.issubset(self.permissions)
        return set(perms).issubset(self.permissions)


@dataclass(frozen=True, slots=True)
class MetaTokenMetadata:
    app_id: str
    token_type: MetaTokenType
    scopes: MetaScopeSet
    user_id: str | None = None
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    is_valid: bool = True
    raw_debug_info: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(UTC) >= self.expires_at


@dataclass(frozen=True, slots=True)
class MetaRateLimitInfo:
    call_count: int = 0  # percentage 0-100
    total_cpu_time: int = 0  # percentage 0-100
    total_time: int = 0  # percentage 0-100
    estimated_time_to_regain_access: int = 0  # minutes
    is_throttled: bool = False

    @classmethod
    def from_headers(cls, headers: dict[str, str]) -> "MetaRateLimitInfo":
        import json

        raw_usage = headers.get("x-app-usage") or headers.get("X-App-Usage")
        if raw_usage:
            try:
                data = json.loads(raw_usage)
                call_count = int(data.get("call_count", 0))
                cpu = int(data.get("total_cpu_time", 0))
                total_time = int(data.get("total_time", 0))
                est_time = int(data.get("estimated_time_to_regain_access", 0))
                throttled = call_count >= 100 or cpu >= 100 or total_time >= 100 or est_time > 0
                return cls(
                    call_count=call_count,
                    total_cpu_time=cpu,
                    total_time=total_time,
                    estimated_time_to_regain_access=est_time,
                    is_throttled=throttled,
                )
            except Exception:
                pass
        return cls()


class MetaApiError(Exception):
    def __init__(
        self,
        message: str,
        code: MetaErrorCode = MetaErrorCode.UNKNOWN_ERROR,
        status_code: int | None = None,
        subcode: int | None = None,
        retry_after_seconds: float | None = None,
        raw_error: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.subcode = subcode
        self.retry_after_seconds = retry_after_seconds
        self.raw_error = raw_error or {}

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(code={self.code.value}, status_code={self.status_code}, "
            f"message={self.message!r}, retry_after={self.retry_after_seconds})"
        )


class MetaAuthError(MetaApiError):
    pass


class MetaPermissionError(MetaApiError):
    pass


class MetaRateLimitError(MetaApiError):
    pass


class MetaNotFoundError(MetaApiError):
    pass


class MetaTransientError(MetaApiError):
    pass


@dataclass(frozen=True, slots=True)
class MetaOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    graph_version: str = "v21.0"
    base_url: str = "https://graph.facebook.com"
    dialog_base_url: str = "https://www.facebook.com"


@dataclass(frozen=True, slots=True)
class MetaOAuthTokenResponse:
    access_token: str
    token_type: str
    expires_in: int | None = None  # seconds
    granted_scopes: MetaScopeSet = field(default_factory=MetaScopeSet)
