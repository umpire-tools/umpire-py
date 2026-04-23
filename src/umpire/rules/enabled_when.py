"""EnabledWhen rule implementation."""

from dataclasses import dataclass

from ..types import Predicate


@dataclass(frozen=True)
class EnabledWhen:
    """Rule that enables a field based on conditions."""

    field: str
    when: Predicate
    reason: str | None = None
