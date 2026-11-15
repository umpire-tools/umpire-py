"""Expression compiler for Umpire JSON expressions."""

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, cast

from ..checks import check_ops
from ..types import Conditions, Values, is_json_primitive
from .validate import _ARRAY_CONDITION_TYPES

Predicate = Callable[[Values, Conditions], bool]


class ExpressionCompiler:
    """Compiler for Umpire expressions."""

    def __init__(
        self,
        field_names: Iterable[str] | None = None,
        condition_names: Iterable[str] | None = None,
        condition_types: Mapping[str, str] | None = None,
    ) -> None:
        """Initialize the expression compiler."""
        self._field_names = set(field_names) if field_names is not None else None
        self._condition_names = set(condition_names) if condition_names is not None else None
        self._condition_types = dict(condition_types or {})

    def compile_cond(self, condition_name: str) -> Predicate:
        """Compile a condition truthy check expression."""
        self._assert_condition(condition_name)

        def predicate(values: Values, conditions: Conditions) -> bool:
            return bool(self._condition_value(condition_name, conditions))

        return predicate

    def compile_cond_eq(self, condition_name: str, value: Any) -> Predicate:
        """Compile a condition scalar equals static value expression."""
        self._assert_condition(condition_name)

        def predicate(values: Values, conditions: Conditions) -> bool:
            return _json_equal(self._condition_value(condition_name, conditions), value)

        return predicate

    def compile_cond_in(self, condition_name: str, values_list: Sequence[Any]) -> Predicate:
        """Compile a condition scalar in static list expression."""
        self._assert_condition(condition_name)

        def predicate(values: Values, conditions: Conditions) -> bool:
            return _json_in(self._condition_value(condition_name, conditions), values_list)

        return predicate

    def compile_field_in_cond(self, field_name: str, condition_name: str) -> Predicate:
        """Compile a field scalar in condition-provided dynamic list expression."""
        self._assert_field(field_name)
        self._assert_condition(condition_name)
        condition_type = self._condition_types.get(condition_name)
        if condition_type is not None and condition_type not in _ARRAY_CONDITION_TYPES:
            raise ValueError(
                f'"fieldInCond" requires an array condition, '
                f'but "{condition_name}" is "{condition_type}"'
            )

        def predicate(values: Values, conditions: Conditions) -> bool:
            condition_list = self._condition_value(condition_name, conditions)
            if condition_list is None:
                return False
            if not isinstance(condition_list, Sequence) or isinstance(condition_list, (str, bytes)):
                raise ValueError(
                    f'Runtime condition "{condition_name}" must be an array for fieldInCond'
                )
            return _json_in(values.get(field_name), condition_list)

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
            literal = expression.get("value")
            return lambda values, conditions: _json_equal(values.get(field), literal)
        if op == "neq":
            field = _string(expression, "field")
            self._assert_field(field)
            literal = expression.get("value")
            return lambda values, conditions: not _json_equal(values.get(field), literal)
        if op == "gt":
            field = _string(expression, "field")
            self._assert_field(field)
            return lambda values, conditions: (
                _number_value(values.get(field)) > _number_literal(expression)
            )
        if op == "gte":
            field = _string(expression, "field")
            self._assert_field(field)
            return lambda values, conditions: (
                _number_value(values.get(field)) >= _number_literal(expression)
            )
        if op == "lt":
            field = _string(expression, "field")
            self._assert_field(field)
            return lambda values, conditions: (
                _number_value(values.get(field)) < _number_literal(expression)
            )
        if op == "lte":
            field = _string(expression, "field")
            self._assert_field(field)
            return lambda values, conditions: (
                _number_value(values.get(field)) <= _number_literal(expression)
            )
        if op == "in":
            field = _string(expression, "field")
            values_list = _sequence(expression, "values")
            self._assert_field(field)
            return lambda values, conditions: _json_in(values.get(field), values_list)
        if op == "notIn":
            field = _string(expression, "field")
            values_list = _sequence(expression, "values")
            self._assert_field(field)
            return lambda values, conditions: not _json_in(values.get(field), values_list)
        if op == "contains":
            field = _string(expression, "field")
            self._assert_field(field)
            literal = _primitive(expression, "value")
            return lambda values, conditions: _json_contains(values.get(field), literal)
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
        if op == "check":
            field = _string(expression, "field")
            self._assert_field(field)
            op_obj = _check_op(_mapping(expression, "check"))
            return lambda values, conditions: op_obj(values.get(field), field) is None

        raise ValueError(f"unknown expression op: {op}")

    def _assert_field(self, field_name: str) -> None:
        if self._field_names is not None and field_name not in self._field_names:
            raise ValueError(f'Unknown field "{field_name}" in expression')

    def _assert_condition(self, condition_name: str) -> None:
        if self._condition_names is not None and condition_name not in self._condition_names:
            raise ValueError(f'Unknown condition "{condition_name}" in expression')

    def _condition_value(self, condition_name: str, conditions: Conditions) -> Any:
        if self._condition_names is not None and condition_name not in conditions:
            raise ValueError(f'Missing runtime condition "{condition_name}"')
        return conditions.get(condition_name)


def _json_equal(left: Any, right: Any) -> bool:
    """Compare two values the way JSON does, without Python's coercions.

    ``True == 1`` and ``False == 0`` in Python, and a dict would answer a
    membership test on its keys; neither matches JSON equality.
    """
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return bool(left == right)
    if isinstance(left, str) and isinstance(right, str):
        return left == right
    return False


def _json_in(value: Any, candidates: Sequence[Any]) -> bool:
    """Return whether a value equals one of the candidates under JSON equality."""
    return any(_json_equal(value, candidate) for candidate in candidates)


def _json_contains(value: Any, literal: Any) -> bool:
    """Return whether an array-valued field holds ``literal``."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return False
    return _json_in(literal, value)


def _number_value(value: Any) -> int | float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return float("nan")
    return value


def _number_literal(expression: Mapping[str, Any]) -> int | float:
    value = expression.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError('Expression "value" must be a number')
    return value


def _check_op(spec: Mapping[str, Any]) -> Any:
    op = _string(spec, "op")
    if op == "email":
        return check_ops.email()
    if op == "url":
        return check_ops.url()
    if op == "matches":
        return check_ops.matches(_string(spec, "pattern"))
    if op == "minLength":
        return check_ops.min_length(_integer(spec, "value"))
    if op == "maxLength":
        return check_ops.max_length(_integer(spec, "value"))
    if op == "min":
        return check_ops.min_value(_number(spec, "value"))
    if op == "max":
        return check_ops.max_value(_number(spec, "value"))
    if op == "range":
        return check_ops.range_value(_number(spec, "min"), _number(spec, "max"))
    if op == "integer":
        return check_ops.integer()
    raise ValueError(f"unknown check op: {op}")


def _string(expression: Mapping[str, Any], key: str) -> str:
    value = expression.get(key)
    if not isinstance(value, str):
        raise ValueError(f'Expression "{key}" must be a string')
    return value


def _primitive(expression: Mapping[str, Any], key: str) -> Any:
    if key not in expression or not is_json_primitive(expression[key]):
        raise ValueError(f'Expression "{key}" must be a JSON primitive')
    return expression[key]


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


def _number(expression: Mapping[str, Any], key: str) -> int | float:
    value = expression.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f'Expression "{key}" must be a number')
    return value


def _integer(expression: Mapping[str, Any], key: str) -> int:
    value = expression.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f'Expression "{key}" must be an integer')
    return value
