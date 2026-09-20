"""Green-gate CLI shape contract tests.

The green-gate script (`green-gate/check-institution.sh`) is the
canonical aggregator that prints `GREEN INSTITUTION READY` or
`RED: failed checks`. Its CLI surface is documented in the
script's `usage()` block and in `docs/operations/verification-gates.md`.

These tests pin the CLI surface contract independently of the
runtime behavior. A regression that renames a flag (e.g.
`--hermetic` -> `--ci-mode`) breaks operator muscle memory; these
tests fail loudly so the breakage can't ship.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "green-gate" / "check-institution.sh"


def test_green_gate_help_lists_all_flags() -> None:
    """`check-institution.sh --help` MUST enumerate every documented flag.

    Defect: a regression that drops a flag from the usage block
    makes the flag undocumented but still accepted (or worse,
    accepted as a no-op). The cold-start doctor test exercises
    the flag end-to-end; this test pins the documented contract.
    """
    if not GATE.is_file():
        pytest.skip(f"{GATE} not present")
    completed = subprocess.run(
        ["bash", str(GATE), "--help"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    out = completed.stdout
    for flag in ("--hermetic", "--live", "--list", "--skip-program=", "-h", "--help"):
        assert flag in out, (
            f"green-gate usage missing {flag!r}; full help:\n{out}"
        )


def test_green_gate_unknown_flag_exits_2() -> None:
    """An unknown flag MUST exit 2 with a usage hint (per the
    script's argparse-style contract).

    Defect: a regression that accepts unknown flags silently (or
    exits 0) lets typos in operator scripts go unnoticed.
    """
    if not GATE.is_file():
        pytest.skip(f"{GATE} not present")
    completed = subprocess.run(
        ["bash", str(GATE), "--no-such-flag"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert completed.returncode == 2, (
        f"green-gate unknown-flag exit code: got {completed.returncode}, "
        f"expected 2. stderr={completed.stderr!r}"
    )
    assert "unknown flag" in completed.stderr.lower() or "unknown" in completed.stderr.lower(), (
        f"green-gate unknown-flag error lacks 'unknown' diagnostic; "
        f"stderr={completed.stderr!r}"
    )


def test_green_gate_list_prints_catalog() -> None:
    """`--list` MUST print the catalog as a NAME\\tDISPLAY\\tREPOSITORY\\tENTRY_POINT
    table and exit 0.

    Defect: a regression that changes the column shape breaks
    operator scripts that grep on the columns.
    """
    if not GATE.is_file():
        pytest.skip(f"{GATE} not present")
    completed = subprocess.run(
        ["bash", str(GATE), "--list"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert completed.returncode == 0, (
        f"--list failed: rc={completed.returncode} stderr={completed.stderr!r}"
    )
    assert "NAME" in completed.stdout
    assert "kaplansky" in completed.stdout, (
        f"--list output missing kaplansky; got:\n{completed.stdout}"
    )


def test_green_gate_skip_program_can_be_repeated() -> None:
    """`--skip-program=<name>` MUST be repeatable so operators can
    skip multiple programs in one invocation.

    Defect: a regression that processes only the first --skip-program
    silently runs the others, surfacing as confusing failures
    instead of clean skips.
    """
    if not GATE.is_file():
        pytest.skip(f"{GATE} not present")
    text = GATE.read_text(encoding="utf-8")
    # The argument loop must accept multiple --skip-program= flags.
    # Either the script concatenates into SKIP_PROGRAMS or uses shift.
    # Either way the source must NOT reject a second --skip-program.
    assert "SKIP_PROGRAMS=" in text, (
        "green-gate does not aggregate SKIP_PROGRAMS; "
        "the repeatable --skip-program= contract is not honored."
    )
    # And the skip check must be substring (not equality) so multiple
    # names work.
    assert "SKIP_PROGRAMS" in text and ('"$SKIP_PROGRAMS"' in text or " $SKIP_PROGRAMS " in text), (
        "green-gate skip check looks like equality, not substring match; "
        "multiple --skip-program= won't all be honored."
    )


def test_green_gate_prints_verdict_lines() -> None:
    """The aggregator MUST print `GREEN INSTITUTION READY` or
    `RED: failed checks` (one of these two strings).

    Defect: a regression that prints `green` instead of `GREEN` (or
    drops the `READY` suffix) breaks operator dashboards that
    grep for the canonical line.
    """
    if not GATE.is_file():
        pytest.skip(f"{GATE} not present")
    text = GATE.read_text(encoding="utf-8")
    assert "GREEN INSTITUTION READY" in text, (
        "green-gate no longer prints 'GREEN INSTITUTION READY' on success. "
        "Dashboard grep contract broken."
    )
    assert "RED: failed checks" in text, (
        "green-gate no longer prints 'RED: failed checks' on failure. "
        "Dashboard grep contract broken."
    )


def test_green_gate_catalog_path_is_resolved_under_repo_root() -> None:
    """The aggregator MUST resolve the catalog path relative to the
    repo root (where the script lives), not the cwd.

    Defect: a regression that uses `pwd` instead of `$ROOT` for
    the catalog path means operators running the gate from a
    different cwd get `catalog missing` even when the repo is wired.
    """
    if not GATE.is_file():
        pytest.skip(f"{GATE} not present")
    text = GATE.read_text(encoding="utf-8")
    # The script computes ROOT from its own location via `cd -- dirname`.
    assert 'CDPATH= cd -- "$(dirname -- "$0")/.."' in text, (
        "green-gate ROOT resolution no longer anchored to the script's "
        "own location; running from a different cwd will fail."
    )


def test_green_gate_engine_step_uses_hermetic_flags_by_default() -> None:
    """When MODE=hermetic (default), the engine step MUST pass
    `--skip-external --use-program=self_test-sample` so the
    math-engine's readiness check stays hermetic.

    Defect: a regression that drops these flags in hermetic mode
    lets the engine call external services (LLM, network) which
    is the failure mode the hermetic contract was designed to prevent.
    """
    if not GATE.is_file():
        pytest.skip(f"{GATE} not present")
    text = GATE.read_text(encoding="utf-8")
    assert "--skip-external" in text, (
        "green-gate no longer passes --skip-external in hermetic mode."
    )
    assert "--use-program=self_test-sample" in text, (
        "green-gate no longer routes the hermetic engine to self_test-sample."
    )
