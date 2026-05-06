import pytest

from umpire import (
    FieldDef,
    umpire,
)


def test_init_defaults() -> None:
    """Test init() returns default values for all fields."""
    fields = {
        "email": FieldDef(default_value="default@example.com"),
        "name": FieldDef(default_value="Anonymous"),
        "age": FieldDef(default_value=0),
    }
    u = umpire(fields)
    result = u.init()
    assert result == {
        "email": "default@example.com",
        "name": "Anonymous",
        "age": 0,
    }


def test_init_overrides() -> None:
    """Test init() applies overrides."""
    fields = {
        "email": FieldDef(default_value="default@example.com"),
        "name": FieldDef(default_value="Anonymous"),
    }
    u = umpire(fields)
    result = u.init(overrides={"email": "override@example.com"})
    assert result == {"email": "override@example.com", "name": "Anonymous"}


def test_init_none_override() -> None:
    """Test init() preserves None override."""
    fields = {
        "email": FieldDef(default_value="default@example.com"),
        "name": FieldDef(default_value="Anonymous"),
    }
    u = umpire(fields)
    result = u.init(overrides={"email": None})
    assert result == {"email": None, "name": "Anonymous"}


def test_init_multiple_overrides() -> None:
    """Test init() with multiple overrides in one call."""
    fields = {
        "email": FieldDef(default_value="default@example.com"),
        "name": FieldDef(default_value="Anonymous"),
    }
    u = umpire(fields)
    result = u.init(overrides={"email": "a", "name": "b"})
    assert result == {"email": "a", "name": "b"}


def test_init_empty_overrides() -> None:
    """Test init() with empty overrides dict returns defaults."""
    fields = {
        "email": FieldDef(default_value="default@example.com"),
        "name": FieldDef(default_value="Anonymous"),
    }
    u = umpire(fields)
    result = u.init(overrides={})
    assert result == {"email": "default@example.com", "name": "Anonymous"}


def test_init_unknown_field_raises() -> None:
    """Test init() raises ValueError for unknown field."""
    fields = {
        "email": FieldDef(),
    }
    u = umpire(fields)
    with pytest.raises(ValueError, match="Unknown field: unknown"):
        u.init(overrides={"unknown": "val"})
