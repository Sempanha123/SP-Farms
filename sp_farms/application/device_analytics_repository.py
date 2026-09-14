from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from sp_farms.domain.device_analytics import DeviceOperationalEvent


class DeviceAnalyticsRepositoryPort(Protocol):
    """Repository port for recording and querying device operational analytics events."""

    def record_event(self, event: DeviceOperationalEvent) -> None:
        """Persist a single operational event."""
        ...

    def record_events(self, events: Sequence[DeviceOperationalEvent]) -> None:
        """Persist multiple operational events in batch."""
        ...

    def list_events(
        self,
        device_key: str | None = None,
        provider: str | None = None,
        since: datetime | None = None,
        limit: int = 1000,
    ) -> Sequence[DeviceOperationalEvent]:
        """Query operational events with optional filtering."""
        ...
