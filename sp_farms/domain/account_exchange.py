from dataclasses import dataclass
from enum import StrEnum
from typing import Any

# Forbidden secret field names
FORBIDDEN_SECRET_FIELDS: frozenset[str] = frozenset({
    "password",
    "passwords",
    "token",
    "access_token",
    "auth_token",
    "session_token",
    "cookie",
    "cookies",
    "secret",
    "secrets",
    "recovery_secret",
    "recovery_code",
    "recovery_codes",
    "private_key",
    "secret_key",
    "two_factor_secret",
    "totp_secret",
})


class ExportFormat(StrEnum):
    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"


class ConflictStrategy(StrEnum):
    SKIP = "skip"
    OVERWRITE = "overwrite"
    ERROR = "error"


class ExportPreset(StrEnum):
    FULL = "full"
    BASIC = "basic"
    SECURITY_AUDIT = "security_audit"
    OPERATIONS = "operations"


# Canonical list of safe exportable fields and readable labels
EXPORT_FIELD_LABELS: dict[str, str] = {
    "platform_uid": "Platform UID",
    "display_name": "Name",
    "primary_email": "Primary Email",
    "phone": "Phone",
    "birthday": "Birthday",
    "gender": "Gender",
    "category": "Category",
    "tags": "Tags",
    "status": "Status",
    "device_name": "Device",
    "device_provider": "Provider",
    "preferred_app": "Preferred App",
    "two_factor_enabled": "2FA Enabled",
    "recovery_email": "Recovery Email",
    "country": "Country",
    "locale": "Locale",
    "timezone": "Timezone",
    "first_name": "First Name",
    "last_name": "Last Name",
    "page_count": "Pages",
    "group_count": "Groups",
    "permission_state": "Permission State",
    "security_state": "Security State",
    "created_at": "Created Date",
    "last_login_at": "Last Login",
    "last_verified_at": "Last Verified",
    "notes": "Notes",
}

PRESET_FIELDS: dict[ExportPreset, tuple[str, ...]] = {
    ExportPreset.FULL: tuple(EXPORT_FIELD_LABELS.keys()),
    ExportPreset.BASIC: (
        "platform_uid",
        "display_name",
        "primary_email",
        "phone",
        "category",
        "status",
        "created_at",
    ),
    ExportPreset.SECURITY_AUDIT: (
        "platform_uid",
        "display_name",
        "primary_email",
        "two_factor_enabled",
        "recovery_email",
        "permission_state",
        "security_state",
        "last_login_at",
        "last_verified_at",
        "notes",
    ),
    ExportPreset.OPERATIONS: (
        "platform_uid",
        "display_name",
        "status",
        "device_name",
        "device_provider",
        "preferred_app",
        "category",
        "tags",
        "notes",
    ),
}


@dataclass(frozen=True, slots=True)
class ImportRowResult:
    row_index: int
    platform_uid: str
    display_name: str
    is_valid: bool
    is_duplicate: bool
    existing_account_id: str | None
    errors: tuple[str, ...]
    normalized_data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ImportDryRunResult:
    total_rows: int
    valid_count: int
    duplicate_count: int
    error_count: int
    rows: tuple[ImportRowResult, ...]

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    @property
    def has_duplicates(self) -> bool:
        return self.duplicate_count > 0


@dataclass(frozen=True, slots=True)
class ImportExecutionResult:
    created_count: int
    updated_count: int
    skipped_count: int
    errors: tuple[str, ...]


def contains_secret_fields(data: dict[str, Any]) -> list[str]:
    found = []
    for k in data:
        cleaned = k.casefold().replace("-", "_").strip()
        if cleaned in FORBIDDEN_SECRET_FIELDS:
            found.append(k)
    return found
