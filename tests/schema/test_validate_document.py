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
    "unknown-top-level-key": _document(rulez=[]),
    "condition-def-not-a-dictionary": _document(conditions={"isAdmin": ["boolean"]}),
    "unknown-member-in-condition-definition": _document(
        conditions={"isAdmin": {"type": "boolean", "surprise": True}}
    ),
    "unsupported-condition-type": _document(conditions={"isAdmin": {"type": "array"}}),
    "any-of-without-rules": _document(rules=[{"type": "anyOf", "rules": []}]),
    "one-of-without-branches": _document(
        rules=[{"type": "oneOf", "group": "auth", "branches": {}}]
    ),
    "either-of-without-branches": _document(
        rules=[{"type": "eitherOf", "group": "auth", "branches": {}}]
    ),
    "either-of-with-empty-branch": _document(
        rules=[{"type": "eitherOf", "group": "auth", "branches": {"a": []}}]
    ),
    "validator-for-unknown-field": _document(validators={"nickname": {"op": "email"}}),
    "validator-not-a-dictionary": _document(validators={"email": "email"}),
    "validator-with-non-string-error": _document(validators={"email": {"op": "email", "error": 5}}),
    "boolean-version": _document(version=True),
    "default-value-member-on-field": _document(fields={"email": {"defaultValue": "x"}}),
    "missing-fields": {"version": 1, "rules": []},
    "empty-fields": {"version": 1, "fields": {}, "rules": []},
    "missing-rules": {"version": 1, "fields": {"email": {}}},
    "rule-reason-not-a-string": _document(rules=[{**_enabled_when(_COND_WHEN), "reason": 5}]),
    "gt-with-string-value": _document(
        rules=[_enabled_when({"op": "gt", "field": "discount", "value": "text"})]
    ),
    "and-exprs-not-an-array": _document(
        rules=[_enabled_when({"op": "and", "exprs": "not-an-array"})]
    ),
    "eq-without-value": _document(rules=[_enabled_when({"op": "eq", "field": "email"})]),
    "in-with-object-values": _document(
        rules=[_enabled_when({"op": "in", "field": "email", "values": [{"a": 1}]})],
    ),
    "check-min-with-nan-value": _document(
        rules=[{"type": "check", "field": "discount", "op": "min", "value": float("nan")}],
    ),
    "missing-version": {"fields": {"email": {}}, "rules": []},
    "excluded-entry-not-a-dictionary": _document(excluded=["custom"]),
    "excluded-entry-without-type": _document(
        excluded=[{"description": "Custom callback cannot be serialized"}]
    ),
    "excluded-entry-with-empty-type": _document(
        excluded=[{"type": "", "description": "Custom callback cannot be serialized"}]
    ),
    "excluded-entry-without-description": _document(excluded=[{"type": "custom"}]),
    "excluded-entry-with-empty-description": _document(
        excluded=[{"type": "custom", "description": ""}]
    ),
    "excluded-entry-with-non-string-field": _document(
        excluded=[{"type": "custom", "description": "Custom", "field": 5}]
    ),
    "excluded-entry-with-non-string-key": _document(
        excluded=[{"type": "custom", "description": "Custom", "key": 5}]
    ),
    "excluded-entry-with-non-string-signature": _document(
        excluded=[{"type": "custom", "description": "Custom", "signature": 5}]
    ),
}


@pytest.mark.parametrize("document", list(_CASES.values()), ids=list(_CASES))
def test_rejects_invalid_document(document: dict[str, object]) -> None:
    with pytest.raises(UmpireSchemaError):
        UmpireSchema.from_json_obj(document)
