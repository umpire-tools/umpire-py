"""Umpire engine implementation."""

import asyncio
import inspect
import math
from collections.abc import Mapping, Sequence
from typing import Any

from .rules import (
    AnyOfRule,
    CheckRule,
    DisablesRule,
    EitherOfRule,
    EnabledWhenRule,
    FairWhenRule,
    OneOfRule,
    RequiresRule,
)
from .types import (
    ChallengeReason,
    ChallengeTrace,
    Conditions,
    FieldAvailability,
    FieldDef,
    Foul,
    GraphEdge,
    IsEmptyStrategy,
    RuleEntry,
    Scorecard,
    ScorecardField,
    UmpireGraph,
    Values,
)

_UNCHANGED = object()


def _is_satisfied(value: Any, field_def: FieldDef) -> bool:
    """Return whether a value satisfies a field's emptiness strategy."""
    if field_def.is_empty == IsEmptyStrategy.STRING:
        return isinstance(value, str) and value != ""
    if field_def.is_empty == IsEmptyStrategy.NUMBER:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and not math.isnan(value)
        )
    if field_def.is_empty == IsEmptyStrategy.BOOLEAN:
        return isinstance(value, bool)
    if field_def.is_empty == IsEmptyStrategy.ARRAY:
        return (
            isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) > 0
        )
    if field_def.is_empty == IsEmptyStrategy.OBJECT:
        return isinstance(value, Mapping) and len(value) > 0
    return value is not None


def _with_status(
    current: FieldAvailability,
    *,
    enabled: bool | None = None,
    required: bool | None = None,
    fair: bool | None = None,
    satisfied: bool | None = None,
    reason: str | None | object = _UNCHANGED,
    reasons: tuple[str, ...] | None = None,
    check_errors: tuple[Any, ...] | None = None,
    valid: bool | None | object = _UNCHANGED,
    error: str | None | object = _UNCHANGED,
) -> FieldAvailability:
    """Create an updated immutable field status."""
    return FieldAvailability(
        enabled=current.enabled if enabled is None else enabled,
        required=current.required if required is None else required,
        fair=current.fair if fair is None else fair,
        satisfied=current.satisfied if satisfied is None else satisfied,
        reason=current.reason if reason is _UNCHANGED else reason,  # type: ignore[arg-type]
        reasons=current.reasons if reasons is None else reasons,
        check_errors=current.check_errors if check_errors is None else check_errors,
        valid=current.valid if valid is _UNCHANGED else valid,  # type: ignore[arg-type]
        error=current.error if error is _UNCHANGED else error,  # type: ignore[arg-type]
    )


def _append_reason(current: FieldAvailability, reason: str) -> tuple[str, tuple[str, ...]]:
    if reason in current.reasons:
        return current.reason or reason, current.reasons
    return current.reason or reason, (*current.reasons, reason)


def _combine_failures(failures: Sequence[FieldAvailability]) -> FieldAvailability:
    first = failures[0]
    reasons = tuple(reason for failure in failures for reason in failure.reasons)
    return _with_status(
        first,
        reason=reasons[0] if reasons else first.reason,
        reasons=reasons,
    )


def _collect_rule_targets(rule: object) -> tuple[str, ...]:
    """Recursively collect leaf target fields from a rule tree."""
    targets: set[str] = set()
    if isinstance(rule, (RequiresRule, EnabledWhenRule, FairWhenRule, CheckRule)):
        targets.add(rule.field)
    elif isinstance(rule, DisablesRule):
        targets.update(rule.targets)
    elif isinstance(rule, OneOfRule):
        for fields in rule.branches.values():
            targets.update(fields)
    elif isinstance(rule, EitherOfRule):
        for branch_rules in rule.branches.values():
            for inner in branch_rules:
                targets.update(_collect_rule_targets(inner))
    elif isinstance(rule, AnyOfRule):
        for inner in rule.rules:
            targets.update(_collect_rule_targets(inner))
    return tuple(sorted(targets))


def _rule_kind(rule: object) -> str:
    """Return a snake_case kind string for a rule."""
    if isinstance(rule, RequiresRule):
        return "requires"
    if isinstance(rule, EnabledWhenRule):
        return "enabled_when"
    if isinstance(rule, FairWhenRule):
        return "fair_when"
    if isinstance(rule, DisablesRule):
        return "disables"
    if isinstance(rule, OneOfRule):
        return "one_of"
    if isinstance(rule, AnyOfRule):
        return "any_of"
    if isinstance(rule, EitherOfRule):
        return "either_of"
    if isinstance(rule, CheckRule):
        return "check"
    return "unknown"


def _rule_targets(rule: object) -> tuple[str, ...]:
    """Return leaf target fields for a rule."""
    return _collect_rule_targets(rule)


def _rule_sources(rule: object) -> tuple[str, ...]:
    """Return source fields for a rule."""
    if isinstance(rule, RequiresRule):
        if rule.dependency is not None:
            return (rule.dependency,)
        return ()
    if isinstance(rule, DisablesRule):
        if rule.source != "":
            return (rule.source,)
        return ()
    return ()


