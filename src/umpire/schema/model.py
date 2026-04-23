"""Schema model for Umpire."""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from ..types import FieldDef, Rule


class UmpireSchemaError(Exception):
    """Exception raised for Umpire schema errors."""

    pass


@dataclass
class UmpireSchema:
    """Schema for Umpire configuration."""

    version: int
    fields: dict[str, FieldDef]
    rules: Sequence[Rule] = field(default_factory=list)
    conditions: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json_obj(cls, dict_obj: dict[str, Any]) -> "UmpireSchema":
        """Create UmpireSchema from a dictionary object."""
        if not isinstance(dict_obj, dict):
            raise UmpireSchemaError("Schema must be a dictionary")

        # Validate version
        version = dict_obj.get("version")
        if version != 1:
            raise UmpireSchemaError("Only version 1 schemas are supported")

        # Parse fields
        fields_dict = dict_obj.get("fields", {})
        fields = {}
        for field_name, field_def_dict in fields_dict.items():
            if not isinstance(field_def_dict, dict):
                raise UmpireSchemaError(f"Field definition for '{field_name}' must be a dictionary")

            # Parse field definition
            required = field_def_dict.get("required", False)
            default_value = field_def_dict.get("defaultValue")
            is_empty_str = field_def_dict.get("isEmpty", "present")

            # Convert isEmpty string to enum
            from ..types import IsEmptyStrategy

            try:
                is_empty = IsEmptyStrategy(is_empty_str)
            except ValueError as e:
                raise UmpireSchemaError(f"Invalid isEmpty strategy: {is_empty_str}") from e

            fields[field_name] = FieldDef(
                required=required, default_value=default_value, is_empty=is_empty
            )

        # TODO: Parse rules and conditions
        rules: list[Rule] = []
        conditions: dict[str, Any] = {}

        return cls(version=version, fields=fields, rules=rules, conditions=conditions)

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
