"""Tests for ``research-institution/scripts/rollback-program.sh --dry-run`` (PP-Y.4)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path("/Users/erinprokopiw/Documents/andrei/research-institution")
SCRIPT = REPO / "scripts" / "rollback-program.sh"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/sh", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env={**os.environ},
        timeout=15,
    )


def test_dry_run_prints_rollback_plan() -> None:
    """--dry-run kaplansky -> exit 0 + ROLLED BACK line."""
    proc = _run(["--dry-run", "kaplansky"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SIGTERM" in proc.stdout
    assert "ROLLED BACK: backup_at=" in proc.stdout


def test_dry_run_unknown_program_exits_clean() -> None:
    """Unknown name is informational; rollback operates on state, not catalog."""
    proc = _run(["--dry-run", "no-such-program"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ROLLED BACK" in proc.stdout
