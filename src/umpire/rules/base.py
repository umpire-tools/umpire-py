"""Base classes for Umpire rules."""

from ..types import Rule


class BaseRule(Rule):
    """Base class for all Umpire rules."""

    def __init__(self, reason: str | None = None):
        """Initialize rule with optional reason."""
        self.reason = reason
