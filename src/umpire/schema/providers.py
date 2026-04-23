"""Condition provider utilities for Umpire."""

from collections.abc import Awaitable, Callable
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
        import inspect

        return inspect.iscoroutinefunction(provider)
    return False


def normalize_providers(providers: dict[str, ConditionProvider]) -> dict[str, Any]:
    """
    Normalize condition providers to resolved values.

    For async providers, this function should be called in an async context
    and the providers should be resolved beforehand.
    """
    normalized = {}
    for key, provider in providers.items():
        if callable(provider):
            # For sync providers, call them
            # For async providers, they should already be resolved
            try:
                normalized[key] = provider()
            except TypeError:
                # If provider() fails, it might be an async provider that wasn't resolved
                normalized[key] = provider
        else:
            # Static value
            normalized[key] = provider
    return normalized
