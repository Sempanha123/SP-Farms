from collections.abc import Hashable
from datetime import datetime
from typing import Protocol, TypeVar

EntityT = TypeVar("EntityT")
IdentifierT = TypeVar("IdentifierT", bound=Hashable, contravariant=True)
RequestT = TypeVar("RequestT", contravariant=True)
ResponseT = TypeVar("ResponseT", covariant=True)


class Repository(Protocol[EntityT, IdentifierT]):
    def get(self, identifier: IdentifierT) -> EntityT | None: ...

    def add(self, entity: EntityT) -> None: ...


class Service(Protocol[RequestT, ResponseT]):
    def execute(self, request: RequestT) -> ResponseT: ...


class Provider(Protocol):
    @property
    def name(self) -> str: ...

    def is_available(self) -> bool: ...


class Clock(Protocol):
    def now(self) -> datetime: ...
