"""Tests for ``research-institution/scripts/watch-program.sh --dry-run`` (PP-Y.2)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path("/Users/erinprokopiw/Documents/andrei/research-institution")
SCRIPT = REPO / "scripts" / "watch-program.sh"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/sh", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env={**os.environ},
        timeout=15,
    )


def test_dry_run_prints_5_windows() -> None:
    """--dry-run kaplansky -> exit 0 + 5 tmux windows listed."""
    proc = _run(["--dry-run", "kaplansky"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "5 tmux windows" in proc.stdout
    for tag in ("status", "activity", "journal", "snapshot", "log tail"):
        assert tag in proc.stdout


def test_unknown_program_exits_2() -> None:
    """Unknown name -> exit 2 + UNKNOWN PROGRAM."""
    proc = _run(["--dry-run", "no-such-program"])
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "UNKNOWN PROGRAM: no-such-program" in proc.stdout
