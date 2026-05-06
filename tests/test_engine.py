import math

from umpire import (
    FieldAvailability,
    FieldDef,
    umpire,
)


def test_umpire_check_empty_conditions() -> None:
    """Test Umpire.check() with empty conditions."""
    fields = {
        "email": FieldDef(required=True),
        "name": FieldDef(required=False, default_value="Anonymous"),
    }
    u = umpire(fields)

    # Test with empty values and conditions
    result = u.check({})
    assert "email" in result
    assert "name" in result
    assert isinstance(result["email"], FieldAvailability)
    assert isinstance(result["name"], FieldAvailability)


def test_umpire_check_with_values() -> None:
    """Test Umpire.check() with provided values."""
    fields = {
        "email": FieldDef(required=True),
        "name": FieldDef(required=False, default_value="Anonymous"),
    }
    u = umpire(fields)

    # Test with some values
    result = u.check({"email": "test@example.com"})
    assert "email" in result
    assert "name" in result

    # Requiredness is structural; satisfaction tracks whether a value is present.
    assert result["email"].required is True
    assert result["email"].satisfied is True

    # Name field should not be required because it has a default
    assert result["name"].required is False


def test_umpire_check_with_conditions() -> None:
    """Test Umpire.check() with conditions."""
    fields = {
        "email": FieldDef(required=True),
        "name": FieldDef(required=False),
        "company": FieldDef(required=False),
    }
    u = umpire(fields)

    # Test with conditions
    result = u.check({"email": "test@example.com"}, {"is_business": True})
    assert "email" in result
    assert "name" in result
    assert "company" in result


def test_umpire_check_field_availability_defaults() -> None:
    """Test that fields get correct default availability."""
    fields = {
        "required_field": FieldDef(required=True),
        "optional_field": FieldDef(required=False),
        "default_field": FieldDef(required=False, default_value="default"),
    }
    u = umpire(fields)

    result = u.check({})

    # Required field without value should be required
    assert result["required_field"].required is True

    # Optional field without value should not be required
    assert result["optional_field"].required is False

    # Field with default should not be required
    assert result["default_field"].required is False


def test_nan_not_satisfied_for_number_strategy() -> None:
    """float('nan') should not be considered satisfied for NUMBER isEmpty strategy."""
    from umpire.types import IsEmptyStrategy

    fields = {"age": FieldDef(is_empty=IsEmptyStrategy.NUMBER)}
    u = umpire(fields)
    result = u.check({"age": float("nan")})
    assert result["age"].satisfied is False
