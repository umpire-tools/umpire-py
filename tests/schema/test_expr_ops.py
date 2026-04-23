"""Tests for expression compiler."""

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

    # Test with non-list condition (should return False)
    result = predicate({"plan_id": "pro"}, {"valid_plans": "not_a_list"})
    assert result is False
