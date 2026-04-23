# umpire-py

省公安 Pythonic reactive derived state for forms and apps with interdependent options.

Umpire is a Python library for managing form field availability, validation, and dependencies. It provides a clean API for defining rules that determine when fields should be required, enabled, or valid based on the current state of your form.

## Status

✅ Core functionality implemented and tested  
✅ Comprehensive test coverage (97%)  
✅ Ready for initial release  

## Installation

```bash
pip install umpire-py
```

## Quick Start

```python
from umpire import (
    FieldDef,
    IsEmptyStrategy,
    check,
    check_ops,
    enabled_when,
    fair_when,
    requires,
    umpire,
)

# Define fields
fields = {
    "email": FieldDef(required=True, is_empty=IsEmptyStrategy.STRING),
    "account_type": FieldDef(required=True, default_value="personal"),
    "company_name": FieldDef(required=False, is_empty=IsEmptyStrategy.STRING),
    "plan_id": FieldDef(required=True, is_empty=IsEmptyStrategy.STRING),
    "password": FieldDef(required=True),
}

# Define rules
rules = [
    # Require company name for business accounts
    requires(
        "company_name",
        when=lambda values, conds: values.get("account_type") == "business",
        reason="Company name is required for business accounts",
    ),
    # Enable discount override for admin users
    enabled_when(
        "discount_override",
        when=lambda values, conds: conds.get("is_admin") is True,
        reason="Admin only",
    ),
    # Make plan valid based on available plans
    fair_when(
        "plan_id",
        when=lambda values, conds: values.get("plan_id") in (conds.get("valid_plans") or []),
        reason="Plan is not available for this account",
    ),
    # Add validation checks
    check("email", check_ops.email()),
    check("password", check_ops.min_length(8)),
]

# Create Umpire instance
u = umpire(fields, rules)

# Check field availability
result = u.check(
    values={"email": "user@example.com", "plan_id": "pro", "password": "password123"},
    conditions={"is_admin": False, "valid_plans": ["basic", "pro", "enterprise"]},
)

# Print results
for field_name, availability in result.items():
    print(f"{field_name}: enabled={availability.enabled}, required={availability.required}, fair={availability.fair}")
```

## Core Concepts

### Field Availability
Each field has three availability properties:
- **enabled**: Whether the field should be enabled/interactive
- **required**: Whether the field must have a value
- **fair**: Whether the field's current value is valid

### Rule Types

#### `requires(field, when, reason)`
Makes a field required when certain conditions are met.

#### `enabled_when(field, when, reason)`
Enables or disables a field based on conditions.

#### `fair_when(field, when, reason)`
Determines if a field's value is valid based on conditions.

#### `disables(source, targets, when, reason)`
Disables target fields when a source field meets conditions.

#### `one_of(group, branches, reason)`
Ensures only one field in a group is enabled.

#### `any_of(rules)`
Passes if any of the provided rules pass.

#### `check(field, op)`
Applies validation checks to fields.

### Check Operations

The `check_ops` namespace provides common validation operations:
- `email(reason)`: Validates email format
- `url(reason)`: Validates URL format
- `matches(pattern, reason)`: Validates against regex pattern
- `min_length(minimum, reason)`: Validates minimum string length
- `max_length(maximum, reason)`: Validates maximum string length
- `min_value(minimum, reason)`: Validates minimum numeric value
- `max_value(maximum, reason)`: Validates maximum numeric value
- `range_value(minimum, maximum, reason)`: Validates numeric range
- `integer(reason)`: Validates integer values

## Async Support

Umpire supports async condition providers:

```python
import asyncio
from umpire import umpire, FieldDef

async def async_condition_provider():
    await asyncio.sleep(0.1)  # Simulate async work
    return True

# Use async providers
u = umpire({"email": FieldDef(required=True)})
conditions = {"is_admin": async_condition_provider}

# Use check_async for async conditions
result = await u.check_async({"email": "user@example.com"}, conditions)
```

## Development setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
```

## Quality checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Or run everything at once:

```bash
make check
```

## Build

```bash
uv build
```

Build artifacts are written to `dist/`.

## Make targets

```bash
make sync      # install/update dev environment
make check     # lint + format-check + type-check + tests
make build     # build source + wheel distributions
```

## Development setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
```

## Quality checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Or run everything at once:

```bash
make check
```

## Build

```bash
uv build
```

Build artifacts are written to `dist/`.

## Make targets

```bash
make sync      # install/update dev environment
make check     # lint + format-check + type-check + tests
make build     # build source + wheel distributions
```
