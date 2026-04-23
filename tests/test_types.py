from umpire import (
    CheckError,
    FieldAvailability,
    FieldDef,
    Foul,
    IsEmptyStrategy,
    umpire,
)


def test_field_def_creation() -> None:
    """Test FieldDef creation with default values."""
    field_def = FieldDef()
    assert field_def.required is False
    assert field_def.default_value is None
    assert field_def.is_empty == IsEmptyStrategy.PRESENT


def test_field_def_creation_with_values() -> None:
    """Test FieldDef creation with custom values."""
    field_def = FieldDef(required=True, default_value="test", is_empty=IsEmptyStrategy.STRING)
    assert field_def.required is True
    assert field_def.default_value == "test"
    assert field_def.is_empty == IsEmptyStrategy.STRING


def test_field_availability_creation() -> None:
    """Test FieldAvailability creation with default values."""
    availability = FieldAvailability()
    assert availability.enabled is True
    assert availability.required is False
    assert availability.fair is True
    assert availability.check_errors == ()


def test_field_availability_creation_with_values() -> None:
    """Test FieldAvailability creation with custom values."""
    error = CheckError("field1", "Invalid value")
    availability = FieldAvailability(
        enabled=False, required=True, fair=False, check_errors=(error,)
    )
    assert availability.enabled is False
    assert availability.required is True
    assert availability.fair is False
    assert availability.check_errors == (error,)


def test_check_error_creation() -> None:
    """Test CheckError creation."""
    error = CheckError("field1", "This field is required")
    assert error.field == "field1"
    assert error.reason == "This field is required"


def test_foul_creation() -> None:
    """Test Foul creation."""
    foul = Foul("field1", "This field became invalid", "suggested_value")
    assert foul.field == "field1"
    assert foul.reason == "This field became invalid"
    assert foul.suggested_value == "suggested_value"


def test_umpire_constructor() -> None:
    """Test umpire constructor function."""
    fields = {
        "email": FieldDef(required=True),
        "name": FieldDef(required=False, default_value="Anonymous"),
    }
    u = umpire(fields)
    assert u is not None


def test_umpire_initialization() -> None:
    """Test Umpire class initialization."""
    fields = {
        "email": FieldDef(required=True),
        "name": FieldDef(required=False, default_value="Anonymous"),
    }
    u = umpire(fields)
    assert u is not None
    # Note: We can't directly access private attributes in tests, but we can test the behavior
