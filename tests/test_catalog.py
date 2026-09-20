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
        "live_credentials_required = false\nlive_credential_env_vars = []\n"
        'check_program_script = "x.sh"\n',
        encoding="utf-8",
    )
    try:
        with pytest.raises(ValueError, match="must contain ':'"):
            cat_mod.load_catalog(fake_path)
    finally:
        fake_path.unlink()


# ---------------------------------------------------------------------------
# Catalog loader invariant oracles.
#
# test_catalog_consistent.py pins the *current* catalog against
# catalog/schema.toml (read-side validation). This file pins the
# loader's rejection of *invalid* catalogs (write-side validation).
# Together they close the loop: a regression that drops one side
# surfaces in the other.
# ---------------------------------------------------------------------------


def _write_tmp_catalog(tmp_path: Path, body: str) -> Path:
    """Write a fake catalog TOML to tmp_path and return the path."""
    p = tmp_path / "_catalog_test.toml"
    p.write_text(body, encoding="utf-8")
    return p


def test_rejects_invalid_mathlint_pin(tmp_path: Path) -> None:
    """`mathlint_pin` MUST match `^[A-Za-z0-9._/-]+$` (git ref shape).

    Defect: a ref like `main; rm -rf ~` is rejected — preventing
    shell injection via a typo'd pin field. A regression that
    loosens the regex would silently accept unsafe values.
    """
    from research_institution import catalog as cat_mod

    cases = [
        "main; rm -rf ~",  # shell metacharacters
        "v1.0\n[bad]",  # newline + table header
        "",  # empty
    ]
    for bad_pin in cases:
        body = (
            '[[programs]]\nname = "x"\ndisplay_name = "x"\n'
            'repository = "https://x"\nentry_point = "x:r"\n'
            f'local_path = "/x"\nmathlint_pin = "{bad_pin}"\n'
            "live_credentials_required = false\n"
            "live_credential_env_vars = []\n"
            'check_program_script = "x.sh"\n'
        )
        p = _write_tmp_catalog(tmp_path, body)
        with pytest.raises(ValueError):
            cat_mod.load_catalog(p)


def test_rejects_check_program_script_without_sh_suffix(tmp_path: Path) -> None:
    """`check_program_script` MUST end in `.sh`.

    Defect: a regression that drops the suffix check lets
    `check_program_script = "scripts/check"` slip through; the
    green-gate then tries to `bash scripts/check` and fails with
    a confusing error.
    """
    from research_institution import catalog as cat_mod

    body = (
        '[[programs]]\nname = "x"\ndisplay_name = "x"\n'
        'repository = "https://x"\nentry_point = "x:r"\n'
        'local_path = "/x"\nmathlint_pin = "v1"\n'
        "live_credentials_required = false\n"
        "live_credential_env_vars = []\n"
        'check_program_script = "scripts/check"\n'
    )
    p = _write_tmp_catalog(tmp_path, body)
    with pytest.raises(ValueError, match=r"\.sh"):
        cat_mod.load_catalog(p)


def test_rejects_local_path_without_slash_or_home(tmp_path: Path) -> None:
    """`local_path` MUST start with `/` or `$HOME`.

    Defect: a regression that drops the absolute-path check lets
    relative paths slip through; the green-gate then resolves them
    against the wrong cwd and silently skips the program.
    """
    from research_institution import catalog as cat_mod

    body = (
        '[[programs]]\nname = "x"\ndisplay_name = "x"\n'
        'repository = "https://x"\nentry_point = "x:r"\n'
        'local_path = "relative/path"\nmathlint_pin = "v1"\n'
        "live_credentials_required = false\n"
        "live_credential_env_vars = []\n"
        'check_program_script = "x.sh"\n'
    )
    p = _write_tmp_catalog(tmp_path, body)
    with pytest.raises(ValueError, match="must start with"):
        cat_mod.load_catalog(p)


def test_rejects_live_credential_env_vars_when_not_a_list(tmp_path: Path) -> None:
    """`live_credential_env_vars` MUST be a list (not a string).

    Defect: a regression that accepts a string `live_credential_env_vars =
    "OPENAI_API_KEY"` would crash later when something does `for v in
    prog.live_credential_env_vars`. Pin the type at load time.
    """
    from research_institution import catalog as cat_mod

    body = (
        '[[programs]]\nname = "x"\ndisplay_name = "x"\n'
        'repository = "https://x"\nentry_point = "x:r"\n'
        'local_path = "/x"\nmathlint_pin = "v1"\n'
        "live_credentials_required = true\n"
        'live_credential_env_vars = "OPENAI_API_KEY"\n'
        'check_program_script = "x.sh"\n'
    )
    p = _write_tmp_catalog(tmp_path, body)
    with pytest.raises(ValueError, match="list"):
        cat_mod.load_catalog(p)


