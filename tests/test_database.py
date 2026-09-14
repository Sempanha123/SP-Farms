from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from sp_farms.infrastructure.database import Database, SystemMetadata, run_migrations

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


def test_clean_database_migrates_and_enables_wal(tmp_path: Path) -> None:
    database = Database(tmp_path / "data.db")
    try:
        assert run_migrations(database, MIGRATIONS) is None
        with database.engine.connect() as connection:
            assert connection.execute(text("PRAGMA journal_mode")).scalar_one() == "wal"
            tables = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).scalars()
            assert {"alembic_version", "system_metadata"} <= set(tables)
    finally:
        database.close()


def test_migration_rerun_is_idempotent(tmp_path: Path) -> None:
    database = Database(tmp_path / "data.db")
    try:
        run_migrations(database, MIGRATIONS)
        assert run_migrations(database, MIGRATIONS) is None
    finally:
        database.close()


def test_unit_of_work_rolls_back_failed_transaction(tmp_path: Path) -> None:
    database = Database(tmp_path / "data.db")
    try:
        run_migrations(database, MIGRATIONS)
        with pytest.raises(RuntimeError), database.unit_of_work() as unit:
            assert unit.session is not None
            unit.session.add(SystemMetadata(key="phase", value="four"))
            unit.session.flush()
            raise RuntimeError("stop")

        with database.unit_of_work() as unit:
            assert unit.session is not None
            count = unit.session.scalar(select(func.count()).select_from(SystemMetadata))
            assert count == 0
    finally:
        database.close()


def test_unit_of_work_commits(tmp_path: Path) -> None:
    database = Database(tmp_path / "data.db")
    try:
        run_migrations(database, MIGRATIONS)
        with database.unit_of_work() as unit:
            assert unit.session is not None
            entity = SystemMetadata(key="phase", value="four")
            unit.session.add(entity)
            unit.commit()
            assert len(entity.id) == 36
            assert entity.created_at is not None
    finally:
        database.close()
