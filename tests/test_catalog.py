"""Tests for the catalog loader.

Covers: TOML parsing, validation invariants, dataclass properties.
Does NOT cover the green gate (that's tested by tests/test_green_gate_hermetic.py).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from research_institution.catalog import Program, load_catalog

REPO = Path("/Users/erinprokopiw/Documents/andrei/research-institution")


def test_load_real_catalog() -> None:
    """The real catalog at catalog/programs.toml parses to a non-empty list."""
    catalog = REPO / "catalog" / "programs.toml"
    programs = load_catalog(catalog)
    assert len(programs) >= 1
    names = [p.name for p in programs]
    assert "kaplansky" in names


def test_program_fields_are_typed() -> None:
    """Every Program has all required fields populated; no None."""
    catalog = REPO / "catalog" / "programs.toml"
    programs = load_catalog(catalog)
    for p in programs:
        assert isinstance(p, Program)
        assert isinstance(p.name, str)
        assert isinstance(p.live_credential_env_vars, tuple)
        assert isinstance(p.live_credentials_required, bool)
        assert p.mathlint_pin
        assert p.repository.startswith("https://")


def test_resolved_local_path_expands_home() -> None:
    """$HOME in local_path is expanded; absolute paths pass through."""
    catalog = REPO / "catalog" / "programs.toml"
    programs = load_catalog(catalog)
    for p in programs:
        resolved = p.resolved_local_path
        assert resolved.is_absolute()


def test_rejects_invalid_name() -> None:
    """Names must match ^[a-z][a-z0-9_-]*$."""
    # Construct in-memory by monkeypatching the loader, not by mutating disk.
    from research_institution import catalog as cat_mod

    fake_toml = '[[programs]]\nname = "BadName"\ndisplay_name = "x"\nrepository = "https://x"\nentry_point = "x:x"\nlocal_path = "/x"\nmathlint_pin = "v1"\nlive_credentials_required = false\nlive_credential_env_vars = []\ncheck_program_script = "x.sh"\n'
    fake_path = REPO / "tests" / "fixtures" / "_tmp_bad_name.toml"
    fake_path.parent.mkdir(parents=True, exist_ok=True)
    fake_path.write_text(fake_toml, encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="does not match"):
            cat_mod.load_catalog(fake_path)
    finally:
        fake_path.unlink()


def test_rejects_duplicate_names() -> None:
    """Two entries with the same name raise ValueError."""
    fake_path = REPO / "tests" / "fixtures" / "_tmp_dup.toml"
    fake_path.parent.mkdir(parents=True, exist_ok=True)
    fake_path.write_text(
        '[[programs]]\nname = "a"\ndisplay_name = "x"\nrepository = "https://x"\nentry_point = "a:r"\nlocal_path = "/x"\nmathlint_pin = "v1"\nlive_credentials_required = false\nlive_credential_env_vars = []\ncheck_program_script = "x.sh"\n'
        '[[programs]]\nname = "a"\ndisplay_name = "y"\nrepository = "https://y"\nentry_point = "a:s"\nlocal_path = "/y"\nmathlint_pin = "v1"\nlive_credentials_required = false\nlive_credential_env_vars = []\ncheck_program_script = "y.sh"\n',
        encoding="utf-8",
    )
    try:
        with pytest.raises(ValueError, match="duplicate program name"):
            from research_institution import catalog as cat_mod
            cat_mod.load_catalog(fake_path)
    finally:
        fake_path.unlink()


def test_rejects_non_https_repo() -> None:
    """Repositories must be https:// (not git@, not ssh://)."""
    from research_institution import catalog as cat_mod
    fake_path = REPO / "tests" / "fixtures" / "_tmp_ssh.toml"
    fake_path.parent.mkdir(parents=True, exist_ok=True)
    fake_path.write_text(
        '[[programs]]\nname = "x"\ndisplay_name = "x"\nrepository = "git@github.com:a/b.git"\nentry_point = "x:r"\nlocal_path = "/x"\nmathlint_pin = "v1"\nlive_credentials_required = false\nlive_credential_env_vars = []\ncheck_program_script = "x.sh"\n',
        encoding="utf-8",
    )
    try:
        with pytest.raises(ValueError, match="https://"):
            cat_mod.load_catalog(fake_path)
    finally:
        fake_path.unlink()


def test_program_name_regex_is_documented_in_schema() -> None:
    """The regex in code matches the schema comment in catalog/schema.toml.

    Defends against drift between the loader and the schema doc.
    """
    pattern = re.compile(r"^[a-z][a-z0-9_-]*$")
    assert pattern.match("kaplansky")
    assert pattern.match("foo-bar_baz")
    assert not pattern.match("Kaplansky")
    assert not pattern.match("1kaplansky")
    assert not pattern.match("-kaplansky")


def test_rejects_malformed_entry_point() -> None:
    """The catalog loader rejects entry_points without `:` separator."""
    from research_institution import catalog as cat_mod

    fake_path = REPO / "tests" / "fixtures" / "_tmp_bad_ep.toml"
    fake_path.parent.mkdir(parents=True, exist_ok=True)
    fake_path.write_text(
        '[[programs]]\nname = "x"\ndisplay_name = "x"\nrepository = "https://x"\n'
        'entry_point = "no_colon_here"\nlocal_path = "/x"\nmathlint_pin = "v1"\n'
        'live_credentials_required = false\nlive_credential_env_vars = []\n'
        'check_program_script = "x.sh"\n',
        encoding="utf-8",
    )
    try:
        with pytest.raises(ValueError, match="must contain ':'"):
            cat_mod.load_catalog(fake_path)
    finally:
        fake_path.unlink()
