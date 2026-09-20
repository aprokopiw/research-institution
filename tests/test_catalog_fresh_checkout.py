"""Catalog <-> filesystem coherence tests for a fresh-checkout operator.

The dispatcher's schema-validation test
(``test_catalog_consistent.py``) verifies the catalog TOML shape.
The architecture-review gate (``test_gate_check.py``) verifies the
mathlint-emit side. Neither covers what happens BETWEEN: when the
operator edits the catalog and a fresh clone of the institution
tries to launch a program, does every referenced path actually
exist on disk?

This file is the third leg of the catalog stool:

  - ``test_catalog_consistent.py``: schema shape (required keys,
    name patterns, pin formats).
  - ``test_gate_check.py``: architecture-review gate parses
    mathlint roadmap.
  - ``test_catalog_fresh_checkout.py`` (THIS FILE): the operator's
    actual machine state matches the catalog's claims.

Tests in this file are skipped when the catalog is unreachable
(clean CI runner without operator dotfiles). On a wired operator
machine they exercise the same paths that ``research start
<program>`` takes on every launch.
"""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

import pytest

from research_institution.catalog import Program, load_catalog

REPO = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO / "catalog" / "programs.toml"


def _catalog() -> list[Program]:
    if not CATALOG_PATH.is_file():
        pytest.skip(f"catalog not reachable at {CATALOG_PATH}")
    try:
        return load_catalog(CATALOG_PATH)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        pytest.fail(f"catalog parse failed: {exc}")


def test_catalog_programs_have_existing_local_paths() -> None:
    """Every catalog entry's ``local_path`` (after ``$HOME`` expansion)
    MUST be an existing directory.

    Defect class: operator edits the catalog with a typo'd path or
    an absolute path that hasn't been created yet. The dispatcher's
    preflight doesn't catch this because ``check_program_script``
    resolution is lazy: the path fails when the supervisor tries to
    chdir into it. The failure surfaces as a noisy ``worker_exit``
    event with no actionable diagnostic.

    Oracle: load the catalog, expand each entry's local_path, assert
    the resolved path is an existing directory. Skipped when the
    catalog is unreachable.
    """
    programs = _catalog()
    if not programs:
        pytest.skip("catalog has no programs[] entries")
    home = Path.home()
    missing: list[str] = []
    for p in programs:
        if not p.local_path:
            missing.append(f"{p.name}: empty local_path")
            continue
        resolved = Path(p.local_path.replace("$HOME", str(home))).expanduser()
        if not resolved.is_dir():
            missing.append(f"{p.name}: {resolved}")
    assert not missing, (
        "Catalog entries with non-existent local_path:\n  - "
        + "\n  - ".join(missing)
        + "\nFix: install the missing repos, update the catalog, "
        "or skip the program at launch time."
    )


def test_catalog_programs_have_resolvable_entry_points() -> None:
    """Every catalog entry's ``entry_point`` MUST resolve to an
    importable module + callable on the active Python.

    Defect class: the entry-point string references a module that
    isn't installed in the active venv (operator installed with
    ``--no-deps``, or the package's pyproject.toml declares the
    wrong module name). The mathlint side then fails to find the
    plugin and the supervisor enters a degraded SOURCE_NO_PROVIDER
    loop at the first decide frame. (This oracle is the
    research-institution-side mirror of mathlint's CROSS_REPO_004.)

    Oracle: parse each entry's entry_point, import the module,
    assert the callable exists. Skipped per entry if the module
    can't be imported (already covered by mathlint's CROSS_REPO_009b
    with stricter semantics).
    """
    programs = _catalog()
    if not programs:
        pytest.skip("catalog has no programs[] entries")

    failures: list[str] = []
    for p in programs:
        ep_str = p.entry_point
        if not ep_str or ":" not in ep_str:
            failures.append(f"{p.name}: malformed entry_point {ep_str!r}")
            continue
        module_path, _, callable_name = ep_str.rpartition(":")
        try:
            module = importlib.import_module(module_path)
        except ImportError:
            # Module-not-installed is a separate concern (tested by
            # CROSS_REPO_009b in math-engine). Skip silently here.
            continue
        if not hasattr(module, callable_name):
            failures.append(f"{p.name}: {module_path}.{callable_name} missing")
    assert not failures, (
        "Catalog entries where module exists but callable is missing:\n  - "
        + "\n  - ".join(failures)
        + "\nFix: update the entry_point string or add the missing symbol."
    )


def test_catalog_check_program_scripts_exist() -> None:
    """Every catalog entry's ``check_program_script`` MUST resolve to
    an existing file under that program's ``local_path``.

    Defect class: operator renames a script in the program repo but
    forgets to update the catalog. The institution green-gate then
    prints ``[program=X] WARN: check script missing; skipping`` and
    silently passes. The supervisor can launch without the operator
    realizing their preflight was no longer exercising that path.

    Oracle: for each catalog entry, assert the resolved
    ``local_path/check_program_script`` exists as a file. Skipped
    when catalog or any individual local_path is unreachable.
    """
    programs = _catalog()
    if not programs:
        pytest.skip("catalog has no programs[] entries")
    home = Path.home()
    failures: list[str] = []
    for p in programs:
        if not p.local_path:
            continue
        base = Path(p.local_path.replace("$HOME", str(home))).expanduser()
        if not base.is_dir():
            continue  # covered by test_catalog_programs_have_existing_local_paths
        script = base / p.check_program_script
        if not script.is_file():
            failures.append(f"{p.name}: {script}")
    assert not failures, (
        "Catalog entries whose check_program_script is missing:\n  - "
        + "\n  - ".join(failures)
        + "\nFix: update the script path in the catalog or restore the "
        "missing script file. The institution green-gate currently "
        "silently skips missing check scripts (WARN-only); this test "
        "tightens that to a hard fail so silent skips cannot regress."
    )


def test_catalog_names_are_unique_across_institution() -> None:
    """No two catalog entries share a name.

    Defect class: a copy-paste duplicate causes the dispatcher's
    ``_require_program`` to match the wrong entry, surfacing a
    program-launch with the wrong local_path / check_program_script
    / entry_point. The schema-validation test catches duplicates
    within the catalog; this test repeats the check post-load so
    a future change that bypasses the schema validator still gets
    caught.
    """
    programs = _catalog()
    if not programs:
        pytest.skip("catalog has no programs[] entries")
    names = [p.name for p in programs]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    assert not duplicates, (
        f"Duplicate program names in catalog: {duplicates}. Each "
        f"name MUST be unique so ``research <verb> <name>`` is unambiguous."
    )
