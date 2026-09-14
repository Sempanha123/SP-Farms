from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ProductEdition(StrEnum):
    FREE = "free"
    PRO = "pro"
    VIP = "vip"
    DEV = "dev"


class LicenseStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    GRACE_PERIOD = "grace_period"
    INVALID_SIGNATURE = "invalid_signature"
    CORRUPTED = "corrupted"
    DEV_MODE = "dev_mode"
    UNLICENSED = "unlicensed"


class FeatureFlag(StrEnum):
    UNLIMITED_ACCOUNTS = "unlimited_accounts"
    UNLIMITED_DEVICES = "unlimited_devices"
    ADVANCED_ANALYTICS = "advanced_analytics"
    AI_CAPTIONS = "ai_captions"
    AUTOMATION_APPIUM = "automation_appium"
    PLUGINS_RUNTIME = "plugins_runtime"
    HYBRID_PUBLISHING = "hybrid_publishing"
    DISASTER_RECOVERY_SCHEDULE = "disaster_recovery_schedule"


@dataclass(frozen=True, slots=True)
class LicensePayload:
    license_id: str
    licensee_name: str
    licensee_email: str
    edition: ProductEdition
    issued_at: datetime
    expires_at: datetime | None
    max_accounts: int
    max_devices: int
    feature_flags: tuple[FeatureFlag, ...]
    grace_period_days: int = 7
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LicenseInfo:
    status: LicenseStatus
    edition: ProductEdition
    payload: LicensePayload | None = None
    message: str = ""
    is_valid: bool = False

    def has_feature(self, feature: FeatureFlag | str) -> bool:
        if self.edition == ProductEdition.DEV:
            return True
        if not self.is_valid or not self.payload:
            # Free tier defaults if unlicensed
            return False
        feat_enum = FeatureFlag(feature) if isinstance(feature, str) else feature
        return feat_enum in self.payload.feature_flags

    def max_accounts_allowed(self) -> int:
        if self.edition == ProductEdition.DEV:
            return 99999
        if not self.is_valid or not self.payload:
            return 5  # Free tier default
        return self.payload.max_accounts

    def max_devices_allowed(self) -> int:
        if self.edition == ProductEdition.DEV:
            return 99999
        if not self.is_valid or not self.payload:
            return 2  # Free tier default
        return self.payload.max_devices
