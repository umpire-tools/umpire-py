"""Umpire engine implementation."""

from collections.abc import Mapping, Sequence

from .types import Conditions, FieldAvailability, FieldDef, Rule, Values


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
