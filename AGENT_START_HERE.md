# Agent Start Here

Read this first:

1. `PYTHON_PORT_PLAN.md`
2. `AGENTS.md`

## Scope for current work

Work from **Recovery execution order** in `PYTHON_PORT_PLAN.md`.

Start with **R5: Schema loading and validation** unless the user asks for a
narrower task.

The current package is a scaffold, not a complete port. Do not continue
packaging/release polish until the behavioral blockers in `PYTHON_PORT_PLAN.md`
are resolved.

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

Audit result: **not complete**.

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

Known gaps:

- Schema loading drops rules and conditions.
- Expression compilation is still narrow and too permissive in places.
- Async provider handling still needs the R6 hardening pass.

Use `PYTHON_PORT_PLAN.md` as the source of truth.
