"""Conformance tests for the pinned umpire-spec fixtures."""

import json
import re
from typing import Any

import pytest

from umpire import FieldAvailability, UmpireSchema, UmpireSchemaError, umpire

from .conformance_fixtures import resolve_conformance_dir

CONFORMANCE_DIR = resolve_conformance_dir()


def _index() -> dict[str, Any]:
    return json.loads((CONFORMANCE_DIR / "index.json").read_text())


def _load(entry: dict[str, Any]) -> dict[str, Any]:
    fixture: dict[str, Any] = json.loads((CONFORMANCE_DIR / entry["path"]).read_text())
    return fixture


def _fixture_params() -> list[pytest.param]:
    return [pytest.param(entry, id=entry["id"]) for entry in _index()["fixtures"]]


def _failure_params() -> list[pytest.param]:
    params: list[pytest.param] = []
    for entry in _index()["failures"]:
        fixture = _load(entry)
        for failure in fixture["failures"]:
            params.append(pytest.param(failure, id=f"{fixture['id']}::{failure['id']}"))
    return params


def _availability(status: FieldAvailability) -> dict[str, Any]:
    result: dict[str, Any] = {
        "enabled": status.enabled,
        "fair": status.fair,
        "required": status.required,
        "reason": status.reason,
        "reasons": list(status.reasons),
        "satisfied": status.satisfied,
    }
    if status.valid is not None:
        result["valid"] = status.valid
    if status.error is not None:
        result["error"] = status.error
    return result


@pytest.mark.parametrize("entry", _fixture_params())
def test_upstream_json_fixtures(entry: dict[str, Any]) -> None:
    """Python runtime should match portable JSON fixture expectations."""
    fixture = _load(entry)
    schema = UmpireSchema.from_json_obj(fixture["schema"])
    u = umpire(schema.fields, schema.rules)

    for case in fixture["cases"]:
        result = u.check(
            case.get("values", {}),
            case.get("conditions", {}),
            previous_values=case.get("prev"),
        )

        assert {field: _availability(status) for field, status in result.items()} == case[
            "expectedAvailability"
        ], f"{fixture['id']}::{case['id']}"


@pytest.mark.parametrize("failure", _failure_params())
def test_upstream_json_failure_fixtures(failure: dict[str, Any]) -> None:
    """Python runtime should reject invalid schemas/runtime inputs like upstream."""
    expected = re.escape(failure["errorIncludes"])

    if failure["phase"] == "validate":
        with pytest.raises(UmpireSchemaError, match=expected):
            UmpireSchema.from_json_obj(failure["schema"])
        return

    schema = UmpireSchema.from_json_obj(failure["schema"])
    u = umpire(schema.fields, schema.rules)
    with pytest.raises(Exception, match=expected):
        u.check(failure.get("values", {}), failure.get("conditions", {}))
