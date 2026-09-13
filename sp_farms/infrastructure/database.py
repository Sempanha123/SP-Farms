from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from shutil import copy2
from types import TracebackType
from typing import Self
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import (
    DateTime,
    Engine,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from sp_farms.application.jobs import JobRepository
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.jobs import Job, JobEvent, JobState
from sp_farms.domain.secrets import SecretReference, SecretType


class Base(DeclarativeBase):
    pass


class EntityMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SystemMetadata(EntityMixin, Base):
    __tablename__ = "system_metadata"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)


class SecretMetadata(EntityMixin, Base):
    __tablename__ = "secret_metadata"

    secret_type: Mapped[str] = mapped_column(String(50), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    vault_ref: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)

    @classmethod
    def from_reference(cls, reference: SecretReference) -> "SecretMetadata":
        return cls(
            id=reference.id,
            secret_type=reference.secret_type.value,
            owner_id=reference.owner_id,
            vault_ref=reference.vault_ref,
            created_at=reference.created_at,
            updated_at=reference.updated_at,
        )

    def to_reference(self) -> SecretReference:
        return SecretReference(
            id=self.id,
            secret_type=SecretType(self.secret_type),
            owner_id=self.owner_id,
            vault_ref=self.vault_ref,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class JobModel(EntityMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_target", "target_type", "target_id"),)

    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), unique=True)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @classmethod
    def from_job(cls, job: Job) -> "JobModel":
        return cls(
            id=job.id,
            job_type=job.job_type,
            target_type=job.target_type,
            target_id=job.target_id,
            state=job.state.value,
            progress=job.progress,
            attempt_count=job.attempt_count,
            max_attempts=job.max_attempts,
            idempotency_key=job.idempotency_key,
            error_code=job.error_code,
            error_message=job.error_message,
            next_retry_at=job.next_retry_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    def update_from_job(self, job: Job) -> None:
        self.job_type = job.job_type
        self.target_type = job.target_type
        self.target_id = job.target_id
        self.state = job.state.value
        self.progress = job.progress
        self.attempt_count = job.attempt_count
        self.max_attempts = job.max_attempts
        self.idempotency_key = job.idempotency_key
        self.error_code = job.error_code
        self.error_message = job.error_message
        self.next_retry_at = job.next_retry_at
        self.updated_at = job.updated_at

    def to_job(self) -> Job:
        return Job(
            id=self.id,
            job_type=self.job_type,
            target_type=self.target_type,
            target_id=self.target_id,
            state=JobState(self.state),
            progress=self.progress,
            attempt_count=self.attempt_count,
            max_attempts=self.max_attempts,
            idempotency_key=self.idempotency_key,
            error_code=self.error_code,
            error_message=self.error_message,
            next_retry_at=_optional_as_utc(self.next_retry_at),
            created_at=_as_utc(self.created_at),
            updated_at=_as_utc(self.updated_at),
        )


class JobEventModel(EntityMixin, Base):
    __tablename__ = "job_events"

    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    from_state: Mapped[str | None] = mapped_column(String(30))
    to_state: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    @classmethod
    def from_event(cls, job_event: JobEvent) -> "JobEventModel":
        return cls(
            id=job_event.id,
            job_id=job_event.job_id,
            from_state=job_event.from_state.value if job_event.from_state else None,
            to_state=job_event.to_state.value,
            message=job_event.message,
            created_at=job_event.created_at,
            updated_at=job_event.created_at,
        )

    def to_event(self) -> JobEvent:
        return JobEvent(
            id=self.id,
            job_id=self.job_id,
            from_state=JobState(self.from_state) if self.from_state else None,
            to_state=JobState(self.to_state),
            message=self.message,
            created_at=_as_utc(self.created_at),
        )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _optional_as_utc(value: datetime | None) -> datetime | None:
    return _as_utc(value) if value is not None else None


class SqlAlchemyJobRepository(JobRepository):
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        if not isinstance(unit_of_work, SqlAlchemyUnitOfWork):
            raise TypeError("SqlAlchemyJobRepository requires SqlAlchemyUnitOfWork")
        self._unit_of_work = unit_of_work

    def add(self, job: Job) -> None:
        session = self._session
        model = session.get(JobModel, job.id)
        if model is None:
            session.add(JobModel.from_job(job))
        else:
            model.update_from_job(job)

    def get(self, job_id: str) -> Job | None:
        model = self._session.get(JobModel, job_id)
        return model.to_job() if model else None

    def find_by_idempotency_key(self, key: str) -> Job | None:
        model = self._session.query(JobModel).filter_by(idempotency_key=key).one_or_none()
        return model.to_job() if model else None

    def list_active(self) -> Sequence[Job]:
        terminal = tuple(state.value for state in JobState if state.is_terminal)
        models = self._session.query(JobModel).filter(JobModel.state.not_in(terminal)).all()
        return tuple(model.to_job() for model in models)

    def add_event(self, job_event: JobEvent) -> None:
        self._session.flush()
        self._session.add(JobEventModel.from_event(job_event))

    def list_events(self, job_id: str) -> Sequence[JobEvent]:
        models = (
            self._session.query(JobEventModel)
            .filter_by(job_id=job_id)
            .order_by(JobEventModel.created_at, JobEventModel.id)
            .all()
        )
        return tuple(model.to_event() for model in models)

    @property
    def _session(self) -> Session:
        return self._unit_of_work._active_session()


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            URL.create("sqlite", database=str(path)),
            connect_args={"timeout": 30},
        )
        event.listen(self.engine, "connect", _configure_sqlite)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    def unit_of_work(self) -> "SqlAlchemyUnitOfWork":
        return SqlAlchemyUnitOfWork(self.session_factory)

    def close(self) -> None:
        self.engine.dispose()


class SqlAlchemyUnitOfWork(AbstractContextManager["SqlAlchemyUnitOfWork"]):
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self.session: Session | None = None

    def __enter__(self) -> Self:
        self.session = self._session_factory()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.session is None:
            return
        if exception_type is not None:
            self.rollback()
        self.session.close()
        self.session = None

    def commit(self) -> None:
        self._active_session().commit()

    def rollback(self) -> None:
        self._active_session().rollback()

    def _active_session(self) -> Session:
        if self.session is None:
            raise RuntimeError("Unit of work is not active")
        return self.session


def run_migrations(database: Database, migrations_path: Path) -> Path | None:
    config = Config(str(migrations_path.parent / "alembic.ini"))
    config.set_main_option("script_location", str(migrations_path))
    script = ScriptDirectory.from_config(config)
    current = _current_revision(database.engine)
    target = script.get_current_head()
    backup = None

    if current is not None and current != target:
        backup = _backup_database(database.path)

    with database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    return backup


def _current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _backup_database(path: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.name}.{stamp}.bak")
    copy2(path, backup)
    return backup


def _configure_sqlite(dbapi_connection: object, connection_record: object) -> None:
    del connection_record
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
    finally:
        cursor.close()
