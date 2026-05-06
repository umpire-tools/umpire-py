from umpire import FieldDef, umpire
from umpire.rules import check, disables, enabled_when, fair_when, one_of, requires
from umpire.types import CheckError


def _always(_values, _conditions):
    return True


def _never(_values, _conditions):
    return False


def _error_op(value, field_name):
    return CheckError(field=field_name, reason="invalid email format")


def test_challenge_unknown_field_raises() -> None:
    u = umpire({"email": FieldDef()})
    try:
        u.challenge("unknown", {})
        raise AssertionError("Expected ValueError")
    except ValueError as e:
        assert "Unknown field" in str(e)


def test_challenge_requires_missing_dependency() -> None:
    u = umpire(
        {"a": FieldDef(), "b": FieldDef()},
        [requires("a", "b")],
    )
    trace = u.challenge("a", {})
    assert trace.field == "a"
    assert trace.enabled is False
    assert len(trace.direct_reasons) == 1
    reason = trace.direct_reasons[0]
    assert reason.rule == "requires"
    assert reason.passed is False
    assert "b" in (reason.reason or "")
    assert reason.details["dependency"] == "b"
    assert reason.details["dependency_satisfied"] is False
    assert len(trace.transitive_deps) == 1
    assert trace.transitive_deps[0]["field"] == "b"


def test_challenge_requires_satisfied_dependency() -> None:
    u = umpire(
        {"a": FieldDef(), "b": FieldDef()},
        [requires("a", "b")],
    )
    trace = u.challenge("a", {"b": "present"})
    assert trace.enabled is True
    assert len(trace.direct_reasons) == 1
    assert trace.direct_reasons[0].passed is True
    assert len(trace.transitive_deps) == 0


def test_challenge_enabled_when_fails() -> None:
    u = umpire(
        {"a": FieldDef()},
        [enabled_when("a", _never, reason="only when active")],
    )
    trace = u.challenge("a", {})
    assert trace.enabled is False
    assert len(trace.direct_reasons) == 1
    reason = trace.direct_reasons[0]
    assert reason.rule == "enabled_when"
    assert reason.passed is False
    assert reason.reason == "only when active"
    assert reason.details["predicate_result"] is False


def test_challenge_enabled_when_passes() -> None:
    u = umpire(
        {"a": FieldDef()},
        [enabled_when("a", _always)],
    )
    trace = u.challenge("a", {})
    assert trace.enabled is True
    assert len(trace.direct_reasons) == 1
    assert trace.direct_reasons[0].passed is True


def test_challenge_fair_when_fails() -> None:
    u = umpire(
        {"a": FieldDef()},
        [fair_when("a", _never, reason="selection expired")],
    )
    trace = u.challenge("a", {"a": "present"})
    assert trace.fair is False
    assert len(trace.direct_reasons) == 1
    reason = trace.direct_reasons[0]
    assert reason.rule == "fair_when"
    assert reason.passed is False
    assert reason.reason == "selection expired"
    assert reason.details["predicate_result"] is False


def test_challenge_disables_active() -> None:
    """Source satisfied: disables rule is active, so target sees passed=False."""
    u = umpire(
        {"source": FieldDef(), "target": FieldDef()},
        [disables("source", "target", reason="overridden")],
    )
    trace = u.challenge("target", {"source": "present"})
    assert trace.enabled is False
    assert len(trace.direct_reasons) == 1
    reason = trace.direct_reasons[0]
    assert reason.rule == "disables"
    assert reason.passed is False
    assert reason.reason == "overridden"
    assert reason.details["source_active"] is True
    assert reason.details["source_satisfied"] is True


def test_challenge_one_of_conflict() -> None:
    """Field 'b' is not in the active branch, so one_of resolution shows conflict."""
    u = umpire(
        {"a": FieldDef(), "b": FieldDef()},
        [one_of("group", {"branch_a": ["a"], "branch_b": ["b"]})],
    )
    trace = u.challenge("b", {"a": "present"})
    assert trace.enabled is False
    assert trace.one_of_resolution is not None
    assert trace.one_of_resolution["active_branch"] == "branch_a"
    assert trace.one_of_resolution["this_branch"] == "branch_b"
    assert len(trace.direct_reasons) == 1
    reason = trace.direct_reasons[0]
    assert reason.rule == "one_of"
    assert reason.passed is False


def test_challenge_check_error() -> None:
    u = umpire(
        {"email": FieldDef()},
        [check("email", _error_op)],
    )
    trace = u.challenge("email", {"email": "bad"})
    assert len(trace.direct_reasons) == 1
    reason = trace.direct_reasons[0]
    assert reason.rule == "check"
    assert reason.passed is False
    assert "invalid email format" in (reason.reason or "")
    assert reason.details["error"] == "invalid email format"
