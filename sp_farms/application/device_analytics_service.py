import json
import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sp_farms.application.device_analytics_repository import DeviceAnalyticsRepositoryPort
from sp_farms.application.ports import Clock
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.device_analytics import (
    DeviceOperationalEvent,
    DeviceReliabilityRating,
    DeviceReliabilityStats,
    FleetReliabilityReport,
    OperationalEventType,
    ProviderReliabilityStats,
)

logger = logging.getLogger(__name__)


class DeviceAnalyticsService:
    """Service orchestrating device reliability telemetry, operational scoring, and diagnostics."""

    def __init__(
        self,
        unit_of_work: Callable[[], UnitOfWork] | None = None,
        repo_factory: Callable[[UnitOfWork], DeviceAnalyticsRepositoryPort] | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._repo_factory = repo_factory
        self._clock = clock
        self._in_memory_events: list[DeviceOperationalEvent] = []

    def _now(self) -> datetime:
        if self._clock:
            return self._clock.now()
        return datetime.now(UTC)

    def record_event(
        self,
        device_key: str,
        provider: str,
        event_type: OperationalEventType | str,
        duration_seconds: float = 0.0,
        error_code: str | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DeviceOperationalEvent:
        """Record an operational telemetry event for a device."""
        ev_type = (
            event_type
            if isinstance(event_type, OperationalEventType)
            else OperationalEventType(event_type)
        )
        event = DeviceOperationalEvent(
            id=str(uuid4()),
            device_key=device_key,
            provider=provider,
            event_type=ev_type,
            duration_seconds=max(0.0, duration_seconds),
            error_code=error_code,
            error_message=error_message,
            metadata=metadata or {},
            created_at=self._now(),
        )

        if self._uow and self._repo_factory:
            with self._uow() as uow:
                repo = self._repo_factory(uow)
                repo.record_event(event)
                uow.commit()
        else:
            self._in_memory_events.append(event)

        return event

    def record_job_completion(
        self,
        device_key: str,
        provider: str,
        success: bool,
        duration_seconds: float,
        retried: bool = False,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Record the outcome of a job execution on a device."""
        if retried:
            self.record_event(
                device_key=device_key,
                provider=provider,
                event_type=OperationalEventType.JOB_RETRY,
                duration_seconds=duration_seconds,
                error_code=error_code,
                error_message=error_message,
            )

        ev_type = (
            OperationalEventType.JOB_SUCCESS if success else OperationalEventType.JOB_FAILURE
        )
        self.record_event(
            device_key=device_key,
            provider=provider,
            event_type=ev_type,
            duration_seconds=duration_seconds,
            error_code=error_code,
            error_message=error_message,
        )

    def record_disconnect(
        self,
        device_key: str,
        provider: str,
        reason: str = "",
    ) -> None:
        """Record an unexpected device disconnection."""
        self.record_event(
            device_key=device_key,
            provider=provider,
            event_type=OperationalEventType.DISCONNECT,
            error_message=reason or "Device disconnected",
        )

    def record_provider_error(
        self,
        device_key: str,
        provider: str,
        error_code: str,
        error_message: str = "",
    ) -> None:
        """Record a provider-level operational failure."""
        self.record_event(
            device_key=device_key,
            provider=provider,
            event_type=OperationalEventType.PROVIDER_ERROR,
            error_code=error_code,
            error_message=error_message,
        )

    def _get_events(
        self,
        device_key: str | None = None,
        provider: str | None = None,
        since: datetime | None = None,
    ) -> Sequence[DeviceOperationalEvent]:
        if self._uow and self._repo_factory:
            with self._uow() as uow:
                repo = self._repo_factory(uow)
                return repo.list_events(device_key=device_key, provider=provider, since=since)
        events = self._in_memory_events
        if device_key:
            events = [e for e in events if e.device_key == device_key]
        if provider:
            events = [e for e in events if e.provider == provider]
        if since:
            events = [e for e in events if e.created_at >= since]
        return events

    def get_device_reliability(
        self,
        device_key: str,
        serial: str | None = None,
        provider: str | None = None,
        since: datetime | None = None,
    ) -> DeviceReliabilityStats:
        """Compute comprehensive operational reliability metrics for a specific device."""
        events = self._get_events(device_key=device_key, since=since)
        effective_serial = serial or (device_key.split(":", 1)[-1] if ":" in device_key else device_key)
        effective_provider = provider or (device_key.split(":", 1)[0] if ":" in device_key else "unknown")

        successful_jobs = 0
        failed_jobs = 0
        retried_jobs = 0
        disconnect_count = 0
        provider_errors = 0
        total_duration = 0.0
        last_seen = None

        for ev in events:
            if last_seen is None or ev.created_at > last_seen:
                last_seen = ev.created_at
            if ev.event_type == OperationalEventType.JOB_SUCCESS:
                successful_jobs += 1
                total_duration += ev.duration_seconds
            elif ev.event_type == OperationalEventType.JOB_FAILURE:
                failed_jobs += 1
                total_duration += ev.duration_seconds
            elif ev.event_type == OperationalEventType.JOB_RETRY:
                retried_jobs += 1
            elif ev.event_type == OperationalEventType.DISCONNECT:
                disconnect_count += 1
            elif ev.event_type == OperationalEventType.PROVIDER_ERROR:
                provider_errors += 1

        total_jobs = successful_jobs + failed_jobs
        avg_duration = round(total_duration / total_jobs, 2) if total_jobs > 0 else 0.0

        # Provider error rate
        total_attempts = total_jobs + provider_errors
        provider_error_rate = (
            round((provider_errors / total_attempts) * 100.0, 2) if total_attempts > 0 else 0.0
        )

        # Uptime estimation
        if since is not None:
            window_sec = max(1.0, (self._now() - since).total_seconds())
            estimated_downtime_sec = min(disconnect_count * 120.0, window_sec)
            uptime_pct = round(max(0.0, 100.0 - (estimated_downtime_sec / window_sec * 100.0)), 2)
        else:
            uptime_pct = round(max(0.0, 100.0 - (disconnect_count * 5.0)), 2)

        # Reliability composite score (0 - 100)
        # Weights: Job success 50%, Uptime 30%, Disconnect penalty 10%, Provider errors 10%
        job_success_pct = (successful_jobs / total_jobs * 100.0) if total_jobs > 0 else 100.0
        disconnect_score = max(0.0, 100.0 - (disconnect_count * 10.0))
        error_score = max(0.0, 100.0 - provider_error_rate)

        composite_score = round(
            (job_success_pct * 0.50)
            + (uptime_pct * 0.30)
            + (disconnect_score * 0.10)
            + (error_score * 0.10),
            2,
        )

        rating = DeviceReliabilityRating.from_score(composite_score)

        return DeviceReliabilityStats(
            device_key=device_key,
            serial=effective_serial,
            provider=effective_provider,
            total_jobs=total_jobs,
            successful_jobs=successful_jobs,
            failed_jobs=failed_jobs,
            retried_jobs=retried_jobs,
            disconnect_count=disconnect_count,
            total_runtime_seconds=round(total_duration, 2),
            average_job_duration_seconds=avg_duration,
            uptime_percentage=uptime_pct,
            provider_error_rate=provider_error_rate,
            reliability_score=composite_score,
            rating=rating,
            last_seen=last_seen,
            diagnostics_summary={
                "provider_errors": provider_errors,
                "job_success_rate": job_success_pct,
            },
        )

    def get_provider_reliability(
        self,
        provider: str,
        since: datetime | None = None,
    ) -> ProviderReliabilityStats:
        """Compute aggregated reliability statistics for a provider across all its devices."""
        events = self._get_events(provider=provider, since=since)
        device_keys = {ev.device_key for ev in events}

        successful_jobs = sum(1 for e in events if e.event_type == OperationalEventType.JOB_SUCCESS)
        failed_jobs = sum(1 for e in events if e.event_type == OperationalEventType.JOB_FAILURE)
        disconnect_count = sum(1 for e in events if e.event_type == OperationalEventType.DISCONNECT)
        provider_errors = sum(1 for e in events if e.event_type == OperationalEventType.PROVIDER_ERROR)
        total_jobs = successful_jobs + failed_jobs

        total_ops = total_jobs + provider_errors
        error_rate = round((provider_errors / total_ops * 100.0), 2) if total_ops > 0 else 0.0

        scores = [
            self.get_device_reliability(d_key, provider=provider, since=since).reliability_score
            for d_key in device_keys
        ]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 100.0

        return ProviderReliabilityStats(
            provider_name=provider,
            total_devices=len(device_keys),
            active_devices=len(device_keys),
            total_jobs=total_jobs,
            successful_jobs=successful_jobs,
            failed_jobs=failed_jobs,
            disconnect_count=disconnect_count,
            provider_error_count=provider_errors,
            provider_error_rate=error_rate,
            average_reliability_score=avg_score,
        )

    def generate_fleet_report(
        self,
        known_devices: Sequence[tuple[str, str, str]] | None = None,
        since: datetime | None = None,
        time_window: str = "24h",
    ) -> FleetReliabilityReport:
        """Generate a complete reliability report for all monitored devices and providers."""
        all_events = self._get_events(since=since)

        # Collect distinct devices
        device_map: dict[str, tuple[str, str]] = {}  # device_key -> (serial, provider)
        if known_devices:
            for key, serial, prov in known_devices:
                device_map[key] = (serial, prov)

        for ev in all_events:
            if ev.device_key not in device_map:
                serial = ev.device_key.split(":", 1)[-1] if ":" in ev.device_key else ev.device_key
                device_map[ev.device_key] = (serial, ev.provider)

        device_stats: list[DeviceReliabilityStats] = []
        providers = set()
        unreliable_devices: list[str] = []

        for d_key, (ser, prov) in device_map.items():
            providers.add(prov)
            stats = self.get_device_reliability(d_key, serial=ser, provider=prov, since=since)
            device_stats.append(stats)
            if stats.reliability_score < 75.0 or stats.disconnect_count >= 3:
                unreliable_devices.append(d_key)

        provider_stats: list[ProviderReliabilityStats] = [
            self.get_provider_reliability(p, since=since) for p in sorted(providers)
        ]

        overall_score = (
            round(sum(d.reliability_score for d in device_stats) / len(device_stats), 2)
            if device_stats
            else 100.0
        )

        return FleetReliabilityReport(
            generated_at=self._now(),
            time_window=time_window,
            device_stats=device_stats,
            provider_stats=provider_stats,
            overall_score=overall_score,
            unreliable_devices=unreliable_devices,
        )

    def export_diagnostics_json(
        self,
        known_devices: Sequence[tuple[str, str, str]] | None = None,
        since: datetime | None = None,
        time_window: str = "24h",
    ) -> str:
        """Export full diagnostics payload as formatted JSON string."""
        report = self.generate_fleet_report(known_devices=known_devices, since=since, time_window=time_window)
        return json.dumps(report.to_diagnostics_dict(), indent=2)

    def export_diagnostics_csv(
        self,
        known_devices: Sequence[tuple[str, str, str]] | None = None,
        since: datetime | None = None,
        time_window: str = "24h",
    ) -> str:
        """Export fleet reliability metrics as CSV string."""
        report = self.generate_fleet_report(known_devices=known_devices, since=since, time_window=time_window)
        return report.to_csv()
