"""Primary-tier inventory walker.

Cited contracts:
    @CTR-0095-prime-directive-check-script-contract
    @INV-0093-institution-green-gate-canonical

Walks the canonical repository tree and returns the set of
primary tier markers in active use. The closed set of eight
tiers (per the verify-constitution §1) is enforced by the
release gate's row 1.

The repo's tier-marker convention is ``tier = "<marker>"``
assignments in test modules (see
``tests/static/test_closed_tier_vocabulary.py``). The walker
matches that exact convention; it does NOT match
``@pytest.mark.<word>`` decorators, which in this codebase
carry markers like ``parametrize`` / ``skipif`` unrelated to
the primary-tier vocabulary.

The walker is conservative: it inspects every Python test
file under ``tests/`` and gathers ``tier = "..."`` values.
The walker does NOT modify any file; it returns an immutable
snapshot.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

__all__ = [
    "CANONICAL_TIERS",
    "FORBIDDEN_TIERS",
    "TIER_ASSIGN_RE",
    "collect_primary_tier_markers",
    "tier_marker_inventory",
]


# Canonical §1 closed set; kept as a frozenset so callers can
# diff it against the inventory.
CANONICAL_TIERS: frozenset[str] = frozenset(
    {
        "unit",
        "property",
        "contract",
        "integration",
        "process",
        "deployment",
        "provider_live",
        "soak",
    }
)

# Six strings that §1 forbids as primary tier markers.
FORBIDDEN_TIERS: frozenset[str] = frozenset(
    {"e2e", "smoke", "acceptance", "endurance", "live", "chaos"}
)


# Match ``tier = "<value>"`` at any indentation; capture the
# quoted value. The leading ``^`` anchors the match to the
# start of a line so docstring prose / inline comments don't
# trigger spurious hits.
TIER_ASSIGN_RE = re.compile(
    r"^\s*tier\s*=\s*['\"]([a-z_]+)['\"]", re.MULTILINE
)


def _iter_test_files(repo_root: Path) -> Iterable[Path]:
    """Yield every Python test file under ``repo_root/tests/``."""
    tests_dir = repo_root / "tests"
    if not tests_dir.is_dir():
        return
    for path in sorted(tests_dir.rglob("*.py")):
        if not path.is_file():
            continue
        parts = path.parts
        if any(
            skip in parts
            for skip in (".venv", "__pycache__", "node_modules", ".git")
        ):
            continue
        # Skip the tier-vocabulary wiring file itself (its job
        # is to enumerate the closed set; including it would
        # add "unit" to the inventory by accident).
        if path.name == "test_closed_tier_vocabulary.py":
            continue
        yield path


def _markers_in_file(path: Path) -> set[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return {match.group(1) for match in TIER_ASSIGN_RE.finditer(text)}


def collect_primary_tier_markers(repo_root: Path | None = None) -> set[str]:
    """Return the set of primary tier markers observed in ``repo_root``.

    Walks every ``tests/**/*.py`` under ``repo_root`` and
    collects values from ``tier = "<marker>"`` assignments.
    The result is the union of every tier marker in active use;
    the release gate diffs the result against ``CANONICAL_TIERS``
    to assert no canonical tier is empty.
    """
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    markers: set[str] = set()
    for path in _iter_test_files(root):
        markers.update(_markers_in_file(path))
    return markers


def tier_marker_inventory(repo_root: Path | None = None) -> dict[str, object]:
    """Return a typed inventory: every observed tier + counts."""
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    counts: dict[str, int] = {}
    for path in _iter_test_files(root):
        for tier in _markers_in_file(path):
            counts[tier] = counts.get(tier, 0) + 1
    return {
        "canonical": sorted(CANONICAL_TIERS),
        "forbidden": sorted(FORBIDDEN_TIERS),
        "observed": sorted(counts.keys()),
        "counts": counts,
        "missing_canonical": sorted(CANONICAL_TIERS - set(counts.keys())),
    }
