"""Tests for ``research-institution/scripts/stop-program.sh --dry-run`` (PP-Y.3)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path("/Users/erinprokopiw/Documents/andrei/research-institution")
SCRIPT = REPO / "scripts" / "stop-program.sh"


def _run(args: list[str], env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["/bin/sh", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )


def test_dry_run_prints_signals() -> None:
    """--dry-run kaplansky -> exit 0 + SIGTERM/SIGKILL sequence."""
    proc = _run(["--dry-run", "kaplansky"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SIGTERM" in proc.stdout
    assert "SIGKILL" in proc.stdout
    assert "stop-actions.jsonl" in proc.stdout


def test_dry_run_unknown_program_exits_2() -> None:
    """Unknown name -> exit 2 + UNKNOWN PROGRAM."""
    proc = _run(["--dry-run", "no-such-program"])
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "UNKNOWN PROGRAM: no-such-program" in proc.stdout
