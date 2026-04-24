"""Rule constructors for Umpire."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from ..types import CheckError, Predicate


def requires(
    field: str,
    dependency: str | None = None,
    when: Predicate | None = None,
    reason: str | None = None,
) -> "RequiresRule":
    """Create a rule that makes a field required based on conditions."""
    return RequiresRule(field, dependency, when, reason)


def enabled_when(field: str, when: Predicate, reason: str | None = None) -> "EnabledWhenRule":
    """Create a rule that enables a field based on conditions."""
    return EnabledWhenRule(field, when, reason)


def disables(
    source: str,
    targets: str | Sequence[str],
    when: Predicate | None = None,
    reason: str | None = None,
) -> "DisablesRule":
    """Create a rule that disables fields based on a source field."""
    if isinstance(targets, str):
        targets = [targets]
    return DisablesRule(source, list(targets), when, reason)


def one_of(
    group: str, branches: Mapping[str, Sequence[str]] | Sequence[str], reason: str | None = None
) -> "OneOfRule":
    """Create a rule that enforces only one field in a group can be enabled."""
    if isinstance(branches, Mapping):
        normalized = {name: list(fields) for name, fields in branches.items()}
    else:
        normalized = {field: [field] for field in branches}
    return OneOfRule(group, normalized, reason)


def any_of(rules: Sequence[object]) -> "AnyOfRule":
    """Create a rule that passes if any of the provided rules pass."""
    return AnyOfRule(list(rules))


def fair_when(field: str, when: Predicate, reason: str | None = None) -> "FairWhenRule":
    """Create a rule that makes a field fair (valid) based on conditions."""
    return FairWhenRule(field, when, reason)


def check(field: str, op: "CheckOp") -> "CheckRule":
    """Create a rule that applies a check operation to a field."""
    return CheckRule(field, op)


# Rule implementations
@dataclass(frozen=True)
class RequiresRule:
    """Rule that makes a field required based on conditions."""

    field: str
    dependency: str | None
    when: Predicate | None
    reason: str | None = None


@dataclass(frozen=True)
class EnabledWhenRule:
    """Rule that enables a field based on conditions."""

    field: str
    when: Predicate
    reason: str | None = None


@dataclass(frozen=True)
class DisablesRule:
    """Rule that disables fields based on a source field."""

    source: str
    targets: list[str]
    when: Predicate | None
    reason: str | None = None


@dataclass(frozen=True)
class OneOfRule:
    """Rule that enforces only one field in a group can be enabled."""

    group: str
    branches: dict[str, list[str]]
    reason: str | None = None


@dataclass(frozen=True)
class AnyOfRule:
    """Rule that passes if any of the provided rules pass."""

    rules: list[object]


@dataclass(frozen=True)
class FairWhenRule:
    """Rule that makes a field fair (valid) based on conditions."""

    field: str
    when: Predicate
    reason: str | None = None


@dataclass(frozen=True)
class CheckRule:
    """Rule that applies a check operation to a field."""

    field: str
    op: "CheckOp"


class CheckOp(Protocol):
    """Protocol for check operations."""

    def __call__(self, value: Any, field_name: str) -> CheckError | None:
        """Evaluate a field value and return a check error when invalid."""
