# Agent Start Here

Read this first:

1. `PYTHON_PORT_PLAN.md`
2. `AGENTS.md`

## Scope for current work

Work from **Recovery execution order** in `PYTHON_PORT_PLAN.md`.

The R1-R7 recovery plan is complete for the current Python package scope.
Start from the user's next request.

The package remains alpha, but the previous behavioral blockers in
`PYTHON_PORT_PLAN.md` have been addressed for the supported surface.

## Workflow

1. Add or update tests first for the behavior you are implementing.
2. Implement the smallest change to pass tests.
3. Run:

```bash
make check
```

## Definition of done (per PR)

- Tests for new behavior exist and pass.
- API is typed and Pythonic (`snake_case`, dataclasses/enums/types).
- No TypeScript-style APIs leaked into public surface.
- No unrelated refactors.

## Current Status

Audit result: **recovery complete for current scope**.

What exists:

- Core files and package layout are present.
- Public constructors and check ops exist.
- Basic async provider resolution exists.
- `make check` can pass with a writable uv cache.
- R1-R4 recovery work is complete for the current Python surface:
  - Contract tests now cover `check` errors, dependency-backed `requires`,
    disabled-required behavior, `any_of`, branch-based `one_of`, and `play`.
  - `FieldAvailability` separates structural state from `satisfied` and
    carries transition `reason` metadata.
  - `play()` now recommends resets only for newly disabled or newly foul
    satisfied values.
- R5 schema recovery is complete for the current supported JSON subset:
  - Schema loading parses fields, conditions, rules, check ops, expressions,
    and excluded warning metadata.
  - Schema validation rejects unknown fields, unknown expression ops, unknown
    check ops, and malformed expression shapes.
  - Expression compilation now raises on invalid `fieldInCond` runtime
    condition shapes instead of silently returning `False`.
- R6 async hardening is complete:
  - Static, sync, async, and awaitable-returning condition providers resolve.
  - Async providers are resolved concurrently.
  - Sync and async provider failures propagate instead of being hidden.

Known gaps:

- Package remains alpha until exercised by downstream integrations.
- The schema loader intentionally supports a practical `@umpire/json` subset,
  not every upstream helper surface.

Use `PYTHON_PORT_PLAN.md` as the source of truth.
