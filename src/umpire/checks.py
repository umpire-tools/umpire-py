"""Check operations for Umpire."""

import re
from dataclasses import KW_ONLY, dataclass
from re import Pattern
from typing import Any

from .types import CheckError


@dataclass
class CheckOp:
    """Base class for check operations."""

    _: KW_ONLY
    reason: str | None = None

    def __call__(self, value: Any, field_name: str) -> CheckError | None:
        """Execute the check operation on a value."""
        raise NotImplementedError


@dataclass
class EmailCheck(CheckOp):
    """Check that a value is a valid email address."""

    def __call__(self, value: Any, field_name: str) -> CheckError | None:
        """Check if the value is a valid email."""
        if not isinstance(value, str):
            return CheckError(field=field_name, reason=self.reason or "Must be a string")

        # Basic email validation regex
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, value):
            return CheckError(
                field=field_name, reason=self.reason or "Must be a valid email address"
            )

        return None


@dataclass
class UrlCheck(CheckOp):
    """Check that a value is a valid URL."""

    def __call__(self, value: Any, field_name: str) -> CheckError | None:
        """Check if the value is a valid URL."""
        if not isinstance(value, str):
            return CheckError(field=field_name, reason=self.reason or "Must be a string")

        # Basic URL validation
        url_pattern = r"^https?://[^\s/$.?#].[^\s]*$"
        if not re.match(url_pattern, value):
            return CheckError(field=field_name, reason=self.reason or "Must be a valid URL")

        return None


@dataclass
class MatchesCheck(CheckOp):
    """Check that a value matches a pattern."""

    pattern: str | Pattern[str]

    def __call__(self, value: Any, field_name: str) -> CheckError | None:
        """Check if the value matches the pattern."""
        if not isinstance(value, str):
            return CheckError(field=field_name, reason=self.reason or "Must be a string")

        if isinstance(self.pattern, str):
            if not re.search(self.pattern, value):
                return CheckError(
                    field=field_name,
                    reason=self.reason or "Must match the required format",
                )
        else:
            if not self.pattern.search(value):
                return CheckError(
                    field=field_name,
                    reason=self.reason or "Must match the required format",
                )

        return None


@dataclass
class MinLengthCheck(CheckOp):
    """Check that a string value has a minimum length."""

    minimum: int

    def __call__(self, value: Any, field_name: str) -> CheckError | None:
        """Check if the string value has at least the minimum length."""
        if not isinstance(value, (str, list, tuple)):
            return CheckError(field=field_name, reason=self.reason or "Must have a length")

        if len(value) < self.minimum:
            return CheckError(
                field=field_name,
                reason=self.reason or f"Must be at least {self.minimum} characters",
            )

        return None


@dataclass
class MaxLengthCheck(CheckOp):
    """Check that a string value has a maximum length."""

    maximum: int

    def __call__(self, value: Any, field_name: str) -> CheckError | None:
        """Check if the string value has at most the maximum length."""
        if not isinstance(value, (str, list, tuple)):
            return CheckError(field=field_name, reason=self.reason or "Must have a length")

        if len(value) > self.maximum:
            return CheckError(
                field=field_name,
                reason=self.reason or f"Must be {self.maximum} characters or fewer",
            )

        return None


@dataclass
class MinValueCheck(CheckOp):
    """Check that a numeric value is at least a minimum."""

    minimum: int | float

    def __call__(self, value: Any, field_name: str) -> CheckError | None:
        """Check if the numeric value is at least the minimum."""
        if not isinstance(value, (int, float)):
            return CheckError(field=field_name, reason=self.reason or "Must be a number")

        if value < self.minimum:
            return CheckError(
                field=field_name, reason=self.reason or f"Must be at least {self.minimum}"
            )

        return None


@dataclass
class MaxValueCheck(CheckOp):
    """Check that a numeric value is at most a maximum."""

    maximum: int | float

    def __call__(self, value: Any, field_name: str) -> CheckError | None:
        """Check if the numeric value is at most the maximum."""
        if not isinstance(value, (int, float)):
            return CheckError(field=field_name, reason=self.reason or "Must be a number")

        if value > self.maximum:
            return CheckError(
                field=field_name, reason=self.reason or f"Must be {self.maximum} or less"
            )

        return None


