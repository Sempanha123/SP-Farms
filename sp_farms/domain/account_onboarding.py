import json
import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import StrEnum
from typing import cast

from sp_farms.domain.accounts import (
    Account,
    AccountGender,
    AccountStatus,
    PermissionState,
    PreferredApp,
    SecurityState,
)

SCHEMA_VERSION = 1
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE_PATTERN = re.compile(r"^\+?[0-9 ()-]+$")
_SECRET_FIELDS = frozenset(
    {
        "access_token",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "password",
        "recovery_code",
        "recovery_codes",
        "refresh_token",
        "secret",
        "session",
        "session_cookie",
        "token",
        "totp_seed",
    }
)
_ACCOUNT_FIELDS = frozenset(
    {
        "account_created_at",
        "avatar_ref",
        "birthday",
        "country",
        "display_name",
        "first_name",
        "gender",
        "group_count",
        "last_login_at",
        "last_name",
        "last_verified_at",
        "locale",
        "notes",
        "page_count",
        "permission_state",
        "phone",
        "platform_uid",
        "preferred_app",
        "primary_email",
        "recovery_email",
        "security_state",
        "status",
        "timezone",
        "two_factor_enabled",
    }
)


class OnboardingSource(StrEnum):
    OFFICIAL_FACEBOOK = "official_facebook"
    AUTHORIZED_METADATA_IMPORT = "authorized_metadata_import"
    MANUAL = "manual"
    DEVELOPMENT_TEST = "development_test"
    AUTHORIZED_SESSION = "authorized_session"


@dataclass(frozen=True, slots=True)
class AccountOnboardingRequest:
    source: OnboardingSource
    display_name: str
    platform_uid: str
    primary_email: str
    first_name: str = ""
    last_name: str = ""
    avatar_ref: str | None = None
    birthday: date | None = None
    gender: AccountGender | None = None
    recovery_email: str | None = None
    phone: str = ""
    country: str = ""
    locale: str = ""
    timezone: str = "UTC"
    account_created_at: datetime | None = None
    status: AccountStatus = AccountStatus.ACTIVE
    two_factor_enabled: bool = False
    notes: str = ""
    preferred_app: PreferredApp = PreferredApp.BROWSER
    last_login_at: datetime | None = None
    last_verified_at: datetime | None = None
    page_count: int = 0
    group_count: int = 0
    permission_state: PermissionState = PermissionState.UNKNOWN
    security_state: SecurityState = SecurityState.UNKNOWN


def validate_onboarding_request(request: AccountOnboardingRequest) -> AccountOnboardingRequest:
    display_name = _text(request.display_name, "Display name", 150, required=True)
    platform_uid = _text(request.platform_uid, "Platform UID", 255, required=True)
    primary_email = _required_email(request.primary_email, "Primary email")
    recovery_email = _optional_email(request.recovery_email, "Recovery email")
    phone = _phone(request.phone)
    if recovery_email and recovery_email.casefold() == primary_email.casefold():
        raise ValueError("Recovery email must differ from primary email")
    if request.preferred_app is PreferredApp.INSTAGRAM:
        raise ValueError("Preferred app must be Facebook, Facebook Lite, or Browser")
    if request.page_count < 0 or request.group_count < 0:
        raise ValueError("Page and group counts cannot be negative")
    for value, field in (
        (request.account_created_at, "Account created timestamp"),
        (request.last_login_at, "Last login timestamp"),
        (request.last_verified_at, "Last verification timestamp"),
    ):
        if value is not None and value.tzinfo is None:
            raise ValueError(f"{field} must include a timezone")
    return replace(
        request,
        display_name=display_name,
        platform_uid=platform_uid,
        primary_email=primary_email,
        recovery_email=recovery_email,
        phone=phone,
        first_name=_text(request.first_name, "First name", 100),
        last_name=_text(request.last_name, "Last name", 100),
        avatar_ref=_optional_text(request.avatar_ref, "Avatar reference", 500),
        country=_text(request.country, "Country", 100),
        locale=_text(request.locale, "Locale", 50),
        timezone=_text(request.timezone, "Timezone", 100, required=True),
        notes=_text(request.notes, "Notes", 10_000),
    )


