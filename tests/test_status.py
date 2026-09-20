"""Tests for the status headline parser (B.5.1).

The headline is a pure-function read of the pi_monitor supervisor's
``health.json`` + ``latest.json`` state files. The parser classifies
state into one of {running, circuit-open, degraded, gate-closed,
stopped, no-supervisor} and formats a one-line summary.

These tests pin the classification logic with synthetic state
files in a tmp_path fixture; no live supervisor is required.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from research_institution.status import (
    format_headline,
    read_status_headline,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _running_health(now: float) -> dict:
    return {
        "audit": {"chain_breaks": 0},
        "circuit": {"open": False, "trip_count": 0, "soft_until_unix": 0.0},
        "degraded": [],
        "execution": {
            "active_key": "kaplansky.x",
            "attempt_ordinal": 3,
            "outcome": "completed",
            "outcome_unix": now,
        },
    }


def _running_latest(now: float) -> dict:
    return {"observed_unix": now}


def test_headline_running(tmp_path: Path) -> None:
    now = time.time()
    _write_json(tmp_path / "health.json", _running_health(now))
    _write_json(tmp_path / "latest.json", _running_latest(now))
    h = read_status_headline("kaplansky", tmp_path)
    assert h.state == "running"
    assert h.program == "kaplansky"
    assert h.uptime_seconds >= 0
    assert h.last_action == "completed (attempt #3)"


def test_headline_circuit_open(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "health.json",
        {
            "circuit": {"open": True, "trip_count": 2, "soft_until_unix": 0.0},
            "degraded": [],
            "execution": {"outcome": "ok"},
        },
    )
    _write_json(tmp_path / "latest.json", {"observed_unix": time.time()})
    h = read_status_headline("kaplansky", tmp_path)
    assert h.state == "circuit-open"


def test_headline_circuit_open_via_trip_count(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "health.json",
        {
            "circuit": {"open": False, "trip_count": 5, "soft_until_unix": 0.0},
            "degraded": [],
            "execution": {"outcome": "ok"},
        },
    )
    _write_json(tmp_path / "latest.json", {"observed_unix": time.time()})
    h = read_status_headline("kaplansky", tmp_path)
    assert h.state == "circuit-open"


def test_headline_degraded(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "health.json",
        {
            "circuit": {"open": False, "trip_count": 0, "soft_until_unix": 0.0},
            "degraded": ["source_unavailable"],
            "execution": {"outcome": "ok"},
        },
    )
    _write_json(tmp_path / "latest.json", {"observed_unix": time.time()})
    h = read_status_headline("kaplansky", tmp_path)
    assert h.state == "degraded"


def test_headline_gate_closed(tmp_path: Path) -> None:
    """A blocked outcome with an empty degraded list == gate-closed."""
    now = time.time()
    _write_json(
        tmp_path / "health.json",
        {
            "circuit": {"open": False, "trip_count": 0, "soft_until_unix": 0.0},
            "degraded": [],
            "execution": {
                "active_key": "",
                "attempt_ordinal": 0,
                "outcome": "blocked",
                "outcome_unix": now,
            },
        },
    )
    _write_json(tmp_path / "latest.json", {"observed_unix": now})
    h = read_status_headline("kaplansky", tmp_path)
    assert h.state == "gate-closed"


def test_headline_stopped(tmp_path: Path) -> None:
    """A stale observation (older than 5 minutes) == stopped."""
    _write_json(tmp_path / "health.json", _running_health(time.time()))
    _write_json(tmp_path / "latest.json", {"observed_unix": time.time() - 600})
    h = read_status_headline("kaplansky", tmp_path)
    assert h.state == "stopped"


def test_headline_stopped_when_supervisor_pid_is_dead(tmp_path: Path) -> None:
    """State files say running, but the supervisor PID is dead.

    The PID liveness check runs BEFORE the other classifiers so
    operators don't chase ghost "degraded" issues. Mutation-test
    oracle: dropping the `os.kill(pid, 0)` check would let stale
    state hide a crashed supervisor.
    """
    health = _running_health(time.time())
    health["supervisor_pid"] = 2_000_000_000  # guaranteed-dead PID
    health["degraded"] = ["source_unavailable"]  # would otherwise say "degraded"
    _write_json(tmp_path / "health.json", health)
    _write_json(tmp_path / "latest.json", _running_latest(time.time()))
    h = read_status_headline("kaplansky", tmp_path)
    assert h.state == "stopped"


def test_headline_no_supervisor_missing_dir(tmp_path: Path) -> None:
    h = read_status_headline("kaplansky", tmp_path / "does-not-exist")
    assert h.state == "no-supervisor"
    assert h.last_action == ""


def test_headline_no_supervisor_malformed(tmp_path: Path) -> None:
    (tmp_path / "health.json").write_text("not json")
    (tmp_path / "latest.json").write_text("{also not")
    h = read_status_headline("kaplansky", tmp_path)
    assert h.state == "no-supervisor"


def test_format_headline_running() -> None:
    out = format_headline(
        type("H", (), {
            "program": "kaplansky",
            "state": "running",
            "uptime_seconds": 3725.0,  # 1h2m5s
            "last_action": "completed (attempt #3)",
        })()
    )
    assert out == "kaplansky: running (1h2m) \u2014 last: completed (attempt #3)"


def test_format_headline_short_uptime() -> None:
    out = format_headline(
        type("H", (), {
            "program": "kaplansky",
            "state": "running",
            "uptime_seconds": 40.0,
            "last_action": "",
        })()
    )
    assert out == "kaplansky: running (40s)"


def test_format_headline_no_uptime() -> None:
    out = format_headline(
        type("H", (), {
            "program": "kaplansky",
            "state": "no-supervisor",
            "uptime_seconds": 0.0,
            "last_action": "",
        })()
    )
    assert out == "kaplansky: no-supervisor"
