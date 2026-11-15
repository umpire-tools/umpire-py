"""Resolution of the pinned umpire-spec conformance fixtures.

The fixtures live under ``spec/`` at the tag pinned in ``mise.toml`` and are
synced by ``mise run spec-sync``. Resolution never falls back to a published
npm package, so a missing spec checkout fails the conformance tests instead of
silently skipping them.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

CONFORMANCE_DIR_ENV_VAR = "UMPIRE_JSON_CONFORMANCE_DIR"
_SPEC_SYNC_HINT = "run `mise run spec-sync` to sync the pinned umpire-spec fixtures"


def resolve_conformance_dir() -> Path:
    """Return the conformance fixture directory, failing when it is missing."""
    configured = os.environ.get(CONFORMANCE_DIR_ENV_VAR)
    directory = (
        Path(configured).expanduser() if configured else _repository_root() / "spec" / "conformance"
    )

    index = directory / "index.json"
    if not index.is_file():
        pytest.fail(f"Conformance index not found at {index}; {_SPEC_SYNC_HINT}")
    return directory


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]
