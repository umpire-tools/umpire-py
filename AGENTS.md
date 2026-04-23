# AGENTS.md

Guidance for contributors and coding agents working on `umpire-py`.

## Mission

Build a Python-native reusable library for Umpire semantics (availability, validity, and foul transitions), not a line-by-line port of TypeScript/Kotlin/Dart code.

## Priority order

1. Behavioral correctness
2. Pythonic API design
3. Minimal, maintainable implementation
4. Performance tuning (only after correctness)

## Pythonic guardrails (important)

- Use `snake_case` for functions/args/attrs.
- Prefer `dataclasses`, `Enum`, and explicit type aliases over OO-heavy class hierarchies.
- Accept `Mapping[str, Any]` / `Sequence[...]` in public APIs where possible; avoid requiring concrete `dict`/`list`.
- Return plain Python types and dataclasses; avoid framework-specific abstractions.
- Raise clear exceptions for invalid schema/configuration; do not silently coerce bad input.

## Anti-patterns to avoid

- Do not mirror TS naming (`enabledWhen`, `defaultValue`, etc.) in Python public APIs.
- Do not introduce builder DSLs that fight Python style.
- Do not add clever metaprogramming or plugin systems early.
- Do not add runtime deps unless they clearly pay for themselves.

## Umpire-specific gotchas

- `check()` computes current availability/validity state.
- `play(before, after, values)` is transition-based; it must use before→after semantics, not recompute from scratch.
- First evaluation should not fabricate fouls.
- Keep expression semantics distinct:
  - `cond`: boolean condition check
  - `condEq`: condition scalar equals static value
  - `condIn`: condition scalar in static set
  - `fieldInCond`: field scalar in runtime condition array

## Async model

- Keep sync and async paths explicit:
  - `check(...)` for already-resolved conditions
  - `check_async(...)` for provider resolution
- Resolve async providers concurrently.

## Testing expectations

- Default to test-first for bug fixes and behavior changes.
- Add focused tests for each rule/edge case.
- Favor readable table-driven tests over dense helper abstractions.

## Scope control

- Default: do exactly what the task asks.
- In autonomous/orchestrator runs, take adjacent low-risk steps needed to fully deliver the requested outcome.
- For high-impact or clearly out-of-scope changes, stop and ask for confirmation.
- Avoid opportunistic refactors.
- Keep public API small until behavior is locked.

## Working plan

Primary implementation plan is in `PYTHON_PORT_PLAN.md`.
Use `AGENT_START_HERE.md` as the entrypoint.
