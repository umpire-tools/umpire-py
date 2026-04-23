"""Umpire engine implementation."""

from collections.abc import Mapping, Sequence

from .rules import (
    CheckRule,
    EnabledWhenRule,
    FairWhenRule,
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
