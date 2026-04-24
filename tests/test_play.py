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
    """Required transitions alone should not fabricate reset fouls."""
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
    assert fouls == []


def test_play_recommends_reset_for_newly_disabled_satisfied_value() -> None:
    """play recommends a reset when a field became disabled and still has a value."""
    fields = {
        "email": FieldDef(required=True),
        "discount": FieldDef(default_value=None),
    }
    u = umpire(fields)

    before = {
        "email": FieldAvailability(required=True),
        "discount": FieldAvailability(enabled=True),
    }
    after = {
        "email": FieldAvailability(required=True),
        "discount": FieldAvailability(enabled=False, reason="overridden by coupon"),
    }
    values = {"email": "test@example.com", "discount": "manual-override"}

    fouls = u.play(before, after, values)
    assert fouls == [Foul("discount", "overridden by coupon", None)]


def test_play_recommends_reset_for_newly_foul_satisfied_value() -> None:
    """play recommends a reset when a field became foul and still has a value."""
    fields = {
        "plan": FieldDef(default_value="basic"),
    }
    u = umpire(fields)

    before = {"plan": FieldAvailability(fair=True)}
    after = {"plan": FieldAvailability(fair=False, reason="plan unavailable")}

    fouls = u.play(before, after, {"plan": "enterprise"})

    assert fouls == [Foul("plan", "plan unavailable", "basic")]
