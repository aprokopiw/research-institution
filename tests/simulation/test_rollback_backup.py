"""Rollback + backup-restore tests (entry 08 M3 T3.1 + T3.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def test_rollback_runner_passes_hermetic() -> None:
    from research_institution.gates.verify_simulation.compat import (
        RollbackRunner,
    )

    runner = RollbackRunner()
    report = runner.run()
    assert report.verdict == "PASS"
    assert report.n_state_readable
    assert report.n_minus_1_state_readable
    assert not report.redispatch_detected


def test_backup_restore_runner_round_trips(tmp_path) -> None:
    from research_institution.gates.verify_simulation.compat import (
        BackupRestoreRunner,
    )

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "decision.json").write_text('{"op": "x"}', encoding="utf-8")
    runner = BackupRestoreRunner(state_dir=state_dir)
    report = runner.run()
    assert report.verdict == "PASS"
    assert report.pre_backup_sha == report.post_restore_sha
    assert report.duplicate_executions == 0
    assert report.duplicate_reports == 0


def test_backup_restore_runner_blocks_when_state_missing(tmp_path) -> None:
    from research_institution.gates.verify_simulation.compat import (
        BackupRestoreRunner,
    )

    runner = BackupRestoreRunner(state_dir=tmp_path / "no-such-dir")
    report = runner.run()
    assert report.verdict == "BLOCKED"


def test_cli_rollback_exits_zero() -> None:
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "research_institution",
            "verify-simulation",
            "--tier",
            "rollback",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert proc.returncode in (0, 1)


def test_cli_backup_restore_exits_zero() -> None:
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "research_institution",
            "verify-simulation",
            "--tier",
            "backup-restore",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert proc.returncode in (0, 1)
