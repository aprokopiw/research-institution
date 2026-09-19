"""Contract tests for the institution catalog.

Per @CTR-0088, every entry in `catalog/programs.toml` MUST
satisfy the schema in `catalog/schema.toml`. The schema is
the source of truth; this test asserts the instance.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

CATALOG_PATH = Path(__file__).resolve().parents[1] / "catalog" / "programs.toml"

_REQUIRED_KEYS = {
    "name",
    "display_name",
    "repository",
    "entry_point",
    "local_path",
    "mathlint_pin",
    "live_credentials_required",
    "live_credential_env_vars",
    "check_program_script",
}
_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
_PIN_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


@pytest.fixture(scope="module")
def catalog() -> dict:
    return tomllib.loads(CATALOG_PATH.read_text())


def test_catalog_toml_parses(catalog: dict) -> None:
    assert "programs" in catalog
    assert isinstance(catalog["programs"], list)
    assert len(catalog["programs"]) >= 1


def test_every_entry_has_required_keys(catalog: dict) -> None:
    for entry in catalog["programs"]:
        assert _REQUIRED_KEYS.issubset(entry.keys()), (
            f"missing keys in entry {entry.get('name')}: {_REQUIRED_KEYS - entry.keys()}"
        )


def test_names_are_unique(catalog: dict) -> None:
    names = [entry["name"] for entry in catalog["programs"]]
    assert len(names) == len(set(names)), f"duplicate program names: {names}"


def test_names_match_pattern(catalog: dict) -> None:
    for entry in catalog["programs"]:
        assert _NAME_RE.match(entry["name"]), (
            f"name {entry['name']!r} does not match {_NAME_RE.pattern}"
        )


def test_entry_points_are_unique(catalog: dict) -> None:
    endpoints = [entry["entry_point"].split(":")[0] for entry in catalog["programs"]]
    assert len(endpoints) == len(set(endpoints)), (
        f"duplicate entry_point modules: {endpoints}"
    )


def test_local_paths_are_absolute_or_homed(catalog: dict) -> None:
    for entry in catalog["programs"]:
        local = entry["local_path"]
        assert local.startswith("/") or local.startswith("$HOME"), (
            f"local_path {local!r} for {entry['name']!r} must start with '/' or '$HOME'"
        )


def test_mathlint_pin_is_valid(catalog: dict) -> None:
    for entry in catalog["programs"]:
        assert _PIN_RE.match(entry["mathlint_pin"]), (
            f"mathlint_pin {entry['mathlint_pin']!r} for {entry['name']!r} "
            f"does not match {_PIN_RE.pattern}"
        )


def test_check_program_script_ends_in_sh(catalog: dict) -> None:
    for entry in catalog["programs"]:
        assert entry["check_program_script"].endswith(".sh"), (
            f"check_program_script for {entry['name']!r} must end with .sh"
        )
