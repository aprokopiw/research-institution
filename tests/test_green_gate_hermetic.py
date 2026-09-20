"""Contract tests for the institution green gate.

Per `@CTR-0088` and `@INV-0093`, the aggregator must exist,
delegate correctly, and default to `--hermetic`.

The canonical implementation lives in
`research_institution.gates.aggregate.check_institution()` and
its `python -m research_institution.gates.aggregate` CLI. The
shell shim at `green-gate/check-institution.sh` is a 4-line
delegator; tests below assert the Python module is correct AND
that the shim is a thin pointer.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from research_institution.gates.aggregate import (
    GateCheck,
    GateReport,
    GateStatus,
    check_institution,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_SHIM = REPO_ROOT / "green-gate" / "check-institution.sh"
GATE_MODULE = "research_institution.gates.aggregate"


def test_check_institution_shim_exists() -> None:
    assert GATE_SHIM.exists(), f"missing {GATE_SHIM}"
    assert GATE_SHIM.stat().st_mode & 0o111, f"{GATE_SHIM} not executable"


def test_check_institution_delegates_correctly() -> None:
    """The shim must exec the Python module — no logic of its own."""
    text = GATE_SHIM.read_text()
    assert GATE_MODULE in text, "shim must delegate to the Python module"
    # And it must support both modes via flag passthrough.
    assert "--hermetic" in text or "$@" in text


def test_hermetic_uses_sample_program() -> None:
    """The Python aggregator hard-codes the bundled sample program
    under hermetic mode (`--use-program=self_test-sample`). Tests pin
    this so the math-engine invocation is never accidentally broadened."""
    import research_institution.gates.aggregate as aggregate

    src = Path(aggregate.__file__).read_text()
    assert "--use-program=self_test-sample" in src


def test_aggregator_default_mode_is_hermetic() -> None:
    """`check_institution()` defaults to hermetic when not invoked from CLI."""
    report = check_institution()  # no mode arg
    assert report.mode == "hermetic"


def test_aggregator_returns_structured_report() -> None:
    """`check_institution()` returns a GateReport with the canonical checks."""
    report = check_institution(mode="hermetic")
    assert isinstance(report, GateReport)
    expected_names = {"v0-ruff", "v-wire", "engine", "supervisor"}
    actual_names = {check.name for check in report.checks}
    assert expected_names.issubset(actual_names), (
        f"missing canonical checks; got {actual_names}, expected at least {expected_names}"
    )
    for check in report.checks:
        assert isinstance(check, GateCheck)
        assert check.status in {GateStatus.PASS, GateStatus.FAIL, GateStatus.SKIP}


def test_aggregator_rejects_unknown_mode() -> None:
    """The mode argument is fail-closed: typos surface, not silently default."""
    with pytest.raises(ValueError, match="mode"):
        check_institution(mode="not-a-mode")


def test_skips_mentioned_program() -> None:
    """`--skip-program=X` produces a SKIP verdict for program=X."""
    report = check_institution(mode="hermetic", skip_programs=("kaplansky",))
    program_checks = [c for c in report.checks if c.name.startswith("program=")]
    assert any(
        c.status is GateStatus.SKIP and c.detail == "skipped by --skip-program"
        for c in program_checks
    ), "no SKIP verdict found for kaplansky"


@pytest.mark.parametrize("runner", ["cli", "python_api"])
def test_run_under_each_surface(runner: str) -> None:
    """Both entry surfaces must produce a coherent verdict."""
    if runner == "cli":
        proc = subprocess.run(
            ["python3", "-m", "research_institution.gates.aggregate", "check"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=60,
            check=False,
        )
        # The CLI never invents a GREEN verdict; it exits 1 on RED.
        assert proc.returncode in (0, 1)
        assert ("GREEN INSTITUTION READY" in proc.stdout) or (
            "RED: failed checks" in proc.stdout
        )
    else:
        report = check_institution(mode="hermetic")
        assert report.ok is True or any(
            c.status is GateStatus.FAIL for c in report.checks
        )
