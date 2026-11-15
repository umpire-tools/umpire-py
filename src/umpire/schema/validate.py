"""Closed-member and shape validation for Umpire v1 documents.

The v1 contract (umpire-spec ``conformance/v1-discrepancy-ledger.md``, rows
V1-01..V1-06 and V1-12) treats every object in a document as closed. This walk
rejects undeclared members and the shape errors the meta-schema enforces before
the parser turns the document into Python objects.
"""

import math
from collections.abc import Mapping, Sequence
from typing import Any

from .errors import UmpireSchemaError

_SCHEMA_MEMBERS = ("version", "conditions", "fields", "rules", "validators", "excluded")
_FIELD_DEF_MEMBERS = ("required", "default", "isEmpty")
_CONDITION_DEF_MEMBERS = ("type", "description")
_EXCLUDED_MEMBERS = ("type", "field", "description", "key", "signature")
_CONDITION_TYPES = frozenset({"boolean", "string", "number", "string[]", "number[]"})
_RULE_TYPES = (
    "requires",
    "enabledWhen",
    "fairWhen",
    "disables",
    "oneOf",
    "eitherOf",
    "anyOf",
    "check",
)

_EXPRESSION_MEMBERS: dict[str, tuple[str, ...]] = {
    "eq": ("op", "field", "value"),
    "neq": ("op", "field", "value"),
    "gt": ("op", "field", "value"),
    "gte": ("op", "field", "value"),
    "lt": ("op", "field", "value"),
    "lte": ("op", "field", "value"),
    "present": ("op", "field"),
    "absent": ("op", "field"),
    "truthy": ("op", "field"),
    "falsy": ("op", "field"),
    "in": ("op", "field", "values"),
    "notIn": ("op", "field", "values"),
    "cond": ("op", "condition"),
    "condEq": ("op", "condition", "value"),
    "condIn": ("op", "condition", "values"),
    "fieldInCond": ("op", "field", "condition"),
    "and": ("op", "exprs"),
    "or": ("op", "exprs"),
    "not": ("op", "expr"),
    "check": ("op", "field", "check"),
}


def validate_document(document: Mapping[str, Any]) -> None:
    """Reject a document that falls outside the closed v1 contract."""
    _assert_known_members(document, _SCHEMA_MEMBERS, "Schema")

    version = document.get("version")
    if "version" not in document:
        raise UmpireSchemaError('Schema must include a "version" field')
    if isinstance(version, bool) or version != 1:
        raise UmpireSchemaError(f'Unsupported schema version "{version}"')

    fields = _mapping(document.get("fields"), 'Schema must include a "fields" object')
    if not fields:
        raise UmpireSchemaError("Schema must include at least one field")

    conditions = _mapping(document.get("conditions", {}), '"conditions" must be a dictionary')
    if "rules" not in document:
        raise UmpireSchemaError('Schema must include a "rules" array')
    rules = _sequence(document.get("rules"), '"rules" must be an array')
    validators = _mapping(document.get("validators", {}), '"validators" must be a dictionary')
    excluded = _sequence(document.get("excluded", ()), '"excluded" must be an array')

    for condition_name, definition in conditions.items():
        _validate_condition(condition_name, definition)

    for field_name, definition in fields.items():
        _validate_field_def(field_name, definition)

    for rule in rules:
        _validate_rule(rule)

    for field_name, validator in validators.items():
        _validate_validator(field_name, validator, fields)

    for entry in excluded:
        _validate_excluded_rule(entry)


def _validate_condition(condition_name: Any, definition: Any) -> None:
    if not isinstance(definition, Mapping):
        raise UmpireSchemaError(f'condition "{condition_name}" definition must be a dictionary')

    _assert_known_members(definition, _CONDITION_DEF_MEMBERS, "condition definition")

    condition_type = definition.get("type")
    if not isinstance(condition_type, str) or condition_type not in _CONDITION_TYPES:
        raise UmpireSchemaError(f'condition "{condition_name}" must use a supported type')

    description = definition.get("description")
    if "description" in definition and not isinstance(description, str):
        raise UmpireSchemaError(
            f'condition "{condition_name}" description must be a string when provided'
        )


def _validate_field_def(field_name: Any, definition: Any) -> None:
    if not isinstance(definition, Mapping):
        raise UmpireSchemaError(f"Field definition for '{field_name}' must be a dictionary")

    _assert_known_members(definition, _FIELD_DEF_MEMBERS, "field definition")

    if "default" in definition and not _is_json_primitive(definition["default"]):
        raise UmpireSchemaError(f'Field "{field_name}" has a non-serializable default value')


