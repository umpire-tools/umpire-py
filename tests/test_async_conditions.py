"""Tests for async condition providers."""

import asyncio
import time
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
async def test_normalize_providers_propagates_failing_provider() -> None:
    """Provider failures should not be silently converted into values."""
    from umpire.schema.providers import normalize_providers

    def failing_provider():
        raise TypeError("Provider failed")

    providers: dict[str, ConditionProvider] = {
        "static_value": "static",
        "failing_provider": failing_provider,
    }

    with pytest.raises(TypeError, match="Provider failed"):
        normalize_providers(providers)


@pytest.mark.asyncio
async def test_check_async_resolves_providers_concurrently() -> None:
    """Async providers should resolve concurrently, not sequentially."""
    fields = {"admin_field": FieldDef(required=False)}

    from umpire import enabled_when

    rules = [
        enabled_when(
            "admin_field",
            when=lambda values, conditions: conditions["first"] and conditions["second"],
        )
    ]
    u = umpire(fields, rules)

    async def first_provider() -> bool:
        await asyncio.sleep(0.05)
        return True

    async def second_provider() -> bool:
        await asyncio.sleep(0.05)
        return True

    start = time.perf_counter()
    result = await u.check_async({}, {"first": first_provider, "second": second_provider})
    elapsed = time.perf_counter() - start

    assert result["admin_field"].enabled is True
    assert elapsed < 0.09


@pytest.mark.asyncio
async def test_check_async_supports_sync_provider_returning_awaitable() -> None:
    """Providers may be ordinary callables that return awaitables."""
    fields = {"admin_field": FieldDef(required=False)}

    from umpire import enabled_when

    rules = [enabled_when("admin_field", when=lambda values, conditions: conditions["is_admin"])]
    u = umpire(fields, rules)

    async def resolve_admin() -> bool:
        await asyncio.sleep(0)
        return True

    def provider():
        return resolve_admin()

    result = await u.check_async({}, {"is_admin": provider})

    assert result["admin_field"].enabled is True


@pytest.mark.asyncio
async def test_check_async_propagates_async_provider_failure() -> None:
    """Async provider failures should fail the check instead of being hidden."""
    fields = {"admin_field": FieldDef(required=False)}
    u = umpire(fields)

    async def failing_provider() -> bool:
        raise RuntimeError("condition exploded")

    with pytest.raises(RuntimeError, match="condition exploded"):
        await u.check_async({}, {"is_admin": failing_provider})


@pytest.mark.asyncio
async def test_check_async_with_previous_values_for_one_of() -> None:
    """check_async should forward previous_values for one_of branch resolution."""
    from umpire import one_of
    from umpire.types import IsEmptyStrategy

    fields = {
        "email": FieldDef(is_empty=IsEmptyStrategy.STRING),
        "phone": FieldDef(is_empty=IsEmptyStrategy.STRING),
    }
    rules = [one_of("contact", {"email": ["email"], "phone": ["phone"]})]
    u = umpire(fields, rules)

    result = await u.check_async(
        {"email": "a@b.com", "phone": "555-1234"},
        previous_values={"email": "", "phone": "555-1234"},
    )
    assert result["email"].enabled is True
    assert result["phone"].enabled is False
