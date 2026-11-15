"""Documents the closed v1 walk must reject, whatever the error message."""

import re

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
    "condition-description-not-a-string": _document(
        conditions={"isAdmin": {"type": "boolean", "description": 5}}
    ),
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
    "string-version": _document(version="1"),
    "fields-not-a-dictionary": _document(fields=["email"]),
    "conditions-not-a-dictionary": _document(conditions=["isAdmin"]),
    "validators-not-a-dictionary": _document(validators=["email"]),
    "rule-not-a-dictionary": _document(rules=[5]),
    "unknown-member-in-nested-check-spec": _document(
        rules=[
            _enabled_when(
                {"op": "check", "field": "email", "check": {"op": "email", "surprise": True}}
            )
        ]
    ),
    "unknown-member-in-validator": _document(
        validators={"email": {"op": "email", "surprise": True}}
    ),
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
    "eq-with-object-value": _document(
        rules=[_enabled_when({"op": "eq", "field": "email", "value": {"a": 1}})]
    ),
    "cond-eq-with-object-value": _document(
        rules=[_enabled_when({"op": "condEq", "condition": "isAdmin", "value": {"a": 1}})]
    ),
    "contains-without-value": _document(rules=[_enabled_when({"op": "contains", "field": "tags"})]),
    "contains-with-array-value": _document(
        rules=[_enabled_when({"op": "contains", "field": "tags", "value": ["a"]})]
    ),
    "contains-on-field-with-list-is-empty": _document(
        fields={"tags": {"isEmpty": ["array"]}, "discount": {}},
        rules=[_enabled_when({"op": "contains", "field": "tags", "value": "a"})],
    ),
    "contains-with-nan-value": _document(
        fields={"tags": {"isEmpty": "array"}, "discount": {}},
        rules=[_enabled_when({"op": "contains", "field": "tags", "value": float("nan")})],
    ),
    "field-default-with-nan": _document(
        fields={"email": {"default": float("nan")}, "discount": {}}
    ),
    "eq-with-infinite-value": _document(
        rules=[_enabled_when({"op": "eq", "field": "email", "value": float("inf")})]
    ),
    "in-on-array-field-inside-not-inside-either-of-branch": _document(
        fields={"tags": {"isEmpty": "array"}, "discount": {}},
        rules=[
            {
                "type": "eitherOf",
                "group": "auth",
                "branches": {
                    "a": [
                        _enabled_when(
                            {
                                "op": "not",
                                "expr": {"op": "in", "field": "tags", "values": ["a"]},
                            }
                        )
                    ]
                },
            }
        ],
    ),
    "in-on-array-field": _document(
        fields={"tags": {"isEmpty": "array"}, "discount": {}},
        rules=[_enabled_when({"op": "in", "field": "tags", "values": ["a"]})],
    ),
    "field-in-cond-on-array-field": _document(
        conditions={"isAdmin": {"type": "string[]"}},
        fields={"tags": {"isEmpty": "array"}, "discount": {}},
        rules=[_enabled_when({"op": "fieldInCond", "field": "tags", "condition": "isAdmin"})],
    ),
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


# Cases pinned to the check that must reject them, so they cannot pass by accident.
_CASE_MESSAGES: dict[str, str] = {
    "field-in-cond-on-array-field": re.escape('"fieldInCond" requires a scalar field'),
}


@pytest.mark.parametrize("case", list(_CASES))
def test_rejects_invalid_document(case: str) -> None:
    with pytest.raises(UmpireSchemaError, match=_CASE_MESSAGES.get(case)):
        UmpireSchema.from_json_obj(_CASES[case])


@pytest.mark.parametrize("is_empty", ["string", "number", "boolean", "object"])
def test_contains_rejects_every_non_array_field(is_empty: str) -> None:
    """contains requires a field that can hold a list, whatever the scalar strategy."""
    document = _document(
        fields={"tags": {"isEmpty": is_empty}, "discount": {}},
        rules=[_enabled_when({"op": "contains", "field": "tags", "value": "a"})],
    )

    with pytest.raises(UmpireSchemaError, match=re.escape('"contains" requires an array field')):
        UmpireSchema.from_json_obj(document)


@pytest.mark.parametrize(
    ("is_empty", "value"),
    [
        ("array", "a"),
        ("present", "a"),
        (None, "a"),
        ("array", None),
        ("array", 22),
        ("array", True),
    ],
    ids=["array", "present", "no-is-empty", "null-value", "number-value", "boolean-value"],
)
def test_contains_accepts_array_capable_fields_and_any_primitive(
    is_empty: str | None, value: object
) -> None:
    """contains may target any field that can hold a list, with any primitive value."""
    definition: dict[str, object] = {} if is_empty is None else {"isEmpty": is_empty}
    document = _document(
        fields={"tags": definition, "discount": {}},
        rules=[_enabled_when({"op": "contains", "field": "tags", "value": value})],
    )

    UmpireSchema.from_json_obj(document)
