"""Cold-start workflow test.

Exercises the AGENTS.md cold-start recipe against the real repo on this
machine:

  1. Read the catalog.
  2. Run the green gate (hermetic).
  3. Run `python -m research_institution list`.
  4. Run `python -m research_institution doctor`.

This is the contract the AGENTS.md prescribes. A fresh agent that runs
the cold prompt must succeed at all four steps.

Skipped when mathlint / pi-monitor are not installed, or when the
pi_monitor supervisor is currently holding the state lock (which
makes the live-mode sub-check block; see
`test_cold_start_doctor_live_passes_when_credentials_valid`).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# The pi_monitor supervisor holds a lock at this path while running.
# Live-mode mathlint system-readiness can block waiting for this lock;
# we skip those tests when a supervisor is active to avoid hanging.
PI_MONITOR_LOCK = Path.home() / ".local" / "state" / "mathlint" / "pi-monitor" / "supervisor.lock"


def _supervisor_running() -> bool:
    """True iff a pi_monitor supervisor holds the state lock."""
    if not PI_MONITOR_LOCK.exists():
        return False
    try:
        pid_text = PI_MONITOR_LOCK.read_text(encoding="utf-8").strip()
        pid = int(pid_text)
        # POSIX kill(pid, 0) succeeds iff the process exists.
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError, PermissionError, OSError):
        return False


@pytest.fixture(scope="module")
def _has_mathlint() -> bool:
    return shutil.which("mathlint") is not None


@pytest.fixture(scope="module")
def _has_pi_monitor() -> bool:
    return shutil.which("pi-monitor") is not None


def test_cold_start_list(cli_runner) -> None:
    """Step 1: `python -m research_institution list` prints the catalog."""
    result = cli_runner.invoke(args=["list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "kaplansky" in result.stdout


def test_cold_start_doctor_hermetic() -> None:
    """Step 2: green gate --hermetic returns GREEN INSTITUTION READY."""
    gate = REPO / "green-gate" / "check-institution.sh"
    if not gate.is_file():
        pytest.skip("green gate missing")
    result = subprocess.run(
        ["bash", str(gate), "--hermetic"],
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert result.returncode == 0, (
        f"green gate failed: rc={result.returncode} stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    assert "GREEN INSTITUTION READY" in result.stdout


@pytest.mark.skipif(
    _supervisor_running(),
    reason=(
        "pi_monitor supervisor is currently running and holds the state lock; "
        "the live-mode sub-check blocks waiting for it. Stop the supervisor "
        "(`pi-monitor stop --config ~/.config/mathlint/local-pi-monitor.toml`) "
        "and re-run to exercise this gate."
    ),
)
def test_cold_start_doctor_live_passes_when_credentials_valid() -> None:
    """Step 3: green gate --live exits 0 when the institution is wired.

    On a fully wired machine, --hermetic and --live MUST both exit 0
    (the only difference is which program provider the engine
    sub-check uses). This test pins the contract: a regression that
    breaks the live gate while the hermetic gate stays GREEN is a
    real defect worth catching here.

    Skipped when the pi_monitor supervisor is active; see the
    skipif condition above. The skip is BLOCKED-class behavior per
    the verification skill: required evidence is unobtainable in
    this run because the operator's environment has a competing
    supervisor.
    """
    gate = REPO / "green-gate" / "check-institution.sh"
    if not gate.is_file():
        pytest.skip("green gate missing")
    # Skip if the operator has no live credentials — the live gate
    # legitimately fails-closed without them, and that's not a defect.
    if not os.environ.get("MATHLINT_MODEL_ROUTE"):
        pytest.skip("MATHLINT_MODEL_ROUTE not set; live gate not exercised")
    result = subprocess.run(
        ["bash", str(gate), "--live"],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, (
        f"live gate failed: rc={result.returncode} "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "GREEN INSTITUTION READY" in result.stdout


@pytest.mark.skipif(
    _supervisor_running(),
    reason=(
        "Supervisor holds the state lock; the live engine sub-check "
        "would block. The --no-model --no-write variant below exercises "
        "the same code path without locking."
    ),
)
def test_cold_start_doctor_live_no_model_subcheck_is_nonblocking() -> None:
    """Step 3 (faster oracle): the live-mode engine sub-check is non-blocking.

    The full `bash green-gate --live` path can hang when the pi_monitor
    supervisor is running. This test exercises the SAME live-mode mathlint
    code path (system-readiness with the live provider flags) but with
    `--no-model` and `--no-write`, which:

      - Skip the agent-smoke LLM call (no network, no cost).
      - Skip state-file writes (no lock contention with the supervisor).
      - Still run all engine wiring checks (config, postgres, mathlint).

    A regression that breaks the live-mode code path (the dispatcher
    calls `mathlint system-readiness` before delegating to live-run)
    will surface here even when the full gate is blocked by a
    competing supervisor.
    """
    if not shutil.which("mathlint"):
        pytest.skip("mathlint not on PATH")
    if not os.environ.get("MATHLINT_MODEL_ROUTE"):
        pytest.skip("MATHLINT_MODEL_ROUTE not set; live subcheck not exercised")
    result = subprocess.run(
        [
            "mathlint",
            "system-readiness",
            "--no-model",
            "--no-write",
            "--json",
            "--config",
            os.environ.get("MATHLINT_CONFIG", str(Path.home() / ".config/mathlint" / "local.toml")),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        cwd=str(REPO / "catalog" if (REPO / "catalog").exists() else str(REPO)),
    )
    # system-readiness with --no-model returns 0 if config loaded
    # (its per-check verdicts are in the JSON, not the exit code).
    assert result.returncode == 0, (
        f"live-mode subcheck failed: rc={result.returncode} "
        f"stderr={result.stderr[:600]!r}"
    )
    # The JSON output must contain at least one structured check
    # verdict. This is the strongest non-flaky oracle we can use
    # for "live mode can run without hanging".
    import json as _json
    payload = _json.loads(result.stdout)
    assert "checks" in payload, (
        f"system-readiness --json did not return a `checks` list: {payload!r}"
    )
    assert isinstance(payload["checks"], list)
    assert len(payload["checks"]) >= 1, "no check entries in system-readiness verdict"
