"""Green-gate CLI shape contract tests.

The canonical aggregator is the Python CLI
`python -m research_institution.gates.aggregate`. The shell
shim at `green-gate/check-institution.sh` is a delegator.
These tests pin the CLI surface contract (flags, exit codes,
verdict lines) so a regression in either surface breaks loudly.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_SHIM = REPO_ROOT / "green-gate" / "check-institution.sh"
GATE_MODULE = "research_institution.gates.aggregate"


def _python_main(argv: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "-m", GATE_MODULE, *argv],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=timeout,
        check=False,
    )


def test_green_gate_help_lists_all_flags() -> None:
    completed = _python_main(["--help"], timeout=5)
    assert completed.returncode == 0
    out = completed.stdout
    for flag in ("--hermetic", "--live", "--skip-program", "-h", "--help"):
        assert flag in out, (
            f"green-gate usage missing {flag!r}; full help:\n{out}"
        )


def test_green_gate_unknown_flag_exits_2() -> None:
    completed = _python_main(["--no-such-flag"], timeout=5)
    assert completed.returncode == 2, (
        f"green-gate unknown-flag exit code: got {completed.returncode}, "
        f"expected 2. stderr={completed.stderr!r}"
    )


def test_green_gate_list_prints_catalog() -> None:
    completed = _python_main(["list"], timeout=5)
    assert completed.returncode == 0, (
        f"list failed: rc={completed.returncode} stderr={completed.stderr!r}"
    )
    assert "NAME" in completed.stdout
    assert "kaplansky" in completed.stdout, (
        f"list output missing kaplansky; got:\n{completed.stdout}"
    )


def test_green_gate_skip_program_can_be_repeated() -> None:
    """`--skip-program X` MUST be repeatable."""
    completed = _python_main(
        ["check", "--skip-program", "kaplansky", "--skip-program", "other"],
        timeout=60,
    )
    # Either green or red is fine; the contract is the SKIP appears
    # in the report.
    assert "skipped by --skip-program" in completed.stdout, (
        f"skip-program not honored: {completed.stdout!r}"
    )


def test_green_gate_prints_verdict_lines() -> None:
    """Aggregator prints one of two canonical lines per @INV-0093."""
    completed = _python_main(["check"], timeout=60)
    out = completed.stdout
    assert ("GREEN INSTITUTION READY" in out) or ("RED: failed checks" in out), (
        f"verdict line missing: {out!r}"
    )


def test_green_gate_shim_forwards_to_module() -> None:
    """The shell shim exists, is executable, and delegates to the module."""
    assert GATE_SHIM.exists()
    assert GATE_SHIM.stat().st_mode & 0o111
    text = GATE_SHIM.read_text()
    assert GATE_MODULE in text, "shim must delegate to the Python module"


def test_green_gate_shim_help_via_module() -> None:
    """Bash shim path produces the same help as the Python module."""
    if not GATE_SHIM.exists():
        pytest.skip(f"{GATE_SHIM} missing")
    completed = subprocess.run(
        [str(GATE_SHIM), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    # Shim inherits exit code from python module; --help exits 0.
    assert completed.returncode == 0, (
        f"shim --help exit {completed.returncode}; {completed.stderr!r}"
    )
    for flag in ("--hermetic", "--live"):
        assert flag in completed.stdout, (
            f"shim --help missing {flag}; ran: {GATE_SHIM}"
        )
