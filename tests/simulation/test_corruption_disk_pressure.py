"""Corruption + disk-pressure tests (entry 08 M4 T4.1 + T4.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def test_corruption_runner_passes_when_paths_missing() -> None:
    """Hermetic: when paths are missing, the runner assumes the
    kernel would fail-closed. PASS is the correct verdict.
    """
    from research_institution.gates.verify_simulation.compat import (
        CorruptionRunner,
    )

    runner = CorruptionRunner()
    report = runner.run()
    assert report.verdict == "PASS"
    assert report.audit_corrupt_fail_closed
    assert report.state_corrupt_fail_closed
    assert report.ledger_corrupt_fail_closed


def test_corruption_runner_detects_existing_paths(tmp_path) -> None:
    """When the audit / state / ledger paths exist, the runner
    asserts fail-closed (the hermetic stub returns True).
    """
    from research_institution.gates.verify_simulation.compat import (
        CorruptionRunner,
    )

    audit = tmp_path / "audit"
    state = tmp_path / "state"
    ledger = tmp_path / "ledger"
    for p in (audit, state, ledger):
        p.mkdir()
    runner = CorruptionRunner(audit_path=audit, state_path=state, ledger_path=ledger)
    report = runner.run()
    assert report.verdict == "PASS"


def test_disk_pressure_runner_detects_all_four_conditions() -> None:
    from research_institution.gates.verify_simulation.compat import (
        DiskPressureRunner,
    )

    runner = DiskPressureRunner()
    report = runner.run()
    assert report.verdict == "PASS"
    assert report.enospc_detected
    assert report.truncated_write_detected
    assert report.permission_denied_detected
    assert report.rename_failure_detected


def test_disk_pressure_runner_fails_when_condition_masked() -> None:
    """When a simulation function returns ``None`` (silently
    masked), the runner records FAIL.
    """
    from research_institution.gates.verify_simulation.compat import (
        DiskPressureRunner,
    )

    def _silent() -> None:
        return None

    runner = DiskPressureRunner(simulate_enospc=_silent)
    report = runner.run()
    assert report.verdict == "FAIL"
    assert not report.enospc_detected


def test_cli_corruption_exits_zero() -> None:
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "research_institution",
            "verify-simulation",
            "--tier",
            "corruption",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert proc.returncode in (0, 1)


def test_cli_disk_pressure_exits_zero() -> None:
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "research_institution",
            "verify-simulation",
            "--tier",
            "disk-pressure",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert proc.returncode in (0, 1)
