"""Tests for Umpire schema loading."""

import pytest

from umpire import (
    IsEmptyStrategy,
    UmpireSchema,
    UmpireSchemaError,
    umpire,
)


def test_schema_from_json_obj_valid() -> None:
    """Test creating schema from valid JSON object."""
    json_obj = {
        "version": 1,
        "fields": {
            "email": {"required": True, "isEmpty": "string"},
            "company_name": {"required": False, "isEmpty": "string"},
        },
    }

    schema = UmpireSchema.from_json_obj(json_obj)
    assert schema.version == 1
    assert len(schema.fields) == 2
    assert "email" in schema.fields
    assert "company_name" in schema.fields

    # Check field definitions
    email_field = schema.fields["email"]
    assert email_field.required is True
    assert email_field.is_empty == IsEmptyStrategy.STRING

    company_field = schema.fields["company_name"]
    assert company_field.required is False
    assert company_field.is_empty == IsEmptyStrategy.STRING


def test_schema_from_json_obj_invalid_not_dict() -> None:
    """Test creating schema with non-dictionary input."""
    with pytest.raises(UmpireSchemaError, match="Schema must be a dictionary"):
        UmpireSchema.from_json_obj("not a dict")  # type: ignore


def test_schema_from_json_obj_invalid_version() -> None:
    """Test creating schema with invalid version."""
    json_obj = {"version": 2, "fields": {}}

    with pytest.raises(UmpireSchemaError, match="Only version 1 schemas are supported"):
        UmpireSchema.from_json_obj(json_obj)


def test_schema_from_json_obj_invalid_field_def() -> None:
    """Test creating schema with invalid field definition."""
    json_obj = {"version": 1, "fields": {"email": "not a dict"}}

    with pytest.raises(
        UmpireSchemaError, match="Field definition for 'email' must be a dictionary"
    ):
        UmpireSchema.from_json_obj(json_obj)


def test_schema_from_json_obj_invalid_is_empty() -> None:
    """Test creating schema with invalid isEmpty strategy."""
    json_obj = {
        "version": 1,
        "fields": {"email": {"required": True, "isEmpty": "invalid_strategy"}},
    }

    with pytest.raises(UmpireSchemaError, match="Invalid isEmpty strategy"):
        UmpireSchema.from_json_obj(json_obj)


def test_schema_from_json_str_valid() -> None:
    """Test creating schema from valid JSON string."""
    json_str = """
    {
        "version": 1,
        "fields": {
            "email": {
                "required": true,
                "isEmpty": "string"
            }
        }
    }
    """

    schema = UmpireSchema.from_json_str(json_str)
    assert schema.version == 1
    assert len(schema.fields) == 1
    assert "email" in schema.fields


def test_schema_from_json_str_invalid() -> None:
    """Test creating schema from invalid JSON string."""
    json_str = "{ invalid json }"

    with pytest.raises(UmpireSchemaError, match="Invalid JSON"):
        UmpireSchema.from_json_str(json_str)


def test_schema_build() -> None:
    """Test building schema with conditions and rules."""
    schema = UmpireSchema.build(conditions={"is_admin": True}, rules=[])

    assert schema.version == 1
    assert schema.conditions == {"is_admin": True}
    assert schema.rules == []


def test_schema_from_json_obj_parses_rules() -> None:
    """Schema loading should produce usable Python rules."""
    json_obj = {
        "version": 1,
        "conditions": {
            "isAdmin": {"type": "boolean"},
            "validPlans": {"type": "string[]"},
        },
        "fields": {
            "email": {"required": True, "isEmpty": "string"},
            "discount": {},
            "plan": {"default": "basic", "isEmpty": "string"},
        },
        "rules": [
            {
                "type": "enabledWhen",
                "field": "discount",
                "when": {"op": "cond", "condition": "isAdmin"},
                "reason": "Admin only",
            },
            {
                "type": "fairWhen",
                "field": "plan",
                "when": {"op": "fieldInCond", "field": "plan", "condition": "validPlans"},
                "reason": "Plan unavailable",
            },
            {"type": "check", "field": "email", "op": "email", "reason": "Bad email"},
        ],
    }

    schema = UmpireSchema.from_json_obj(json_obj)
    u = umpire(schema.fields, schema.rules)

    result = u.check(
        {"email": "not-email", "plan": "enterprise"},
        {"isAdmin": False, "validPlans": ["basic", "pro"]},
    )

    assert result["discount"].enabled is False
    assert result["discount"].reason == "Admin only"
    assert result["plan"].fair is False
    assert result["plan"].reason == "Plan unavailable"
    assert result["email"].check_errors[0].reason == "Bad email"


def test_schema_from_json_obj_rejects_unknown_rule_field() -> None:
    """Rule field references must be validated."""
    json_obj = {
        "version": 1,
        "fields": {"email": {}},
        "rules": [
            {"type": "enabledWhen", "field": "missing", "when": {"op": "cond", "condition": "ok"}}
        ],
        "conditions": {"ok": {"type": "boolean"}},
    }

    with pytest.raises(UmpireSchemaError, match="unknown field"):
        UmpireSchema.from_json_obj(json_obj)


def test_schema_from_json_obj_rejects_unknown_expression_op() -> None:
    """Expression ops should fail clearly when unknown."""
    json_obj = {
        "version": 1,
        "fields": {"email": {}},
        "conditions": {"ok": {"type": "boolean"}},
        "rules": [
            {
                "type": "enabledWhen",
                "field": "email",
                "when": {"op": "mystery", "condition": "ok"},
            }
        ],
    }

    with pytest.raises(UmpireSchemaError, match="unknown expression op"):
        UmpireSchema.from_json_obj(json_obj)


def test_schema_from_json_obj_preserves_excluded_warnings() -> None:
    """Excluded rules are warning metadata, not hard failures."""
    json_obj = {
        "version": 1,
        "fields": {"email": {}},
        "rules": [],
        "excluded": [
            {
                "type": "custom",
                "field": "email",
                "description": "Custom callback cannot be serialized",
            }
        ],
    }

    schema = UmpireSchema.from_json_obj(json_obj)

    assert len(schema.excluded) == 1
    assert schema.warnings == ("Excluded rule custom: Custom callback cannot be serialized",)
