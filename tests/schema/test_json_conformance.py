"""Conformance tests for upstream @umpire/json fixtures."""

import json
from pathlib import Path
from typing import Any

import pytest

from umpire import FieldAvailability, UmpireSchema, umpire

CONFORMANCE_DIR = Path("/Users/douglasbrown/Code/umpire/packages/json/conformance")


def _load_index() -> dict[str, Any]:
    if not CONFORMANCE_DIR.exists():
        pytest.skip("upstream @umpire/json conformance fixtures are not available")
    return json.loads((CONFORMANCE_DIR / "index.json").read_text())


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


@pytest.mark.parametrize("entry", _load_index()["fixtures"])
def test_upstream_json_fixture(entry: dict[str, Any]) -> None:
    """Python runtime should match portable JSON fixture expectations."""
    fixture = json.loads((CONFORMANCE_DIR / entry["path"]).read_text())
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


@pytest.mark.parametrize("entry", _load_index()["failures"])
def test_upstream_json_failure_fixture(entry: dict[str, Any]) -> None:
    """Python runtime should reject invalid schemas/runtime inputs like upstream."""
    fixture = json.loads((CONFORMANCE_DIR / entry["path"]).read_text())

    for failure in fixture["failures"]:
        if failure["phase"] == "validate":
            with pytest.raises(Exception, match=failure["errorIncludes"]):
                UmpireSchema.from_json_obj(failure["schema"])
            continue

        schema = UmpireSchema.from_json_obj(failure["schema"])
        u = umpire(schema.fields, schema.rules)
        with pytest.raises(Exception, match=failure["errorIncludes"]):
            u.check(failure.get("values", {}), failure.get("conditions", {}))
