import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sp_farms.application.job_service import JobService
from sp_farms.application.worker import (
    ConcurrencyLimits,
    FakeStressJobHandler,
    JobExecutionContext,
    WorkerSupervisor,
)
from sp_farms.domain.jobs import JobState
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyJobRepository,
    run_migrations,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


@pytest.fixture
def test_setup(tmp_path: Path) -> tuple[Database, JobService, MutableClock]:
    database = Database(tmp_path / "data.db")
    run_migrations(database, MIGRATIONS)
    clock = MutableClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    service = JobService(database.unit_of_work, SqlAlchemyJobRepository, clock)
    return database, service, clock


def test_fake_stress_job_executes_and_records_progress(
    test_setup: tuple[Database, JobService, MutableClock],
) -> None:
    database, service, clock = test_setup
    try:
        supervisor = WorkerSupervisor(service, clock)
        supervisor.register_handler("stress", FakeStressJobHandler(steps=4))

        job, _ = service.create_job("stress", "device", "dev-1")
        service.transition_job(job.id, JobState.QUEUED, "Queued")

        assert supervisor.tick() == 1
        time.sleep(0.1)

        completed = service.get_job(job.id)
        assert completed is not None
        assert completed.state is JobState.SUCCEEDED
        assert completed.progress == 100

        events = service.list_events(job.id)
        assert [e.to_state for e in events] == [
            JobState.PENDING,
            JobState.QUEUED,
            JobState.RUNNING,
            JobState.SUCCEEDED,
        ]
        supervisor.stop()
    finally:
        database.close()


def test_cancellation_of_running_job(
    test_setup: tuple[Database, JobService, MutableClock],
) -> None:
    database, service, clock = test_setup
    try:
        supervisor = WorkerSupervisor(service, clock)
        cancelled_detected = False

        def slow_handler(ctx: JobExecutionContext) -> None:
            nonlocal cancelled_detected
            for i in range(10):
                ctx.check_cancelled()
                ctx.record_progress((i + 1) * 10)
                time.sleep(0.05)

        supervisor.register_handler("slow", slow_handler)

        job, _ = service.create_job("slow", "device", "dev-1")
        service.transition_job(job.id, JobState.QUEUED, "Queued")

        assert supervisor.tick() == 1
        time.sleep(0.08)

        cancelled = supervisor.cancel_job(job.id, "Operator stopped job")
        assert cancelled
        time.sleep(0.1)

        final_job = service.get_job(job.id)
        assert final_job is not None
        assert final_job.state is JobState.CANCELLED
        supervisor.stop()
    finally:
        database.close()


def test_retry_and_backoff_until_failure(
    test_setup: tuple[Database, JobService, MutableClock],
) -> None:
    database, service, clock = test_setup
    try:
        supervisor = WorkerSupervisor(service, clock)

        def failing_handler(ctx: JobExecutionContext) -> None:
            raise RuntimeError("Network timeout")

        supervisor.register_handler("failing", failing_handler)

        job, _ = service.create_job("failing", "device", "dev-1", max_attempts=2)
        service.transition_job(job.id, JobState.QUEUED, "Queued")

        # First attempt -> transitions to RETRYING
        assert supervisor.tick() == 1
        time.sleep(0.1)

        job1 = service.get_job(job.id)
        assert job1 is not None
        assert job1.state is JobState.RETRYING
        assert job1.attempt_count == 1
        assert job1.next_retry_at is not None
        assert job1.error_code == "execution_failure"

        # Not runnable yet before retry time
        assert supervisor.tick() == 0

        # Advance clock past backoff delay
        clock.advance(5.0)

        # Second attempt -> reaches max_attempts (2) -> transitions to FAILED
        assert supervisor.tick() == 1
        time.sleep(0.1)

        job2 = service.get_job(job.id)
        assert job2 is not None
        assert job2.state is JobState.FAILED
        assert job2.attempt_count == 2
        assert job2.error_code == "max_attempts_exceeded"

        supervisor.stop()
    finally:
        database.close()


