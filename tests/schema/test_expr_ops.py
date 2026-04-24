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
