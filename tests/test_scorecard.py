"""Tests for Umpire.scorecard()."""

from umpire import FieldDef, umpire
from umpire.rules import enabled_when, requires


def test_scorecard_no_previous_values() -> None:
    u = umpire({"email": FieldDef(), "name": FieldDef()})
    card = u.scorecard({"email": "test@test.com"})
    assert card.fouls == ()
    assert card.changed_fields == ()
    assert card.cascading_fields == ()
    assert "email" in card.fields
    assert card.fields["email"].value == "test@test.com"


def test_scorecard_field_has_incoming_edges() -> None:
    u = umpire(
        {"a": FieldDef(), "b": FieldDef()},
        [requires("a", "b")],
    )
    card = u.scorecard({"b": "ok"})
    field_a = card.fields["a"]
    assert len(field_a.incoming) == 1
    assert field_a.incoming[0].source == "b"
    assert field_a.incoming[0].kind == "requires"


def test_scorecard_field_has_value_and_flags() -> None:
    u = umpire(
        {"a": FieldDef(required=True), "b": FieldDef()},
    )
    card = u.scorecard({"a": "hello"})
    field_a = card.fields["a"]
    assert field_a.value == "hello"
    assert field_a.present is True
    assert field_a.satisfied is True
    assert field_a.enabled is True
    assert field_a.fair is True
    assert field_a.required is True
    field_b = card.fields["b"]
    assert field_b.value is None
    assert field_b.present is False
    assert field_b.satisfied is False


def test_scorecard_changed_fields_detected() -> None:
    u = umpire({"email": FieldDef(), "name": FieldDef()})
    card = u.scorecard(
        {"email": "new@test.com", "name": "same"},
        previous_values={"email": "old@test.com", "name": "same"},
    )
    assert card.changed_fields == ("email",)


def test_scorecard_fouls_on_disabled_field() -> None:
    u = umpire(
        {"a": FieldDef(), "b": FieldDef()},
        [requires("a", "b")],
    )
    card = u.scorecard(
        {"a": "value", "b": None},
        previous_values={"a": "value", "b": "ok"},
    )
    assert len(card.fouls) == 1
    assert card.fouls[0].field == "a"
    assert "a" in card.fouled_fields
    assert "a" in card.fouls_by_field
    assert card.fouls_by_field["a"].field == "a"
    # field "a" should show the foul and be changed=False (value didn't change), cascaded=True
    assert card.fields["a"].foul is not None
    assert card.fields["a"].foul.field == "a"
    assert card.fields["a"].changed is False


def test_scorecard_cascading_fields() -> None:
    u = umpire(
        {"a": FieldDef(), "b": FieldDef()},
        [requires("a", "b")],
    )
    card = u.scorecard(
        {"a": "value", "b": None},
        previous_values={"a": "value", "b": "ok"},
    )
    assert card.fouled_fields == ("a",)
    assert card.directly_fouled_fields == ()
    assert "a" in card.cascading_fields
    assert "b" not in card.cascading_fields
    # a was cascaded because its value didn't change but availability did
    assert card.fields["a"].cascaded is True
    assert card.fields["b"].cascaded is False


def test_scorecard_include_challenge() -> None:
    u = umpire(
        {"a": FieldDef()},
        [enabled_when("a", lambda v, c: False, reason="never")],
    )
    card_no = u.scorecard({"a": "val"}, include_challenge=False)
    assert card_no.fields["a"].trace is None

    card_yes = u.scorecard({"a": "val"}, include_challenge=True)
    trace = card_yes.fields["a"].trace
    assert trace is not None
    assert trace.field == "a"
    assert trace.enabled is False  # enabled_when predicate returned False
    assert len(trace.direct_reasons) >= 1
