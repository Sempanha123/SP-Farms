"""Repository port for publishing attempts and logs."""

from collections.abc import Sequence
from typing import Protocol

from sp_farms.domain.publishing import PublishAttempt, PublishStatus


class PublishRepositoryPort(Protocol):
    """Persistence protocol for publish attempts."""

    def save(self, attempt: PublishAttempt) -> None:
        """Persist or update a publish attempt."""
        ...

    def get(self, attempt_id: str) -> PublishAttempt | None:
        """Retrieve a publish attempt by ID."""
        ...

    def get_by_idempotency_key(self, key: str) -> PublishAttempt | None:
        """Retrieve an attempt by idempotency key to prevent duplicates."""
        ...

    def list_recent(
        self,
        limit: int = 50,
        status: PublishStatus | None = None,
        destination_id: str | None = None,
        campaign_id: str | None = None,
    ) -> Sequence[PublishAttempt]:
        """List publish attempts with optional filtering."""
        ...
