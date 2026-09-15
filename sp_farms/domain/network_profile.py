"""Domain models for per-account VPN and proxy network profiles."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import uuid4


class NetworkProfileType(StrEnum):
    SYSTEM = "system"
    VPN = "vpn"
    HTTP_PROXY = "http_proxy"
    HTTPS_PROXY = "https_proxy"
    SOCKS5 = "socks5"


class FallbackPolicy(StrEnum):
    STOP = "stop"
    USE_FALLBACK_PROFILE = "use_fallback_profile"
    USE_SYSTEM_NETWORK = "use_system_network"


class NetworkBindingStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    FAILED = "failed"
    PENDING_VERIFY = "pending_verify"


@dataclass(frozen=True, slots=True)
class NetworkProfile:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    profile_type: NetworkProfileType = NetworkProfileType.SYSTEM
    provider_name: str = ""
    host: str = ""
    port: int = 0
    username_secret_ref: str | None = None
    password_secret_ref: str | None = None
    config_file_secret_ref: str | None = None
    protocol: str = "tcp"
    country_code: str = ""
    region_label: str = ""
    city_label: str = ""
    dns_mode: str = "auto"
    enabled: bool = True
    verify_before_use: bool = True
    require_success: bool = True
    fallback_profile_id: str | None = None
    notes: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_health_check_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None


@dataclass(frozen=True, slots=True)
class AccountNetworkBinding:
    account_id: str
    network_profile_id: str
    id: str = field(default_factory=lambda: str(uuid4()))
    apply_before_restore: bool = True
    require_network: bool = True
    fallback_policy: FallbackPolicy = FallbackPolicy.STOP
    last_applied_device_id: str | None = None
    last_verified_at: datetime | None = None
    status: NetworkBindingStatus = NetworkBindingStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PageNetworkOverride:
    page_id: str
    network_profile_id: str
    id: str = field(default_factory=lambda: str(uuid4()))
    enabled: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class NetworkVerificationResult:
    success: bool
    profile_id: str | None = None
    observed_ip: str | None = None
    observed_country: str | None = None
    observed_region: str | None = None
    latency_ms: float = 0.0
    is_match: bool = True
    error_code: str | None = None
    error_message: str | None = None
    message: str | None = None


class NetworkRequirementError(RuntimeError):
    """Raised when required network cannot be established before restore."""
