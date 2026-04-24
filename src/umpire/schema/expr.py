"""Expression compiler for Umpire JSON expressions."""

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, cast

from ..types import Conditions, Values

Predicate = Callable[[Values, Conditions], bool]


class ExpressionCompiler:
    """Compiler for Umpire expressions."""

    def __init__(
        self,
        field_names: Iterable[str] | None = None,
        condition_names: Iterable[str] | None = None,
    ) -> None:
        """Initialize the expression compiler."""
        self._field_names = set(field_names) if field_names is not None else None
        self._condition_names = set(condition_names) if condition_names is not None else None

    def compile_cond(self, condition_name: str) -> Predicate:
        """Compile a condition truthy check expression."""
        self._assert_condition(condition_name)

        def predicate(values: Values, conditions: Conditions) -> bool:
            return bool(conditions.get(condition_name))

        return predicate

    def compile_cond_eq(self, condition_name: str, value: Any) -> Predicate:
        """Compile a condition scalar equals static value expression."""
        self._assert_condition(condition_name)

        def predicate(values: Values, conditions: Conditions) -> bool:
            return bool(conditions.get(condition_name) == value)

        return predicate

    def compile_cond_in(self, condition_name: str, values_list: Sequence[Any]) -> Predicate:
        """Compile a condition scalar in static list expression."""
        self._assert_condition(condition_name)

        def predicate(values: Values, conditions: Conditions) -> bool:
            return bool(conditions.get(condition_name) in values_list)

        return predicate

    def compile_field_in_cond(self, field_name: str, condition_name: str) -> Predicate:
        """Compile a field scalar in condition-provided dynamic list expression."""
        self._assert_field(field_name)
        self._assert_condition(condition_name)

        def predicate(values: Values, conditions: Conditions) -> bool:
            condition_list = conditions.get(condition_name)
            if condition_list is None:
                return False
            if not isinstance(condition_list, Sequence) or isinstance(condition_list, (str, bytes)):
                raise ValueError(
                    f'Runtime condition "{condition_name}" must be an array for fieldInCond'
                )
            return bool(values.get(field_name) in condition_list)

        return predicate

    def compile_expr(self, expression: Mapping[str, Any]) -> Predicate:
        """Compile a JSON expression object."""
        op = expression.get("op")
        if not isinstance(op, str):
            raise ValueError("Expression must include a string op")

        if op == "cond":
            return self.compile_cond(_string(expression, "condition"))
        if op == "condEq":
            return self.compile_cond_eq(_string(expression, "condition"), expression.get("value"))
        if op == "condIn":
            return self.compile_cond_in(
                _string(expression, "condition"), _sequence(expression, "values")
            )
        if op == "fieldInCond":
            return self.compile_field_in_cond(
                _string(expression, "field"), _string(expression, "condition")
            )
        if op == "present":
            field = _string(expression, "field")
            self._assert_field(field)
            return lambda values, conditions: values.get(field) is not None
        if op == "absent":
            field = _string(expression, "field")
            self._assert_field(field)
            return lambda values, conditions: values.get(field) is None
        if op == "truthy":
            field = _string(expression, "field")
            self._assert_field(field)
            return lambda values, conditions: bool(values.get(field))
        if op == "falsy":
            field = _string(expression, "field")
            self._assert_field(field)
            return lambda values, conditions: not values.get(field)
        if op == "eq":
            field = _string(expression, "field")
            self._assert_field(field)
            return lambda values, conditions: values.get(field) == expression.get("value")
        if op == "neq":
            field = _string(expression, "field")
            self._assert_field(field)
            return lambda values, conditions: values.get(field) != expression.get("value")
        if op == "in":
            field = _string(expression, "field")
            values_list = _sequence(expression, "values")
            self._assert_field(field)
            return lambda values, conditions: values.get(field) in values_list
        if op == "notIn":
            field = _string(expression, "field")
            values_list = _sequence(expression, "values")
            self._assert_field(field)
            return lambda values, conditions: values.get(field) not in values_list
        if op == "and":
            predicates = [self.compile_expr(entry) for entry in _exprs(expression)]
            return lambda values, conditions: all(
                predicate(values, conditions) for predicate in predicates
            )
        if op == "or":
            predicates = [self.compile_expr(entry) for entry in _exprs(expression)]
            return lambda values, conditions: any(
                predicate(values, conditions) for predicate in predicates
            )
        if op == "not":
            predicate = self.compile_expr(_mapping(expression, "expr"))
            return lambda values, conditions: not predicate(values, conditions)

        raise ValueError(f"unknown expression op: {op}")

    def _assert_field(self, field_name: str) -> None:
        if self._field_names is not None and field_name not in self._field_names:
            raise ValueError(f'Unknown field "{field_name}" in expression')

    def _assert_condition(self, condition_name: str) -> None:
        if self._condition_names is not None and condition_name not in self._condition_names:
            raise ValueError(f'Unknown condition "{condition_name}" in expression')


def _string(expression: Mapping[str, Any], key: str) -> str:
    value = expression.get(key)
    if not isinstance(value, str):
        raise ValueError(f'Expression "{key}" must be a string')
    return value


def _mapping(expression: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = expression.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f'Expression "{key}" must be an object')
    return value


def _sequence(expression: Mapping[str, Any], key: str) -> Sequence[Any]:
    value = expression.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f'Expression "{key}" must be an array')
    return value


def _exprs(expression: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    exprs = _sequence(expression, "exprs")
    if not all(isinstance(entry, Mapping) for entry in exprs):
        raise ValueError('Expression "exprs" must contain objects')
    return cast(Sequence[Mapping[str, Any]], exprs)
