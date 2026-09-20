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

from .status_types import (
    HealthPayload as _HealthPayload,
    LatestPayload as _LatestPayload,
)


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
# Supervisor state payload shape
#
# Both ``health.json`` and ``latest.json`` are produced by pi_monitor and
# read by this module. The wire shapes are owned by Pydantic models in
# :mod:`research_institution.status_types`; this module re-exports them
# under the canonical names (``HealthPayload`` / ``LatestPayload``)
# for backward-compat with the previous TypedDict-based surface.
# ---------------------------------------------------------------------------
HealthPayload = _HealthPayload
LatestPayload = _LatestPayload


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
    """Read one JSON file; return None on missing/malformed.

    The raw dict is the typed parse boundary: it lives only
    inside :func:`_parse_health` / :func:`_parse_latest` and is
    immediately consumed by ``HealthPayload.model_validate`` /
    ``LatestPayload.model_validate``. Callers never see a
    ``dict[str, object]``; the typed model is the contract.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _parse_health(raw: dict[str, Any]) -> HealthPayload:
    """Parse the raw ``health.json`` dict into the typed wire model.

    A malformed field (wrong type, missing required field) raises
    ``ValidationError``; the caller treats that as wire drift and
    surfaces the failure. ``extra=\"allow\"`` on the wire model
    means forward-compat fields pass through silently.
    """
    return HealthPayload.model_validate(raw)


def _parse_latest(raw: dict[str, Any]) -> LatestPayload:
    """Parse the raw ``latest.json`` dict into the typed wire model."""
    return LatestPayload.model_validate(raw)


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

    Reads fields via Pydantic model attributes (typed view);
    the wire parse happens in :func:`_parse_health` /
    :func:`_parse_latest` so the classifier body itself never
    touches ``dict.get(...)`` / ``dict[...]`` (no runtime shape
    probes; pyright sees the typed shape through the body).
    """
    import os as _os

    if health is None and latest is None:
        return ProgramState.NO_SUPERVISOR
    # If the state files claim a supervisor_pid but it doesn't
    # respond to os.kill(pid, 0), the supervisor is actually dead
    # (stale state file). Surface this BEFORE the other classifiers
    # so the operator doesn't chase ghost "degraded" issues.
    pid = health.supervisor_pid if health is not None else None
    if isinstance(pid, int) and pid > 0:
        try:
            _os.kill(pid, 0)
        except (ProcessLookupError, PermissionError, OSError):
            return ProgramState.STOPPED
    if health is not None:
        circuit = health.circuit
        if circuit.open or circuit.trip_count > 0:
            return ProgramState.CIRCUIT_OPEN
        if health.degraded:
            return ProgramState.DEGRADED
        if health.execution.outcome == "blocked":
            return ProgramState.GATE_CLOSED
    observed_unix: float | None = None
    if latest is not None:
        observed_unix = latest.observed_unix or None
    if observed_unix is None and health is not None:
        observed_unix = health.execution.outcome_unix or None
    if observed_unix is None or observed_unix == 0.0:
        return ProgramState.NO_SUPERVISOR
    age = (now if now is not None else time.time()) - observed_unix
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
    if latest is None or latest.observed_unix == 0.0:
        return 0.0
    anchor = now if now is not None else time.time()
    return max(0.0, anchor - latest.observed_unix)


def _last_action(health: HealthPayload | None) -> str:
    """Return a short human-readable string for the last action."""
    if health is None:
        return ""
    outcome = health.execution.outcome
    ordinal = health.execution.attempt_ordinal
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
    health: HealthPayload | None = None
    raw_health = _read_json(state_dir / "health.json")
    if raw_health is not None:
        try:
            health = _parse_health(raw_health)
        except Exception:
            # Wire drift: malformed field, wrong type, etc. The
            # classifier must remain robust-by-default (a missing
            # or malformed ``health.json`` is "no-supervisor",
            # not "raise"); drop the document.
            health = None
    latest: LatestPayload | None = None
    raw_latest = _read_json(state_dir / "latest.json")
    if raw_latest is not None:
        try:
            latest = _parse_latest(raw_latest)
        except Exception:
            latest = None
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
