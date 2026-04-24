"""Schema model for Umpire."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ..checks import check_ops
from ..rules import (
    CheckRule,
    any_of,
    disables,
    either_of,
    enabled_when,
    fair_when,
    one_of,
    requires,
)
from ..types import FieldDef, IsEmptyStrategy, Rule
from .expr import ExpressionCompiler


class UmpireSchemaError(Exception):
    """Exception raised for Umpire schema errors."""


@dataclass
class UmpireSchema:
    """Schema for Umpire configuration."""

    version: int
    fields: dict[str, FieldDef]
    rules: Sequence[Rule] = field(default_factory=list)
    conditions: dict[str, Any] = field(default_factory=dict)
    excluded: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()

    @classmethod
    def from_json_obj(cls, dict_obj: Mapping[str, Any]) -> "UmpireSchema":
        """Create UmpireSchema from a dictionary object."""
        if not isinstance(dict_obj, Mapping):
            raise UmpireSchemaError("Schema must be a dictionary")

        version = dict_obj.get("version")
        if version != 1:
            raise UmpireSchemaError("Only version 1 schemas are supported")

        fields = _parse_fields(_mapping(dict_obj, "fields", default={}))
        conditions = dict(_mapping(dict_obj, "conditions", default={}))
        condition_types = _condition_types(conditions)
        compiler = ExpressionCompiler(
            field_names=fields.keys(),
            condition_names=conditions.keys() if conditions else None,
            condition_types=condition_types,
        )
        rules = _parse_rules(
            _sequence(dict_obj, "rules", default=[]),
            field_names=set(fields),
            compiler=compiler,
        )
        rules.extend(_parse_validators(_mapping(dict_obj, "validators", default={}), set(fields)))
        excluded = tuple(dict(entry) for entry in _sequence(dict_obj, "excluded", default=[]))
        warnings = tuple(_excluded_warning(entry) for entry in excluded)

        return cls(
            version=version,
            fields=fields,
            rules=rules,
            conditions=conditions,
            excluded=excluded,
            warnings=warnings,
        )

    @classmethod
    def from_json_str(cls, json_text: str) -> "UmpireSchema":
        """Create UmpireSchema from a JSON string."""
        try:
            dict_obj = json.loads(json_text)
        except json.JSONDecodeError as e:
            raise UmpireSchemaError(f"Invalid JSON: {e}") from e

        return cls.from_json_obj(dict_obj)

    @classmethod
    def build(
        cls, conditions: dict[str, Any] | None = None, rules: Sequence[Rule] = ()
    ) -> "UmpireSchema":
        """Build a UmpireSchema with the given conditions and rules."""
        return cls(version=1, fields={}, rules=list(rules), conditions=conditions or {})


def _parse_fields(fields_dict: Mapping[str, Any]) -> dict[str, FieldDef]:
    fields: dict[str, FieldDef] = {}
    for field_name, field_def_dict in fields_dict.items():
        if not isinstance(field_name, str):
            raise UmpireSchemaError("Field names must be strings")
        if not isinstance(field_def_dict, Mapping):
            raise UmpireSchemaError(f"Field definition for '{field_name}' must be a dictionary")

        required = field_def_dict.get("required", False)
        if not isinstance(required, bool):
            raise UmpireSchemaError(f"Field '{field_name}' required must be a boolean")

        default_value = field_def_dict.get("default", field_def_dict.get("defaultValue"))
        is_empty_str = field_def_dict.get("isEmpty", "present")

        try:
            is_empty = IsEmptyStrategy(is_empty_str)
        except ValueError as e:
            raise UmpireSchemaError(f"Invalid isEmpty strategy: {is_empty_str}") from e

        fields[field_name] = FieldDef(
            required=required,
            default_value=default_value,
            is_empty=is_empty,
        )

    return fields


def _parse_rules(
    rules_list: Sequence[Any],
    *,
    field_names: set[str],
    compiler: ExpressionCompiler,
) -> list[Rule]:
    rules: list[Rule] = []
    for rule_obj in rules_list:
        if not isinstance(rule_obj, Mapping):
            raise UmpireSchemaError("Rule must be a dictionary")
        rules.extend(_parse_rule(rule_obj, field_names=field_names, compiler=compiler))
    return rules


def _parse_rule(
    rule_obj: Mapping[str, Any],
    *,
    field_names: set[str],
    compiler: ExpressionCompiler,
) -> list[Rule]:
    rule_type = rule_obj.get("type")
    if not isinstance(rule_type, str):
        raise UmpireSchemaError("Rule must include a string type")

    try:
        if rule_type == "requires":
            field = _field(rule_obj, "field", field_names)
            reason = _optional_string(rule_obj, "reason")
            if "dependency" in rule_obj:
                return [
                    requires(
                        field, dependency=_field(rule_obj, "dependency", field_names), reason=reason
                    )
                ]
            if "dependencies" in rule_obj:
                dependencies = _sequence(rule_obj, "dependencies")
                if not dependencies:
                    raise UmpireSchemaError("requires dependencies must not be empty")
                parsed: list[Rule] = []
                for dependency in dependencies:
                    if isinstance(dependency, str):
                        _assert_known_field(dependency, field_names)
                        parsed.append(requires(field, dependency=dependency, reason=reason))
                    elif isinstance(dependency, Mapping):
                        parsed.append(
                            enabled_when(field, compiler.compile_expr(dependency), reason=reason)
                        )
                    else:
                        raise UmpireSchemaError("requires dependency must be a field or expression")
                return parsed
            return [
                enabled_when(
                    field, compiler.compile_expr(_mapping(rule_obj, "when")), reason=reason
                )
            ]

        if rule_type == "enabledWhen":
            field = _field(rule_obj, "field", field_names)
            return [
                enabled_when(
                    field,
                    compiler.compile_expr(_mapping(rule_obj, "when")),
                    reason=_optional_string(rule_obj, "reason"),
                )
            ]

        if rule_type == "fairWhen":
            field = _field(rule_obj, "field", field_names)
            return [
                fair_when(
                    field,
                    compiler.compile_expr(_mapping(rule_obj, "when")),
                    reason=_optional_string(rule_obj, "reason"),
                )
            ]

        if rule_type == "disables":
            targets = [
                _known_field(target, field_names) for target in _sequence(rule_obj, "targets")
            ]
            reason = _optional_string(rule_obj, "reason")
            if "source" in rule_obj:
                return [disables(_field(rule_obj, "source", field_names), targets, reason=reason)]
            return [
                disables(
                    "",
                    targets,
                    when=compiler.compile_expr(_mapping(rule_obj, "when")),
                    reason=reason,
                )
            ]

        if rule_type == "oneOf":
            branches = _mapping(rule_obj, "branches")
            return [one_of(_string(rule_obj, "group"), _parse_branches(branches, field_names))]

        if rule_type == "anyOf":
            inner = _parse_rules(
                _sequence(rule_obj, "rules"), field_names=field_names, compiler=compiler
            )
            return [any_of(inner)]

        if rule_type == "eitherOf":
            branches = _mapping(rule_obj, "branches")
            parsed_branches = {
                branch: _parse_rules(
                    _sequence_value(branch_rules),
                    field_names=field_names,
                    compiler=compiler,
                )
                for branch, branch_rules in branches.items()
                if isinstance(branch, str)
            }
            if len(parsed_branches) != len(branches):
                raise UmpireSchemaError("eitherOf branch names must be strings")
            return [either_of(_string(rule_obj, "group"), parsed_branches)]

        if rule_type == "check":
            field = _field(rule_obj, "field", field_names)
            return [
                CheckRule(
                    field,
                    _parse_check_op(rule_obj, _optional_string(rule_obj, "reason")),
                    affects_fair=True,
                )
            ]
    except ValueError as e:
        raise UmpireSchemaError(str(e)) from e

    raise UmpireSchemaError(f"unknown rule type: {rule_type}")


def _parse_validators(validators: Mapping[str, Any], field_names: set[str]) -> list[Rule]:
    rules: list[Rule] = []
    for field_name, spec in validators.items():
        field = _known_field(field_name, field_names)
        if not isinstance(spec, Mapping):
            raise UmpireSchemaError(f'Validator for "{field}" must be a dictionary')
        reason = _optional_string(spec, "error")
        rules.append(CheckRule(field, _parse_check_op(spec, reason), validation=True))
    return rules


def _condition_types(conditions: Mapping[str, Any]) -> dict[str, str]:
    types: dict[str, str] = {}
    for name, definition in conditions.items():
        if not isinstance(definition, Mapping):
            raise UmpireSchemaError(f'Condition "{name}" must be a dictionary')
        condition_type = definition.get("type")
        if not isinstance(condition_type, str):
            raise UmpireSchemaError(f'Condition "{name}" must include a string type')
        types[name] = condition_type
    return types


def _parse_check_op(rule_obj: Mapping[str, Any], reason: str | None) -> Any:
    op = _string(rule_obj, "op")
    if op == "email":
        return check_ops.email(reason=reason)
    if op == "url":
        return check_ops.url(reason=reason)
    if op == "matches":
        return check_ops.matches(_string(rule_obj, "pattern"), reason=reason)
    if op == "minLength":
        return check_ops.min_length(_integer(rule_obj, "value"), reason=reason)
    if op == "maxLength":
        return check_ops.max_length(_integer(rule_obj, "value"), reason=reason)
    if op == "min":
        return check_ops.min_value(_number(rule_obj, "value"), reason=reason)
    if op == "max":
        return check_ops.max_value(_number(rule_obj, "value"), reason=reason)
    if op == "range":
        return check_ops.range_value(
            _number(rule_obj, "min"), _number(rule_obj, "max"), reason=reason
        )
    if op == "integer":
        return check_ops.integer(reason=reason)
    raise UmpireSchemaError(f"unknown check op: {op}")


def _parse_branches(branches: Mapping[str, Any], field_names: set[str]) -> dict[str, list[str]]:
    parsed: dict[str, list[str]] = {}
    for branch, fields in branches.items():
        if not isinstance(branch, str):
            raise UmpireSchemaError("oneOf branch names must be strings")
        parsed[branch] = [_known_field(field, field_names) for field in _sequence_value(fields)]
    return parsed


def _excluded_warning(entry: Mapping[str, Any]) -> str:
    rule_type = entry.get("type", "unknown")
    description = entry.get("description", "No description provided")
    return f"Excluded rule {rule_type}: {description}"


def _mapping(obj: Mapping[str, Any], key: str, default: Any = None) -> Mapping[str, Any]:
    value = obj.get(key, default)
    if not isinstance(value, Mapping):
        raise UmpireSchemaError(f'"{key}" must be a dictionary')
    return value


def _sequence(obj: Mapping[str, Any], key: str, default: Any = None) -> Sequence[Any]:
    value = obj.get(key, default)
    return _sequence_value(value, label=key)


def _sequence_value(value: Any, label: str = "value") -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise UmpireSchemaError(f'"{label}" must be an array')
    return value


def _string(obj: Mapping[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str):
        raise UmpireSchemaError(f'"{key}" must be a string')
    return value


def _optional_string(obj: Mapping[str, Any], key: str) -> str | None:
    value = obj.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise UmpireSchemaError(f'"{key}" must be a string')
    return value


def _number(obj: Mapping[str, Any], key: str) -> int | float:
    value = obj.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise UmpireSchemaError(f'"{key}" must be a number')
    return value


def _integer(obj: Mapping[str, Any], key: str) -> int:
    value = obj.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise UmpireSchemaError(f'"{key}" must be an integer')
    return value


def _field(obj: Mapping[str, Any], key: str, field_names: set[str]) -> str:
    return _known_field(_string(obj, key), field_names)


def _known_field(field_name: Any, field_names: set[str]) -> str:
    if not isinstance(field_name, str):
        raise UmpireSchemaError("field reference must be a string")
    _assert_known_field(field_name, field_names)
    return field_name


def _assert_known_field(field_name: str, field_names: set[str]) -> None:
    if field_name not in field_names:
        raise UmpireSchemaError(f'unknown field "{field_name}"')
