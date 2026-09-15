from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sp_farms.application.job_service import JobService
from sp_farms.domain.jobs import JobState
from sp_farms.infrastructure.database import (
    Database,
    SqlAlchemyJobRepository,
    run_migrations,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


def make_service(database: Database, clock: FixedClock) -> JobService:
    return JobService(database.unit_of_work, SqlAlchemyJobRepository, clock)


def test_job_transitions_are_validated_and_audited(tmp_path: Path) -> None:
    database = Database(tmp_path / "data.db")
    clock = FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
    try:
        run_migrations(database, MIGRATIONS)
        service = make_service(database, clock)
        job, created = service.create_job("sync", "device", "device-1")

        assert created
        with pytest.raises(ValueError, match="pending to running"):
            service.transition_job(job.id, JobState.RUNNING, "Started")

        clock.value += timedelta(seconds=1)
        service.transition_job(job.id, JobState.QUEUED, "Queued")
        clock.value += timedelta(seconds=1)
        completed = service.transition_job(job.id, JobState.RUNNING, "Started")

        with database.unit_of_work() as unit:
            events = SqlAlchemyJobRepository(unit).list_events(job.id)

        assert completed.state is JobState.RUNNING
        assert [event.to_state for event in events] == [
            JobState.PENDING,
            JobState.QUEUED,
            JobState.RUNNING,
        ]
        assert events[-1].from_state is JobState.QUEUED
    finally:
        database.close()


def test_idempotency_key_returns_existing_job(tmp_path: Path) -> None:
    database = Database(tmp_path / "data.db")
    clock = FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
    try:
        run_migrations(database, MIGRATIONS)
        service = make_service(database, clock)

        first, first_created = service.create_job(
            "sync", "device", "device-1", idempotency_key="sync:device-1"
        )
        second, second_created = service.create_job(
            "sync", "device", "device-1", idempotency_key="sync:device-1"
        )

        assert first_created
        assert not second_created
        assert second.id == first.id
        with database.unit_of_work() as unit:
            assert len(SqlAlchemyJobRepository(unit).list_events(first.id)) == 1
    finally:
        database.close()


def test_job_persists_across_database_reopen(tmp_path: Path) -> None:
    path = tmp_path / "data.db"
    clock = FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
    database = Database(path)
    run_migrations(database, MIGRATIONS)
    job, _ = make_service(database, clock).create_job("sync", "device", "device-1")
    database.close()

    reopened = Database(path)
    try:
        with reopened.unit_of_work() as unit:
            persisted = SqlAlchemyJobRepository(unit).get(job.id)
        assert persisted == job
    finally:
        reopened.close()


def test_running_job_is_retried_after_restart(tmp_path: Path) -> None:
    path = tmp_path / "data.db"
    clock = FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
    database = Database(path)
    run_migrations(database, MIGRATIONS)
    service = make_service(database, clock)
    job, _ = service.create_job("sync", "device", "device-1")
    service.transition_job(job.id, JobState.QUEUED, "Queued")
    service.transition_job(job.id, JobState.RUNNING, "Started")
    database.close()

    reopened = Database(path)
    try:
        clock.value += timedelta(minutes=1)
        restarted_service = make_service(reopened, clock)
        assert restarted_service.recover_interrupted_jobs() == 1

        with reopened.unit_of_work() as unit:
            repository = SqlAlchemyJobRepository(unit)
            recovered = repository.get(job.id)
            events = repository.list_events(job.id)

        assert recovered is not None
        assert recovered.state is JobState.RETRYING
        assert recovered.error_code == "app_restart_recovery"
        assert events[-1].to_state is JobState.RETRYING
    finally:
        reopened.close()
