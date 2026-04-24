"""Helpers for resolving upstream @umpire/json conformance fixtures."""

from __future__ import annotations

import json
import os
import shutil
import tarfile
import urllib.request
from pathlib import Path
from typing import Any

import pytest

PACKAGE_NAME = "@umpire/json"
DEFAULT_VERSION = "0.1.0-alpha.9"
REGISTRY_URL = "https://registry.npmjs.org/@umpire/json"


def resolve_conformance_dir(pytestconfig: pytest.Config) -> Path:
    local_dir = os.environ.get("UMPIRE_JSON_CONFORMANCE_DIR")
    if local_dir:
        path = Path(local_dir).expanduser()
        _require_index(path, "UMPIRE_JSON_CONFORMANCE_DIR")
        return path

    version = os.environ.get("UMPIRE_JSON_VERSION", DEFAULT_VERSION)
    target = _cache_root(pytestconfig) / version / "conformance"
    if (target / "index.json").exists():
        return target

    tarball_url = _tarball_url(version)
    archive_path = _cache_root(pytestconfig) / f"json-{version}.tgz"
    extract_root = _cache_root(pytestconfig) / f"extract-{version}"

    try:
        urllib.request.urlretrieve(tarball_url, archive_path)
        _extract_conformance(archive_path, extract_root)
        extracted = extract_root / "package" / "conformance"
        _require_index(extracted, f"{PACKAGE_NAME}@{version}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(target, ignore_errors=True)
        shutil.move(str(extracted), target)
    except Exception as exc:
        pytest.skip(
            f"could not fetch {PACKAGE_NAME} conformance fixtures {version}: {exc}. "
            "Set UMPIRE_JSON_CONFORMANCE_DIR for local fixtures or publish a fixture-bearing "
            "package and pin UMPIRE_JSON_VERSION."
        )
    finally:
        shutil.rmtree(extract_root, ignore_errors=True)

    return target


def _cache_root(pytestconfig: pytest.Config) -> Path:
    return Path(str(pytestconfig.cache.mkdir("umpire-json")))


def _require_index(path: Path, source: str) -> None:
    if not (path / "index.json").exists():
        pytest.fail(f"{source} does not contain conformance/index.json: {path}")


def _tarball_url(version: str) -> str:
    with urllib.request.urlopen(REGISTRY_URL, timeout=30) as response:
        metadata: dict[str, Any] = json.load(response)

    package = metadata.get("versions", {}).get(version)
    if package is None:
        available = ", ".join(sorted(metadata.get("versions", {}).keys()))
        raise ValueError(
            f"{PACKAGE_NAME} version {version!r} was not found; available: {available}"
        )

    tarball = package.get("dist", {}).get("tarball")
    if not isinstance(tarball, str):
        raise ValueError(f"{PACKAGE_NAME} version {version!r} does not expose a tarball URL")
    return tarball


def _extract_conformance(archive_path: Path, extract_root: Path) -> None:
    shutil.rmtree(extract_root, ignore_errors=True)
    extract_root.mkdir(parents=True)

    with tarfile.open(archive_path, "r:gz") as archive:
        members = [
            member
            for member in archive.getmembers()
            if member.name.startswith("package/conformance/")
        ]
        if not members:
            raise ValueError("tarball does not contain package/conformance")
        for member in members:
            _validate_member_path(extract_root, member)
        archive.extractall(extract_root, members)


def _validate_member_path(extract_root: Path, member: tarfile.TarInfo) -> None:
    destination = (extract_root / member.name).resolve()
    if not destination.is_relative_to(extract_root.resolve()):
        raise ValueError(f"unsafe tarball path: {member.name}")
