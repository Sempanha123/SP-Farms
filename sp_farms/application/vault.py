from collections.abc import Callable
from typing import Protocol


class Vault(Protocol):
    def store(self, reference: str, value: str) -> None: ...

    def retrieve(self, reference: str) -> str | None: ...

    def delete(self, reference: str) -> None: ...


class Clipboard(Protocol):
    def text(self) -> str: ...

    def set_text(self, value: str) -> None: ...


class ClearScheduler(Protocol):
    def schedule(self, delay_seconds: float, callback: Callable[[], None]) -> None: ...


def reveal_temporarily(
    secret: str,
    clipboard: Clipboard,
    scheduler: ClearScheduler,
    timeout_seconds: float = 30,
) -> None:
    clipboard.set_text(secret)

    def clear_if_unchanged() -> None:
        if clipboard.text() == secret:
            clipboard.set_text("")

    scheduler.schedule(timeout_seconds, clear_if_unchanged)