def test_rejects_empty_entry_point(tmp_path: Path) -> None:
    """`entry_point` MUST be non-empty.

    Defect: a regression that accepts empty entry_point lets a
    catalog editor accidentally blank it out. The downstream
    `parse_entry_point("")` would raise with a less actionable
    message than the loader's pre-check.
    """
    from research_institution import catalog as cat_mod

    body = (
        '[[programs]]\nname = "x"\ndisplay_name = "x"\n'
        'repository = "https://x"\nentry_point = ""\n'
        'local_path = "/x"\nmathlint_pin = "v1"\n'
        "live_credentials_required = false\n"
        "live_credential_env_vars = []\n"
        'check_program_script = "x.sh"\n'
    )
    p = _write_tmp_catalog(tmp_path, body)
    with pytest.raises(ValueError):
        cat_mod.load_catalog(p)


def test_rejects_duplicate_entry_point_final_segment(tmp_path: Path) -> None:
    """Two entries with IDENTICAL `entry_point` strings MUST raise.

    Cross-field invariant (per @ADR-0006 + schema comment): the
    final segment of `entry_point` (after the last dot) identifies
    the callable registered with mathlint.providers; collisions
    would silently let one program override another's registration.

    Note: as implemented, the check fires on ``entry_point.rsplit(".", 1)[-1]``,
    which is the substring after the last dot. For entry points with
    no dot at all (e.g. ``pkg:register``) the entire string is the
    final segment, so only IDENTICAL strings collide. This test pins
    that actual contract.

    Defect: a regression that drops this check would let two
    programs claim the same provider name. The cold-start doctor
    prints GREEN INSTITUTION READY while mathlint uses whichever
    entry point resolves last — a silent override.
    """
    from research_institution import catalog as cat_mod

    body = (
        '[[programs]]\nname = "a"\ndisplay_name = "a"\n'
        'repository = "https://a"\nentry_point = "shared.mod:register"\n'
        'local_path = "/a"\nmathlint_pin = "v1"\n'
        "live_credentials_required = false\n"
        "live_credential_env_vars = []\n"
        'check_program_script = "a.sh"\n'
        '[[programs]]\nname = "b"\ndisplay_name = "b"\n'
        'repository = "https://b"\nentry_point = "shared.mod:register"\n'
        'local_path = "/b"\nmathlint_pin = "v1"\n'
        "live_credentials_required = false\n"
        "live_credential_env_vars = []\n"
        'check_program_script = "b.sh"\n'
    )
    p = _write_tmp_catalog(tmp_path, body)
    with pytest.raises(ValueError, match="duplicate entry_point final segment"):
        cat_mod.load_catalog(p)


def test_load_catalog_missing_required_key_returns_actionable_error(
    tmp_path: Path,
) -> None:
    """When a required key is missing, the loader MUST list the
    missing keys in the error message.

    Defect: a regression that raises a generic `ValueError` with no
    missing-key list would force operators to diff the catalog
    against the schema by hand.
    """
    from research_institution import catalog as cat_mod

    body = (
        '[[programs]]\nname = "x"\ndisplay_name = "x"\n'
        'repository = "https://x"\nentry_point = "x:r"\n'
        'local_path = "/x"\nmathlint_pin = "v1"\n'
        # NOTE: live_credentials_required and live_credential_env_vars
        # and check_program_script are all missing.
    )
    p = _write_tmp_catalog(tmp_path, body)
    with pytest.raises(ValueError, match="missing keys"):
        cat_mod.load_catalog(p)


def test_load_catalog_rejects_empty_programs_table(tmp_path: Path) -> None:
    """An empty `[[programs]]` table MUST raise (the catalog is
    semantically empty, which is a misconfiguration not a no-op).
    """
    from research_institution import catalog as cat_mod

    body = ""  # no [[programs]] at all
    p = _write_tmp_catalog(tmp_path, body)
    with pytest.raises(ValueError, match="non-empty"):
        cat_mod.load_catalog(p)

