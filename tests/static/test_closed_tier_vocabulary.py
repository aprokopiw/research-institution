"""Closed tier-vocabulary wiring check (per-repo skeleton).

Per `.specify/memory/constitution-verify.md` §1 and the plan's T4.3,
every test in every repo carries **exactly one** primary ``tier``
marker from the closed set:

    unit | property | contract | integration | process |
    deployment | provider_live | soak

The forbidden primary markers (`e2e`, `smoke`, `acceptance`,
`endurance`, `live`, `chaos`) MUST NOT appear as primary tier
markers anywhere; they encode different dimensions and produced
documented drift.

This module is the **wiring** for that check at the
research-institution repo. The actual tier-marker migration lands
in entries 01/02/03 (math / pi_monitor / kaplansky) and 06
(research-institution's own tests). Today no tier markers exist in
``tests/``; the check therefore trivially passes.

When a future entry introduces tier markers, this module scans
them and fails on any forbidden primary marker. The promotion of
this stub into the full enforcement check is owned by entry 06.
"""

from __future__ import annotations

import re
from pathlib import Path


REPO = Path("/Users/erinprokopiw/Documents/andrei/research-institution")
TESTS_DIR = REPO / "tests"

# Closed primary-tier vocabulary (constitution §1).
CLOSED_TIER_MARKERS: frozenset[str] = frozenset(
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

# Forbidden primary-tier markers (constitution §1.2).
FORBIDDEN_TIER_MARKERS: frozenset[str] = frozenset(
    {"e2e", "smoke", "acceptance", "endurance", "live", "chaos"}
)

# Match ``tier = "<value>"`` (single or double quotes) at any
# indentation; capture the quoted value. Anchored to the start of
# the string to avoid matching substrings inside larger identifiers
# or docstrings.
TIER_ASSIGN_RE = re.compile(r"^\s*tier\s*=\s*['\"]([a-z_]+)['\"]", re.MULTILINE)


def _iter_tier_assignments() -> list[tuple[Path, str, int]]:
    """Yield ``(path, marker, line_number)`` for every tier assignment
    found under ``tests/``. Excludes this file (the wiring itself)."""
    out: list[tuple[Path, str, int]] = []
    for path in sorted(TESTS_DIR.rglob("*.py")):
        if path.resolve() == Path(__file__).resolve():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in TIER_ASSIGN_RE.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            out.append((path, match.group(1), line_no))
    return out


def test_no_forbidden_tier_markers_in_tests() -> None:
    """No ``tier = "..."`` assignment uses a forbidden primary marker.

    Today no tier assignments exist in ``tests/`` (the migration
    lands in entries 01/02/03/06). When future entries add markers,
    this check fails on any forbidden primary marker per §1.2.
    """
    offenders: list[str] = []
    for path, marker, line_no in _iter_tier_assignments():
        if marker in FORBIDDEN_TIER_MARKERS:
            offenders.append(f"{path}:{line_no}: tier={marker!r} (forbidden)")
    assert not offenders, (
        "forbidden primary tier markers present:\n  " + "\n  ".join(offenders)
    )


def test_all_tier_markers_are_in_closed_set() -> None:
    """Every ``tier = "..."`` assignment uses a closed-set marker.

    If a future entry introduces a new primary tier marker without
    amending constitution §1, this check fails. The set is closed
    on purpose: new tiers require an amendment + ADR justification.
    """
    offenders: list[str] = []
    for path, marker, line_no in _iter_tier_assignments():
        if marker not in CLOSED_TIER_MARKERS:
            offenders.append(
                f"{path}:{line_no}: tier={marker!r} not in closed set "
                f"{sorted(CLOSED_TIER_MARKERS)}"
            )
    assert not offenders, (
        "tier markers outside the closed set:\n  " + "\n  ".join(offenders)
    )


def test_closed_set_is_exactly_eight() -> None:
    """Sanity-check the closed set is exactly eight members (§1.1)."""
    assert len(CLOSED_TIER_MARKERS) == 8, (
        f"closed tier set drifted to {len(CLOSED_TIER_MARKERS)} members; "
        "amend §1 + update CLOSED_TIER_MARKERS in lockstep"
    )
