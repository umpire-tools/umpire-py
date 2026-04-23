"""Tests for Umpire schema loading."""

import pytest

from umpire import (
    IsEmptyStrategy,
    UmpireSchema,
    UmpireSchemaError,
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
