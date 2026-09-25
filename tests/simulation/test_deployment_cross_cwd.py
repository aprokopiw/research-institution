"""Cross-cwd ``research doctor`` test (entry 07 T1.3 / FR-3)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def test_deployment_runner_dry_run_exits_zero() -> None:
    """The dry-run deployment tier prints rendered ProgramArguments
    without spawning subprocesses and exits 0.
    """
    from research_institution.gates.verify_simulation.deployment import (
        DeploymentRunner,
    )

    runner = DeploymentRunner(repo_root=REPO)
    report = runner.run_dry()
    assert report.verdict in ("PASS", "BLOCKED")
    assert len(report.rendered_argv) >= 1
    assert report.rendered_argv[0].endswith("pi-monitor")


def test_deployment_runner_renders_consistent_argv() -> None:
    """Two consecutive renders return byte-equal argv (FR-2)."""
    from research_institution.gates.verify_simulation.deployment import (
        DeploymentRunner,
    )

    runner = DeploymentRunner(repo_root=REPO)
    a = runner.render()
    b = runner.render()
    assert a.argv == b.argv


def test_isolated_env_cleans_on_success() -> None:
    """``isolated_env`` removes its temp HOME on clean exit."""
    from research_institution.gates.verify_simulation.deployment import (
        isolated_env,
    )

    with isolated_env(repo_root=REPO) as env:
        home = env["HOME"]
        assert Path(home).exists()
    assert not Path(home).exists()


def test_isolated_env_preserves_on_exception() -> None:
    """``isolated_env`` preserves the temp HOME when the body raises."""
    from research_institution.gates.verify_simulation.deployment import (
        isolated_env,
    )

    captured_home: str | None = None
    with pytest.raises(RuntimeError):
        with isolated_env(repo_root=REPO) as env:
            captured_home = env["HOME"]
            assert Path(captured_home).exists()
            raise RuntimeError("simulated failure")
    assert captured_home is not None
    # Preserved on exception for post-mortem inspection.
    assert Path(captured_home).exists()


def test_cli_deployment_dry_run_exits_zero() -> None:
    """``--tier deployment --dry-run`` exits 0."""
    rc = subprocess.run(
        [
            sys.executable,
            "-m",
            "research_institution",
            "verify-simulation",
            "--tier",
            "deployment",
            "--dry-run",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    ).returncode
    assert rc == 0, f"deployment --dry-run rc={rc}"


def test_cli_deployment_with_isolated_label_dry_runs() -> None:
    """``--tier deployment --dry-run --macos-isolated-label=<unique>`` exits 0."""
    label = f"verify-sim-deploy-test-{os.getpid()}"
    rc = subprocess.run(
        [
            sys.executable,
            "-m",
            "research_institution",
            "verify-simulation",
            "--tier",
            "deployment",
            "--dry-run",
            "--macos-isolated-label",
            label,
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    ).returncode
    assert rc == 0, f"deployment --macos-isolated-label rc={rc}"
