"""Umpire engine implementation."""

from collections.abc import Mapping, Sequence

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
        result = {}
        for field_name, field_def in self._fields.items():
            # A field is required if:
            # 1. It's marked as required in its definition
            # 2. It doesn't have a value provided AND doesn't have a default value
            required = (
                field_def.required and field_name not in values and field_def.default_value is None
            )
            result[field_name] = FieldAvailability(required=required)

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
