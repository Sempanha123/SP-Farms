from collections.abc import Callable
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
from sqlalchemy import DateTime, Engine, String, create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

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
