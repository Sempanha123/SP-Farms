import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime


class BatchQueue[T]:
    """Thread-safe batching queue that flushes via size or interval triggers."""

    def __init__(
        self,
        flush_handler: Callable[[Sequence[T]], None],
        max_batch_size: int = 100,
        max_interval_seconds: float = 0.5,
    ) -> None:
        self._flush_handler = flush_handler
        self._max_batch_size = max_batch_size
        self._max_interval_seconds = max_interval_seconds
        self._items: list[T] = []
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._last_flush_at = datetime.now(UTC)

    def enqueue(self, item: T) -> None:
        with self._lock:
            self._items.append(item)
            if len(self._items) >= self._max_batch_size:
                self._trigger_flush_unlocked()
            elif self._timer is None:
                self._timer = threading.Timer(self._max_interval_seconds, self.flush)
                self._timer.daemon = True
                self._timer.start()

    def enqueue_many(self, items: Sequence[T]) -> None:
        with self._lock:
            self._items.extend(items)
            if len(self._items) >= self._max_batch_size:
                self._trigger_flush_unlocked()
            elif self._timer is None:
                self._timer = threading.Timer(self._max_interval_seconds, self.flush)
                self._timer.daemon = True
                self._timer.start()

    def flush(self) -> int:
        with self._lock:
            return self._trigger_flush_unlocked()

    def _trigger_flush_unlocked(self) -> int:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

        if not self._items:
            return 0

        batch = list(self._items)
        self._items.clear()
        self._last_flush_at = datetime.now(UTC)

        try:
            self._flush_handler(batch)
        except Exception:
            # Let exceptions propagate or handle gracefully
            raise

        return len(batch)

    def pending_count(self) -> int:
        with self._lock:
            return len(self._items)
