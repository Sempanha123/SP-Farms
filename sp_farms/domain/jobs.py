from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import uuid4


class JobState(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    RETRYING = "retrying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in (JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED)


_ALLOWED_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.PENDING: frozenset({JobState.QUEUED, JobState.CANCELLED}),
    JobState.QUEUED: frozenset({JobState.RUNNING, JobState.CANCELLED}),
    JobState.RUNNING: frozenset(
        {
            JobState.WAITING_APPROVAL,
            JobState.RETRYING,
            JobState.SUCCEEDED,
            JobState.FAILED,
            JobState.CANCELLED,
        }
    ),
    JobState.WAITING_APPROVAL: frozenset({JobState.RUNNING, JobState.CANCELLED}),
    JobState.RETRYING: frozenset({JobState.RUNNING, JobState.FAILED, JobState.CANCELLED}),
    JobState.SUCCEEDED: frozenset(),
    JobState.FAILED: frozenset(),
    JobState.CANCELLED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class JobEvent:
    id: str
    job_id: str
    from_state: JobState | None
    to_state: JobState
    message: str
    created_at: datetime


@dataclass(slots=True)
class Job:
    id: str
    job_type: str
    target_type: str
    target_id: str
    state: JobState
    progress: int
    attempt_count: int
    max_attempts: int
    idempotency_key: str | None
    error_code: str | None
    error_message: str | None
    next_retry_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def transition_to(
        self,
        new_state: JobState,
        message: str,
        now: datetime,
        error_code: str | None = None,
        error_message: str | None = None,
        next_retry_at: datetime | None = None,
        attempt_count: int | None = None,
    ) -> JobEvent:
        allowed = _ALLOWED_TRANSITIONS[self.state]
        if new_state not in allowed:
            raise ValueError(
                f"Invalid job state transition from {self.state.value} to {new_state.value}"
            )
        event = JobEvent(
            id=str(uuid4()),
            job_id=self.id,
            from_state=self.state,
            to_state=new_state,
            message=message,
            created_at=now,
        )
        self.state = new_state
        self.updated_at = now
        if error_code is not None:
            self.error_code = error_code
        if error_message is not None:
            self.error_message = error_message
        if next_retry_at is not None:
            self.next_retry_at = next_retry_at
        if attempt_count is not None:
            self.attempt_count = attempt_count
        return event

    def record_progress(self, progress: int, now: datetime) -> None:
        if not 0 <= progress <= 100:
            raise ValueError(f"Progress must be between 0 and 100, got {progress}")
        self.progress = progress
        self.updated_at = now

    def record_attempt(self) -> int:
        self.attempt_count += 1
        return self.attempt_count

    def is_runnable(self, now: datetime) -> bool:
        if self.state is JobState.QUEUED:
            return True
        if self.state is JobState.RETRYING:
            return self.next_retry_at is None or self.next_retry_at <= now
        return False


def calculate_backoff(
    attempt_count: int,
    base_seconds: float = 1.0,
    max_seconds: float = 60.0,
) -> timedelta:
    factor = 2 ** max(0, attempt_count - 1)
    delay = min(max_seconds, base_seconds * factor)
    return timedelta(seconds=delay)