def _validate_rule(rule: Any) -> None:
    if not isinstance(rule, Mapping):
        raise UmpireSchemaError("Rule must be a dictionary")

    rule_type = rule.get("type")
    if not isinstance(rule_type, str):
        raise UmpireSchemaError("Rule must include a string type")
    if rule_type not in _RULE_TYPES:
        raise UmpireSchemaError(f"unknown rule type: {rule_type}")

    _assert_known_members(rule, _rule_members(rule), "Rule")

    reason = rule.get("reason")
    if "reason" in rule and not isinstance(reason, str):
        raise UmpireSchemaError('Rule "reason" must be a string when provided')

    if rule_type == "requires":
        if "dependency" in rule:
            return
        if "dependencies" in rule:
            for dependency in _sequence(
                rule.get("dependencies"), 'Rule "requires" dependencies must be an array'
            ):
                if isinstance(dependency, Mapping):
                    _validate_expression(dependency)
            return
        _validate_expression(rule.get("when"))
        return

    if rule_type in ("enabledWhen", "fairWhen"):
        _validate_expression(rule.get("when"))
        return

    if rule_type == "disables":
        if "source" not in rule:
            _validate_expression(rule.get("when"))
        return

    if rule_type == "oneOf":
        return

    if rule_type == "anyOf":
        inner_rules = _sequence(rule.get("rules"), 'Rule "anyOf" rules must be an array')
        if not inner_rules:
            raise UmpireSchemaError("anyOf() requires at least one rule")
        for inner_rule in inner_rules:
            _validate_rule(inner_rule)
        return

    if rule_type == "eitherOf":
        group = rule.get("group")
        branches = _mapping(rule.get("branches"), 'Rule "eitherOf" branches must be a dictionary')
        if not branches:
            raise UmpireSchemaError(f'eitherOf("{group}") must include at least one branch')
        for branch_name, branch_rules in branches.items():
            entries = _sequence(
                branch_rules, f'Rule "eitherOf" branch "{branch_name}" must be an array'
            )
            if not entries:
                raise UmpireSchemaError(
                    f'eitherOf("{group}") branch "{branch_name}" must not be empty'
                )
            for inner_rule in entries:
                _validate_rule(inner_rule)
        return

    if rule_type == "check":
        _validate_validator_spec(rule, additional_members=("type", "field", "reason"))


def _rule_members(rule: Mapping[str, Any]) -> tuple[str, ...]:
    rule_type = rule.get("type")

    if rule_type == "requires":
        if "dependency" in rule:
            return ("type", "field", "dependency", "reason")
        if "dependencies" in rule:
            return ("type", "field", "dependencies", "reason")
        return ("type", "field", "when", "reason")

    if rule_type in ("enabledWhen", "fairWhen"):
        return ("type", "field", "when", "reason")

    if rule_type == "disables":
        if "source" in rule:
            return ("type", "source", "targets", "reason")
        return ("type", "when", "targets", "reason")

    if rule_type in ("oneOf", "eitherOf"):
        return ("type", "group", "branches")

    if rule_type == "anyOf":
        return ("type", "rules")

    if rule_type == "check":
        return ("type", "field", "reason", *_validator_spec_members(rule.get("op")))

    raise UmpireSchemaError(f"unknown rule type: {rule_type}")


def _validate_expression(expression: Any) -> None:
    if not isinstance(expression, Mapping):
        raise UmpireSchemaError("Expression must be a dictionary")

    op = expression.get("op")
    if not isinstance(op, str):
        raise UmpireSchemaError("Expression must include a string op")

    members = _EXPRESSION_MEMBERS.get(op)
    if members is None:
        raise UmpireSchemaError(f"unknown expression op: {op}")

    _assert_known_members(expression, members, "Expression")
    _assert_members_present(expression, members[1:], f'Expression "{op}"')

    # A future `contains` op joins eq/neq: same members, same
    # "value must be a JSON primitive" check.
    if op in ("eq", "neq"):
        _assert_string(expression["field"], f'Expression "{op}" field')
        _assert_primitive(expression["value"], f'Expression "{op}" value')
    elif op in ("gt", "gte", "lt", "lte"):
        _assert_string(expression["field"], f'Expression "{op}" field')
        _assert_number(expression["value"], f'Expression "{op}" value')
    elif op in ("present", "absent", "truthy", "falsy"):
        _assert_string(expression["field"], f'Expression "{op}" field')
    elif op in ("in", "notIn"):
        _assert_string(expression["field"], f'Expression "{op}" field')
        _assert_primitive_array(expression["values"], f'Expression "{op}" values')
    elif op == "cond":
        _assert_string(expression["condition"], 'Expression "cond" condition')
    elif op == "condEq":
        _assert_string(expression["condition"], 'Expression "condEq" condition')
        _assert_primitive(expression["value"], 'Expression "condEq" value')
    elif op == "condIn":
        _assert_string(expression["condition"], 'Expression "condIn" condition')
        _assert_primitive_array(expression["values"], 'Expression "condIn" values')
    elif op == "fieldInCond":
        _assert_string(expression["field"], 'Expression "fieldInCond" field')
        _assert_string(expression["condition"], 'Expression "fieldInCond" condition')
    elif op in ("and", "or"):
        for entry in _sequence(expression["exprs"], f'Expression "{op}" exprs must be an array'):
            _validate_expression(entry)
    elif op == "not":
        _validate_expression(expression["expr"])
    elif op == "check":
        _assert_string(expression["field"], 'Expression "check" field')
        _validate_validator_spec(expression["check"])


