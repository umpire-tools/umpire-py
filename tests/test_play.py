from umpire import (
    FieldAvailability,
    FieldDef,
    Foul,
    umpire,
)


def test_play_no_changes() -> None:
    """Test play method with no changes in availability."""
    fields = {
        "email": FieldDef(required=True),
        "name": FieldDef(required=False),
    }
    u = umpire(fields)

    # Same before and after states
    before = {
        "email": FieldAvailability(required=True),
        "name": FieldAvailability(required=False),
    }
    after = {
        "email": FieldAvailability(required=True),
        "name": FieldAvailability(required=False),
    }
    values = {"email": "test@example.com"}

    fouls = u.play(before, after, values)
    assert fouls == []


def test_play_field_becomes_required_with_value() -> None:
    """Test play method when field becomes required but has a value."""
    fields = {
        "email": FieldDef(required=True),
    }
    u = umpire(fields)

    # Field becomes required but has a value
    before = {
        "email": FieldAvailability(required=False),
    }
    after = {
        "email": FieldAvailability(required=True),
    }
    values = {"email": "test@example.com"}

    fouls = u.play(before, after, values)
    assert fouls == []  # No foul because field has a value


def test_play_field_becomes_required_without_value() -> None:
    """Test play method when field becomes required and has no value."""
    fields = {
        "email": FieldDef(required=True),
    }
    u = umpire(fields)

    # Field becomes required and has no value
    before = {
        "email": FieldAvailability(required=False),
    }
    after = {
        "email": FieldAvailability(required=True),
    }
    values = {}  # No email value

    fouls = u.play(before, after, values)
    assert len(fouls) == 1
    assert isinstance(fouls[0], Foul)
    assert fouls[0].field == "email"
    assert "became required" in fouls[0].reason


def test_play_multiple_fields() -> None:
    """Test play method with multiple fields."""
    fields = {
        "email": FieldDef(required=True),
        "name": FieldDef(required=False),
        "age": FieldDef(required=True),
    }
    u = umpire(fields)

    # Mix of changes
    before = {
        "email": FieldAvailability(required=False),
        "name": FieldAvailability(required=False),
        "age": FieldAvailability(required=False),
    }
    after = {
        "email": FieldAvailability(required=True),
        "name": FieldAvailability(required=False),
        "age": FieldAvailability(required=True),
    }
    values = {"email": "test@example.com"}  # email has value, age doesn't

    fouls = u.play(before, after, values)
    assert len(fouls) == 1  # Only age should generate a foul
    assert fouls[0].field == "age"
    assert "became required" in fouls[0].reason
