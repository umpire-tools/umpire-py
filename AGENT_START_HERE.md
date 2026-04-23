# Agent Start Here

Read this first:

1. `PYTHON_PORT_PLAN.md`
2. `AGENTS.md`

## Scope for first pass

Work **Phase 1 only** from `PYTHON_PORT_PLAN.md`:

- Core types
- `umpire(...)` constructor
- `Umpire.check()`

Do not start rules beyond minimum scaffolding for `check()` and do not implement schema loading yet.

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
