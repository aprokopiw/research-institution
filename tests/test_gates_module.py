"""Tests for the canonical Python gates package.

The gates package replaced several shell scripts. Each test
pins a contract that the shell scripts satisfied so we don't
accidentally lose behavior during the rewrite.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from research_institution.gates.aggregate import (
    GateCheck,
    GateReport,
    GateStatus,
    check_institution,
)
from research_institution.gates.bootstrap import bootstrap_install
from research_institution.gates.runner import run


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_runner_resolves_bare_names() -> None:
    """The runner prepends the project's venv bin so subprocess
    resolution does not depend on the operator's interactive
    shell environment."""
    if not (REPO_ROOT / ".venv" / "bin" / "python").exists():
        pytest.skip("project venv not present")
    result = run(("python", "--version"))
    assert result.ok
    # And the resolved argv points at the venv's python binary.
    assert str(REPO_ROOT / ".venv" / "bin" / "python") in str(result.command)


def test_runner_swallows_bash_not_on_path() -> None:
    """When the operator strips PATH down to the venv, the
    runner must still find bash via the system PATH it carries
    forward from the parent env.
    """
    if not shutil.which("bash"):
        pytest.skip("bash not on system PATH")
    # Set a tiny PATH missing bash; the runner should re-inject it.
    saved = os.environ.get("PATH", "")
    try:
        os.environ["PATH"] = "/usr/bin:/bin"
        result = run(("bash", "--version"), cwd=REPO_ROOT)
        assert result.ok, f"rc={result.returncode} stderr={result.stderr}"
    finally:
        os.environ["PATH"] = saved


def test_runner_returns_captured_output() -> None:
    """`RunResult` captures stdout/stderr text so test oracles can
    inspect them without re-running.
    """
    result = run(("echo", "hello-world"))
    assert result.ok
    assert "hello-world" in result.stdout


def test_runner_propagates_cwd() -> None:
    """`cwd=` arg flows through to subprocess.run."""
    if not shutil.which("pwd"):
        pytest.skip("pwd not on PATH")
    parent = REPO_ROOT.parent
    result = run(("pwd",), cwd=parent)
    assert str(parent) in result.stdout.rstrip()
    assert result.cwd == str(parent)


def test_runner_returns_nonzero_on_failure() -> None:
    """Failed commands report non-ok."""
    if not shutil.which("false"):
        pytest.skip("false not on PATH")
    result = run(("false",))
    assert not result.ok
    assert result.returncode != 0


def test_bootstrap_step_dataclass_shape() -> None:
    """`BootstrapStep` and `BootstrapReport` are exposed via
    the package surface — the prior shell aggregator had no
    structured return shape.
    """
    from research_institution.gates.bootstrap import (
        BootstrapReport,
        BootstrapStep,
        bootstrap_install,
    )

    report = bootstrap_install()
    assert isinstance(report, BootstrapReport)
    assert all(isinstance(s, BootstrapStep) for s in report.steps)


def test_bootstrap_install_is_idempotent() -> None:
    """Two consecutive calls return equivalent verdicts.

    A regression that accidentally introduces side-effects
    (e.g. partial purge on idempotent re-run) would show up
    here.
    """
    first = bootstrap_install()
    second = bootstrap_install()
    assert first.ok == second.ok
    assert len(first.steps) == len(second.steps)
    assert first.programs_installed == second.programs_installed


def test_aggregator_gate_check_dataclass_shape() -> None:
    """`GateCheck` exposes the canonical fields used by the
    institution gate; downstream operator dashboards grep on
    these labels.
    """
    check = GateCheck(
        name="test-check", status=GateStatus.PASS, detail="ok"
    )
    assert check.ok is True
    assert check.name == "test-check"
    assert check.detail == "ok"


def test_aggregator_gate_report_aggregates_results() -> None:
    """`GateReport.ok` is True iff every check passed or was skipped."""
    passing = GateReport(
        checks=(
            GateCheck(name="a", status=GateStatus.PASS),
            GateCheck(name="b", status=GateStatus.SKIP, detail="reason"),
        ),
        mode="hermetic",
    )
    failing = GateReport(
        checks=(
            GateCheck(name="a", status=GateStatus.PASS),
            GateCheck(name="b", status=GateStatus.FAIL, detail="ohno"),
        ),
        mode="hermetic",
    )
    assert passing.ok is True
    assert failing.ok is False
    assert len(failing.failures) == 1
    assert failing.failures[0].name == "b"


def test_aggregator_render_emits_verdict_line() -> None:
    """`GateReport.render()` must include the canonical verdict line."""
    passing = GateReport(
        checks=(GateCheck(name="a", status=GateStatus.PASS),),
        mode="hermetic",
    )
    failing = GateReport(
        checks=(GateCheck(name="a", status=GateStatus.FAIL, detail="d"),),
        mode="hermetic",
    )
    assert "GREEN INSTITUTION READY" in passing.render()
    assert "RED: failed checks" in failing.render()
    assert "a" in failing.render()


def test_aggregator_default_mode_is_hermetic() -> None:
    """Backward-compat with the prior shell's default."""
    report = check_institution()
    assert report.mode == "hermetic"