def test_concurrency_limits_enforcement(
    test_setup: tuple[Database, JobService, MutableClock],
) -> None:
    database, service, clock = test_setup
    try:
        limits = ConcurrencyLimits(
            max_total_workers=3,
            max_per_provider=2,
            max_per_target=1,
        )
        supervisor = WorkerSupervisor(service, clock, limits=limits)

        def blocking_handler(ctx: JobExecutionContext) -> None:
            while not ctx.is_cancelled:
                time.sleep(0.02)

        supervisor.register_handler("block", blocking_handler)

        # Job 1: provider A, target A1
        j1, _ = service.create_job("block", "provider_a", "dev-1")
        service.transition_job(j1.id, JobState.QUEUED, "Queued")

        # Job 2: provider A, target A1 (duplicate destination -> blocked by max_per_target=1)
        j2, _ = service.create_job("block", "provider_a", "dev-1")
        service.transition_job(j2.id, JobState.QUEUED, "Queued")

        # Job 3: provider A, target A2 (allowed for provider A, fills provider cap 2)
        j3, _ = service.create_job("block", "provider_a", "dev-2")
        service.transition_job(j3.id, JobState.QUEUED, "Queued")

        # Job 4: provider A, target A3 (blocked by max_per_provider=2)
        j4, _ = service.create_job("block", "provider_a", "dev-3")
        service.transition_job(j4.id, JobState.QUEUED, "Queued")

        # Job 5: provider B, target B1 (allowed, fills total cap 3)
        j5, _ = service.create_job("block", "provider_b", "dev-4")
        service.transition_job(j5.id, JobState.QUEUED, "Queued")

        # Job 6: provider B, target B2 (blocked by max_total_workers=3)
        j6, _ = service.create_job("block", "provider_b", "dev-5")
        service.transition_job(j6.id, JobState.QUEUED, "Queued")

        dispatched = supervisor.tick()
        assert dispatched == 3  # j1, j3, j5 dispatched

        # Second tick dispatches 0 because all limit slots full
        assert supervisor.tick() == 0

        # Heartbeats recorded for active workers
        heartbeats = supervisor.list_heartbeats()
        assert len(heartbeats) >= 3

        supervisor.stop()
    finally:
        database.close()


def test_exception_containment_does_not_crash_supervisor(
    test_setup: tuple[Database, JobService, MutableClock],
) -> None:
    database, service, clock = test_setup
    try:
        supervisor = WorkerSupervisor(service, clock)

        def buggy_handler(ctx: JobExecutionContext) -> None:
            raise TypeError("Severe unexpected type error inside job handler")

        supervisor.register_handler("buggy", buggy_handler)

        job, _ = service.create_job("buggy", "device", "dev-1", max_attempts=1)
        service.transition_job(job.id, JobState.QUEUED, "Queued")

        assert supervisor.tick() == 1
        time.sleep(0.1)

        result = service.get_job(job.id)
        assert result is not None
        assert result.state is JobState.FAILED
        assert "Severe unexpected type error" in (result.error_message or "")

        # Supervisor can still process subsequent jobs
        supervisor.register_handler("ok", FakeStressJobHandler(steps=1))
        job_ok, _ = service.create_job("ok", "device", "dev-2")
        service.transition_job(job_ok.id, JobState.QUEUED, "Queued")

        assert supervisor.tick() == 1
        time.sleep(0.05)
        assert service.get_job(job_ok.id).state is JobState.SUCCEEDED  # type: ignore[union-attr]

        supervisor.stop()
    finally:
        database.close()


def test_graceful_shutdown_stops_poller_and_cancels_work(
    test_setup: tuple[Database, JobService, MutableClock],
) -> None:
    database, service, clock = test_setup
    try:
        supervisor = WorkerSupervisor(service, clock)
        handler = FakeStressJobHandler(steps=50, step_delay_seconds=0.05)
        supervisor.register_handler("stress", handler)

        job, _ = service.create_job("stress", "device", "dev-1")
        service.transition_job(job.id, JobState.QUEUED, "Queued")

        supervisor.start(poll_interval_seconds=0.05)
        time.sleep(0.1)

        # Stop supervisor gracefully
        supervisor.stop(timeout_seconds=2.0)

        final_job = service.get_job(job.id)
        assert final_job is not None
        assert final_job.state in (JobState.CANCELLED, JobState.SUCCEEDED)
    finally:
        database.close()
