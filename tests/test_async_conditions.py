"""Tests for async condition providers."""

import asyncio
from typing import Any

import pytest

from umpire import FieldDef, umpire
from umpire.schema.providers import ConditionProvider


async def async_condition_provider() -> bool:
    """Async condition provider that returns True."""
    await asyncio.sleep(0.01)  # Simulate async work
    return True


def sync_condition_provider() -> bool:
    """Sync condition provider that returns False."""
    return False


def test_is_async_provider() -> None:
    """Test the is_async_provider utility function."""
    from umpire.schema.providers import is_async_provider

    # Test with async function
    assert is_async_provider(async_condition_provider) is True

    # Test with sync function
    assert is_async_provider(sync_condition_provider) is False

    # Test with static value
    assert is_async_provider(True) is False
    assert is_async_provider("static_value") is False


@pytest.mark.asyncio
async def test_check_async_with_async_provider() -> None:
    """Test Umpire.check_async() with async condition providers."""
    fields = {
        "email": FieldDef(required=True),
        "admin_field": FieldDef(required=False),
    }

    def is_admin(values: dict[str, Any], conditions: dict[str, Any]) -> bool:
        return conditions.get("is_admin") is True

    from umpire import enabled_when

    rules = [enabled_when("admin_field", when=is_admin, reason="Admin only")]

    u = umpire(fields, rules)

    # Test with async provider
    conditions: dict[str, ConditionProvider] = {
        "is_admin": async_condition_provider,
    }

    # Test with resolved conditions for now
    result = await u.check_async({"email": "test@example.com"}, conditions)
    assert result["admin_field"].enabled is True


@pytest.mark.asyncio
async def test_normalize_providers_with_failing_provider() -> None:
    """Test normalize_providers with a provider that raises TypeError."""
    from umpire.schema.providers import normalize_providers

    # Create a provider that will raise TypeError when called
    def failing_provider():
        raise TypeError("Provider failed")

    # Test with mixed providers including one that fails
    providers: dict[str, ConditionProvider] = {
        "static_value": "static",
        "failing_provider": failing_provider,
    }

    # Normalize providers - the failing provider should remain as a callable
    normalized = normalize_providers(providers)
    assert "static_value" in normalized
    assert "failing_provider" in normalized
    assert normalized["static_value"] == "static"
    assert callable(normalized["failing_provider"])  # Should remain as callable
