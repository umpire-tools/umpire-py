# umpire-py

🛂 Pythonic reactive derived state for forms and apps with interdependent options.

## Status

Initial project scaffold for a reusable Python library.

## Installation

```bash
pip install umpire-py
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
