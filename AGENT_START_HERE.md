# Agent Start Here

Read this first:

1. `PYTHON_PORT_PLAN.md`
2. `AGENTS.md`

## Scope for current work

Work from **Recovery execution order** in `PYTHON_PORT_PLAN.md`.

Start with **R1: Replace placeholder tests with contract/parity tests** unless
the user asks for a narrower task.

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

Known gaps:

- `check(...)` rules are ignored by `Umpire.check()`.
- `any_of(...)` is a no-op.
- `requires(..., dependency=...)` does not enforce dependency semantics.
- `one_of(...)` does not model named branches or previous-state resolution.
- `play(...)` does not implement Umpire transition reset semantics.
- Schema loading drops rules and conditions.
- Tests currently bless placeholders instead of proving parity.

Use `PYTHON_PORT_PLAN.md` as the source of truth.
