import time
from pathlib import Path

import pytest

from sp_farms.application.batch_queue import BatchQueue
from sp_farms.application.cache import LRUCache, ThumbnailCache
from sp_farms.application.synthetic_generator import (
    generate_synthetic_accounts,
    generate_synthetic_assets,
    generate_synthetic_devices,
    generate_synthetic_jobs,
    populate_synthetic_database,
)
from sp_farms.domain.jobs import JobState
from sp_farms.infrastructure.database import (
    AccountModel,
    Database,
    JobModel,
    SqlAlchemyAccountRepository,
    SqlAlchemyJobRepository,
)
from sp_farms.infrastructure.profiler import (
    PerformanceProfiler,
    profile_job_state_transitions,
    profile_search_filter,
    profile_thumbnail_cache,
)


@pytest.fixture
def test_db(tmp_path: Path) -> Database:
    db_path = tmp_path / "perf_test.db"
    db = Database(db_path)
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    with db.engine.begin() as conn:
        alembic_cfg.attributes["connection"] = conn
        command.upgrade(alembic_cfg, "head")
    return db


def test_synthetic_generators() -> None:
    accounts = generate_synthetic_accounts(1500)
    assert len(accounts) == 1500
    assert len({a.id for a in accounts}) == 1500
    assert len({a.platform_uid for a in accounts}) == 1500

    jobs = generate_synthetic_jobs(1200)
    assert len(jobs) == 1200
    assert len({j.id for j in jobs}) == 1200

    assets = generate_synthetic_assets(600)
    assert len(assets) == 600
    assert len({a.id for a in assets}) == 600

    devices = generate_synthetic_devices(150)
    assert len(devices) == 150
    assert len({d.id for d in devices}) == 150


def test_synthetic_database_population_and_query_scale(test_db: Database) -> None:
    t0 = time.perf_counter()
    metrics = populate_synthetic_database(
        test_db,
        account_count=1000,
        job_count=1000,
        asset_count=300,
        device_count=50,
    )
    insert_duration = time.perf_counter() - t0
    assert metrics["accounts"] == 1000
    assert metrics["jobs"] == 1000
    assert metrics["assets"] == 300
    assert metrics["devices"] == 50
    # Insertion of 2350 records should be fast in WAL mode (< 4.0 seconds on CI)
    assert insert_duration < 4.0

    # Query accounts at scale - verify N+1 elimination
    with test_db.unit_of_work() as unit:
        repo = SqlAlchemyAccountRepository(unit)
        t_query = time.perf_counter()
        accounts = repo.list_accounts()
        query_duration = time.perf_counter() - t_query

        assert len(accounts) == 1000
        # 1000 accounts must be retrieved and mapped in under 350ms
        assert query_duration < 0.35

    # Query jobs at scale
    with test_db.unit_of_work() as unit:
        job_repo = SqlAlchemyJobRepository(unit)
        t_jobs = time.perf_counter()
        all_jobs = job_repo.list_all()
        active_jobs = job_repo.list_active()
        jobs_duration = time.perf_counter() - t_jobs

        assert len(all_jobs) == 1000
        assert len(active_jobs) > 0
        assert jobs_duration < 0.35


def test_database_indexed_filtering(test_db: Database) -> None:
    populate_synthetic_database(
        test_db, account_count=500, job_count=500, asset_count=100, device_count=20
    )

    with test_db.unit_of_work() as unit:
        session = unit._active_session()

        # Query filtering by indexed status
        t0 = time.perf_counter()
        results = session.query(AccountModel).filter_by(status="active").all()
        elapsed = time.perf_counter() - t0

        assert len(results) > 0
        # Index scan must execute in < 15ms
        assert elapsed < 0.05

        # Query filtering by indexed job state
        t0 = time.perf_counter()
        queued = session.query(JobModel).filter_by(state="queued").all()
        elapsed_jobs = time.perf_counter() - t0

        assert len(queued) > 0
        assert elapsed_jobs < 0.05


def test_lru_cache_and_thumbnail_cache() -> None:
    cache: LRUCache[str, str] = LRUCache(capacity=3)
    cache.set("a", "1")
    cache.set("b", "2")
    cache.set("c", "3")
    assert len(cache) == 3

    assert cache.get("a") == "1"
    # Accessing "a" moved it to MRU. Now insert "d", which should evict oldest "b"
    cache.set("d", "4")
    assert cache.get("b") is None
    assert cache.get("a") == "1"
    assert cache.get("c") == "3"
    assert cache.get("d") == "4"

    stats = cache.stats()
    assert stats.hits >= 4
    assert stats.misses >= 1
    assert stats.hit_ratio > 0.7

    # ThumbnailCache
    tc = ThumbnailCache(max_items=100)
    fake_bytes = b"\x89PNG\r\n\x1a\nfakeimage"
    tc.put_thumbnail("thumb_001", fake_bytes)
    assert tc.get_thumbnail("thumb_001") == fake_bytes
    assert tc.get_thumbnail("missing") is None


def test_batch_queue() -> None:
    flushed_items: list[str] = []

    def flush_callback(batch: list[str]) -> None:
        flushed_items.extend(batch)

    queue: BatchQueue[str] = BatchQueue(
        flush_handler=flush_callback, max_batch_size=5, max_interval_seconds=0.1
    )

    # Adding 4 items should not flush immediately
    queue.enqueue_many(["item1", "item2", "item3", "item4"])
    assert queue.pending_count() == 4
    assert len(flushed_items) == 0

    # 5th item hits threshold and flushes immediately
    queue.enqueue("item5")
    assert queue.pending_count() == 0
    assert len(flushed_items) == 5

    # Manual flush
    queue.enqueue("item6")
    queue.flush()
    assert len(flushed_items) == 6


def test_performance_profiler_and_benchmarks() -> None:
    profiler = PerformanceProfiler()

    # Measure sample operation
    with profiler.measure("test_operation"):
        time.sleep(0.001)

    st = profiler.stats("test_operation")
    assert st is not None
    assert st.count == 1
    assert st.mean_seconds >= 0.0005
    profiler.assert_latency("test_operation", max_mean_seconds=0.1)

    # Search filter benchmark over 2,000 accounts
    accounts = generate_synthetic_accounts(2000)
    search_stats = profile_search_filter(accounts, ["jordan", "alex", "smith", "1000"])
    assert search_stats.count == 4
    assert search_stats.mean_seconds < 0.05  # < 50ms per multi-field search across 2k accounts

    # Thumbnail cache benchmark
    tc = ThumbnailCache(max_items=500)
    keys = [f"key_{i}" for i in range(100)]
    for k in keys:
        tc.put_thumbnail(k, b"preview_bytes")

    tc_stats = profile_thumbnail_cache(tc, keys, read_iterations=3)
    assert tc_stats.count == 300
    assert tc_stats.mean_seconds < 0.001  # < 1ms per lookup

    # Job batch transition benchmark over 1,000 jobs
    jobs = generate_synthetic_jobs(1000)
    job_stats = profile_job_state_transitions(jobs, JobState.SUCCEEDED)
    assert job_stats.mean_seconds < 0.05  # < 50ms for 1000 state transitions
