from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass
class Result(Generic[T, E]):
    is_success: bool
    value: Optional[T] = None
    error: Optional[E] = None

    @staticmethod
    def success(value: T) -> "Result[T, E]":
        return Result(is_success=True, value=value)

    @staticmethod
    def failure(error: E) -> "Result[T, E]":
        return Result(is_success=False, error=error)
