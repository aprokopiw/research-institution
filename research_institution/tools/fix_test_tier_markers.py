"""One-shot: stamp required pytest tier markers on tier-directory tests.

Repositories in the kernel/OS mental model split tests into
tier directories (tests/contracts, tests/integration, etc.)
and require every test file in those directories to declare
the matching ``@pytest.mark.<tier>`` marker. Files that
violate this are invisible to per-tier pytest selection
(``-m <tier>``) and to CI lane gating.

This script:

  - Identifies every Python file under a tier directory that
    lacks the required marker (using mathlint's
    ``check_test_conventions`` rules, shipped here as
    ``_required_markers_by_dir``).
  - Inserts a module-level ``pytestmark = pytest.mark.<tier>``
    line at the top of each offending file (after the
    docstring + ``from __future__ import annotations`` import,
    if present).
  - Leaves files alone when they already have the marker.

Idempotent. Safe to re-run on math-engine or any sibling repo.
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


TIER_REQUIRED_MARKERS: dict[str, str] = {
    "tests/invariants": "invariant",
    "tests/property": "property",
    "tests/contracts": "contract",
    "tests/integration": "integration",
    "tests/e2e": "e2e",
    "tests/smoke": "smoke",
    "tests/chaos": "chaos",
    "tests/acceptance": "acceptance",
}


@dataclass(frozen=True, slots=True)
class FixReport:
    """The result of one file fix."""

    path: Path
    changed: bool
    reason: str = ""


def _marker_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _has_marker_anywhere(tree: ast.Module, marker_name: str) -> bool:
    """True iff the module declares the required marker either
    at module level (``pytestmark = ...``) or on ANY of its test
    functions (as a direct ``@pytest.mark.<marker>`` decorator).
    Mirrors the semantics of mathlint's
    ``tests/check_test_conventions.py`` so this tool never disagrees
    with the gate that consumes it.
    """
    # Module-level pytestmark.
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "pytestmark":
                    value = node.value
                    if isinstance(value, (ast.List, ast.Tuple)):
                        for elt in value.elts:
                            name = _marker_name(elt)
                            if name == marker_name:
                                return True
                    else:
                        name = _marker_name(value)
                        if name == marker_name:
                            return True
    # Function-level decorators on test_* functions.
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test"):
            continue
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                name = _marker_name(decorator.func)
                if name == marker_name:
                    return True
            else:
                name = _marker_name(decorator)
                if name == marker_name:
                    return True
    return False


def _insert_at_top(source: str, line: str) -> str:
    """Insert ``line`` immediately after the docstring and
    ``from __future__ import annotations`` import (if either
    is present), so the new marker line is reachable by the
    AST-based checker AND visible at the top of the file.
    """
    lines = source.splitlines(keepends=True)
    insert_at = 0
    # Skip the docstring (a Module-level Expr of a Constant string).
    tree = ast.parse(source)
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        docstring_node = tree.body[0]
        insert_at = (
            docstring_node.end_lineno if docstring_node.end_lineno is not None else 1
        )
    # Skip the ``from __future__ import annotations`` import when
    # it is the next statement after the docstring.
    future_imported = False
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            future_imported = True
            insert_at = node.end_lineno if node.end_lineno is not None else insert_at
            break
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        break
    if future_imported:
        # keep the import line; place marker after it.
        insert_at = max(insert_at, 1)
    prefix = lines[:insert_at]
    suffix = lines[insert_at:]
    while prefix and prefix[-1].strip() == "":
        prefix.pop()
    new_prefix = [*prefix, "\n", f"{line}\n"]
    return "".join(list(new_prefix) + list(suffix))


def _needs_pytest_import(source: str) -> bool:
    """True iff the source uses ``pytest.mark`` or ``pytestmark`` but
    does NOT currently import pytest."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    uses_pytest_mark = any(
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "pytest"
        for node in ast.walk(tree)
    )
    imports_pytest = False
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "pytest":
                    imports_pytest = True
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.split(".")[0] == "pytest"
        ):
            imports_pytest = True
    return uses_pytest_mark and not imports_pytest


