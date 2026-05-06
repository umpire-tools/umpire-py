"""Core type definitions for Umpire."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
    """Availability information for a field.

    Fields are populated by programmatic rule evaluation (engine.py).
    The `valid` and `error` fields are schema-validator-only and are not
    populated by programmatic rule evaluation — they exist for JSON schema
    conformance.
    """

    enabled: bool = True
    required: bool = False
    fair: bool = True
    satisfied: bool = False
    reason: str | None = None
    reasons: tuple[str, ...] = ()
    check_errors: tuple["CheckError", ...] = ()
    # schema-validator only; not populated by programmatic rule evaluation
    valid: bool | None = None
    # schema-validator only; not populated by programmatic rule evaluation
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


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    kind: str


@dataclass(frozen=True)
class UmpireGraph:
    nodes: tuple[str, ...]
    edges: tuple[GraphEdge, ...]


@dataclass(frozen=True)
class RuleEntry:
    index: int
    id: str
    kind: str
    targets: tuple[str, ...]
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChallengeReason:
    rule: str
    passed: bool
    reason: str | None = None
    rule_index: int | None = None
    rule_id: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChallengeTrace:
    field: str
    enabled: bool
    fair: bool
    direct_reasons: tuple[ChallengeReason, ...]
    transitive_deps: tuple[Mapping[str, Any], ...] = ()
    one_of_resolution: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ScorecardField:
    field: str
    value: Any
    present: bool
    satisfied: bool
    enabled: bool
    fair: bool
    required: bool
    reason: str | None
    reasons: tuple[str, ...]
    changed: bool
    cascaded: bool
    foul: Foul | None
    incoming: tuple[GraphEdge, ...]
    outgoing: tuple[GraphEdge, ...]
    trace: ChallengeTrace | None = None


@dataclass(frozen=True)
class Scorecard:
    check: Mapping[str, FieldAvailability]
    graph: UmpireGraph
    fields: Mapping[str, ScorecardField]
    changed_fields: tuple[str, ...]
    fouls: tuple[Foul, ...]
    fouls_by_field: Mapping[str, Foul]
    fouled_fields: tuple[str, ...]
    directly_fouled_fields: tuple[str, ...]
    cascading_fields: tuple[str, ...]
