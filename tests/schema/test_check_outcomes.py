"""Availability outcomes for rule forms loaded from a document.

Each case loads a document, then runs ``check()`` twice: once with conditions
that satisfy the rule and once with conditions that do not.
"""

import pytest

from umpire import UmpireSchema, umpire

_REQUIRES_WITH_WHEN = {
    "version": 1,
    "conditions": {"isAdmin": {"type": "boolean"}},
    "fields": {"email": {}, "discount": {}},
    "rules": [
        {
            "type": "requires",
            "field": "discount",
            "when": {"op": "cond", "condition": "isAdmin"},
            "reason": "Admin only",
        }
    ],
}

_REQUIRES_WITH_EXPRESSION_DEPENDENCIES = {
    "version": 1,
    "conditions": {"isAdmin": {"type": "boolean"}},
    "fields": {"email": {}, "coupon": {}},
    "rules": [
        {
            "type": "requires",
            "field": "coupon",
            "dependencies": [{"op": "cond", "condition": "isAdmin"}],
            "reason": "Needs an admin",
        }
    ],
}

_DISABLES_WITH_WHEN = {
    "version": 1,
    "conditions": {"isPaused": {"type": "boolean"}},
    "fields": {"email": {}, "discount": {}},
    "rules": [
        {
            "type": "disables",
            "when": {"op": "cond", "condition": "isPaused"},
            "targets": ["discount"],
            "reason": "Paused",
        }
    ],
}

_OUTCOMES = [
    pytest.param(
        _REQUIRES_WITH_WHEN, "discount", {"isAdmin": True}, True, id="requires-when-satisfied"
    ),
    pytest.param(
        _REQUIRES_WITH_WHEN, "discount", {"isAdmin": False}, False, id="requires-when-unsatisfied"
    ),
    pytest.param(
        _REQUIRES_WITH_EXPRESSION_DEPENDENCIES,
        "coupon",
        {"isAdmin": True},
        True,
        id="requires-dependencies-satisfied",
    ),
    pytest.param(
        _REQUIRES_WITH_EXPRESSION_DEPENDENCIES,
        "coupon",
        {"isAdmin": False},
        False,
        id="requires-dependencies-unsatisfied",
    ),
    pytest.param(
        _DISABLES_WITH_WHEN, "discount", {"isPaused": False}, True, id="disables-when-inactive"
    ),
    pytest.param(
        _DISABLES_WITH_WHEN, "discount", {"isPaused": True}, False, id="disables-when-active"
    ),
]


@pytest.mark.parametrize(("document", "field", "conditions", "expected_enabled"), _OUTCOMES)
def test_loaded_rule_decides_availability(
    document: dict[str, object],
    field: str,
    conditions: dict[str, object],
    expected_enabled: bool,
) -> None:
    schema = UmpireSchema.from_json_obj(document)

    result = umpire(schema.fields, schema.rules).check({}, conditions)

    assert result[field].enabled is expected_enabled
