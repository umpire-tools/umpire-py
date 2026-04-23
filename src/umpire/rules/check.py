"""Check rule implementation."""

from dataclasses import dataclass

from ..checks import CheckOp


@dataclass(frozen=True)
class Check:
    """Rule that applies a check operation to a field."""

    field: str
    op: CheckOp
