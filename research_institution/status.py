"""One-line status headline for a supervised research program.

The dispatcher's `research status <program>` (B.5.1) returns a
single-line headline when called without --verbose. With --verbose
it delegates to `mathlint research-status` for the full output.

The headline is derived from the pi_monitor supervisor's runtime
state files (``health.json``, ``latest.json``) under
``~/.local/state/mathlint/pi-monitor/``. The headline grammar:

    <program>: <state> (<uptime>) \u2014 last: <action_summary>

The six :data:`ProgramState` values are closed; see the enum for
their meanings. The parser is pure (no subprocess, no I/O beyond
reading the state files). Tests use ``FakeEnvironment`` to inject
a temp state dir.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal


class ProgramState(StrEnum):
    """Closed vocabulary of supervisor program states.

    Each member is a :class:`enum.StrEnum` so equality against
    the wire string works without explicit ``.value`` access, and
    pyright strict checks exhaustiveness across match statements.
    The set is closed; a future contributor adding a new state
    must add a member here AND surface it in
    :func:`_classify`. Mirroring a string literal in tests is a
    CI-detectable smell \u2014 the enum catches it at edit time.
    """

    RUNNING = "running"
    CIRCUIT_OPEN = "circuit-open"
    GATE_CLOSED = "gate-closed"
    DEGRADED = "degraded"
    STOPPED = "stopped"
    NO_SUPERVISOR = "no-supervisor"


#: Closed literal alias for tests + downstream code that wants
#: to declare a state without importing the StrEnum.
ProgramStateLiteral = Literal[
    "running", "circuit-open", "gate-closed", "degraded", "stopped", "no-supervisor"
]


@dataclass(frozen=True, slots=True)
class StatusHeadline:
    """One-line summary of a program's supervisor state.

    `state` is one of the closed :class:`ProgramState` values.
    `uptime` is the elapsed seconds since the supervisor's first
    observation (or 0 if unknown). `last` is the last action
    summary string from the supervisor's `execution` block;
    empty if no action has been taken.
    """

    program: str
    state: ProgramState
    uptime_seconds: float
    last_action: str


def _read_json(path: Path) -> dict[str, Any] | None:
    """Read one JSON file; return None on missing/malformed."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _classify(
    health: dict[str, Any] | None,
    latest: dict[str, Any] | None,
    *,
    now: float | None = None,
) -> ProgramState:
    """Map the supervisor's state JSON to a canonical :class:`ProgramState`.

    `now` is the wall-clock anchor for the staleness check
    (`observed_unix + 300s`). Defaults to `time.time()`; tests
    inject a frozen `now` to keep assertions deterministic.
    """
    import os as _os

    if health is None and latest is None:
        return ProgramState.NO_SUPERVISOR
    health = health or {}
    latest = latest or {}
    # If the state files claim a supervisor_pid but it doesn't
    # respond to os.kill(pid, 0), the supervisor is actually dead
    # (stale state file). Surface this BEFORE the other classifiers
    # so the operator doesn't chase ghost "degraded" issues.
    pid = health.get("supervisor_pid") or 0
    if pid > 0:
        try:
            _os.kill(pid, 0)
        except (ProcessLookupError, PermissionError, OSError):
            return ProgramState.STOPPED
    circuit = health.get("circuit", {})
    if circuit.get("open") or (circuit.get("trip_count", 0) or 0) > 0:
        return ProgramState.CIRCUIT_OPEN
    degraded: list[object] = health.get("degraded") or []
    if degraded:
        return ProgramState.DEGRADED
    execution = health.get("execution", {})
    if execution.get("outcome") == "blocked":
        return ProgramState.GATE_CLOSED
    observed_unix = latest.get("observed_unix") or health.get("execution", {}).get("outcome_unix")
    if observed_unix is None:
        return ProgramState.NO_SUPERVISOR
    age = (now if now is not None else time.time()) - float(observed_unix)
    if age > 300:  # 5 minutes
        return ProgramState.STOPPED
    return ProgramState.RUNNING


def _uptime_seconds(latest: dict[str, Any] | None, *, now: float | None = None) -> float:
    """Return seconds elapsed since the supervisor's first observation.

    Uses `latest.observed_unix` (sample timestamp) as a proxy. For
    true uptime we'd need a separate `started_at_unix` field;
    until then, sample timestamp is the best signal we have.

    `now` is the wall-clock anchor; defaults to `time.time()` so
    production callers stay zero-arg.
    """
    if latest is None:
        return 0.0
    obs = latest.get("observed_unix")
    if obs is None:
        return 0.0
    anchor = now if now is not None else time.time()
    return max(0.0, anchor - float(obs))


def _last_action(health: dict[str, Any] | None) -> str:
    """Return a short human-readable string for the last action."""
    if health is None:
        return ""
    execution = health.get("execution", {})
    outcome = execution.get("outcome") or ""
    ordinal = execution.get("attempt_ordinal")
    if not outcome:
        return ""
    if ordinal:
        return f"{outcome} (attempt #{ordinal})"
    return outcome


def read_status_headline(
    program: str,
    state_dir: Path,
    *,
    now: float | None = None,
) -> StatusHeadline:
    """Read the supervisor state files and return a StatusHeadline.

    Public API. The CLI calls this; tests call this with a
    fixture-populated state_dir.

    Tolerant: missing files, malformed JSON, and absent fields all
    map to a sensible default state rather than raising. The
    dispatcher's contract is "one-line headline or 'unknown'", not
    "raise on transient state corruption".

    `now` is the wall-clock anchor used for staleness + uptime.
    Defaults to `time.time()`; tests inject a frozen `now` to
    pin staleness boundaries deterministically.
    """
    health = _read_json(state_dir / "health.json")
    latest = _read_json(state_dir / "latest.json")
    return StatusHeadline(
        program=program,
        state=_classify(health, latest, now=now),
        uptime_seconds=_uptime_seconds(latest, now=now),
        last_action=_last_action(health),
    )


def format_headline(headline: StatusHeadline) -> str:
    """Format one StatusHeadline as a single-line string for `typer.echo`."""
    parts = [f"{headline.program}: {headline.state}"]
    if headline.uptime_seconds > 0:
        # 1h21m shape; under 60s is just "<n>s".
        s = int(headline.uptime_seconds)
        if s < 60:
            parts.append(f"({s}s)")
        else:
            h, rem = divmod(s, 3600)
            m = rem // 60
            if h > 0:
                parts.append(f"({h}h{m}m)")
            else:
                parts.append(f"({m}m)")
    if headline.last_action:
        parts.append(f"\u2014 last: {headline.last_action}")
    return " ".join(parts)


__all__ = ["StatusHeadline", "format_headline", "read_status_headline"]
