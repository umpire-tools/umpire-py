"""Conformance tests for upstream @umpire/json fixtures."""

import json
from pathlib import Path
from typing import Any

import pytest

from umpire import FieldAvailability, UmpireSchema, umpire

from .conformance_fixtures import resolve_conformance_dir


@pytest.fixture(scope="session")
def conformance_dir(pytestconfig: pytest.Config) -> Path:
    return resolve_conformance_dir(pytestconfig)


@pytest.fixture(scope="session")
def conformance_index(conformance_dir: Path) -> dict[str, Any]:
    return json.loads((conformance_dir / "index.json").read_text())


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


def test_upstream_json_fixtures(
    conformance_dir: Path,
    conformance_index: dict[str, Any],
) -> None:
    """Python runtime should match portable JSON fixture expectations."""
    for entry in conformance_index["fixtures"]:
        fixture = json.loads((conformance_dir / entry["path"]).read_text())
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


def test_upstream_json_failure_fixtures(
    conformance_dir: Path,
    conformance_index: dict[str, Any],
) -> None:
    """Python runtime should reject invalid schemas/runtime inputs like upstream."""
    for entry in conformance_index["failures"]:
        fixture = json.loads((conformance_dir / entry["path"]).read_text())

        for failure in fixture["failures"]:
            if failure["phase"] == "validate":
                with pytest.raises(Exception, match=failure["errorIncludes"]):
                    UmpireSchema.from_json_obj(failure["schema"])
                continue

            schema = UmpireSchema.from_json_obj(failure["schema"])
            u = umpire(schema.fields, schema.rules)
            with pytest.raises(Exception, match=failure["errorIncludes"]):
                u.check(failure.get("values", {}), failure.get("conditions", {}))
