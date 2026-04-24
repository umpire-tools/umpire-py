# Umpire — Python Port Plan

Purpose: give implementation agents a concrete, Pythonic path to ship `umpire-py` as a reusable library.

This started as a starter execution plan (not a full spec rewrite). It became
the working recovery plan for completing the Python port.

Current status: **recovery complete for the current Python package scope, with
upstream JSON conformance fixtures passing locally**. The package remains alpha,
but R1-R7 below have been executed and committed. The local quality suite passes
with `UV_CACHE_DIR=/tmp/uv-cache make check`.

---

## Completion audit

Initial audit after the Qwen3 Coder port found the following blockers, all of
which are now addressed for the supported Python surface:

1. `check(...)` rules are not evaluated by `Umpire.check()`, so invalid values
   do not populate `FieldAvailability.check_errors`.
2. `any_of(...)` is currently a no-op instead of OR semantics across compatible
   inner rules.
3. `requires(field, dependency=...)` stores the dependency but does not evaluate
   dependency satisfaction or dependency availability.
4. `one_of(...)` uses a flat branch list and "disable all but first populated"
   behavior, but Umpire core uses named branches and previous-state assisted
   active-branch resolution.
5. Disabled fields can still report `required=True`; Umpire core semantics say
   disabled fields are not required.
6. `play(...)` is not transition-correct. It currently fabricates missing
   required-value fouls and misses the core reset recommendation behavior:
   suggest resets only for fields that became disabled or foul and still hold a
   stale satisfied value.
7. Field satisfaction and required-ness are conflated. Umpire core keeps
   structural availability (`enabled`, `required`, `fair`) separate from whether
   the current value is satisfied/present.
8. Schema loading parses fields only, drops rules and conditions, and does not
   validate field references, expression ops, check ops, or excluded rules.
9. Expression compilation only covers a tiny subset and often returns `False`
   where schema/runtime validation should raise a clear exception.
10. Tests asserted placeholders in several places instead of the intended
    behavior, so passing tests did not prove port completeness.

Porting north star:

- Match Umpire semantics, not TypeScript names or implementation shape.
- Keep the Python API small and Pythonic.
- Prefer focused parity tests and simple dataclass-based internals over a
  line-by-line port.

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
- `FieldAvailability(enabled: bool, required: bool, fair: bool, satisfied: bool, reason: str | None, check_errors: tuple[CheckError, ...])`
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

## Recovery execution order

Work test-first. For each phase:

1. Add failing tests that describe the intended Umpire semantics.
2. Implement the smallest Pythonic change that passes them.
3. Run `UV_CACHE_DIR=/tmp/uv-cache make check`.
4. Update this plan if the phase uncovers a new semantic decision.

| Phase | Content | Completion gate |
|---|---|---|
| R1 | Replace placeholder tests with contract/parity tests | Tests fail against current placeholders for `check`, `requires`, `any_of`, `one_of`, `play`, and schema rules |
| R2 | Core state model and emptiness | `enabled`, `required`, `fair`, value satisfaction, defaults, and `IsEmptyStrategy` are distinct and covered |
| R3 | Rule evaluation semantics | `requires`, `enabled_when`, `disables`, `fair_when`, `check`, `any_of`, and `one_of` match the intended Umpire behavior |
| R4 | Transition semantics | `play()` only reports before-to-after reset recommendations for newly disabled or newly foul satisfied values |
| R5 | Schema loading and validation | JSON schema fields, rules, expressions, checks, conditions, and excluded warnings load or fail clearly |
| R6 | Async hardening | Sync/static/async providers resolve correctly, async providers run concurrently, and provider failures propagate |
| R7 | Docs/API/release polish | README examples match behavior, public API is typed, and no TS-style names leak into Python APIs |

Completion status:

- R1-R4 complete in commit `b75aead`.
- R5 complete in commit `c306557`.
- R6 complete in commit `56feaab`.
- R7 complete after README/example/plan polish.
- JSON conformance added after R7 in response to review; the Python runtime now
  runs the upstream fixture/failure set from
  `~/Code/umpire/packages/json/conformance` when available.

Suggested R1 test list:

- `check("email", check_ops.email())` adds one `CheckError` for invalid email
  and none for valid or unsatisfied inactive values.
- Disabled fields report `required=False`.
- `requires("confirm", dependency="password")` requires dependency satisfaction
  and dependency availability/fairness.
- Multiple gate rules on the same target are ANDed.
- `any_of([...])` implements OR across compatible rule constraints.
- `one_of(...)` supports named branches and previous-state resolution.
- `play(before, after, values)` returns no fouls for first evaluation or
  unchanged snapshots.
- `play(...)` recommends resetting a stale value only when that field became
  disabled or foul.
- `UmpireSchema.from_json_obj(...)` parses rules and raises on unknown fields or
  unknown expression/check ops.
- `fieldInCond` raises for non-array runtime conditions instead of silently
  returning `False`.

Implementation notes for R2-R4:

- Consider adding `satisfied: bool` to `FieldAvailability` if it keeps the
  Python model honest. If that public API expansion feels too large, keep
  satisfaction internal but do not use `required` as a proxy for missing value.
- Rule evaluation should be deterministic and stable across calls. Avoid
  mutating caller-provided `values` or `conditions`.
- Prefer a small internal evaluator over many ad hoc `isinstance` branches in
  `Umpire.check()`. A light protocol/dataclass approach is enough; avoid a
  heavy class hierarchy unless it demonstrably simplifies behavior.
- Keep `check` rule errors separate from `fair_when`. `check` is a validation
  error surface; `fair_when` is availability/foul semantics.
- `play()` should compare real before/after availability, not recompute from
  scratch unless the API is intentionally changed to accept snapshots.

Implementation notes for R5:

- Preserve Python public names even when parsing JSON names from `@umpire/json`.
  For example, accept JSON `default`/`defaultValue` only at the schema boundary
  and expose `default_value` in Python.
- Validate `version == 1`.
- Validate that all rule and expression field references exist.
- Validate known expression ops and check ops.
- Preserve `excluded` as warning-level metadata, not a hard error.
- Build usable `Rule` objects from parsed schema rules.

Historical phase table from the original starter plan:

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