def _rule_id(rule: object, seen: dict[str, int]) -> str:
    """Return a stable, deterministic ID for a rule."""
    kind = _rule_kind(rule)
    if isinstance(rule, RequiresRule):
        if rule.dependency is not None:
            base = f"{kind}:{rule.field}:{rule.dependency}"
        else:
            base = f"{kind}:{rule.field}"
    elif isinstance(rule, (OneOfRule, EitherOfRule)):
        base = f"{kind}:{rule.group}"
    elif isinstance(rule, (EnabledWhenRule, FairWhenRule, CheckRule)):
        base = f"{kind}:{rule.field}"
    elif isinstance(rule, DisablesRule):
        base = f"{kind}:{rule.source}" if rule.source else f"{kind}:_any_source"
    elif isinstance(rule, AnyOfRule):
        base = f"{kind}"
    else:
        base = kind

    count = seen.get(base, 0) + 1
    seen[base] = count
    if count > 1:
        return f"{base}#{count}"
    return base


def umpire(fields: Mapping[str, FieldDef], rules: Sequence[object] = ()) -> "Umpire":
    """Create a new Umpire instance."""
    return Umpire(fields, rules)


class Umpire:
    """Main Umpire engine for evaluating field availability and transitions."""

    def __init__(self, fields: Mapping[str, FieldDef], rules: Sequence[object] = ()):
        """Initialize Umpire with fields and rules."""
        self._fields = dict(fields)
        self._rules = list(rules)

    def init(self, overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Return initial values for all known fields.

        Args:
            overrides: Optional mapping of field names to override values.
                       Only known fields are accepted.

        Returns:
            Dict mapping field names to their initial values.

        Raises:
            ValueError: If an override key does not match any known field.
        """
        result: dict[str, Any] = {}
        for field_name, field_def in self._fields.items():
            result[field_name] = field_def.default_value
        if overrides is not None:
            for key, value in overrides.items():
                if key not in self._fields:
                    raise ValueError(f"Unknown field: {key}")
                result[key] = value
        return result

    def rules(self) -> list[RuleEntry]:
        """Return stable RuleEntry objects for all rules.

        Returns:
            List of RuleEntry, one per rule, preserving rule order.
            IDs are deterministic and unique.
        """
        seen: dict[str, int] = {}
        entries: list[RuleEntry] = []
        for i, rule in enumerate(self._rules):
            kind = _rule_kind(rule)
            targets = _rule_targets(rule)
            sources = _rule_sources(rule)
            rule_id = _rule_id(rule, seen)
            entries.append(
                RuleEntry(
                    index=i,
                    id=rule_id,
                    kind=kind,
                    targets=targets,
                    sources=sources,
                )
            )
        return entries

    def graph(self) -> UmpireGraph:
        """Return the structural field graph.

        Edges are created for:
        - requires(dependency, target): dependency -> target (kind "requires")
        - disables(source, targets): source -> target (kind "disables")
        - one_of(group, branches): cross-branch field pairs (kind "one_of")
        - any_of(...) / either_of(...): inner rule edges are included

        No edges for: enabled_when, fair_when, predicate-only requires,
        check, or empty-source disables.
        """
        nodes_set: set[str] = set(self._fields.keys())
        edges: list[GraphEdge] = []

        def collect_edges(rules: Sequence[object]) -> None:
            for rule in rules:
                if isinstance(rule, RequiresRule):
                    if rule.dependency is not None:
                        edges.append(
                            GraphEdge(source=rule.dependency, target=rule.field, kind="requires")
                        )
                        nodes_set.add(rule.dependency)
                        nodes_set.add(rule.field)
                elif isinstance(rule, DisablesRule):
                    if rule.source:
                        nodes_set.add(rule.source)
                        for target in rule.targets:
                            edges.append(
                                GraphEdge(source=rule.source, target=target, kind="disables")
                            )
                            nodes_set.add(target)
                elif isinstance(rule, OneOfRule):
                    branch_fields = list(rule.branches.values())
                    for i, fields_a in enumerate(branch_fields):
                        for fields_b in branch_fields[i + 1 :]:
                            for fa in fields_a:
                                for fb in fields_b:
                                    edges.append(GraphEdge(source=fa, target=fb, kind="one_of"))
                                    edges.append(GraphEdge(source=fb, target=fa, kind="one_of"))
                                    nodes_set.add(fa)
                                    nodes_set.add(fb)
                elif isinstance(rule, AnyOfRule):
                    collect_edges(rule.rules)
                elif isinstance(rule, EitherOfRule):
                    for branch_rules in rule.branches.values():
                        collect_edges(branch_rules)

        collect_edges(self._rules)

        return UmpireGraph(
            nodes=tuple(sorted(nodes_set)),
            edges=tuple(edges),
        )

    def challenge(
        self,
        field: str,
        values: Values,
        conditions: Conditions | None = None,
        previous_values: Values | None = None,
    ) -> ChallengeTrace:
        """Analyze why a field has its current availability state."""
        if field not in self._fields:
            raise ValueError(f"Unknown field: {field}")

        if conditions is None:
            conditions = {}

        avail = self.check(values, conditions, previous_values)
        field_avail = avail[field]

        rule_entries = self.rules()

        direct_reasons: list[ChallengeReason] = []
        transitive_deps: list[Mapping[str, Any]] = []
        one_of_resolution: Mapping[str, Any] | None = None

        for i, rule in enumerate(self._rules):
            targets = _rule_targets(rule)
            if field not in targets:
                continue

            rule_id = rule_entries[i].id

            if isinstance(rule, RequiresRule):
                reasons, deps = self._challenge_requires(
                    rule, field, i, rule_id, values, conditions, avail
                )
                direct_reasons.extend(reasons)
                transitive_deps.extend(deps)

            elif isinstance(rule, EnabledWhenRule):
                direct_reasons.append(
                    self._challenge_enabled_when(rule, field, i, rule_id, values, conditions)
                )

            elif isinstance(rule, FairWhenRule):
                direct_reasons.append(
                    self._challenge_fair_when(rule, field, i, rule_id, values, conditions)
                )

            elif isinstance(rule, DisablesRule):
                direct_reasons.append(
                    self._challenge_disables(rule, field, i, rule_id, values, conditions, avail)
                )

            elif isinstance(rule, OneOfRule):
                reason, resolution = self._challenge_one_of(
                    rule, field, i, rule_id, values, previous_values, avail
                )
                direct_reasons.append(reason)
                if resolution is not None:
                    one_of_resolution = resolution

            elif isinstance(rule, CheckRule):
                direct_reasons.append(self._challenge_check(rule, field, i, rule_id, values, avail))

            elif isinstance(rule, AnyOfRule):
                self._collect_challenge_reasons(
                    rule.rules,
                    field,
                    values,
                    conditions,
                    previous_values,
                    avail,
                    rule_entries,
                    direct_reasons,
                    transitive_deps,
                )

            elif isinstance(rule, EitherOfRule):
                for branch_rules in rule.branches.values():
                    self._collect_challenge_reasons(
                        branch_rules,
                        field,
                        values,
                        conditions,
                        previous_values,
                        avail,
                        rule_entries,
                        direct_reasons,
                        transitive_deps,
                    )

        return ChallengeTrace(
            field=field,
            enabled=field_avail.enabled,
            fair=field_avail.fair,
            direct_reasons=tuple(direct_reasons),
            transitive_deps=tuple(transitive_deps),
            one_of_resolution=one_of_resolution,
        )

    def _challenge_requires(
        self,
        rule: "RequiresRule",
        field: str,
        rule_index: int,
        rule_id: str,
        values: Values,
        conditions: Conditions,
        avail: Mapping[str, FieldAvailability],
    ) -> tuple[list["ChallengeReason"], list[Mapping[str, Any]]]:
        """Challenge a requires rule."""
        transitive: list[Mapping[str, Any]] = []
        reasons: list[ChallengeReason] = []

        if rule.dependency is not None:
            dep_status = avail.get(rule.dependency)
            dep_ok = (
                dep_status is not None
                and dep_status.enabled
                and dep_status.fair
                and dep_status.satisfied
            )
            when_ok = rule.when is None or rule.when(values, conditions)
            passed = dep_ok and when_ok

            dep_value = values.get(rule.dependency)
            reasons.append(
                ChallengeReason(
                    rule="requires",
                    passed=passed,
                    reason=rule.reason or f"requires {rule.dependency}" if not passed else None,
                    rule_index=rule_index,
                    rule_id=rule_id,
                    details={
                        "dependency": rule.dependency,
                        "dependency_value": dep_value,
                        "dependency_satisfied": dep_status.satisfied if dep_status else False,
                        "dependency_enabled": dep_status.enabled if dep_status else False,
                        "dependency_fair": dep_status.fair if dep_status else False,
                    },
                )
            )

            if not passed:
                transitive.append(
                    {
                        "field": rule.dependency,
                        "enabled": dep_status.enabled if dep_status else False,
                        "fair": dep_status.fair if dep_status else False,
                        "satisfied": dep_status.satisfied if dep_status else False,
                        "reason": dep_status.reason or "not available"
                        if dep_status
                        else "unknown field",
                    }
                )
        else:
            predicate_result = rule.when(values, conditions) if rule.when else True
            passed = predicate_result
            reasons.append(
                ChallengeReason(
                    rule="requires",
                    passed=passed,
                    reason=None if passed else (rule.reason or "required condition not met"),
                    rule_index=rule_index,
                    rule_id=rule_id,
                    details={"predicate_result": predicate_result},
                )
            )

        return reasons, transitive

    def _challenge_enabled_when(
        self,
        rule: "EnabledWhenRule",
        field: str,
        rule_index: int,
        rule_id: str,
        values: Values,
        conditions: Conditions,
    ) -> "ChallengeReason":
        """Challenge an enabled_when rule."""
        predicate_result = rule.when(values, conditions)
        field_def = self._fields.get(field, FieldDef())
        value = values.get(field, field_def.default_value)
        return ChallengeReason(
            rule="enabled_when",
            passed=predicate_result,
            reason=None if predicate_result else (rule.reason or "condition not met"),
            rule_index=rule_index,
            rule_id=rule_id,
            details={"predicate_result": predicate_result, "field_value": value},
        )

    def _challenge_fair_when(
        self,
        rule: "FairWhenRule",
        field: str,
        rule_index: int,
        rule_id: str,
        values: Values,
        conditions: Conditions,
    ) -> "ChallengeReason":
        """Challenge a fair_when rule."""
        predicate_result = rule.when(values, conditions)
        field_def = self._fields.get(field, FieldDef())
        value = values.get(field, field_def.default_value)
        return ChallengeReason(
            rule="fair_when",
            passed=predicate_result,
            reason=None if predicate_result else (rule.reason or "selection is no longer valid"),
            rule_index=rule_index,
            rule_id=rule_id,
            details={"predicate_result": predicate_result, "field_value": value},
        )

    def _challenge_disables(
        self,
        rule: "DisablesRule",
        field: str,
        rule_index: int,
        rule_id: str,
        values: Values,
        conditions: Conditions,
        avail: Mapping[str, FieldAvailability],
    ) -> "ChallengeReason":
        """Challenge a disables rule from the target field's perspective."""
        source_active = (
            rule.source == "" or (rule.source in avail and avail[rule.source].satisfied)
        ) and (rule.when is None or rule.when(values, conditions))
        passed = not source_active

        source_value = values.get(rule.source) if rule.source else None
        source_satisfied = (
            avail[rule.source].satisfied if rule.source and rule.source in avail else False
        )
        return ChallengeReason(
            rule="disables",
            passed=passed,
            reason=None if passed else (rule.reason or f"overridden by {rule.source}"),
            rule_index=rule_index,
            rule_id=rule_id,
            details={
                "source": rule.source or "",
                "source_value": source_value,
                "source_satisfied": source_satisfied,
                "source_active": source_active,
            },
        )

    def _challenge_one_of(
        self,
        rule: "OneOfRule",
        field: str,
        rule_index: int,
        rule_id: str,
        values: Values,
        previous_values: Values | None,
        avail: Mapping[str, FieldAvailability],
    ) -> tuple["ChallengeReason", Mapping[str, Any] | None]:
        """Challenge a one_of rule for a field."""
        active_branch = self._resolve_one_of_branch(rule, values, previous_values)

        active_fields: set[str] = set()
        if active_branch is not None:
            active_fields = set(rule.branches.get(active_branch, []))
        field_in_active = field in active_fields

        resolution: dict[str, Any] | None = None
        if active_branch is not None:
            all_branches: dict[str, list[str]] = dict(rule.branches.items())
            resolution = {
                "group": rule.group,
                "active_branch": active_branch,
                "this_branch": next(
                    (name for name, fields in rule.branches.items() if field in fields), None
                ),
                "branches": {
                    name: {
                        "fields": fields,
                        "is_active": name == active_branch,
                    }
                    for name, fields in all_branches.items()
                },
            }

        passed = active_branch is None or field_in_active
        return (
            ChallengeReason(
                rule="one_of",
                passed=passed,
                reason=None
                if passed
                else (rule.reason or f"conflicts with {active_branch} strategy"),
                rule_index=rule_index,
                rule_id=rule_id,
                details={
                    "group": rule.group,
                    "active_branch": active_branch,
                    "field_in_active": field_in_active,
                },
            ),
            resolution,
        )

    def _challenge_check(
        self,
        rule: "CheckRule",
        field: str,
        rule_index: int,
        rule_id: str,
        values: Values,
        avail: Mapping[str, FieldAvailability],
    ) -> "ChallengeReason":
        """Challenge a check rule."""
        field_avail = avail.get(field)
        if field_avail is None or not field_avail.enabled or not field_avail.satisfied:
            return ChallengeReason(
                rule="check",
                passed=True,
                reason=None,
                rule_index=rule_index,
                rule_id=rule_id,
                details={"skipped": True, "reason": "field not enabled or not satisfied"},
            )

        field_def = self._fields.get(field, FieldDef())
        value = values.get(field, field_def.default_value)
        error = rule.op(value, field)

        passed = error is None
        return ChallengeReason(
            rule="check",
            passed=passed,
            reason=error.reason if error else None,
            rule_index=rule_index,
            rule_id=rule_id,
            details={
                "error": error.reason if error else None,
                "affects_fair": rule.affects_fair,
                "validation": rule.validation,
            },
        )

    def _collect_challenge_reasons(
        self,
        rules: Sequence[object],
        field: str,
        values: Values,
        conditions: Conditions,
        previous_values: Values | None,
        avail: Mapping[str, FieldAvailability],
        rule_entries: list["RuleEntry"],
        direct_reasons: list["ChallengeReason"],
        transitive_deps: list[Mapping[str, Any]],
    ) -> None:
        """Recursively collect challenge reasons from inner rules."""
        for inner_rule in rules:
            targets = _rule_targets(inner_rule)
            if field not in targets:
                if isinstance(inner_rule, AnyOfRule):
                    self._collect_challenge_reasons(
                        inner_rule.rules,
                        field,
                        values,
                        conditions,
                        previous_values,
                        avail,
                        rule_entries,
                        direct_reasons,
                        transitive_deps,
                    )
                elif isinstance(inner_rule, EitherOfRule):
                    for branch_rules in inner_rule.branches.values():
                        self._collect_challenge_reasons(
                            branch_rules,
                            field,
                            values,
                            conditions,
                            previous_values,
                            avail,
                            rule_entries,
                            direct_reasons,
                            transitive_deps,
                        )
                continue

            inner_index = self._rules.index(inner_rule) if inner_rule in self._rules else -1
            inner_id = ""
            if 0 <= inner_index < len(rule_entries):
                inner_id = rule_entries[inner_index].id

            if isinstance(inner_rule, RequiresRule):
                reasons, deps = self._challenge_requires(
                    inner_rule, field, inner_index, inner_id, values, conditions, avail
                )
                direct_reasons.extend(reasons)
                transitive_deps.extend(deps)
            elif isinstance(inner_rule, EnabledWhenRule):
                direct_reasons.append(
                    self._challenge_enabled_when(
                        inner_rule, field, inner_index, inner_id, values, conditions
                    )
                )
            elif isinstance(inner_rule, FairWhenRule):
                direct_reasons.append(
                    self._challenge_fair_when(
                        inner_rule, field, inner_index, inner_id, values, conditions
                    )
                )
            elif isinstance(inner_rule, DisablesRule):
                direct_reasons.append(
                    self._challenge_disables(
                        inner_rule, field, inner_index, inner_id, values, conditions, avail
                    )
                )
            elif isinstance(inner_rule, OneOfRule):
                reason, _resolution = self._challenge_one_of(
                    inner_rule, field, inner_index, inner_id, values, previous_values, avail
                )
                direct_reasons.append(reason)
            elif isinstance(inner_rule, CheckRule):
                direct_reasons.append(
                    self._challenge_check(inner_rule, field, inner_index, inner_id, values, avail)
                )
            elif isinstance(inner_rule, AnyOfRule):
                self._collect_challenge_reasons(
                    inner_rule.rules,
                    field,
                    values,
                    conditions,
                    previous_values,
                    avail,
                    rule_entries,
                    direct_reasons,
                    transitive_deps,
                )
            elif isinstance(inner_rule, EitherOfRule):
                for branch_rules in inner_rule.branches.values():
                    self._collect_challenge_reasons(
                        branch_rules,
                        field,
                        values,
                        conditions,
                        previous_values,
                        avail,
                        rule_entries,
                        direct_reasons,
                        transitive_deps,
                    )

    def scorecard(
        self,
        values: Values,
        conditions: Conditions | None = None,
        previous_values: Values | None = None,
        include_challenge: bool = False,
    ) -> Scorecard:
        if conditions is None:
            conditions = {}

        check_result = self.check(values, conditions, previous_values)
        graph_result = self.graph()

        fields: dict[str, ScorecardField] = {}
        for field_name, field_def in self._fields.items():
            avail = check_result[field_name]
            value = values.get(field_name, field_def.default_value)
            present = field_name in values

            incoming: list[GraphEdge] = []
            outgoing: list[GraphEdge] = []
            for edge in graph_result.edges:
                if edge.target == field_name:
                    incoming.append(edge)
                if edge.source == field_name:
                    outgoing.append(edge)

            trace = None
            if include_challenge:
                trace = self.challenge(field_name, values, conditions, previous_values)

            fields[field_name] = ScorecardField(
                field=field_name,
                value=value,
                present=present,
                satisfied=avail.satisfied,
                enabled=avail.enabled,
                fair=avail.fair,
                required=avail.required,
                reason=avail.reason,
                reasons=avail.reasons,
                changed=False,
                cascaded=False,
                foul=None,
                incoming=tuple(incoming),
                outgoing=tuple(outgoing),
                trace=trace,
            )

        changed_field_names: tuple[str, ...] = ()
        fouls: tuple[Foul, ...] = ()
        fouls_by_field: dict[str, Foul] = {}
        fouled_field_names: tuple[str, ...] = ()
        directly_fouled_field_names: tuple[str, ...] = ()
        cascading_field_names: tuple[str, ...] = ()

        if previous_values is not None:
            before_check = self.check(previous_values, conditions)
            fouls = tuple(self.play(before_check, check_result, values))

            fouls_by_field = {f.field: f for f in fouls}
            fouled_field_names = tuple(sorted(fouls_by_field.keys()))

            changed_set: set[str] = set()
            for field_name in self._fields:
                prev_value = previous_values.get(field_name, _UNCHANGED)
                curr_value = values.get(field_name, _UNCHANGED)
                if prev_value != curr_value:
                    changed_set.add(field_name)
            changed_field_names = tuple(sorted(changed_set))

            directly_fouled = set(fouled_field_names) & changed_set
            directly_fouled_field_names = tuple(sorted(directly_fouled))

            cascading_set: set[str] = set()
            for field_name in self._fields:
                before_avail = before_check.get(field_name)
                after_avail = check_result.get(field_name)
                if (
                    before_avail is not None
                    and after_avail is not None
                    and before_avail != after_avail
                ):
                    value_changed = field_name in changed_set
                    if not value_changed:
                        cascading_set.add(field_name)
            cascading_field_names = tuple(sorted(cascading_set))

            for field_name in fouled_field_names:
                sf = fields[field_name]
                fields[field_name] = ScorecardField(
                    field=sf.field,
                    value=sf.value,
                    present=sf.present,
                    satisfied=sf.satisfied,
                    enabled=sf.enabled,
                    fair=sf.fair,
                    required=sf.required,
                    reason=sf.reason,
                    reasons=sf.reasons,
                    changed=field_name in changed_set,
                    cascaded=field_name in cascading_set,
                    foul=fouls_by_field.get(field_name),
                    incoming=sf.incoming,
                    outgoing=sf.outgoing,
                    trace=sf.trace,
                )

            for field_name in self._fields:
                if field_name in fouled_field_names:
                    continue
                sf = fields[field_name]
                is_changed = field_name in changed_set
                is_cascaded = field_name in cascading_set
                if is_changed or is_cascaded:
                    fields[field_name] = ScorecardField(
                        field=sf.field,
                        value=sf.value,
                        present=sf.present,
                        satisfied=sf.satisfied,
                        enabled=sf.enabled,
                        fair=sf.fair,
                        required=sf.required,
                        reason=sf.reason,
                        reasons=sf.reasons,
                        changed=is_changed,
                        cascaded=is_cascaded,
                        foul=None,
                        incoming=sf.incoming,
                        outgoing=sf.outgoing,
                        trace=sf.trace,
                    )

        return Scorecard(
            check=check_result,
            graph=graph_result,
            fields=fields,
            changed_fields=changed_field_names,
            fouls=fouls,
            fouls_by_field=fouls_by_field,
            fouled_fields=fouled_field_names,
            directly_fouled_fields=directly_fouled_field_names,
            cascading_fields=cascading_field_names,
        )

    def check(
        self,
        values: Values,
        conditions: Conditions | None = None,
        previous_values: Values | None = None,
    ) -> Mapping[str, FieldAvailability]:
        """
        Check field availability based on current values and conditions.

        Args:
            values: Current field values
            conditions: Current conditions (optional)

        Returns:
            Mapping of field names to their availability information
        """
        if conditions is None:
            conditions = {}

        result: dict[str, FieldAvailability] = {}
        for field_name, field_def in self._fields.items():
            value = values.get(field_name)
            satisfied = _is_satisfied(value, field_def)
            result[field_name] = FieldAvailability(
                enabled=True,
                required=field_def.required,
                fair=True,
                satisfied=satisfied,
            )

        for rule in self._rules:
            if isinstance(rule, RequiresRule):
                self._apply_requires(rule, values, conditions, result)
            elif isinstance(rule, EnabledWhenRule):
                self._apply_enabled_when(rule, values, conditions, result)
            elif isinstance(rule, FairWhenRule):
                self._apply_fair_when(rule, values, conditions, result)
            elif isinstance(rule, DisablesRule):
                self._apply_disables(rule, values, conditions, result)
            elif isinstance(rule, OneOfRule):
                self._apply_one_of(rule, values, previous_values, result)
            elif isinstance(rule, AnyOfRule):
                self._apply_any_of(rule, values, conditions, previous_values, result)
            elif isinstance(rule, EitherOfRule):
                self._apply_either_of(rule, values, conditions, previous_values, result)
            elif isinstance(rule, CheckRule) and rule.field in result:
                self._apply_check(rule, values, result)

        self._stabilize_dependency_requires(values, conditions, result)

        return result

    def _stabilize_dependency_requires(
        self,
        values: Values,
        conditions: Conditions,
        result: dict[str, FieldAvailability],
    ) -> None:
        dependency_rules = [
            rule
            for rule in self._rules
            if isinstance(rule, RequiresRule) and rule.dependency is not None
        ]
        if not dependency_rules:
            return

        prev_changed: set[tuple[str, str]] = set()
        max_iterations = len(dependency_rules) * 2
        iteration = 0

        while True:
            iteration += 1
            if iteration > max_iterations:
                raise ValueError(
                    "Dependency chain exceeded maximum iterations "
                    f"({len(dependency_rules)} rules, {iteration} iterations)"
                )

            before = dict(result)
            for rule in dependency_rules:
                self._apply_requires(rule, values, conditions, result)
            if before == result:
                return

            changed_fields = {f for f, a in result.items() if before.get(f) != a}
            current_changed: set[tuple[str, str]] = set()
            for rule in dependency_rules:
                assert rule.dependency is not None  # filtered above
                chain_key = (rule.field, rule.dependency)
                if changed_fields & {rule.field, rule.dependency}:
                    if chain_key in prev_changed:
                        raise ValueError(
                            f"Circular dependency detected: {rule.field} ↔ {rule.dependency}"
                        )
                    current_changed.add(chain_key)
            prev_changed = current_changed

    def _apply_requires(
        self,
        rule: RequiresRule,
        values: Values,
        conditions: Conditions,
        result: dict[str, FieldAvailability],
    ) -> None:
        if rule.field not in result:
            return

        current = result[rule.field]
        if rule.dependency is not None:
            dependency_status = result.get(rule.dependency)
            dependency_ok = (
                dependency_status is not None
                and dependency_status.enabled
                and dependency_status.fair
                and dependency_status.satisfied
            )
            if dependency_ok and (rule.when is None or rule.when(values, conditions)):
                return
            reason, reasons = _append_reason(current, rule.reason or f"requires {rule.dependency}")
            result[rule.field] = _with_status(
                current,
                enabled=False,
                required=False,
                reason=reason,
                reasons=reasons,
            )
            return

        if rule.when is not None and rule.when(values, conditions):
            result[rule.field] = _with_status(current, required=True)

    def _apply_enabled_when(
        self,
        rule: EnabledWhenRule,
        values: Values,
        conditions: Conditions,
        result: dict[str, FieldAvailability],
    ) -> None:
        if rule.field not in result:
            return
        current = result[rule.field]
        if rule.when(values, conditions):
            return
        reason, reasons = _append_reason(current, rule.reason or "condition not met")
        result[rule.field] = _with_status(
            current,
            enabled=False,
            required=False,
            reason=reason,
            reasons=reasons,
        )

    def _apply_fair_when(
        self,
        rule: FairWhenRule,
        values: Values,
        conditions: Conditions,
        result: dict[str, FieldAvailability],
    ) -> None:
        if rule.field not in result:
            return
        current = result[rule.field]
        if not current.enabled or not current.satisfied or rule.when(values, conditions):
            result[rule.field] = _with_status(current, fair=True)
            return
        reason, reasons = _append_reason(current, rule.reason or "selection is no longer valid")
        result[rule.field] = _with_status(
            current,
            fair=False,
            reason=reason,
            reasons=reasons,
        )

    def _apply_disables(
        self,
        rule: DisablesRule,
        values: Values,
        conditions: Conditions,
        result: dict[str, FieldAvailability],
    ) -> None:
        source_active = (
            rule.source == "" or (rule.source in result and result[rule.source].satisfied)
        ) and (rule.when is None or rule.when(values, conditions))
        if not source_active:
            return
        for target in rule.targets:
            if target in result:
                reason, reasons = _append_reason(
                    result[target], rule.reason or f"overridden by {rule.source}"
                )
                result[target] = _with_status(
                    result[target],
                    enabled=False,
                    required=False,
                    reason=reason,
                    reasons=reasons,
                )

    def _apply_check(
        self,
        rule: CheckRule,
        values: Values,
        result: dict[str, FieldAvailability],
    ) -> None:
        current = result[rule.field]
        if not current.enabled or not current.satisfied:
            return
        value = values.get(rule.field, self._fields[rule.field].default_value)
        error = rule.op(value, rule.field)
        if error is None:
            if rule.validation:
                result[rule.field] = _with_status(current, valid=True, error=None)
            return
        result[rule.field] = _with_status(
            current,
            fair=False if rule.affects_fair else current.fair,
            reason=error.reason if rule.affects_fair else current.reason,
            reasons=(*current.reasons, error.reason) if rule.affects_fair else current.reasons,
            check_errors=(*current.check_errors, error),
            valid=False if rule.validation else current.valid,
            error=error.reason if rule.validation else current.error,
        )

    def _apply_any_of(
        self,
        rule: AnyOfRule,
        values: Values,
        conditions: Conditions,
        previous_values: Values | None,
        result: dict[str, FieldAvailability],
    ) -> None:
        if not rule.rules:
            return

        snapshots = []
        targets: set[str] = set()
        for inner_rule in rule.rules:
            scratch = dict(result)
            if isinstance(inner_rule, RequiresRule):
                if inner_rule.dependency is None and inner_rule.when is not None:
                    current = scratch[inner_rule.field]
                    if not inner_rule.when(values, conditions):
                        reason, reasons = _append_reason(
                            current, inner_rule.reason or "required condition not met"
                        )
                        scratch[inner_rule.field] = _with_status(
                            current,
                            enabled=False,
                            required=False,
                            reason=reason,
                            reasons=reasons,
                        )
                else:
                    self._apply_requires(inner_rule, values, conditions, scratch)
                targets.add(inner_rule.field)
            elif isinstance(inner_rule, EnabledWhenRule):
                self._apply_enabled_when(inner_rule, values, conditions, scratch)
                targets.add(inner_rule.field)
            elif isinstance(inner_rule, FairWhenRule):
                self._apply_fair_when(inner_rule, values, conditions, scratch)
                targets.add(inner_rule.field)
            elif isinstance(inner_rule, OneOfRule):
                self._apply_one_of(inner_rule, values, previous_values, scratch)
                targets.update(field for fields in inner_rule.branches.values() for field in fields)
            elif isinstance(inner_rule, EitherOfRule):
                self._apply_either_of(inner_rule, values, conditions, previous_values, scratch)
            elif isinstance(inner_rule, DisablesRule):
                self._apply_disables(inner_rule, values, conditions, scratch)
                targets.update(inner_rule.targets)
            elif isinstance(inner_rule, CheckRule):
                if inner_rule.field in scratch:
                    self._apply_check(inner_rule, values, scratch)
                targets.add(inner_rule.field)
            snapshots.append(scratch)

        for target in targets:
            passing = [
                snapshot[target]
                for snapshot in snapshots
                if target in snapshot and snapshot[target].enabled and snapshot[target].fair
            ]
            if passing:
                result[target] = passing[0]
            elif target in snapshots[0]:
                failures = [snapshot[target] for snapshot in snapshots if target in snapshot]
                result[target] = _combine_failures(failures)

    def _apply_either_of(
        self,
        rule: EitherOfRule,
        values: Values,
        conditions: Conditions,
        previous_values: Values | None,
        result: dict[str, FieldAvailability],
    ) -> None:
        branch_snapshots: list[dict[str, FieldAvailability]] = []
        branch_targets: list[set[str]] = []

        for branch_rules in rule.branches.values():
            scratch = dict(result)
            targets: set[str] = set()
            for inner_rule in branch_rules:
                self._apply_rule_to_scratch(
                    inner_rule, values, conditions, previous_values, scratch
                )
                targets.update(_collect_rule_targets(inner_rule))
            branch_snapshots.append(scratch)
            branch_targets.append(targets)

        # Determine which branches pass holistically
        passing_indices: list[int] = []
        for i, (snapshot, targets) in enumerate(
            zip(branch_snapshots, branch_targets, strict=False)
        ):
            if not targets:
                # Branch with zero leaf targets passes trivially
                passing_indices.append(i)
            elif all(
                field in snapshot and snapshot[field].enabled and snapshot[field].fair
                for field in targets
            ):
                passing_indices.append(i)

        if passing_indices:
            # Apply first passing branch's entire snapshot
            first = branch_snapshots[passing_indices[0]]
            for field, availability in first.items():
                if availability != result.get(field):
                    result[field] = availability
        else:
            # No branch passes — combine failures per-target
            all_targets: set[str] = set()
            for targets in branch_targets:
                all_targets.update(targets)
            for target in all_targets:
                failures = [s[target] for s in branch_snapshots if target in s]
                if failures:
                    result[target] = _combine_failures(failures)

    def _apply_rule_to_scratch(
        self,
        rule: object,
        values: Values,
        conditions: Conditions,
        previous_values: Values | None,
        scratch: dict[str, FieldAvailability],
    ) -> None:
        if isinstance(rule, RequiresRule):
            self._apply_requires(rule, values, conditions, scratch)
        elif isinstance(rule, EnabledWhenRule):
            self._apply_enabled_when(rule, values, conditions, scratch)
        elif isinstance(rule, FairWhenRule):
            self._apply_fair_when(rule, values, conditions, scratch)
        elif isinstance(rule, DisablesRule):
            self._apply_disables(rule, values, conditions, scratch)
        elif isinstance(rule, OneOfRule):
            self._apply_one_of(rule, values, previous_values, scratch)
        elif isinstance(rule, AnyOfRule):
            self._apply_any_of(rule, values, conditions, previous_values, scratch)
        elif isinstance(rule, EitherOfRule):
            self._apply_either_of(rule, values, conditions, previous_values, scratch)
        elif isinstance(rule, CheckRule) and rule.field in scratch:
            self._apply_check(rule, values, scratch)

    def _apply_one_of(
        self,
        rule: OneOfRule,
        values: Values,
        previous_values: Values | None,
        result: dict[str, FieldAvailability],
    ) -> None:
        active_branch = self._resolve_one_of_branch(rule, values, previous_values)
        if active_branch is None:
            return

        active_fields = set(rule.branches[active_branch])
        for branch_fields in rule.branches.values():
            for field in branch_fields:
                if field not in result or field in active_fields:
                    continue
                current = result[field]
                reason, reasons = _append_reason(
                    current, rule.reason or f"conflicts with {active_branch} strategy"
                )
                result[field] = _with_status(
                    current,
                    enabled=False,
                    required=False,
                    reason=reason,
                    reasons=reasons,
                )

    def _resolve_one_of_branch(
        self, rule: OneOfRule, values: Values, previous_values: Values | None
    ) -> str | None:
        satisfied = [
            name
            for name, fields in rule.branches.items()
            if any(
                field in self._fields and _is_satisfied(values.get(field), self._fields[field])
                for field in fields
            )
        ]
        if not satisfied:
            return None
        if len(satisfied) == 1:
            return satisfied[0]
        if previous_values is not None:
            previous_satisfied = {
                name
                for name, fields in rule.branches.items()
                if any(
                    field in self._fields
                    and _is_satisfied(previous_values.get(field), self._fields[field])
                    for field in fields
                )
            }
            newly_satisfied = [name for name in satisfied if name not in previous_satisfied]
            if len(newly_satisfied) == 1:
                return newly_satisfied[0]
        return satisfied[0]

    def play(
        self,
        before: Mapping[str, FieldAvailability],
        after: Mapping[str, FieldAvailability],
        values: Values,
    ) -> Sequence[Foul]:
        """
        Compare availability state transitions and generate fouls for relevant changes.

        Args:
            before: Previous field availability state
            after: Current field availability state
            values: Current field values

        Returns:
            Sequence of fouls representing invalid transitions
        """
        fouls: list[Foul] = []

        for field_name, after_avail in after.items():
            before_avail = before.get(field_name)
            field_def = self._fields.get(field_name, FieldDef())
            value = values.get(field_name)
            if before_avail is None or not _is_satisfied(value, field_def):
                continue

            became_disabled = before_avail.enabled and not after_avail.enabled
            became_foul = before_avail.fair and not after_avail.fair
            if not became_disabled and not became_foul:
                continue

            suggested_value = field_def.default_value
            if value == suggested_value:
                continue

            fouls.append(
                Foul(
                    field=field_name,
                    reason=after_avail.reason
                    or ("field disabled" if became_disabled else "field fouled"),
                    suggested_value=suggested_value,
                )
            )

        return fouls

    async def check_async(
        self,
        values: Values,
        conditions: Mapping[str, Any] | None = None,
        previous_values: Values | None = None,
    ) -> Mapping[str, FieldAvailability]:
        """
        Check field availability based on current values and async conditions.

        This method resolves async condition providers concurrently and then
        evaluates field availability using the resolved conditions.

        Args:
            values: Current field values
            conditions: Current conditions with potential async providers (optional)

        Returns:
            Mapping of field names to their availability information
        """
        if conditions is None:
            conditions = {}

        resolved_conditions: dict[str, Any] = {}
        async_keys: list[str] = []
        async_values = []

        for key, provider in conditions.items():
            value = provider() if callable(provider) else provider
            if inspect.isawaitable(value):
                async_keys.append(key)
                async_values.append(value)
            else:
                resolved_conditions[key] = value

        if async_values:
            async_results = await asyncio.gather(*async_values)
            resolved_conditions.update(dict(zip(async_keys, async_results, strict=True)))

        return self.check(values, resolved_conditions, previous_values=previous_values)
