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
        self, values: Values, conditions: Conditions | None = None
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

        # Initialize all fields with default availability
        result: dict[str, FieldAvailability] = {}
        for field_name, _field_def in self._fields.items():
            result[field_name] = FieldAvailability()

        # Evaluate rules to determine field availability
        for rule in self._rules:
            if isinstance(rule, RequiresRule):
                # Evaluate requires rule
                if (rule.when is None or rule.when(values, conditions)) and rule.field in result:
                    current = result[rule.field]
                    result[rule.field] = FieldAvailability(
                        enabled=current.enabled,
                        required=True,
                        fair=current.fair,
                        check_errors=current.check_errors,
                    )
            elif isinstance(rule, EnabledWhenRule):
                # Evaluate enabled_when rule
                if rule.field in result:
                    current = result[rule.field]
                    if rule.when(values, conditions):
                        result[rule.field] = FieldAvailability(
                            enabled=True,
                            required=current.required,
                            fair=current.fair,
                            check_errors=current.check_errors,
                        )
                    else:
                        result[rule.field] = FieldAvailability(
                            enabled=False,
                            required=current.required,
                            fair=current.fair,
                            check_errors=current.check_errors,
                        )
            elif isinstance(rule, FairWhenRule):
                # Evaluate fair_when rule
                if rule.field in result:
                    current = result[rule.field]
                    if rule.when(values, conditions):
                        result[rule.field] = FieldAvailability(
                            enabled=current.enabled,
                            required=current.required,
                            fair=True,
                            check_errors=current.check_errors,
                        )
                    else:
                        result[rule.field] = FieldAvailability(
                            enabled=current.enabled,
                            required=current.required,
                            fair=False,
                            check_errors=current.check_errors,
                        )
            elif isinstance(rule, DisablesRule):
                # Evaluate disables rule
                # Check if the source field has a value and condition is met (if specified)
                if rule.source in values and (rule.when is None or rule.when(values, conditions)):
                    # Disable the target fields
                    for target in rule.targets:
                        if target in result:
                            current = result[target]
                            result[target] = FieldAvailability(
                                enabled=False,
                                required=current.required,
                                fair=current.fair,
                                check_errors=current.check_errors,
                            )
            elif isinstance(rule, OneOfRule):
                # Evaluate one_of rule
                # Count how many of the branches are enabled/selected
                enabled_count = 0
                enabled_fields = []
                for branch in rule.branches:
                    if branch in values and values[branch] is not None:
                        # For simplicity, we'll consider a field "enabled" if it has a value
                        enabled_count += 1
                        enabled_fields.append(branch)

                # If more than one field is enabled, disable all but the first one
                # (This is a simple implementation - could be more sophisticated)
                if enabled_count > 1:
                    # Disable all but the first enabled field
                    for field in enabled_fields[1:]:
                        if field in result:
                            current = result[field]
                            result[field] = FieldAvailability(
                                enabled=False,
                                required=current.required,
                                fair=current.fair,
                                check_errors=current.check_errors,
                            )
            elif isinstance(rule, AnyOfRule):
                # Evaluate any_of rule
                # For now, we'll just pass through - any_of rules would typically
                # be used to group other rules, not directly affect field availability
                pass
            elif isinstance(rule, CheckRule):
                # Evaluate check rule - this affects check_errors
                pass  # Check rules are evaluated separately

        # Handle field definitions for required status
        # Only set required status from field definition if it wasn't already set by a rule
        for field_name, field_def in self._fields.items():
            if field_name not in result:
                result[field_name] = FieldAvailability()

            # A field is required if:
            # 1. It's marked as required in its definition AND wasn't already
            #    made required by a rule
            # 2. It doesn't have a value provided AND doesn't have a default value
            current = result[field_name]
            if not current.required:  # Only set from field definition if not already
                # required by rule
                required = (
                    field_def.required
                    and field_name not in values
                    and field_def.default_value is None
                )
                result[field_name] = FieldAvailability(
                    enabled=current.enabled,
                    required=required,
                    fair=current.fair,
                    check_errors=current.check_errors,
                )

        return result

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

        # Compare each field's availability between before and after states
        for field_name in before:
            if field_name in after:
                after_avail = after[field_name]

                # Check for transitions that would create fouls
                # For example, if a field became required but has no value
                if after_avail.required and field_name not in values:
                    fouls.append(
                        Foul(
                            field=field_name,
                            reason=f"Field '{field_name}' became required but has no value",
                        )
                    )

                # Add more foul detection logic here as rules are implemented
                # This is a simplified implementation for now

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
