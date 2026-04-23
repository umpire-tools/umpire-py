"""Disables rule implementation."""

from collections.abc import Sequence
from dataclasses import dataclass

from ..types import Predicate


@dataclass(frozen=True)
class Disables:
    """Rule that disables fields based on a source field."""

    source: str
    targets: Sequence[str]
    when: Predicate | None = None
    reason: str | None = None
