# umpire-py

Python-native Umpire semantics for object-shaped state with interdependent
availability, validation, and transition reset recommendations.

This package is intentionally small: no required runtime dependencies, typed
dataclasses/enums, and a Pythonic public API rather than a line-by-line port of
the TypeScript package.

## Status

`umpire-py` is an early Python port. The core runtime, JSON schema subset, async
condition providers, and focused contract tests are implemented, but the package
should still be treated as alpha until real downstream integration exercises the
API. The local test suite also runs the upstream `@umpire/json` conformance
fixtures. Set `UMPIRE_JSON_CONFORMANCE_DIR` for local fixture development, or
let the tests fetch the pinned `@umpire/json` package version from npm.

For convenient local runs, copy `.env.example` to `.env` and point
`UMPIRE_JSON_CONFORMANCE_DIR` at a local conformance directory. `.env` is
gitignored and loaded by `make`, so `make check` can use local fixtures without
command-line environment variables.

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

fields = {
    "email": FieldDef(required=True, is_empty=IsEmptyStrategy.STRING),
    "password": FieldDef(required=True, is_empty=IsEmptyStrategy.STRING),
    "confirm_password": FieldDef(is_empty=IsEmptyStrategy.STRING),
    "account_type": FieldDef(default_value="personal"),
    "company_name": FieldDef(is_empty=IsEmptyStrategy.STRING),
    "discount_override": FieldDef(),
    "plan_id": FieldDef(required=True, default_value="basic", is_empty=IsEmptyStrategy.STRING),
}

rules = [
    # Predicate-only requires makes a field conditionally required.
    requires(
        "company_name",
        when=lambda values, conds: values.get("account_type") == "business",
        reason="Company name is required for business accounts",
    ),
    # Dependency-backed requires gates availability until the dependency is satisfied.
    requires("confirm_password", dependency="password"),
    enabled_when(
        "discount_override",
        when=lambda values, conds: conds.get("is_admin") is True,
        reason="Admin only",
    ),
    fair_when(
        "plan_id",
        when=lambda values, conds: values.get("plan_id") in (conds.get("valid_plans") or []),
        reason="Plan is not available for this account",
    ),
    check("email", check_ops.email()),
    check("password", check_ops.min_length(8)),
]

u = umpire(fields, rules)

result = u.check(
    values={
        "email": "user@example.com",
        "password": "password123",
        "confirm_password": "password123",
        "plan_id": "pro",
    },
    conditions={"is_admin": False, "valid_plans": ["basic", "pro", "enterprise"]},
)

for field_name, availability in result.items():
    print(
        field_name,
        availability.enabled,
        availability.required,
        availability.fair,
        availability.satisfied,
        availability.check_errors,
    )
```

## Core Concepts

Each field produces a `FieldAvailability`:

- `enabled`: whether the field should be interactive.
- `required`: whether the field is structurally required while enabled.
- `fair`: whether the current value is allowed by availability rules.
- `satisfied`: whether the current value is present according to the field's
  `IsEmptyStrategy`.
- `check_errors`: validation errors from `check(...)` rules.
- `reason`: the first availability/fairness reason, useful for display and
  transition recommendations.

`check(...)` computes the current state. `play(before, after, values)` compares
two already-computed states and recommends resets only for values that became
disabled or foul and still hold a satisfied stale value.

## Rule Types

- `requires(field, when=...)`: makes a field conditionally required.
- `requires(field, dependency=...)`: enables a field only when the dependency is
  satisfied, enabled, and fair.
- `enabled_when(field, when, reason=None)`: enables or disables a field.
- `fair_when(field, when, reason=None)`: marks a satisfied value as fair or foul.
- `disables(source, targets, when=None, reason=None)`: disables targets when the
  source value is satisfied and the optional predicate passes.
- `one_of(group, branches, reason=None)`: enables only the active named branch.
- `any_of(rules)`: applies OR semantics across compatible inner rules.
- `check(field, op)`: applies validation checks and reports `check_errors`.

## Check Operations

The `check_ops` namespace provides common validation operations:

- `email(reason=None)`
- `url(reason=None)`
- `matches(pattern, reason=None)`
- `min_length(minimum, reason=None)`
- `max_length(maximum, reason=None)`
- `min_value(minimum, reason=None)`
- `max_value(maximum, reason=None)`
- `range_value(minimum, maximum, reason=None)`
- `integer(reason=None)`

## JSON Schema Loading

`UmpireSchema.from_json_obj(...)` and `UmpireSchema.from_json_str(...)` load the
supported `@umpire/json` subset into Python fields and rules.

```python
from umpire import UmpireSchema, umpire

schema = UmpireSchema.from_json_obj(
    {
        "version": 1,
        "conditions": {"isAdmin": {"type": "boolean"}},
        "fields": {"discount": {}},
        "rules": [
            {
                "type": "enabledWhen",
                "field": "discount",
                "when": {"op": "cond", "condition": "isAdmin"},
                "reason": "Admin only",
            }
        ],
    }
)

u = umpire(schema.fields, schema.rules)
```

Schema loading validates version, field references, expression ops, and check
ops. Unsupported serialized rules can be preserved in `schema.excluded` with
human-readable `schema.warnings`.

## Async Conditions

Use `check_async(...)` when conditions are provided by sync or async providers.
Async providers are resolved concurrently and provider failures propagate.

```python
from umpire import FieldDef, enabled_when, umpire


async def is_admin_provider() -> bool:
    return True


u = umpire(
    {"admin_field": FieldDef()},
    [enabled_when("admin_field", lambda values, conds: conds["is_admin"])],
)

result = await u.check_async({}, {"is_admin": is_admin_provider})
```

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
UV_CACHE_DIR=/tmp/uv-cache make check
uv build
```

`make check` runs linting, format checks, mypy, and the test suite.
