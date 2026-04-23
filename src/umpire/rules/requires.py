"""Requires rule implementation."""

from dataclasses import dataclass

from ..types import Predicate


@dataclass(frozen=True)
class Requires:
    """Rule that makes a field required based on conditions."""

    field: str
    dependency: str | None
    when: Predicate | None
    reason: str | None = None
