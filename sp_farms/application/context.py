from collections.abc import Callable
from dataclasses import dataclass, field

from sp_farms.application.ports import Clock

ShutdownHook = Callable[[], None]


@dataclass(slots=True)
class ApplicationContext:
    clock: Clock
    _shutdown_hooks: list[ShutdownHook] = field(default_factory=list)
    _closed: bool = False

    def add_shutdown_hook(self, hook: ShutdownHook) -> None:
        if self._closed:
            raise RuntimeError("Application context is closed")
        self._shutdown_hooks.append(hook)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for hook in reversed(self._shutdown_hooks):
            hook()
