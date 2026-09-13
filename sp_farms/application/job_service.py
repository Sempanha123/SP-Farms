from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from sp_farms.application.jobs import JobRepository
from sp_farms.application.ports import Clock
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.jobs import Job, JobEvent, JobState


class JobService:
    def __init__(
        self,
        unit_of_work: Callable[[], UnitOfWork],
        repository_factory: Callable[[UnitOfWork], JobRepository],
        clock: Clock,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._repository_factory = repository_factory
        self._clock = clock

    def create_job(
        self,
        job_type: str,
        target_type: str,
        target_id: str,
        max_attempts: int = 3,
        idempotency_key: str | None = None,
    ) -> tuple[Job, bool]:
        now = self._clock.now()
        with self._unit_of_work() as unit:
            repository = self._repository_factory(unit)
            if idempotency_key is not None:
                existing = repository.find_by_idempotency_key(idempotency_key)
                if existing is not None:
                    return existing, False

            job = Job(
                id=str(uuid4()),
                job_type=job_type,
                target_type=target_type,
                target_id=target_id,
                state=JobState.PENDING,
                progress=0,
                attempt_count=0,
                max_attempts=max_attempts,
                idempotency_key=idempotency_key,
                error_code=None,
                error_message=None,
                next_retry_at=None,
                created_at=now,
                updated_at=now,
            )
            event = JobEvent(
                id=str(uuid4()),
                job_id=job.id,
                from_state=None,
                to_state=JobState.PENDING,
                message="Job created",
                created_at=now,
            )
            repository.add(job)
            repository.add_event(event)
            unit.commit()
            return job, True

    def transition_job(
        self,
        job_id: str,
        new_state: JobState,
        message: str,
        error_code: str | None = None,
        error_message: str | None = None,
        next_retry_at: datetime | None = None,
    ) -> Job:
        now = self._clock.now()
        with self._unit_of_work() as unit:
            repository = self._repository_factory(unit)
            job = repository.get(job_id)
            if job is None:
                raise KeyError(f"Job not found: {job_id}")
            event = job.transition_to(
                new_state=new_state,
                message=message,
                now=now,
                error_code=error_code,
                error_message=error_message,
                next_retry_at=next_retry_at,
            )
            repository.add(job)
            repository.add_event(event)
            unit.commit()
            return job

    def recover_interrupted_jobs(self) -> int:
        now = self._clock.now()
        with self._unit_of_work() as unit:
            repository = self._repository_factory(unit)
            recovered = 0
            for job in repository.list_active():
                if job.state is JobState.RUNNING:
                    recovery_state = (
                        JobState.RETRYING
                        if job.attempt_count < job.max_attempts
                        else JobState.FAILED
                    )
                    event = job.transition_to(
                        recovery_state,
                        "Interrupted by application restart",
                        now,
                        error_code="app_restart_recovery",
                        error_message="Job interrupted while running",
                    )
                    repository.add(job)
                    repository.add_event(event)
                    recovered += 1
            if recovered:
                unit.commit()
            return recovered
