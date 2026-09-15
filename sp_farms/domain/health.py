"""Domain models for application health checks, crash recovery, and update management."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    component: str
    status: HealthStatus
    message: str
    latency_ms: float = 0.0
    details: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        return self.status == HealthStatus.HEALTHY


@dataclass(frozen=True, slots=True)
class HealthSummary:
    overall_status: HealthStatus
    checks: Sequence[HealthCheckResult]
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_fully_healthy(self) -> bool:
        return self.overall_status == HealthStatus.HEALTHY

    @property
    def healthy_count(self) -> int:
        return sum(1 for c in self.checks if c.status == HealthStatus.HEALTHY)

    @property
    def degraded_count(self) -> int:
        return sum(1 for c in self.checks if c.status == HealthStatus.DEGRADED)

    @property
    def critical_count(self) -> int:
        return sum(1 for c in self.checks if c.status == HealthStatus.CRITICAL)


@dataclass(frozen=True, slots=True)
class SafeModeState:
    safe_mode_active: bool
    unclean_shutdowns_count: int
    last_crash_at: datetime | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class AppVersionInfo:
    current_version: str
    latest_version: str
    is_update_available: bool
    channel: str = "stable"
    release_notes: str = ""
    download_url: str = ""
    published_at: str = ""
