"""Tests for expression compiler."""

import pytest

from umpire.schema.expr import ExpressionCompiler


def test_compile_cond() -> None:
    """Test compiling condition truthy check expression."""
    compiler = ExpressionCompiler()
    predicate = compiler.compile_cond("is_admin")

    # Test with truthy condition
    result = predicate({}, {"is_admin": True})
    assert result is True

    # Test with falsy condition
    result = predicate({}, {"is_admin": False})
    assert result is False

    # Test with missing condition
    result = predicate({}, {})
    assert result is False


def test_compile_cond_eq() -> None:
    """Test compiling condition scalar equals static value expression."""
    compiler = ExpressionCompiler()
    predicate = compiler.compile_cond_eq("user_type", "admin")

    # Test with matching value
    result = predicate({}, {"user_type": "admin"})
    assert result is True

    # Test with non-matching value
    result = predicate({}, {"user_type": "user"})
    assert result is False

    # Test with missing condition
    result = predicate({}, {})
    assert result is False


def test_compile_cond_in() -> None:
    """Test compiling condition scalar in static list expression."""
    compiler = ExpressionCompiler()
    predicate = compiler.compile_cond_in("role", ["admin", "moderator"])

    # Test with value in list
    result = predicate({}, {"role": "admin"})
    assert result is True

    # Test with value not in list
    result = predicate({}, {"role": "user"})
    assert result is False

    # Test with missing condition
    result = predicate({}, {})
    assert result is False


def test_compile_field_in_cond() -> None:
    """Test compiling field scalar in condition-provided dynamic list expression."""
    compiler = ExpressionCompiler()
    predicate = compiler.compile_field_in_cond("plan_id", "valid_plans")

    # Test with field value in condition list
    result = predicate({"plan_id": "pro"}, {"valid_plans": ["basic", "pro", "enterprise"]})
    assert result is True

    # Test with field value not in condition list
    result = predicate({"plan_id": "invalid"}, {"valid_plans": ["basic", "pro", "enterprise"]})
    assert result is False

    # Test with missing condition list
    result = predicate({"plan_id": "pro"}, {})
    assert result is False

    # Test with missing field value
    result = predicate({}, {"valid_plans": ["basic", "pro", "enterprise"]})
    assert result is False

    with pytest.raises(ValueError, match="must be an array"):
        predicate({"plan_id": "pro"}, {"valid_plans": "not_a_list"})


def test_compile_expr_rejects_unknown_field() -> None:
    """Expression validation should catch bad field references."""
    compiler = ExpressionCompiler(field_names={"email"})

    with pytest.raises(ValueError, match="Unknown field"):
        compiler.compile_expr({"op": "present", "field": "missing"})


def test_compile_expr_rejects_unknown_condition() -> None:
    """Expression validation should catch bad condition references."""
    compiler = ExpressionCompiler(condition_names={"isAdmin"})

    with pytest.raises(ValueError, match="Unknown condition"):
        compiler.compile_expr({"op": "cond", "condition": "missing"})


def test_compile_expr_contains_matches_array_elements() -> None:
    """contains finds one primitive in an array-valued field."""
    compiler = ExpressionCompiler(field_names={"tags"})
    predicate = compiler.compile_expr({"op": "contains", "field": "tags", "value": "lefty"})

    assert predicate({"tags": ["lefty", "righty"]}, {}) is True
    assert predicate({"tags": []}, {}) is False
    assert predicate({"tags": ["righty"]}, {}) is False


@pytest.mark.parametrize(
    ("field_value", "expected"),
    [(None, False), ("lefty", False), ({"lefty": 1}, False), (7, False)],
    ids=["null", "scalar", "object", "number"],
)
def test_compile_expr_contains_requires_an_array(field_value: object, expected: bool) -> None:
    """A value that is not an array holds no elements."""
    compiler = ExpressionCompiler(field_names={"tags"})
    predicate = compiler.compile_expr({"op": "contains", "field": "tags", "value": "lefty"})

    assert predicate({"tags": field_value}, {}) is expected


def test_compile_expr_contains_rejects_missing_value() -> None:
    """contains needs one primitive to look for."""
    compiler = ExpressionCompiler(field_names={"tags"})

    with pytest.raises(ValueError, match="value"):
        compiler.compile_expr({"op": "contains", "field": "tags"})


