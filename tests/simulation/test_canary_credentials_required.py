"""Provider canary credentials-required test (entry 07 T2.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def test_canary_runner_refuses_without_live() -> None:
    """``--tier provider-canary`` without ``--live`` returns REFUSED."""
    from research_institution.gates.verify_simulation.canary import CanaryRunner

    runner = CanaryRunner(live=False)
    report = runner.run()
    assert report.verdict == "REFUSED"
    assert "requires --live" in report.detail


def test_canary_runner_blocks_when_credentials_absent() -> None:
    """``--live`` without MATHLINT_MODEL_ROUTE + auth.json returns BLOCKED."""
    from research_institution.gates.verify_simulation.canary import CanaryRunner

    runner = CanaryRunner(live=True)
    # If the operator happens to have the credentials set, the
    # verdict is CANARY_PASS — the BLOCKED assertion only fires
    # when both credentials are absent. Skip in that case.
    report = runner.run()
    if report.has_model_route and report.has_auth_json:
        pytest.skip(
            "operator has real credentials; CANARY_PASS is the correct path"
        )
    assert report.verdict == "CANARY_BLOCKED"
    assert "credentials absent" in report.detail


def test_canary_runner_only_supports_rate_defer_restart() -> None:
    """The runner refuses scenarios other than ``rate-defer-restart``
    per FR-5 (the only canonical canary scenario at first).
    """
    from research_institution.gates.verify_simulation.canary import CanaryRunner

    with pytest.raises(ValueError):
        CanaryRunner(scenario="happy-three-cycle", live=True)


def test_cli_provider_canary_without_live_exits_two() -> None:
    """``--tier provider-canary`` without ``--live`` exits 2
    with an actionable error (FR-5 + T2.2).
    """
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "research_institution",
            "verify-simulation",
            "--tier",
            "provider-canary",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert proc.returncode == 2
    assert "--live" in proc.stderr


def test_cli_provider_canary_with_live_exits_zero_or_78() -> None:
    """``--tier provider-canary --live --scenario rate-defer-restart``
    exits 0 (CANARY_PASS) or 78 (CANARY_BLOCKED). Both are correct
    paths depending on credentials.
    """
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "research_institution",
            "verify-simulation",
            "--tier",
            "provider-canary",
            "--live",
            "--scenario",
            "rate-defer-restart",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert proc.returncode in (0, 78)
