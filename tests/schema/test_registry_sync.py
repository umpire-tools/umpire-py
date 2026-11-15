"""Keep the walk's registries and the parser's coverage in step.

The closed v1 walk accepts an expression op or a rule type only if it is listed
in ``validate.py``. Each listing must also be compilable by the parser, or a
document that passes the walk fails to load. The tables below hold the minimal
document entry for each registry name; keying them by that name makes a new
registry entry fail the suite until it has a row here.
"""

import pytest

from umpire import UmpireSchema
from umpire.schema.validate import _EXPRESSION_MEMBERS, _RULE_TYPES

_COND = {"op": "cond", "condition": "isAdmin"}

_MINIMAL_EXPRESSIONS: dict[str, dict[str, object]] = {
    "eq": {"op": "eq", "field": "email", "value": "someone@example.com"},
    "neq": {"op": "neq", "field": "email", "value": "someone@example.com"},
    "gt": {"op": "gt", "field": "discount", "value": 1},
    "gte": {"op": "gte", "field": "discount", "value": 1},
    "lt": {"op": "lt", "field": "discount", "value": 1},
    "lte": {"op": "lte", "field": "discount", "value": 1},
    "present": {"op": "present", "field": "email"},
    "absent": {"op": "absent", "field": "email"},
    "truthy": {"op": "truthy", "field": "email"},
    "falsy": {"op": "falsy", "field": "email"},
    "in": {"op": "in", "field": "email", "values": ["someone@example.com"]},
    "notIn": {"op": "notIn", "field": "email", "values": ["someone@example.com"]},
    "cond": _COND,
    "condEq": {"op": "condEq", "condition": "isAdmin", "value": True},
    "condIn": {"op": "condIn", "condition": "isAdmin", "values": [True]},
    "fieldInCond": {"op": "fieldInCond", "field": "email", "condition": "recipients"},
    "and": {"op": "and", "exprs": [_COND]},
    "or": {"op": "or", "exprs": [_COND]},
    "not": {"op": "not", "expr": _COND},
    "check": {"op": "check", "field": "email", "check": {"op": "email"}},
}

_ENABLED_WHEN = {"type": "enabledWhen", "field": "email", "when": _COND}

_MINIMAL_RULES: dict[str, dict[str, object]] = {
    "requires": {"type": "requires", "field": "email", "dependency": "discount"},
    "enabledWhen": _ENABLED_WHEN,
    "fairWhen": {"type": "fairWhen", "field": "email", "when": _COND},
    "disables": {"type": "disables", "source": "email", "targets": ["discount"]},
    "oneOf": {
        "type": "oneOf",
        "group": "contact",
        "branches": {"a": ["email"], "b": ["discount"]},
    },
    "eitherOf": {
        "type": "eitherOf",
        "group": "contact",
        "branches": {"a": [_ENABLED_WHEN]},
    },
    "anyOf": {"type": "anyOf", "rules": [_ENABLED_WHEN]},
    "check": {"type": "check", "field": "email", "op": "email"},
}


def _document(rules: list[dict[str, object]]) -> dict[str, object]:
    return {
        "version": 1,
        "conditions": {
            "isAdmin": {"type": "boolean"},
            "recipients": {"type": "string[]"},
        },
        "fields": {"email": {}, "discount": {}},
        "rules": rules,
    }


def test_expression_table_covers_every_expression_member() -> None:
    assert set(_MINIMAL_EXPRESSIONS) == set(_EXPRESSION_MEMBERS)


def test_rule_table_covers_every_rule_type() -> None:
    assert set(_MINIMAL_RULES) == set(_RULE_TYPES)


@pytest.mark.parametrize("op", list(_MINIMAL_EXPRESSIONS))
def test_every_expression_op_compiles(op: str) -> None:
    document = _document([{**_ENABLED_WHEN, "when": _MINIMAL_EXPRESSIONS[op]}])

    schema = UmpireSchema.from_json_obj(document)

    assert len(schema.rules) == 1


@pytest.mark.parametrize("rule_type", list(_MINIMAL_RULES))
def test_every_rule_type_parses(rule_type: str) -> None:
    schema = UmpireSchema.from_json_obj(_document([_MINIMAL_RULES[rule_type]]))

    assert len(schema.rules) == 1