_MEMBERSHIP_CASES: dict[str, tuple[dict[str, object], dict[str, object], bool]] = {
    "contains-boolean-is-not-one": (
        {"op": "contains", "field": "f", "value": True},
        {"f": [1]},
        False,
    ),
    "contains-one-is-not-boolean": (
        {"op": "contains", "field": "f", "value": 1},
        {"f": [True]},
        False,
    ),
    "contains-zero-is-not-false": (
        {"op": "contains", "field": "f", "value": 0},
        {"f": [False]},
        False,
    ),
    "contains-numbers-compare-by-value": (
        {"op": "contains", "field": "f", "value": 22},
        {"f": [22.0]},
        True,
    ),
    "contains-string-is-not-number": (
        {"op": "contains", "field": "f", "value": "22"},
        {"f": [22]},
        False,
    ),
    "contains-string-field-is-not-an-array": (
        {"op": "contains", "field": "f", "value": "l"},
        {"f": "lefty"},
        False,
    ),
    "contains-null-matches-null": (
        {"op": "contains", "field": "f", "value": None},
        {"f": [None]},
        True,
    ),
    "in-one-is-not-boolean": ({"op": "in", "field": "f", "values": [1]}, {"f": True}, False),
    "not-in-one-is-not-boolean": (
        {"op": "notIn", "field": "f", "values": [1]},
        {"f": True},
        True,
    ),
    "eq-one-is-not-boolean": ({"op": "eq", "field": "f", "value": 1}, {"f": True}, False),
    "neq-one-is-not-boolean": ({"op": "neq", "field": "f", "value": 1}, {"f": True}, True),
}

_CONDITION_CASES: dict[str, tuple[dict[str, object], dict[str, object], bool]] = {
    "cond-eq-one-is-not-boolean": (
        {"op": "condEq", "condition": "flag", "value": 1},
        {"flag": True},
        False,
    ),
    "cond-in-one-is-not-boolean": (
        {"op": "condIn", "condition": "flag", "values": [1]},
        {"flag": True},
        False,
    ),
    "field-in-cond-one-is-not-boolean": (
        {"op": "fieldInCond", "field": "f", "condition": "ids"},
        {"f": True, "ids": [1]},
        False,
    ),
}


_CONDITION_TYPES = {"flag": "boolean", "ids": "number[]"}


@pytest.mark.parametrize(
    ("expression", "values", "expected"),
    list(_MEMBERSHIP_CASES.values()),
    ids=list(_MEMBERSHIP_CASES),
)
def test_membership_and_equality_ops_do_not_coerce(
    expression: dict[str, object], values: dict[str, object], expected: bool
) -> None:
    """Field ops compare like JSON, not like Python's `True == 1`."""
    compiler = ExpressionCompiler(field_names={"f"})

    assert compiler.compile_expr(expression)(values, {}) is expected


@pytest.mark.parametrize(
    ("expression", "conditions", "expected"),
    list(_CONDITION_CASES.values()),
    ids=list(_CONDITION_CASES),
)
def test_condition_ops_do_not_coerce(
    expression: dict[str, object], conditions: dict[str, object], expected: bool
) -> None:
    """Condition ops compare like JSON, not like Python's `True == 1`."""
    compiler = ExpressionCompiler(
        field_names={"f"},
        condition_names=_CONDITION_TYPES.keys(),
        condition_types=_CONDITION_TYPES,
    )

    assert compiler.compile_expr(expression)({}, conditions) is expected


def test_compile_expr_supports_boolean_composition() -> None:
    """JSON expressions can compose smaller predicates."""
    compiler = ExpressionCompiler(field_names={"email"}, condition_names={"isAdmin"})
    predicate = compiler.compile_expr(
        {
            "op": "or",
            "exprs": [
                {"op": "present", "field": "email"},
                {"op": "cond", "condition": "isAdmin"},
            ],
        }
    )

    assert predicate({}, {"isAdmin": False}) is False
    assert predicate({}, {"isAdmin": True}) is True
    assert predicate({"email": "a@example.com"}, {"isAdmin": False}) is True
