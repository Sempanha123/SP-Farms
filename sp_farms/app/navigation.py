from collections.abc import Callable, Iterable
from dataclasses import dataclass

from PySide6.QtGui import QKeySequence


@dataclass(frozen=True, slots=True)
class Command:
    id: str
    title: str
    shortcut: str
    handler: Callable[[], None]
    keywords: tuple[str, ...] = ()

    def matches(self, query: str) -> bool:
        terms = query.casefold().split()
        haystack = " ".join((self.title, self.id, *self.keywords)).casefold()
        return all(term in haystack for term in terms)


class NavigationService:
    def __init__(self, navigate: Callable[[str], None]) -> None:
        self._navigate = navigate
        self._commands: dict[str, Command] = {}

    def register(self, command: Command) -> None:
        if command.id in self._commands:
            raise ValueError(f"Duplicate command id: {command.id}")
        normalized = QKeySequence(command.shortcut).toString()
        for existing in self._commands.values():
            if normalized and QKeySequence(existing.shortcut).toString() == normalized:
                raise ValueError(f"Shortcut collision: {command.shortcut}")
        self._commands[command.id] = command

    def register_routes(self, routes: Iterable[tuple[str, str]]) -> None:
        for index, (route, shortcut) in enumerate(routes):

            def navigate_to(name: str = route) -> None:
                self._navigate(name)

            self.register(
                Command(
                    id=f"navigate.{route.casefold()}",
                    title=f"Open {route}",
                    shortcut=shortcut,
                    handler=navigate_to,
                    keywords=("navigate", "module", str(index + 1)),
                )
            )

    def execute(self, command_id: str) -> None:
        self._commands[command_id].handler()

    def search(self, query: str) -> tuple[Command, ...]:
        return tuple(command for command in self._commands.values() if command.matches(query))

    @property
    def commands(self) -> tuple[Command, ...]:
        return tuple(self._commands.values())
