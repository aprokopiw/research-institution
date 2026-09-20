"""Tests for the supervisor probe helper.

The dispatcher relies on `SupervisorState.is_alive` to refuse
duplicate-spawn races. Pin the contract with deterministic
subprocess doubles (FakeRunner) and an explicit PID liveness check.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


from research_institution.supervisor import (
    _pid_alive,
    probe_supervisor,
)


class FakeRunner:
    """Queue-driven subprocess double that mirrors `subprocess.run`."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.responses: list[subprocess.CompletedProcess[str]] = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        if self.responses:
            return self.responses.pop(0)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


def test_pid_alive_for_current_process() -> None:
    """os.getpid() is by definition alive."""
    assert _pid_alive(os.getpid()) is True


def test_pid_alive_zero() -> None:
    assert _pid_alive(0) is False


def test_pid_alive_negative() -> None:
    assert _pid_alive(-1) is False


def test_pid_alive_nonexistent() -> None:
    """A pid that almost certainly doesn't exist returns False."""
    # PIDs in [4, 1000) are reserved/daemon; pick a very large one
    # that we're confident is unused in this test environment.
    assert _pid_alive(2_000_000_000) is False


def test_probe_supervisor_no_binary(tmp_path: Path) -> None:
    """If pi-monitor is missing, probe returns not-alive without raising."""
    runner = FakeRunner()
    runner.responses = [
        FileNotFoundError("pi-monitor: not on PATH"),
    ]

    def raising_runner(cmd, **kw):
        runner.calls.append(list(cmd))
        raise runner.responses.pop(0)

    state = probe_supervisor(tmp_path / "config.toml", runner=raising_runner)
    assert state.is_alive is False
    assert state.supervisor_pid == 0
    assert state.worker_pid == 0
    assert state.status_payload is None


def test_probe_supervisor_nonzero_exit(tmp_path: Path) -> None:
    """A nonzero exit (e.g. supervisor not running) -> not-alive."""
    runner = FakeRunner()
    runner.responses = [
        subprocess.CompletedProcess(["pi-monitor"], 1, stdout="", stderr="no supervisor"),
    ]
    state = probe_supervisor(tmp_path / "config.toml", runner=runner)
    assert state.is_alive is False


def test_probe_supervisor_malformed_json(tmp_path: Path) -> None:
    runner = FakeRunner()
    runner.responses = [
        subprocess.CompletedProcess(["pi-monitor"], 0, stdout="not json", stderr=""),
    ]
    state = probe_supervisor(tmp_path / "config.toml", runner=runner)
    assert state.is_alive is False


def test_probe_supervisor_alive_pid(tmp_path: Path) -> None:
    """When the JSON includes the current PID, is_alive is True."""
    runner = FakeRunner()
    payload = (
        '{"supervisor_pid": '
        + str(os.getpid())
        + ', "worker_pid": 0, "project": "x", "root": "/tmp", "state_dir": "/tmp/x"}'
    )
    runner.responses = [
        subprocess.CompletedProcess(["pi-monitor"], 0, stdout=payload, stderr=""),
    ]
    state = probe_supervisor(tmp_path / "config.toml", runner=runner)
    assert state.is_alive is True
    assert state.supervisor_pid == os.getpid()
    assert state.worker_pid == 0
    assert state.status_payload is not None
    assert state.status_payload["project"] == "x"


def test_probe_supervisor_dead_pid(tmp_path: Path) -> None:
    """A stale PID in the JSON + that PID no longer responds -> not-alive."""
    runner = FakeRunner()
    payload = '{"supervisor_pid": 2000000000, "worker_pid": 0, "project": "x"}'
    runner.responses = [
        subprocess.CompletedProcess(["pi-monitor"], 0, stdout=payload, stderr=""),
    ]
    state = probe_supervisor(tmp_path / "config.toml", runner=runner)
    assert state.is_alive is False
    assert state.supervisor_pid == 2_000_000_000  # preserved from JSON


def test_probe_supervisor_missing_pids(tmp_path: Path) -> None:
    """JSON without pids defaults to 0 / not-alive."""
    runner = FakeRunner()
    payload = '{"project": "x", "root": "/tmp"}'
    runner.responses = [
        subprocess.CompletedProcess(["pi-monitor"], 0, stdout=payload, stderr=""),
    ]
    state = probe_supervisor(tmp_path / "config.toml", runner=runner)
    assert state.is_alive is False
    assert state.supervisor_pid == 0
