"""Tests for the status headline parser (B.5.1).

The headline is a pure-function read of the pi_monitor supervisor's
``health.json`` + ``latest.json`` state files. The parser classifies
state into one of the eleven closed ``ProgramState`` values
(service-installed, running, rate-deferred, source-wait,
operator-paused, terminal-stop, circuit-open, gate-closed,
degraded, stopped, no-supervisor) and formats a one-line summary.

The new states the autonomous-research brief introduces are
exercised at the bottom of the file:

* ``RATE_DEFERRED`` — ``health.next_eligible_unix > 0``.
* ``SOURCE_WAIT`` — ``health.source.last_kind == "wait"``.
* ``OPERATOR_PAUSED`` — ``health.source_paused``.
* ``TERMINAL_STOP`` — ``health.stopped`` or supervisor PID
  dead or staleness boundary exceeded.

These tests pin the classification logic with synthetic state
files in a tmp_path fixture; no live supervisor is required.

Wall-clock isolation: every test passes a frozen `NOW` value via
the `now=` kwarg of `read_status_headline`. The parser's staleness
boundary (5 minutes) is exercised with `NOW` = `observed_unix` for
"fresh", and `NOW` = `observed_unix + 301` for "stale". This
removes the implicit coupling to `time.time()` that made the
previous version of this file fragile to test ordering.
"""

from __future__ import annotations

import json
from pathlib import Path

from research_institution.status import (
    ProgramState,
    StatusHeadline,
    format_headline,
    read_status_headline,
    HealthPayload,
    LatestPayload,
)

# A frozen wall-clock anchor for every test in this module.
# 2026-01-01T00:00:00Z. Chosen to be a stable, memorable value.
NOW = 1_767_225_600.0


