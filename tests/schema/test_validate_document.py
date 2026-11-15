"""Documents the closed v1 walk must reject, whatever the error message."""

import pytest

from umpire import UmpireSchema, UmpireSchemaError

_COND_WHEN = {"op": "cond", "condition": "isAdmin"}


def _document(**overrides: object) -> dict[str, object]:
    document: dict[str, object] = {
        "version": 1,
        "conditions": {"isAdmin": {"type": "boolean"}},
        "fields": {"email": {}, "discount": {}},
        "rules": [],
    }
    document.update(overrides)
    return document


def _enabled_when(when: object) -> dict[str, object]:
    return {"type": "enabledWhen", "field": "discount", "when": when}


_CASES: dict[str, dict[str, object]] = {
    "unknown-member-in-and": _document(
        rules=[
            _enabled_when(
                {
                    "op": "and",
                    "exprs": [{**_COND_WHEN, "surprise": True}],
                }
            )
        ]
    ),
    "unknown-member-in-or": _document(
        rules=[
            _enabled_when(
                {
                    "op": "or",
                    "exprs": [{**_COND_WHEN, "surprise": True}],
                }
            )
        ]
    ),
    "unknown-member-in-not": _document(
        rules=[_enabled_when({"op": "not", "expr": {**_COND_WHEN, "surprise": True}})],
    ),
    "unknown-member-in-requires-dependencies": _document(
        rules=[
            {
                "type": "requires",
                "field": "email",
                "dependencies": [{**_COND_WHEN, "surprise": True}],
            }
        ]
    ),
    "unknown-member-in-any-of": _document(
        rules=[
            {
                "type": "anyOf",
                "rules": [{**_enabled_when(_COND_WHEN), "surprise": True}],
            }
        ]
    ),
    "unknown-member-in-either-of-branch": _document(
        rules=[
            {
                "type": "eitherOf",
                "group": "auth",
                "branches": {"a": [{**_enabled_when(_COND_WHEN), "surprise": True}]},
            }
        ]
    ),
    "error-member-on-rule-level-check": _document(
        rules=[
            {"type": "check", "field": "email", "op": "email", "error": "Not valid"},
        ]
    ),
    "cross-op-member-on-rule-level-check": _document(
        rules=[{"type": "check", "field": "email", "op": "email", "value": 1}],
    ),
    "requires-with-dependency-and-when": _document(
        rules=[
            {
                "type": "requires",
                "field": "email",
                "dependency": "discount",
                "when": _COND_WHEN,
            }
        ]
    ),
    "disables-with-source-and-when": _document(
        rules=[
            {
                "type": "disables",
                "source": "email",
                "targets": ["discount"],
                "when": _COND_WHEN,
            }
        ]
    ),
    "boolean-version": _document(version=True),
    "default-value-member-on-field": _document(fields={"email": {"defaultValue": "x"}}),
    "missing-fields": {"version": 1, "rules": []},
    "missing-rules": {"version": 1, "fields": {"email": {}}},
    "eq-without-value": _document(rules=[_enabled_when({"op": "eq", "field": "email"})]),
    "in-with-object-values": _document(
        rules=[_enabled_when({"op": "in", "field": "email", "values": [{"a": 1}]})],
    ),
}


@pytest.mark.parametrize("document", list(_CASES.values()), ids=list(_CASES))
def test_rejects_invalid_document(document: dict[str, object]) -> None:
    with pytest.raises(UmpireSchemaError):
        UmpireSchema.from_json_obj(document)
