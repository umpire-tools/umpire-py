"""Condition provider utilities for Umpire."""

import inspect
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

# Type alias for condition providers
ConditionProvider = (
    Any  # Static value
    | Callable[[], Any]  # Sync provider
    | Callable[[], Awaitable[Any]]  # Async provider
)


def is_async_provider(provider: ConditionProvider) -> bool:
    """Check if a provider is async."""
    if callable(provider):
        return inspect.iscoroutinefunction(provider)
    return False


def normalize_providers(providers: Mapping[str, ConditionProvider]) -> dict[str, Any]:
    """
    Normalize condition providers to resolved values.

    For async providers, this function should be called in an async context
    and the providers should be resolved beforehand.
    """
    normalized = {}
    for key, provider in providers.items():
        if callable(provider):
            normalized[key] = provider()
        else:
            normalized[key] = provider
    return normalized
