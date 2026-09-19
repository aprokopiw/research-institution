"""Tests for ``research-institution/scripts/launch-program.sh --dry-run`` (PP-Y.1)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path("/Users/erinprokopiw/Documents/andrei/research-institution")
SCRIPT = REPO / "scripts" / "launch-program.sh"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/sh", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env={**os.environ},
        timeout=30,
    )


def test_dry_run_kaplansky_reports_would_launch() -> None:
    """--dry-run kaplansky -> exit 0 + LAUNCHED line."""
    proc = _run(["--dry-run", "kaplansky"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "would launch: mathlint-kaplansky start" in proc.stdout
    assert "LAUNCHED: pid=dry-run" in proc.stdout


def test_unknown_program_exits_2() -> None:
    """Unknown name -> exit 2 + UNKNOWN PROGRAM."""
    proc = _run(["--dry-run", "no-such-program"])
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "UNKNOWN PROGRAM: no-such-program" in proc.stdout


def test_no_args_exits_64() -> None:
    """No name -> exit 64 (usage error)."""
    proc = _run([])
    assert proc.returncode == 64, proc.stdout + proc.stderr
    assert "USAGE" in proc.stderr
