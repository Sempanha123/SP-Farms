from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from sp_farms.domain.audit import AuditEvent, AuditResult


class AuditRepository(Protocol):
    def add(self, event: AuditEvent) -> None:
        """Persist a new audit event."""
        ...

    def get(self, event_id: str) -> AuditEvent | None:
        """Retrieve an audit event by ID."""
        ...

    def list_events(
        self,
        limit: int = 100,
        offset: int = 0,
        result: AuditResult | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        action: str | None = None,
    ) -> Sequence[AuditEvent]:
        """List audit events matching criteria ordered by timestamp descending."""
        ...

    def list_errors(
        self,
        limit: int = 100,
        offset: int = 0,
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> Sequence[AuditEvent]:
        """List audit events that represent failures or errors."""
        ...

    def prune(self, older_than: datetime) -> int:
        """Prune audit records older than the given retention cutoff, returning deleted count."""
        ...
