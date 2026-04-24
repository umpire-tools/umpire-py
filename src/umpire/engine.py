"""Umpire engine implementation."""

import asyncio
import inspect
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
from .types import Conditions, FieldAvailability, FieldDef, Foul, Rule, Values

_UNCHANGED = object()


def _is_satisfied(value: Any, field_def: FieldDef) -> bool:
    """Return whether a value satisfies a field's emptiness strategy."""
    if field_def.is_empty.value == "string":
        return isinstance(value, str) and value != ""
    if field_def.is_empty.value == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if field_def.is_empty.value == "boolean":
        return isinstance(value, bool)
    if field_def.is_empty.value == "array":
        return (
            isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) > 0
        )
    if field_def.is_empty.value == "object":
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


def umpire(fields: Mapping[str, FieldDef], rules: Sequence[Rule] = ()) -> "Umpire":
    """Create a new Umpire instance."""
    return Umpire(fields, rules)


class Umpire:
    """Main Umpire engine for evaluating field availability and transitions."""

    def __init__(self, fields: Mapping[str, FieldDef], rules: Sequence[Rule] = ()):
        """Initialize Umpire with fields and rules."""
        self._fields = dict(fields)
        self._rules = list(rules)

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
            value = values.get(field_name, field_def.default_value)
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
        for _ in range(len(dependency_rules)):
            before = dict(result)
            for rule in dependency_rules:
                self._apply_requires(rule, values, conditions, result)
            if before == result:
                return

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
        branch_snapshots = []
        targets: set[str] = set()
        for branch_rules in rule.branches.values():
            scratch = dict(result)
            for inner_rule in branch_rules:
                self._apply_rule_to_scratch(
                    inner_rule, values, conditions, previous_values, scratch
                )
                if isinstance(inner_rule, (RequiresRule, EnabledWhenRule, FairWhenRule, CheckRule)):
                    targets.add(inner_rule.field)
                elif isinstance(inner_rule, DisablesRule):
                    targets.update(inner_rule.targets)
                elif isinstance(inner_rule, OneOfRule):
                    targets.update(
                        field for fields in inner_rule.branches.values() for field in fields
                    )
                elif isinstance(inner_rule, EitherOfRule):
                    targets.update(
                        field
                        for rules in inner_rule.branches.values()
                        for rule_item in rules
                        if hasattr(rule_item, "field")
                        for field in [rule_item.field]
                    )
            branch_snapshots.append(scratch)

        for target in targets:
            passing = [
                snapshot[target]
                for snapshot in branch_snapshots
                if target in snapshot and snapshot[target].enabled and snapshot[target].fair
            ]
            if passing:
                result[target] = passing[0]
                continue
            failures = [snapshot[target] for snapshot in branch_snapshots if target in snapshot]
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
            value = values.get(field_name, field_def.default_value)
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
        self, values: Values, conditions: Mapping[str, Any] | None = None
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

        return self.check(values, resolved_conditions)
