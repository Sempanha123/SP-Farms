import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class CacheStats:
    hits: int
    misses: int
    size: int
    capacity: int

    @property
    def hit_ratio(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class LRUCache[K, V]:
    """Thread-safe bounded Least Recently Used (LRU) cache with TTL support."""

    def __init__(self, capacity: int = 1024, ttl_seconds: float | None = None) -> None:
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        self._capacity = capacity
        self._ttl = timedelta(seconds=ttl_seconds) if ttl_seconds is not None else None
        self._entries: OrderedDict[K, tuple[V, datetime | None]] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: K, default: V | None = None) -> V | None:
        with self._lock:
            if key not in self._entries:
                self._misses += 1
                return default

            value, expires_at = self._entries[key]
            if expires_at is not None and datetime.now(UTC) > expires_at:
                del self._entries[key]
                self._misses += 1
                return default

            self._entries.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: K, value: V) -> None:
        with self._lock:
            expires_at = datetime.now(UTC) + self._ttl if self._ttl is not None else None
            if key in self._entries:
                self._entries.move_to_end(key)
                self._entries[key] = (value, expires_at)
                return

            if len(self._entries) >= self._capacity:
                self._entries.popitem(last=False)

            self._entries[key] = (value, expires_at)

    def invalidate(self, key: K) -> bool:
        with self._lock:
            if key in self._entries:
                del self._entries[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                size=len(self._entries),
                capacity=self._capacity,
            )

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


class ThumbnailCache:
    """Specialized thumbnail cache for avatar and asset thumbnail previews."""

    def __init__(self, max_items: int = 500, default_ttl_seconds: float = 3600.0) -> None:
        self._cache: LRUCache[str, bytes] = LRUCache(
            capacity=max_items, ttl_seconds=default_ttl_seconds
        )

    def get_thumbnail(self, path_or_key: str) -> bytes | None:
        return self._cache.get(path_or_key)

    def put_thumbnail(self, path_or_key: str, data: bytes) -> None:
        self._cache.set(path_or_key, data)

    def invalidate(self, path_or_key: str) -> bool:
        return self._cache.invalidate(path_or_key)

    def clear(self) -> None:
        self._cache.clear()

    @property
    def stats(self) -> CacheStats:
        return self._cache.stats()


class Debouncer:
    """Thread-safe delay-based debouncer to throttle rapid user inputs or events."""

    def __init__(self, delay_seconds: float = 0.15) -> None:
        self._delay_seconds = delay_seconds
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def debounce(self, callback: Callable[[], None]) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._delay_seconds, callback)
            self._timer.daemon = True
            self._timer.start()

    def cancel(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