def _ensure_pytest_import(source: str) -> str:
    """Add ``import pytest`` after the docstring + future-import block
    when the file uses pytest but doesn't import it. Idempotent.
    """
    if not _needs_pytest_import(source):
        return source
    lines = source.splitlines(keepends=True)
    insert_at = 0
    tree = ast.parse(source)
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        insert_at = tree.body[0].end_lineno or 1
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            insert_at = node.end_lineno or insert_at
            continue
        break
    while insert_at < len(lines) and lines[insert_at].strip() == "":
        insert_at += 1
    return "".join(
        lines[:insert_at] + ["import pytest\n"] + lines[insert_at:]
    )


def _fix_one(test_file: Path, required_marker: str) -> FixReport:
    """Apply the fix to a single test file."""
    try:
        source = test_file.read_text(encoding="utf-8")
    except OSError as error:
        return FixReport(path=test_file, changed=False, reason=f"read failed: {error}")
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return FixReport(path=test_file, changed=False, reason=f"syntax error: {error}")
    if _has_marker_anywhere(tree, required_marker):
        return FixReport(path=test_file, changed=False, reason="already has marker")
    updated = _ensure_pytest_import(source)
    marker_line = f"pytestmark = pytest.mark.{required_marker}\n"
    updated = _insert_at_top(updated, marker_line)
    try:
        # Parse once more to make sure the edit is still valid Python.
        ast.parse(updated)
    except SyntaxError as error:
        return FixReport(
            path=test_file,
            changed=False,
            reason=f"edit would introduce syntax error: {error}",
        )
    test_file.write_text(updated, encoding="utf-8")
    return FixReport(path=test_file, changed=True, reason="added module-level pytestmark")


def _iter_test_files(tier_dir: Path) -> Iterable[Path]:
    yield from sorted(tier_dir.rglob("test_*.py"))


def fix_repo(repo_root: Path, *, write: bool) -> dict[str, list[FixReport]]:
    """Find every offending test file under ``repo_root``, optionally
    fixing each. Returns a dict mapping ``tier_dir -> reports`` so a
    caller can render a precise summary.
    """
    out: dict[str, list[FixReport]] = {}
    for tier_dir_name, required_marker in TIER_REQUIRED_MARKERS.items():
        tier_dir = repo_root / tier_dir_name
        if not tier_dir.is_dir():
            continue
        reports = [
            _fix_one(test_file, required_marker) if write
            else _check_one(test_file, required_marker)
            for test_file in _iter_test_files(tier_dir)
        ]
        out[tier_dir_name] = [r for r in reports if r.changed or r.reason]
    return out


def _check_one(test_file: Path, required_marker: str) -> FixReport:
    """Read-only variant: report which files would be fixed, do not write."""
    try:
        source = test_file.read_text(encoding="utf-8")
    except OSError as error:
        return FixReport(path=test_file, changed=False, reason=f"read failed: {error}")
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return FixReport(path=test_file, changed=False, reason=f"syntax error: {error}")
    if _has_marker_anywhere(tree, required_marker):
        return FixReport(path=test_file, changed=False, reason="already has marker")
    return FixReport(
        path=test_file,
        changed=False,
        reason=f"missing required marker '{required_marker}' (would add)",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fix-test-tier-markers",
        description=(
            "Stamp pytest tier markers on tests/ subdirectory tests. "
            "Idempotent."
        ),
    )
    parser.add_argument(
        "repo_root",
        type=Path,
        nargs="?",
        default=Path.cwd(),
        help="Repo root (default: cwd).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually mutate files (default: dry-run, print only).",
    )
    ns = parser.parse_args(argv)
    result = fix_repo(ns.repo_root.resolve(), write=ns.apply)
    if not result:
        print("no tier directories under that repo root", file=sys.stderr)
        return 2
    total_changed = 0
    total_skipped = 0
    for tier_dir_name, reports in result.items():
        if not reports:
            continue
        changed = [r for r in reports if r.changed]
        skipped = [r for r in reports if not r.changed]
        verb = "applied" if ns.apply else "would apply"
        print(f"[{tier_dir_name}] {verb} {len(changed)}; skipped {len(skipped)}")
        for r in changed:
            print(f"  + {r.path} ({r.reason})")
        for r in skipped[:3]:
            print(f"  - {r.path} ({r.reason})")
        total_changed += len(changed)
        total_skipped += len(skipped)
    print(f"summary: {total_changed} {'fixed' if ns.apply else 'would fix'}; {total_skipped} skipped")
    return 0


if __name__ == "__main__":  # pragma: no cover — entry point
    raise SystemExit(main())
