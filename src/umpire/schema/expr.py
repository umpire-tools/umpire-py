"""Expression compiler for Umpire."""

from collections.abc import Callable
from typing import Any

from ..types import Conditions, Values


class ExpressionCompiler:
    """Compiler for Umpire expressions."""

    def __init__(self) -> None:
        """Initialize the expression compiler."""
        pass

    def compile_cond(self, condition_name: str) -> Callable[[Values, Conditions], bool]:
        """Compile a condition truthy check expression."""

        def predicate(values: Values, conditions: Conditions) -> bool:
            condition_value = conditions.get(condition_name)
            return bool(condition_value)

        return predicate

    def compile_cond_eq(
        self, condition_name: str, value: Any
    ) -> Callable[[Values, Conditions], bool]:
        """Compile a condition scalar equals static value expression."""

        def predicate(values: Values, conditions: Conditions) -> bool:
            condition_value = conditions.get(condition_name)
            return bool(condition_value == value)

        return predicate

    def compile_cond_in(
        self, condition_name: str, values_list: list[Any]
    ) -> Callable[[Values, Conditions], bool]:
        """Compile a condition scalar in static list expression."""

        def predicate(values: Values, conditions: Conditions) -> bool:
            condition_value = conditions.get(condition_name)
            return bool(condition_value in values_list)

        return predicate

    def compile_field_in_cond(
        self, field_name: str, condition_name: str
    ) -> Callable[[Values, Conditions], bool]:
        """Compile a field scalar in condition-provided dynamic list expression."""

        def predicate(values: Values, conditions: Conditions) -> bool:
            field_value = values.get(field_name)
            condition_list = conditions.get(condition_name, [])
            if isinstance(condition_list, (list, tuple)):
                return bool(field_value in condition_list)
            return False

        return predicate
