from dataclasses import dataclass, field
from typing import TypeVar, cast

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class AppError:
    code: str
    message: str
    cause: Exception | None = field(default=None, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Result[T]:
    _value: T | None = None
    _error: AppError | None = None

    def __post_init__(self) -> None:
        if (self._value is None) == (self._error is None):
            raise ValueError("Result must contain exactly one of value or error")

    @classmethod
    def success(cls, value: T) -> "Result[T]":
        return cls(_value=value)

    @classmethod
    def failure(cls, error: AppError) -> "Result[T]":
        return cls(_error=error)

    @property
    def is_success(self) -> bool:
        return self._error is None

    @property
    def value(self) -> T:
        if self._error is not None:
            raise ValueError(f"Cannot read failed result: {self._error.code}")
        return cast("T", self._value)

    @property
    def error(self) -> AppError:
        if self._error is None:
            raise ValueError("Cannot read error from successful result")
        return self._error
