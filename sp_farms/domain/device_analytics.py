from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class DeviceReliabilityRating(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"

    @classmethod
    def from_score(cls, score: float) -> "DeviceReliabilityRating":
        if score >= 90.0:
            return cls.EXCELLENT
        if score >= 75.0:
            return cls.GOOD
        if score >= 60.0:
            return cls.FAIR
        if score >= 40.0:
            return cls.POOR
        return cls.CRITICAL


class OperationalEventType(StrEnum):
    HEARTBEAT = "heartbeat"
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    JOB_START = "job_start"
    JOB_SUCCESS = "job_success"
    JOB_FAILURE = "job_failure"
    JOB_RETRY = "job_retry"
    PROVIDER_ERROR = "provider_error"


@dataclass(frozen=True, slots=True)
class DeviceOperationalEvent:
    id: str
    device_key: str
    provider: str
    event_type: OperationalEventType
    duration_seconds: float = 0.0
    error_code: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class DeviceReliabilityStats:
    device_key: str
    serial: str
    provider: str
    total_jobs: int = 0
    successful_jobs: int = 0
    failed_jobs: int = 0
    cancelled_jobs: int = 0
    retried_jobs: int = 0
    disconnect_count: int = 0
    total_runtime_seconds: float = 0.0
    average_job_duration_seconds: float = 0.0
    uptime_percentage: float = 100.0
    provider_error_rate: float = 0.0
    reliability_score: float = 100.0
    rating: DeviceReliabilityRating = DeviceReliabilityRating.EXCELLENT
    last_seen: datetime | None = None
    diagnostics_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def job_success_rate(self) -> float:
        if self.total_jobs <= 0:
            return 100.0
        return round((self.successful_jobs / self.total_jobs) * 100.0, 2)

    @property
    def retry_rate(self) -> float:
        if self.total_jobs <= 0:
            return 0.0
        return round((self.retried_jobs / self.total_jobs) * 100.0, 2)


@dataclass(frozen=True, slots=True)
class ProviderReliabilityStats:
    provider_name: str
    total_devices: int = 0
    active_devices: int = 0
    total_jobs: int = 0
    successful_jobs: int = 0
    failed_jobs: int = 0
    disconnect_count: int = 0
    provider_error_count: int = 0
    provider_error_rate: float = 0.0
    average_reliability_score: float = 100.0


@dataclass(frozen=True, slots=True)
class FleetReliabilityReport:
    generated_at: datetime
    time_window: str
    device_stats: Sequence[DeviceReliabilityStats]
    provider_stats: Sequence[ProviderReliabilityStats]
    overall_score: float
    unreliable_devices: Sequence[str]

    def to_diagnostics_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "time_window": self.time_window,
            "overall_score": self.overall_score,
            "unreliable_devices": list(self.unreliable_devices),
            "providers": [
                {
                    "name": p.provider_name,
                    "total_devices": p.total_devices,
                    "active_devices": p.active_devices,
                    "total_jobs": p.total_jobs,
                    "successful_jobs": p.successful_jobs,
                    "failed_jobs": p.failed_jobs,
                    "disconnect_count": p.disconnect_count,
                    "error_rate": p.provider_error_rate,
                    "avg_reliability_score": p.average_reliability_score,
                }
                for p in self.provider_stats
            ],
            "devices": [
                {
                    "device_key": d.device_key,
                    "serial": d.serial,
                    "provider": d.provider,
                    "reliability_score": d.reliability_score,
                    "rating": d.rating.value,
                    "uptime_percentage": d.uptime_percentage,
                    "disconnect_count": d.disconnect_count,
                    "total_jobs": d.total_jobs,
                    "successful_jobs": d.successful_jobs,
                    "failed_jobs": d.failed_jobs,
                    "retried_jobs": d.retried_jobs,
                    "job_success_rate": d.job_success_rate,
                    "avg_job_duration_sec": d.average_job_duration_seconds,
                    "provider_error_rate": d.provider_error_rate,
                    "last_seen": d.last_seen.isoformat() if d.last_seen else None,
                }
                for d in self.device_stats
            ],
        }

    def to_csv(self) -> str:
        lines = [
            "device_key,serial,provider,reliability_score,rating,uptime_pct,disconnects,total_jobs,successful_jobs,failed_jobs,retried_jobs,avg_duration_sec,provider_error_rate"
        ]
        for d in self.device_stats:
            lines.append(
                f"{d.device_key},{d.serial},{d.provider},{d.reliability_score:.2f},{d.rating.value},"
                f"{d.uptime_percentage:.2f},{d.disconnect_count},{d.total_jobs},{d.successful_jobs},"
                f"{d.failed_jobs},{d.retried_jobs},{d.average_job_duration_seconds:.2f},{d.provider_error_rate:.2f}"
            )
        return "\n".join(lines)