def parse_onboarding_document(payload: str) -> AccountOnboardingRequest:
    try:
        loaded = cast(object, json.loads(payload))
    except json.JSONDecodeError as exc:
        raise ValueError("Metadata import must be valid JSON") from exc
    if not isinstance(loaded, dict):
        raise ValueError("Metadata import must be a JSON object")
    document = cast(dict[str, object], loaded)
    _reject_secret_fields(document)
    _require_known_fields(document, {"schema_version", "source", "account"}, "document")
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Unsupported metadata schema version; expected {SCHEMA_VERSION}")
    raw_account = document.get("account")
    if not isinstance(raw_account, dict):
        raise ValueError("Metadata document account must be an object")
    account = cast(dict[str, object], raw_account)
    _require_known_fields(account, _ACCOUNT_FIELDS, "account")
    source = _enum(
        OnboardingSource,
        document.get("source", OnboardingSource.AUTHORIZED_METADATA_IMPORT.value),
        "source",
    )
    if source in {OnboardingSource.OFFICIAL_FACEBOOK, OnboardingSource.AUTHORIZED_SESSION}:
        raise ValueError("Connected account metadata must come from a configured connector")
    return validate_onboarding_request(
        AccountOnboardingRequest(
            source=source,
            display_name=_string_value(account, "display_name", required=True),
            platform_uid=_string_value(account, "platform_uid", required=True),
            primary_email=_string_value(account, "primary_email", required=True),
            first_name=_string_value(account, "first_name"),
            last_name=_string_value(account, "last_name"),
            avatar_ref=_optional_string_value(account, "avatar_ref"),
            birthday=_date_value(account, "birthday"),
            gender=_optional_enum(AccountGender, account.get("gender"), "gender"),
            recovery_email=_optional_string_value(account, "recovery_email"),
            phone=_string_value(account, "phone"),
            country=_string_value(account, "country"),
            locale=_string_value(account, "locale"),
            timezone=_string_value(account, "timezone", default="UTC"),
            account_created_at=_datetime_value(account, "account_created_at"),
            status=_enum(AccountStatus, account.get("status", "active"), "status"),
            two_factor_enabled=_bool_value(account, "two_factor_enabled"),
            notes=_string_value(account, "notes"),
            preferred_app=_enum(
                PreferredApp,
                account.get("preferred_app", "browser"),
                "preferred_app",
            ),
            last_login_at=_datetime_value(account, "last_login_at"),
            last_verified_at=_datetime_value(account, "last_verified_at"),
            page_count=_int_value(account, "page_count"),
            group_count=_int_value(account, "group_count"),
            permission_state=_enum(
                PermissionState,
                account.get("permission_state", "unknown"),
                "permission_state",
            ),
            security_state=_enum(
                SecurityState,
                account.get("security_state", "unknown"),
                "security_state",
            ),
        )
    )


def export_account_metadata(account: Account) -> str:
    data = {
        "schema_version": SCHEMA_VERSION,
        "source": OnboardingSource.AUTHORIZED_METADATA_IMPORT.value,
        "account": {
            "display_name": account.display_name,
            "platform_uid": account.platform_uid,
            "primary_email": account.primary_email,
            "first_name": account.first_name,
            "last_name": account.last_name,
            "avatar_ref": account.avatar_ref,
            "birthday": account.birthday.isoformat() if account.birthday else None,
            "gender": account.gender.value if account.gender else None,
            "recovery_email": account.recovery_email,
            "phone": account.phone,
            "country": account.country,
            "locale": account.locale,
            "timezone": account.timezone,
            "account_created_at": _isoformat(account.account_created_at),
            "status": account.status.value,
            "two_factor_enabled": account.two_factor_enabled,
            "notes": account.notes,
            "preferred_app": account.preferred_app.value,
            "last_login_at": _isoformat(account.last_login_at),
            "last_verified_at": _isoformat(account.last_verified_at),
            "page_count": account.page_count,
            "group_count": account.group_count,
            "permission_state": account.permission_state.value,
            "security_state": account.security_state.value,
        },
    }
    return json.dumps(data, indent=2, sort_keys=True)


