"""Umpire engine implementation."""

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

from .rules import (
    AnyOfRule,
    CheckRule,
    DisablesRule,
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
    return value is not None


def _with_status(
    current: FieldAvailability,
    *,
    enabled: bool | None = None,
    required: bool | None = None,
    fair: bool | None = None,
    satisfied: bool | None = None,
    reason: str | None | object = _UNCHANGED,
    check_errors: tuple[Any, ...] | None = None,
) -> FieldAvailability:
    """Create an updated immutable field status."""
    return FieldAvailability(
        enabled=current.enabled if enabled is None else enabled,
        required=current.required if required is None else required,
        fair=current.fair if fair is None else fair,
        satisfied=current.satisfied if satisfied is None else satisfied,
        reason=current.reason if reason is _UNCHANGED else reason,  # type: ignore[arg-type]
        check_errors=current.check_errors if check_errors is None else check_errors,
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
                if rule.field in result:
                    current = result[rule.field]
                    if rule.when(values, conditions):
                        result[rule.field] = _with_status(current, enabled=True, reason=None)
                    else:
                        result[rule.field] = _with_status(
                            current,
                            enabled=False,
                            required=False,
                            reason=rule.reason or "condition not met",
                        )
            elif isinstance(rule, FairWhenRule):
                if rule.field in result:
                    current = result[rule.field]
                    if (
                        not current.enabled
                        or not current.satisfied
                        or rule.when(values, conditions)
                    ):
                        result[rule.field] = _with_status(current, fair=True)
                    else:
                        result[rule.field] = _with_status(
                            current,
                            fair=False,
                            reason=rule.reason or "selection is no longer valid",
                        )
            elif isinstance(rule, DisablesRule):
                source_active = (
                    rule.source in result
                    and result[rule.source].satisfied
                    and (rule.when is None or rule.when(values, conditions))
                )
                if source_active:
                    for target in rule.targets:
                        if target in result:
                            current = result[target]
                            result[target] = _with_status(
                                current,
                                enabled=False,
                                required=False,
                                reason=rule.reason or f"overridden by {rule.source}",
                            )
            elif isinstance(rule, OneOfRule):
                self._apply_one_of(rule, values, previous_values, result)
            elif isinstance(rule, AnyOfRule):
                self._apply_any_of(rule, values, conditions, previous_values, result)
            elif isinstance(rule, CheckRule) and rule.field in result:
                current = result[rule.field]
                if current.enabled and current.satisfied:
                    value = values.get(rule.field, self._fields[rule.field].default_value)
                    error = rule.op(value, rule.field)
                    if error is not None:
                        result[rule.field] = _with_status(
                            current, check_errors=(*current.check_errors, error)
                        )

        return result

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
            result[rule.field] = _with_status(
                current,
                enabled=False,
                required=False,
                reason=rule.reason or f"requires {rule.dependency}",
            )
            return

        if rule.when is not None and rule.when(values, conditions):
            result[rule.field] = _with_status(current, required=True)

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
                        scratch[inner_rule.field] = _with_status(
                            current,
                            enabled=False,
                            required=False,
                            reason=inner_rule.reason or "required condition not met",
                        )
                else:
                    self._apply_requires(inner_rule, values, conditions, scratch)
                targets.add(inner_rule.field)
            elif isinstance(inner_rule, EnabledWhenRule):
                if inner_rule.field in scratch:
                    current = scratch[inner_rule.field]
                    scratch[inner_rule.field] = _with_status(
                        current,
                        enabled=inner_rule.when(values, conditions),
                        required=current.required if inner_rule.when(values, conditions) else False,
                    )
                    targets.add(inner_rule.field)
            elif isinstance(inner_rule, FairWhenRule):
                if inner_rule.field in scratch:
                    current = scratch[inner_rule.field]
                    fair = not current.satisfied or inner_rule.when(values, conditions)
                    scratch[inner_rule.field] = _with_status(current, fair=fair)
                    targets.add(inner_rule.field)
            elif isinstance(inner_rule, OneOfRule):
                self._apply_one_of(inner_rule, values, previous_values, scratch)
                targets.update(field for fields in inner_rule.branches.values() for field in fields)
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
                result[target] = snapshots[0][target]

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
                result[field] = _with_status(
                    current,
                    enabled=False,
                    required=False,
                    reason=rule.reason or f"conflicts with {active_branch} strategy",
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
        self, values: Values, conditions: dict[str, Any] | None = None
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

        # Resolve async condition providers concurrently
        resolved_conditions = {}
        async_providers = {}
        sync_providers = {}

        # Separate async and sync providers
        for key, provider in conditions.items():
            from .schema.providers import is_async_provider

            if is_async_provider(provider):
                async_providers[key] = provider
            else:
                sync_providers[key] = provider

        # Resolve sync providers first
        from .schema.providers import normalize_providers

        resolved_conditions.update(normalize_providers(sync_providers))

        # Resolve async providers concurrently
        if async_providers:
            async_tasks = {key: provider() for key, provider in async_providers.items()}
            async_results = await asyncio.gather(*async_tasks.values())
            resolved_async = dict(zip(async_tasks.keys(), async_results, strict=False))
            resolved_conditions.update(resolved_async)

        # Use resolved conditions for the check
        return self.check(values, resolved_conditions)
