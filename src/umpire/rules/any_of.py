"""AnyOf rule implementation."""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class AnyOf:
    """Rule that passes if any of the provided rules pass."""

    rules: Sequence[object]