@dataclass
class RangeValueCheck(CheckOp):
    """Check that a numeric value is within a range."""

    minimum: int | float
    maximum: int | float

    def __call__(self, value: Any, field_name: str) -> CheckError | None:
        """Check if the numeric value is within the range."""
        if not isinstance(value, (int, float)):
            return CheckError(field=field_name, reason=self.reason or "Must be a number")

        if not (self.minimum <= value <= self.maximum):
            return CheckError(
                field=field_name,
                reason=self.reason or f"Must be between {self.minimum} and {self.maximum}",
            )

        return None


@dataclass
class IntegerCheck(CheckOp):
    """Check that a value is an integer."""

    def __call__(self, value: Any, field_name: str) -> CheckError | None:
        """Check if the value is an integer."""
        if not isinstance(value, int) or isinstance(value, bool):
            return CheckError(field=field_name, reason=self.reason or "Must be a whole number")

        return None


def email(reason: str | None = None) -> EmailCheck:
    """Create an email check operation."""
    return EmailCheck(reason=reason)


def url(reason: str | None = None) -> UrlCheck:
    """Create a URL check operation."""
    return UrlCheck(reason=reason)


def matches(pattern: str | Pattern[str], reason: str | None = None) -> MatchesCheck:
    """Create a pattern matching check operation."""
    if isinstance(pattern, str):
        try:
            re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}") from e
    return MatchesCheck(pattern=pattern, reason=reason)


def min_length(minimum: int, reason: str | None = None) -> MinLengthCheck:
    """Create a minimum length check operation."""
    return MinLengthCheck(minimum=minimum, reason=reason)


def max_length(maximum: int, reason: str | None = None) -> MaxLengthCheck:
    """Create a maximum length check operation."""
    return MaxLengthCheck(maximum=maximum, reason=reason)


def min_value(minimum: int | float, reason: str | None = None) -> MinValueCheck:
    """Create a minimum value check operation."""
    return MinValueCheck(minimum=minimum, reason=reason)


def max_value(maximum: int | float, reason: str | None = None) -> MaxValueCheck:
    """Create a maximum value check operation."""
    return MaxValueCheck(maximum=maximum, reason=reason)


def range_value(
    minimum: int | float, maximum: int | float, reason: str | None = None
) -> RangeValueCheck:
    """Create a range value check operation."""
    return RangeValueCheck(minimum=minimum, maximum=maximum, reason=reason)


def integer(reason: str | None = None) -> IntegerCheck:
    """Create an integer check operation."""
    return IntegerCheck(reason=reason)


# Create a namespace object for check operations
class CheckOps:
    """Namespace for check operations."""

    @staticmethod
    def email(reason: str | None = None) -> EmailCheck:
        """Create an email check operation."""
        return email(reason)

    @staticmethod
    def url(reason: str | None = None) -> UrlCheck:
        """Create a URL check operation."""
        return url(reason)

    @staticmethod
    def matches(pattern: str | Pattern[str], reason: str | None = None) -> MatchesCheck:
        """Create a pattern matching check operation."""
        return matches(pattern, reason)

    @staticmethod
    def min_length(minimum: int, reason: str | None = None) -> MinLengthCheck:
        """Create a minimum length check operation."""
        return min_length(minimum, reason)

    @staticmethod
    def max_length(maximum: int, reason: str | None = None) -> MaxLengthCheck:
        """Create a maximum length check operation."""
        return max_length(maximum, reason)

    @staticmethod
    def min_value(minimum: int | float, reason: str | None = None) -> MinValueCheck:
        """Create a minimum value check operation."""
        return min_value(minimum, reason)

    @staticmethod
    def max_value(maximum: int | float, reason: str | None = None) -> MaxValueCheck:
        """Create a maximum value check operation."""
        return max_value(maximum, reason)

    @staticmethod
    def range_value(
        minimum: int | float, maximum: int | float, reason: str | None = None
    ) -> RangeValueCheck:
        """Create a range value check operation."""
        return range_value(minimum, maximum, reason)

    @staticmethod
    def integer(reason: str | None = None) -> IntegerCheck:
        """Create an integer check operation."""
        return integer(reason)


# Create an instance of CheckOps for the public API
check_ops = CheckOps()