def _validate_validator_spec(spec: Any, additional_members: Sequence[str] = ()) -> None:
    if not isinstance(spec, Mapping):
        raise UmpireSchemaError("Validator spec must be a dictionary")

    _assert_known_members(
        spec,
        (*_validator_spec_members(spec.get("op")), *additional_members),
        "Validator spec",
    )


def _validate_validator(field_name: Any, validator: Any, field_names: Mapping[str, Any]) -> None:
    if field_name not in field_names:
        raise UmpireSchemaError(f'validator for unknown field "{field_name}"')

    if not isinstance(validator, Mapping):
        raise UmpireSchemaError(f'Validator for "{field_name}" must be a dictionary')

    _assert_known_members(
        validator, (*_validator_spec_members(validator.get("op")), "error"), "Validator spec"
    )

    error = validator.get("error")
    if "error" in validator and not isinstance(error, str):
        raise UmpireSchemaError(
            f'Validator for "{field_name}" must use a string error when provided'
        )


def _validate_excluded_rule(rule: Any) -> None:
    if not isinstance(rule, Mapping):
        raise UmpireSchemaError("Excluded rule must be a dictionary")

    _assert_known_members(rule, _EXCLUDED_MEMBERS, "Excluded rule")

    rule_type = rule.get("type")
    if not isinstance(rule_type, str) or not rule_type:
        raise UmpireSchemaError("Excluded rules must include a non-empty string type")

    description = rule.get("description")
    if not isinstance(description, str) or not description:
        raise UmpireSchemaError("Excluded rules must include a non-empty string description")

    for member in ("field", "key", "signature"):
        if member in rule and not isinstance(rule[member], str):
            raise UmpireSchemaError(f'Excluded rule "{member}" must be a string when provided')


def _validator_spec_members(op: Any) -> tuple[str, ...]:
    if op in ("email", "url", "integer"):
        return ("op",)
    if op == "matches":
        return ("op", "pattern")
    if op in ("minLength", "maxLength", "min", "max"):
        return ("op", "value")
    if op == "range":
        return ("op", "min", "max")
    return ("op",)


def _assert_known_members(value: Mapping[str, Any], allowed: Sequence[str], context: str) -> None:
    for key in value:
        if key not in allowed:
            raise UmpireSchemaError(
                f'{context} has unknown member "{key}"; expected {", ".join(allowed)}'
            )


def _is_json_primitive(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _assert_string(value: Any, context: str) -> None:
    if not isinstance(value, str):
        raise UmpireSchemaError(f"{context} must be a string")


def _assert_number(value: Any, context: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UmpireSchemaError(f"{context} must be a finite number")
    if not math.isfinite(value):
        raise UmpireSchemaError(f"{context} must be a finite number")


def _assert_primitive(value: Any, context: str) -> None:
    if not _is_json_primitive(value):
        raise UmpireSchemaError(f"{context} must be a JSON primitive")


def _assert_primitive_array(value: Any, context: str) -> None:
    message = f"{context} must be an array of JSON primitives"
    entries = _sequence(value, message)
    if not all(_is_json_primitive(entry) for entry in entries):
        raise UmpireSchemaError(message)


def _assert_members_present(value: Mapping[str, Any], members: Sequence[str], context: str) -> None:
    for member in members:
        if member not in value:
            raise UmpireSchemaError(f'{context} must include a "{member}" member')


def _mapping(value: Any, message: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise UmpireSchemaError(message)
    return value


def _sequence(value: Any, message: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise UmpireSchemaError(message)
    return value
