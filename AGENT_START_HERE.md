# Agent Start Here

Read this first:

1. `PYTHON_PORT_PLAN.md`
2. `AGENTS.md`

## Scope for current work

Work on **Phase 6** from `PYTHON_PORT_PLAN.md`:

- Comprehensive tests and fixture parity
- Improve test coverage across all modules
- Ensure all rule types are properly tested
- Ensure all check operations are properly tested

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
✅ Phase 1 complete:
- Core types implemented in src/umpire/types.py
- umpire(...) constructor and Umpire class implemented in src/umpire/engine.py
- Umpire.check() method implemented
- All tests passing, quality checks passing
✅ Phase 2 complete:
- Rule constructors implemented in src/umpire/rules/
- Umpire.play() method enhanced with rule evaluation
- Tests for rules and play method implemented
✅ Phase 3 complete:
- Named check ops fully implemented in src/umpire/checks.py
- Schema loading implemented in src/umpire/schema/
- Expression compiler working correctly
✅ Phase 4 complete:
- Async condition providers implemented
- check_async() method implemented
- Tests for async functionality implemented and passing
✅ Phase 5 in progress:
- Comprehensive tests and fixture parity being improved
- Test coverage increased from 68% to 84%
- Missing rule types (disables, one_of, any_of) now properly tested
- All check operations now properly tested

(End of file - total 50 lines)