def mask_email(value: str) -> str:
    local, separator, domain = value.partition("@")
    if not separator:
        return "***"
    return f"{local[:1]}***@{domain}"


def mask_phone(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    if not digits:
        return "—"
    visible = min(4, max(2, len(digits) // 2))
    return f"***{digits[-visible:]}"


def _reject_secret_fields(value: object) -> None:
    if isinstance(value, dict):
        for key, child in cast(dict[object, object], value).items():
            if isinstance(key, str) and key.casefold() in _SECRET_FIELDS:
                raise ValueError(f"Secret-bearing field '{key}' is not permitted")
            _reject_secret_fields(child)
    elif isinstance(value, list):
        for child in cast(list[object], value):
            _reject_secret_fields(child)


def _require_known_fields(
    value: dict[str, object], allowed: set[str] | frozenset[str], location: str
) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"Unknown {location} field: {sorted(unknown)[0]}")


def _string_value(
    value: dict[str, object], key: str, *, required: bool = False, default: str = ""
) -> str:
    raw = value.get(key, default)
    if not isinstance(raw, str):
        raise ValueError(f"{key} must be a string")
    if required and not raw.strip():
        raise ValueError(f"{key} is required")
    return raw


def _optional_string_value(value: dict[str, object], key: str) -> str | None:
    raw = value.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(f"{key} must be a string or null")
    return raw


def _bool_value(value: dict[str, object], key: str) -> bool:
    raw = value.get(key, False)
    if not isinstance(raw, bool):
        raise ValueError(f"{key} must be a boolean")
    return raw


def _int_value(value: dict[str, object], key: str) -> int:
    raw = value.get(key, 0)
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise ValueError(f"{key} must be an integer")
    return raw


def _date_value(value: dict[str, object], key: str) -> date | None:
    raw = value.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(f"{key} must be an ISO date string or null")
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an ISO date string") from exc


def _datetime_value(value: dict[str, object], key: str) -> datetime | None:
    raw = value.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(f"{key} must be an ISO timestamp string or null")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{key} must be an ISO timestamp string") from exc
    return parsed


def _enum[EnumT: StrEnum](
    enum_type: type[EnumT], value: object, field: str
) -> EnumT:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ValueError(f"Unsupported {field}: {value}") from exc


def _optional_enum[EnumT: StrEnum](
    enum_type: type[EnumT], value: object, field: str
) -> EnumT | None:
    return None if value is None else _enum(enum_type, value, field)


def _text(value: str, field: str, maximum: int, *, required: bool = False) -> str:
    normalized = value.strip()
    if required and not normalized:
        raise ValueError(f"{field} is required")
    if len(normalized) > maximum:
        raise ValueError(f"{field} must not exceed {maximum} characters")
    return normalized


def _optional_text(value: str | None, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    normalized = _text(value, field, maximum)
    return normalized or None


def _required_email(value: str, field: str) -> str:
    normalized = _text(value, field, 320, required=True)
    if not _EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError(f"{field} must be a valid email address")
    return normalized


def _optional_email(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    normalized = _text(value, field, 320)
    if normalized and not _EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError(f"{field} must be a valid email address")
    return normalized or None


def _phone(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return ""
    digits = "".join(character for character in normalized if character.isdigit())
    if not _PHONE_PATTERN.fullmatch(normalized) or not 7 <= len(digits) <= 15:
        raise ValueError("Phone must contain 7-15 digits and may start with +")
    return f"+{digits}" if normalized.startswith("+") else digits


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
