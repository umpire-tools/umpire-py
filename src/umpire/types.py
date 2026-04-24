"""Core type definitions for Umpire."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class IsEmptyStrategy(Enum):
    """Strategy for determining if a field is empty."""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    PRESENT = "present"


@dataclass(frozen=True)
class FieldDef:
    """Definition of a field in the Umpire system."""

    required: bool = False
    default_value: Any = None
    is_empty: IsEmptyStrategy = IsEmptyStrategy.PRESENT


@dataclass(frozen=True)
class FieldAvailability:
    """Availability information for a field."""

    enabled: bool = True
    required: bool = False
    fair: bool = True
    satisfied: bool = False
    reason: str | None = None
    reasons: tuple[str, ...] = ()
    check_errors: tuple["CheckError", ...] = ()
    valid: bool | None = None
    error: str | None = None


@dataclass(frozen=True)
class CheckError:
    """Error information for a field check."""

    field: str
    reason: str


@dataclass(frozen=True)
class Foul:
    """Foul information for a field transition."""

    field: str
    reason: str
    suggested_value: Any = None


# Type aliases
Values = Mapping[str, Any]
Conditions = Mapping[str, Any]
Predicate = Callable[[Values, Conditions], bool]


class Rule(Protocol):
    """Protocol for rule implementations."""

    pass
