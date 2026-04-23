# Umpire — Python Port Plan

Purpose: give implementation agents a concrete, Pythonic path to ship `umpire-py` as a reusable library.

This is a starter execution plan (not a full spec rewrite).

---

## Overview

Port the core Umpire model (`check` + `play`) to Python first, then add schema loading and async condition resolution.

For Python, prefer a **single package** initially:

- **`umpire`** — pure Python runtime (no framework dependency)

Optional integrations (FastAPI, Pydantic convenience, form adapters) can be separate packages later if demand appears.

---

## Product goals

1. Deterministic, testable rule evaluation.
2. Typed public API that feels natural in Python.
3. Zero required runtime dependencies for core.
4. JSON schema compatibility with `@umpire/json` output.

---

## Public API (Pythonic)

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

u = umpire(
    fields={
        "email": FieldDef(required=True, is_empty=IsEmptyStrategy.STRING),
        "account_type": FieldDef(required=True, default_value="personal"),
        "company_name": FieldDef(required=False, is_empty=IsEmptyStrategy.STRING),
        "plan_id": FieldDef(required=True, is_empty=IsEmptyStrategy.STRING),
    },
    rules=[
        requires(
            "company_name",
            when=lambda values, conds: values.get("account_type") == "business",
            reason="Company name is required for business accounts",
        ),
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
    ],
)

after = u.check(values={"email": "x@y.com", "plan_id": "pro"}, conditions={"is_admin": False})
fouls = u.play(before=before, after=after, values={"plan_id": "pro"})
```

---

## Core types

Use `dataclasses` + `Enum` + `typing`.

- `FieldDef(required: bool = False, default_value: Any = None, is_empty: IsEmptyStrategy = PRESENT)`
- `IsEmptyStrategy`: `STRING | NUMBER | BOOLEAN | ARRAY | PRESENT`
- `FieldAvailability(enabled: bool, required: bool, fair: bool, check_errors: tuple[CheckError, ...])`
- `CheckError(field: str, reason: str)`
- `Foul(field: str, reason: str, suggested_value: Any | None = None)`
- `Rule` protocol or callable object (internal shape is implementation detail)

Type aliases:

- `Values = Mapping[str, Any]`
- `Conditions = Mapping[str, Any]`
- `Predicate = Callable[[Values, Conditions], bool]`

---

## Rule constructors

Implement first-class constructors mirroring core concepts:

- `requires(field, dependency=None, when=None, reason=None)`
- `enabled_when(field, when, reason=None)`
- `disables(source, targets, when=None, reason=None)`
- `one_of(group, branches)`
- `any_of(rules)`
- `fair_when(field, when, reason=None)`
- `check(field, op)`

Keep snake_case naming in Python.

---

## check ops

`check_ops` namespace/object with:

- `email(reason=None)`
- `url(reason=None)`
- `matches(pattern, reason=None)`
- `min_length(minimum, reason=None)`
- `max_length(maximum, reason=None)`
- `min_value(minimum, reason=None)`
- `max_value(maximum, reason=None)`
- `range_value(minimum, maximum, reason=None)`
- `integer(reason=None)`

`matches` should accept either `str` or compiled `re.Pattern`.

---

## JSON schema loading (`schema.build(...)`)

Provide:

- `UmpireSchema.from_json_obj(dict_obj)`
- `UmpireSchema.from_json_str(json_text)`
- `UmpireSchema.build(conditions: dict[str, ConditionProvider] | None = None, rules: Sequence[Rule] = ())`

Rules for loader:

1. Validate `version == 1`; otherwise raise `UmpireSchemaError`.
2. Validate field references in rules.
3. Validate known expression/check op names.
4. Preserve `excluded` as warnings (not hard errors).

---

## Async conditions

Support both sync and async condition providers.

- Sync: `u.check(values, conditions=resolved_conditions)`
- Async: `await u.check_async(values)` (resolves providers concurrently)

Implementation guidance:

- Represent provider as `Callable[[], Any] | Callable[[], Awaitable[Any]] | Any`.
- In `check_async`, normalize providers and resolve via `asyncio.gather`.
- `play(...)` remains synchronous.

---

## Package layout

```text
src/umpire/
  __init__.py
  types.py                # FieldDef, FieldAvailability, Foul, CheckError, enums
  engine.py               # Umpire class, umpire(...) constructor
  rules/
    __init__.py
    base.py
    requires.py
    enabled_when.py
    disables.py
    one_of.py
    any_of.py
    fair_when.py
    check.py
  checks.py               # CheckOp + check_ops implementation
  schema/
    __init__.py
    model.py              # UmpireSchema
    expr.py               # expression compiler
    providers.py          # condition provider utilities
```

Tests:

```text
tests/
  test_engine.py
  test_rules.py
  test_checks.py
  test_play.py
  schema/
    test_schema_load.py
    test_expr_ops.py
  test_async_conditions.py
```

---

## Implementation guidance for LLM jump-start

### 1) Deterministic evaluation order

- Evaluate rules in input order.
- Build availability in one pass, then checks/fairness pass.
- Do not mutate caller-provided `values` / `conditions` mappings.

### 2) Foul transition semantics

- `play(before, after, values)` compares availability state transition.
- Fouls should only reflect relevant before→after changes.
- First `check` call should not produce fouls by itself.

### 3) Expression op semantics (easy to mix up)

- `cond`: boolean condition truthy check.
- `condEq`: condition scalar equals static value.
- `condIn`: condition scalar is in static list.
- `fieldInCond`: field scalar is in condition-provided dynamic list.

`condIn` and `fieldInCond` are not interchangeable.

### 4) Schema `excluded` behavior

- Emit warning-level signal.
- Continue loading schema successfully.

### 5) Async provider resolution

- Resolve all async providers in parallel.
- If any provider fails, propagate failure and skip evaluation.

---

## Testing strategy

Required baseline:

1. Rule behavior parity tests (`requires`, `enabled_when`, `fair_when`, `check`).
2. `play` transition tests (before/after edge cases).
3. Expression compiler tests for all condition ops.
4. Schema validation failure tests.
5. Async condition resolution tests (parallel + failure propagation).

Nice-to-have after baseline:

- Property tests for idempotence/determinism (Hypothesis).

---

## Execution order

| Phase | Content |
|---|---|
| 1 | Core types + `umpire(...)` + `Umpire.check()` |
| 2 | Rule constructors + `Umpire.play()` |
| 3 | Named check ops |
| 4 | Schema loading + expression compiler |
| 5 | Async condition providers + `check_async()` |
| 6 | Comprehensive tests + fixture parity |
| 7 | Packaging polish (API surface, docs, release checklist) |

Parallelization guidance:

- Phase 3 can run in parallel with late Phase 2.
- Phase 6 can begin as soon as any phase lands (test-first for each feature).

---

## Divergence from Dart/Kotlin plans

| Decision | Python |
|---|---|
| Artifact split | Start single package (`umpire`) |
| API style | Functional constructors + dataclasses |
| Async model | `asyncio` with explicit `check_async` |
| Serialization | `json` stdlib (no required dep) |
| Typing model | Gradual typing (`typing`, `Protocol`) |
| Reactive integration | Out of scope for v0 core |

---

## Open questions

1. Should we keep stdlib-only runtime forever, or allow optional `pydantic` helpers?
2. Do we want immutable mapping inputs (`Mapping`) only, or support mutable dict ergonomics explicitly?
3. Should `check_ops.email/url` rely on regex-only validation or optional external validators?
4. Is a future `umpire-fastapi` adapter worth creating, or should examples suffice?
