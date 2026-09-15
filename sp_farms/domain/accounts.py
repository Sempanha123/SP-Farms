from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import StrEnum
from uuid import uuid4


class AccountStatus(StrEnum):
    ACTIVE = "active"
    ATTENTION = "attention"
    DISABLED = "disabled"


class AccountGender(StrEnum):
    FEMALE = "female"
    MALE = "male"
    NON_BINARY = "non_binary"
    UNSPECIFIED = "unspecified"


class PreferredApp(StrEnum):
    FACEBOOK = "facebook"
    FACEBOOK_LITE = "facebook_lite"
    INSTAGRAM = "instagram"
    BROWSER = "browser"


class PermissionState(StrEnum):
    UNKNOWN = "unknown"
    COMPLETE = "complete"
    LIMITED = "limited"
    REVOKED = "revoked"


class SecurityState(StrEnum):
    UNKNOWN = "unknown"
    SECURE = "secure"
    REVIEW_REQUIRED = "review_required"
    COMPROMISED = "compromised"


class AccountHealthState(StrEnum):
    HEALTHY = "healthy"
    ATTENTION = "attention"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class AccountCategory:
    id: str
    name: str
    color: str


@dataclass(frozen=True, slots=True)
class AccountTag:
    id: str
    name: str
    color: str


@dataclass(frozen=True, slots=True)
class AccountDeviceAssignment:
    account_id: str
    provider: str
    external_id: str


@dataclass(frozen=True, slots=True)
class Account:
    id: str
    display_name: str
    first_name: str
    last_name: str
    platform_uid: str
    primary_email: str
    phone: str
    country: str
    locale: str
    timezone: str
    status: AccountStatus
    two_factor_enabled: bool
    preferred_app: PreferredApp
    permission_state: PermissionState
    security_state: SecurityState
    avatar_ref: str | None = None
    birthday: date | None = None
    gender: AccountGender | None = None
    recovery_email: str | None = None
    account_created_at: datetime | None = None
    category_id: str | None = None
    tag_ids: tuple[str, ...] = ()
    notes: str = ""
    assigned_device: AccountDeviceAssignment | None = None
    last_login_at: datetime | None = None
    last_verified_at: datetime | None = None
    page_count: int = 0
    group_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    archived_at: datetime | None = None

    @classmethod
    def create(
        cls,
        display_name: str,
        platform_uid: str,
        primary_email: str,
        now: datetime,
    ) -> "Account":
        return cls(
            id=str(uuid4()),
            display_name=_required(display_name, "Display name", 150),
            first_name="",
            last_name="",
            platform_uid=_required(platform_uid, "Platform UID", 255),
            primary_email=_required(primary_email, "Primary email", 320),
            phone="",
            country="",
            locale="",
            timezone="UTC",
            status=AccountStatus.ACTIVE,
            two_factor_enabled=False,
            preferred_app=PreferredApp.BROWSER,
            permission_state=PermissionState.UNKNOWN,
            security_state=SecurityState.UNKNOWN,
            created_at=now,
            updated_at=now,
        )

    def archive(self, now: datetime) -> "Account":
        return replace(self, archived_at=now, updated_at=now)


@dataclass(frozen=True, slots=True)
class AccountHealth:
    score: int
    state: AccountHealthState
    reasons: tuple[str, ...]


def calculate_account_health(account: Account) -> AccountHealth:
    score = 100
    reasons: list[str] = []

    deductions = (
        (account.status is AccountStatus.DISABLED, 60, "Account is disabled"),
        (account.status is AccountStatus.ATTENTION, 25, "Account needs attention"),
        (
            account.security_state is SecurityState.COMPROMISED,
            70,
            "Security state is compromised",
        ),
        (
            account.security_state is SecurityState.REVIEW_REQUIRED,
            30,
            "Security review is required",
        ),
        (
            account.permission_state is PermissionState.REVOKED,
            40,
            "Permissions are revoked",
        ),
        (
            account.permission_state is PermissionState.LIMITED,
            15,
            "Permissions are limited",
        ),
        (not account.two_factor_enabled, 15, "Two-factor authentication is disabled"),
        (account.last_verified_at is None, 10, "Account has not been verified"),
        (account.assigned_device is None, 5, "No device is assigned"),
        (
            not account.first_name or not account.country or not account.locale,
            5,
            "Profile metadata is incomplete",
        ),
    )
    for applies, deduction, reason in deductions:
        if applies:
            score -= deduction
            reasons.append(reason)

    score = max(0, score)
    if score >= 80:
        state = AccountHealthState.HEALTHY
    elif score >= 50:
        state = AccountHealthState.ATTENTION
    else:
        state = AccountHealthState.CRITICAL
    return AccountHealth(score, state, tuple(reasons))


def validate_account(account: Account) -> None:
    _required(account.display_name, "Display name", 150)
    _required(account.platform_uid, "Platform UID", 255)
    _required(account.primary_email, "Primary email", 320)
    if account.page_count < 0 or account.group_count < 0:
        raise ValueError("Page and group counts cannot be negative")


def validate_label(value: str) -> str:
    return _required(value, "Name", 100)


def _required(value: str, field: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ValueError(f"{field} must contain 1-{maximum} characters")
    return normalized
