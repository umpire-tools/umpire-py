"""FairWhen rule implementation."""

from dataclasses import dataclass

from ..types import Predicate


@dataclass(frozen=True)
class FairWhen:
    """Rule that makes a field fair (valid) based on conditions."""

    field: str
    when: Predicate
    reason: str | None = None
