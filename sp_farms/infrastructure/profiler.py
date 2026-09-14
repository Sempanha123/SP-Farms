import statistics
import time
from collections import defaultdict
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from sp_farms.application.cache import ThumbnailCache
from sp_farms.domain.accounts import Account
from sp_farms.domain.jobs import Job, JobState


@dataclass(frozen=True)
class MetricStats:
    name: str
    count: int
    total_seconds: float
    mean_seconds: float
    min_seconds: float
    max_seconds: float
    p95_seconds: float
    ops_per_second: float


class PerformanceProfiler:
    """Latency profiler capturing operation execution times and percentile distributions."""

    def __init__(self) -> None:
        self._samples: dict[str, list[float]] = defaultdict(list)

    @contextmanager
    def measure(self, name: str, item_count: int = 1) -> Generator[None, None, None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - t0
            self._samples[name].append(elapsed)

    def record(self, name: str, elapsed_seconds: float) -> None:
        self._samples[name].append(elapsed_seconds)

    def stats(self, name: str) -> MetricStats | None:
        samples = self._samples.get(name)
        if not samples:
            return None

        total = sum(samples)
        count = len(samples)
        mean = statistics.mean(samples)
        min_val = min(samples)
        max_val = max(samples)

        sorted_samples = sorted(samples)
        p95_idx = int(len(sorted_samples) * 0.95)
        p95 = sorted_samples[min(p95_idx, len(sorted_samples) - 1)]
        ops_sec = count / total if total > 0 else 0.0

        return MetricStats(
            name=name,
            count=count,
            total_seconds=total,
            mean_seconds=mean,
            min_seconds=min_val,
            max_seconds=max_val,
            p95_seconds=p95,
            ops_per_second=ops_sec,
        )

    def all_stats(self) -> dict[str, MetricStats]:
        result = {}
        for name in self._samples:
            st = self.stats(name)
            if st is not None:
                result[name] = st
        return result

    def assert_latency(self, name: str, max_mean_seconds: float) -> None:
        st = self.stats(name)
        if st is None:
            raise AssertionError(f"No samples recorded for metric '{name}'")
        if st.mean_seconds > max_mean_seconds:
            mean_ms = st.mean_seconds * 1000
            max_ms = max_mean_seconds * 1000
            raise AssertionError(
                f"Metric '{name}' exceeded max mean threshold: {mean_ms:.2f}ms > {max_ms:.2f}ms"
            )


def profile_startup(factory: Callable[[], Any], iterations: int = 3) -> MetricStats:
    """Measure bootstrap/startup time over multiple iterations."""
    profiler = PerformanceProfiler()
    for _ in range(iterations):
        with profiler.measure("app_startup"):
            instance = factory()
            if hasattr(instance, "close"):
                instance.close()
    return profiler.stats("app_startup")  # type: ignore[return-value]


def profile_search_filter(accounts: Sequence[Account], queries: Sequence[str]) -> MetricStats:
    """Measure in-memory multi-field search and filter throughput."""
    profiler = PerformanceProfiler()
    for q in queries:
        with profiler.measure("search_filter"):
            pattern = q.lower()
            _ = [
                a
                for a in accounts
                if pattern in a.display_name.lower()
                or pattern in a.primary_email.lower()
                or pattern in a.platform_uid.lower()
            ]
    return profiler.stats("search_filter")  # type: ignore[return-value]


def profile_thumbnail_cache(
    cache: ThumbnailCache, keys: Sequence[str], read_iterations: int = 5
) -> MetricStats:
    """Measure thumbnail cache retrieval performance."""
    profiler = PerformanceProfiler()
    for _ in range(read_iterations):
        for k in keys:
            with profiler.measure("thumbnail_lookup"):
                _ = cache.get_thumbnail(k)
    return profiler.stats("thumbnail_lookup")  # type: ignore[return-value]


def profile_job_state_transitions(jobs: list[Job], target_state: JobState) -> MetricStats:
    """Measure batch state transitions and progress updates."""
    profiler = PerformanceProfiler()
    with profiler.measure("batch_job_updates", item_count=len(jobs)):
        for j in jobs:
            j.state = target_state
            j.progress = 100 if target_state == JobState.SUCCEEDED else j.progress
    return profiler.stats("batch_job_updates")  # type: ignore[return-value]