def _write_json(path: Path, payload: HealthPayload | LatestPayload | dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Pydantic models serialize via model_dump; raw dicts serialize as-is.
    if isinstance(payload, (HealthPayload, LatestPayload)):
        payload = payload.model_dump(exclude_none=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _running_health(now: float) -> HealthPayload:
    return HealthPayload.model_validate(
        {
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
    )


def _running_latest(now: float) -> LatestPayload:
    return LatestPayload.model_validate({"observed_unix": now})


def test_headline_running(tmp_path: Path) -> None:
    _write_json(tmp_path / "health.json", _running_health(NOW))
    _write_json(tmp_path / "latest.json", _running_latest(NOW))
    h = read_status_headline("kaplansky", tmp_path, now=NOW)
    assert h.state is ProgramState.RUNNING
    assert h.program == "kaplansky"
    assert h.uptime_seconds == 0.0
    assert h.last_action == "completed (attempt #3)"


def test_headline_running_uptime_is_observed_age(tmp_path: Path) -> None:
    """Uptime is the elapsed time since observed_unix, not always 0."""
    _write_json(tmp_path / "health.json", _running_health(NOW))
    _write_json(tmp_path / "latest.json", _running_latest(NOW))
    h = read_status_headline("kaplansky", tmp_path, now=NOW + 12.5)
    assert h.state is ProgramState.RUNNING
    assert h.uptime_seconds == 12.5


def test_headline_circuit_open(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "health.json",
        {
            "circuit": {"open": True, "trip_count": 2, "soft_until_unix": 0.0},
            "degraded": [],
            "execution": {"outcome": "ok"},
        },
    )
    _write_json(tmp_path / "latest.json", _running_latest(NOW))
    h = read_status_headline("kaplansky", tmp_path, now=NOW)
    assert h.state is ProgramState.CIRCUIT_OPEN


def test_headline_circuit_open_via_trip_count(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "health.json",
        {
            "circuit": {"open": False, "trip_count": 5, "soft_until_unix": 0.0},
            "degraded": [],
            "execution": {"outcome": "ok"},
        },
    )
    _write_json(tmp_path / "latest.json", _running_latest(NOW))
    h = read_status_headline("kaplansky", tmp_path, now=NOW)
    assert h.state is ProgramState.CIRCUIT_OPEN


def test_headline_degraded(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "health.json",
        {
            "circuit": {"open": False, "trip_count": 0, "soft_until_unix": 0.0},
            "degraded": ["source_unavailable"],
            "execution": {"outcome": "ok"},
        },
    )
    _write_json(tmp_path / "latest.json", _running_latest(NOW))
    h = read_status_headline("kaplansky", tmp_path, now=NOW)
    assert h.state is ProgramState.DEGRADED


def test_headline_gate_closed(tmp_path: Path) -> None:
    """A blocked outcome with an empty degraded list == gate-closed."""
    _write_json(
        tmp_path / "health.json",
        {
            "circuit": {"open": False, "trip_count": 0, "soft_until_unix": 0.0},
            "degraded": [],
            "execution": {
                "active_key": "",
                "attempt_ordinal": 0,
                "outcome": "blocked",
                "outcome_unix": NOW,
            },
        },
    )
    _write_json(tmp_path / "latest.json", _running_latest(NOW))
    h = read_status_headline("kaplansky", tmp_path, now=NOW)
    assert h.state is ProgramState.GATE_CLOSED


def test_headline_stopped_after_5_minutes(tmp_path: Path) -> None:
    """A stale observation (older than 5 minutes) == stopped.

    Boundary test: NOW - 300s = still running; NOW - 301s = stopped.
    Pins the exact staleness threshold against regression.
    """
    health = _running_health(NOW).model_copy(update={"supervisor_pid": None})
    _write_json(tmp_path / "health.json", health)
    _write_json(tmp_path / "latest.json", _running_latest(NOW))
    # Exactly at the 5-minute boundary, still "running" (off-by-one oracle).
    boundary = read_status_headline("kaplansky", tmp_path, now=NOW + 300.0)
    assert boundary.state == "running"
    # One second past the boundary, "stopped".
    past = read_status_headline("kaplansky", tmp_path, now=NOW + 301.0)
    assert past.state == "terminal-stop"


def test_headline_stopped_when_supervisor_pid_is_dead(tmp_path: Path) -> None:
    """State files say running, but the supervisor PID is dead.

    The PID liveness check runs BEFORE the other classifiers so
    operators don't chase ghost "degraded" issues. Mutation-test
    oracle: dropping the `os.kill(pid, 0)` check would let stale
    state hide a crashed supervisor.
    """
    health = _running_health(NOW).model_copy(
        update={
            "supervisor_pid": 2_000_000_000,  # guaranteed-dead PID
            "degraded": ["source_unavailable"],  # would otherwise say "degraded"
        }
    )
    _write_json(tmp_path / "health.json", health)
    _write_json(tmp_path / "latest.json", _running_latest(NOW))
    h = read_status_headline("kaplansky", tmp_path, now=NOW)
    assert h.state is ProgramState.TERMINAL_STOP


def test_headline_no_supervisor_missing_dir(tmp_path: Path) -> None:
    h = read_status_headline("kaplansky", tmp_path / "does-not-exist", now=NOW)
    assert h.state is ProgramState.NO_SUPERVISOR
    assert h.last_action == ""


def test_headline_no_supervisor_malformed(tmp_path: Path) -> None:
    (tmp_path / "health.json").write_text("not json")
    (tmp_path / "latest.json").write_text("{also not")
    h = read_status_headline("kaplansky", tmp_path, now=NOW)
    assert h.state is ProgramState.NO_SUPERVISOR


def test_format_headline_running() -> None:
    out = format_headline(
        StatusHeadline(
            program="kaplansky",
            state=ProgramState.RUNNING,
            uptime_seconds=3725.0,  # 1h2m5s
            last_action="completed (attempt #3)",
        )
    )
    assert out == "kaplansky: running (1h2m) \u2014 last: completed (attempt #3)"


def test_format_headline_short_uptime() -> None:
    out = format_headline(
        StatusHeadline(
            program="kaplansky",
            state=ProgramState.RUNNING,
            uptime_seconds=40.0,
            last_action="",
        )
    )
    assert out == "kaplansky: running (40s)"


def test_format_headline_no_uptime() -> None:
    out = format_headline(
        StatusHeadline(
            program="kaplansky",
            state=ProgramState.NO_SUPERVISOR,
            uptime_seconds=0.0,
            last_action="",
        )
    )
    assert out == "kaplansky: no-supervisor"


# ---------------------------------------------------------------------------
# New states (autonomous-research brief Section E visibility)
# ---------------------------------------------------------------------------


def test_headline_rate_deferred(tmp_path: Path) -> None:
    """A positive ``next_eligible_unix`` is classified as RATE_DEFERRED.

    The deadline persists on the headline so the operator can
    read "when will the supervisor re-ask" without parsing
    the audit log or the rate-limit ledger.
    """
    health = _running_health(NOW).model_copy(
        update={
            "next_eligible_unix": NOW + 3600.0,
            "source_paused": False,
            "stopped": False,
        }
    )
    _write_json(tmp_path / "health.json", health)
    _write_json(tmp_path / "latest.json", _running_latest(NOW))
    h = read_status_headline("kaplansky", tmp_path, now=NOW)
    assert h.state is ProgramState.RATE_DEFERRED
    assert h.wake_unix == NOW + 3600.0
    assert h.wake_trigger == "rate_defer"


def test_headline_source_wait(tmp_path: Path) -> None:
    """A source Wait is classified as SOURCE_WAIT.

    The ``wait_next_ask_unix`` from the supervisor's source
    snapshot becomes the headline's ``wake_unix``; the wake
    trigger is ``source_wait``.
    """
    health = _running_health(NOW).model_copy(
        update={
            "next_eligible_unix": 0.0,
            "source_paused": False,
            "stopped": False,
            "source": {
                "last_kind": "wait",
                "paused": False,
                "wait_next_ask_unix": NOW + 60.0,
                "wait_wake_on_move": True,
            },
        }
    )
    _write_json(tmp_path / "health.json", health)
    _write_json(tmp_path / "latest.json", _running_latest(NOW))
    h = read_status_headline("kaplansky", tmp_path, now=NOW)
    assert h.state is ProgramState.SOURCE_WAIT
    assert h.wake_unix == NOW + 60.0
    assert h.wake_trigger == "source_wait"


def test_headline_operator_paused(tmp_path: Path) -> None:
    """A capability-gated OperatorRequired pause is OPERATOR_PAUSED."""
    health = _running_health(NOW).model_copy(
        update={
            "next_eligible_unix": 0.0,
            "source_paused": True,
            "stopped": False,
        }
    )
    _write_json(tmp_path / "health.json", health)
    _write_json(tmp_path / "latest.json", _running_latest(NOW))
    h = read_status_headline("kaplansky", tmp_path, now=NOW)
    assert h.state is ProgramState.OPERATOR_PAUSED


def test_headline_terminal_stop_intentional(tmp_path: Path) -> None:
    """``health.stopped = True`` (intentional stop) is TERMINAL_STOP,
    not STOPPED (the legacy dead-supervisor state)."""
    health = _running_health(NOW).model_copy(
        update={
            "next_eligible_unix": 0.0,
            "source_paused": False,
            "stopped": True,
        }
    )
    _write_json(tmp_path / "health.json", health)
    _write_json(tmp_path / "latest.json", _running_latest(NOW))
    h = read_status_headline("kaplansky", tmp_path, now=NOW)
    assert h.state is ProgramState.TERMINAL_STOP


def test_headline_last_completed_cycle(tmp_path: Path) -> None:
    """The headline carries the wall-clock time of the last
    completed cycle so the operator can read progress at a
    glance.
    """
    cycle_unix = NOW - 60.0
    health = _running_health(NOW).model_copy(
        update={
            "next_eligible_unix": 0.0,
            "source_paused": False,
            "stopped": False,
        }
    )
    health.execution.outcome_unix = cycle_unix
    _write_json(tmp_path / "health.json", health)
    _write_json(tmp_path / "latest.json", _running_latest(NOW))
    h = read_status_headline("kaplansky", tmp_path, now=NOW)
    assert h.last_completed_cycle_unix == cycle_unix


def test_format_headline_includes_wake_when_deferred() -> None:
    """The headline renders the wake time + trigger when active."""
    h = StatusHeadline(
        program="kaplansky",
        state=ProgramState.RATE_DEFERRED,
        uptime_seconds=120.0,
        last_action="",
        wake_unix=NOW + 3600.0,
        wake_trigger="rate_defer",
        service_installed=False,
        last_completed_cycle_unix=0.0,
    )
    out = format_headline(h)
    assert "next ask:" in out
    assert "rate_defer" in out
