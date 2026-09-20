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
from typing import Any, Literal, TypedDict, cast


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


# ---------------------------------------------------------------------------
# Supervisor state payload shape (TypedDict)
#
# Both ``health.json`` and ``latest.json`` are produced by pi_monitor and
# read by this module. They share a common ``execution`` sub-record;
# ``health.json`` adds ``circuit`` + ``degraded`` + ``supervisor_pid``.
# These TypedDicts replace the previous ``dict[str, Any]`` parameters.
# ---------------------------------------------------------------------------


class ExecutionPayload(TypedDict, total=False):
    """Subset of the supervisor execution record shared by both files."""

    outcome: str
    attempt_ordinal: int
    outcome_unix: float
    active_key: str


class HealthPayload(TypedDict, total=False):
    """Wire shape of ``health.json`` as written by pi_monitor.

    All fields are optional because the supervisor emits incrementally.
    ``supervisor_pid`` may be ``None`` when the test fixture wants to
    skip the liveness probe without setting a real PID.
    """

    supervisor_pid: int | None
    audit: dict[str, object]
    circuit: dict[str, object]
    degraded: list[object]
    execution: ExecutionPayload


class LatestPayload(TypedDict, total=False):
    """Wire shape of ``latest.json`` as written by pi_monitor."""

    observed_unix: float
    execution: ExecutionPayload


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


def _truthy_int(value: object) -> int:
    """Coerce an arbitrary JSON value to a non-negative int, defaulting to 0.

    The supervisor's wire payloads treat missing keys as 0. Anything
    that isn't a JSON number is reported as 0 rather than raising —
    the classifier is robust-by-default to wire drift.
    """
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def _classify(
    health: HealthPayload | None,
    latest: LatestPayload | None,
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
    pid_raw = health.get("supervisor_pid")
    pid: int = pid_raw if isinstance(pid_raw, int) else 0
    if pid > 0:
        try:
            _os.kill(pid, 0)
        except (ProcessLookupError, PermissionError, OSError):
            return ProgramState.STOPPED
    circuit: dict[str, object] = health.get("circuit") or {}
    if circuit.get("open") or _truthy_int(circuit.get("trip_count", 0)) > 0:
        return ProgramState.CIRCUIT_OPEN
    degraded: list[object] = list(health.get("degraded") or [])
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


def _uptime_seconds(latest: LatestPayload | None, *, now: float | None = None) -> float:
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


def _last_action(health: HealthPayload | None) -> str:
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
    # The JSON boundary lives at _read_json. The TypedDict cast here is
    # honest because the pi_monitor writer produces a structurally
    # compatible dict; any drift surfaces at runtime as KeyError/TypeError
    # in _classify, not as a silent type-system lie.
    health = cast("HealthPayload | None", _read_json(state_dir / "health.json"))
    latest = cast("LatestPayload | None", _read_json(state_dir / "latest.json"))
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
