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

#: Outcome vocabulary is owned by pi_monitor's runtime layer (INV-022).
#: We re-export the relevant constants so the institution's headline
#: classifier has a single source of truth — no string literals that
#: happen to equal the canonical value at the wire.
from pi_monitor.runtime.worker_outcomes import OUTCOME_BLOCKED
from typing import Any

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

    SERVICE_INSTALLED = "service-installed"
    RUNNING = "running"
    RATE_DEFERRED = "rate-deferred"
    SOURCE_WAIT = "source-wait"
    OPERATOR_PAUSED = "operator-paused"
    TERMINAL_STOP = "terminal-stop"
    CIRCUIT_OPEN = "circuit-open"
    GATE_CLOSED = "gate-closed"
    DEGRADED = "degraded"
    STOPPED = "stopped"
    NO_SUPERVISOR = "no-supervisor"


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

    `wake_unix` is the wall-clock time the supervisor will next
    ask the source (the rate-defer deadline under
    ``wait_until_eligible``, or the wait policy's next-ask
    time). ``0.0`` when no defer / wait is active.

    `wake_trigger` names the wake source so the operator can
    read ``state`` to understand *when* + *why* the next ask
    will happen (``rate_defer`` / ``source_wait`` /
    ``poll_backstop`` / ``backoff``). Empty when no defer is
    active.

    `service_installed` is True iff the LaunchAgent plist is
    on disk under ``~/Library/LaunchAgents/<label>.plist``.
    The classifier reports ``SERVICE_INSTALLED`` /
    ``NO_SUPERVISOR`` based on this flag combined with the
    supervisor liveness probe.

    `last_completed_cycle_unix` is the wall-clock time of the
    last completed research cycle (a finalized attempt with
    a recorded outcome_unix). ``0.0`` when no cycle has
    completed yet.
    """

    program: str
    state: ProgramState
    uptime_seconds: float
    last_action: str
    wake_unix: float = 0.0
    wake_trigger: str = ""
    service_installed: bool = False
    last_completed_cycle_unix: float = 0.0


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
            return ProgramState.TERMINAL_STOP
    if health is not None:
        circuit = health.circuit
        if circuit.open or circuit.trip_count > 0:
            return ProgramState.CIRCUIT_OPEN
        if health.degraded:
            return ProgramState.DEGRADED
        if health.execution.outcome == OUTCOME_BLOCKED:
            return ProgramState.GATE_CLOSED
        # Operator-pause wins over run/wait: a paused source
        # stays paused until the operator control-channel
        # ``resume`` clears it (INV-021 surface).
        if health.source_paused:
            return ProgramState.OPERATOR_PAUSED
        # Intentional terminal stop (``state.stopped=True``) is
        # distinct from a dead supervisor: the operator stopped
        # it on purpose (or the source requested Stop); restart
        # is operator-initiated.
        if health.stopped:
            return ProgramState.TERMINAL_STOP
        # Timed rate-defer (under ``wait_until_eligible``) is
        # the new state the brief introduces: the supervisor is
        # alive but holding the next-ask at the rolling-window
        # deadline. The deadline itself is read from
        # ``health.next_eligible_unix`` (introduced in
        # @INV-025 / @ADR-0026).
        next_eligible = getattr(health, "next_eligible_unix", 0.0) or 0.0
        if next_eligible > 0.0:
            return ProgramState.RATE_DEFERRED
        # Normal source wait: the source returned Wait and the
        # supervisor is honoring ``wait_next_ask_unix``.
        if health.source.last_kind == "wait":
            return ProgramState.SOURCE_WAIT
    observed_unix: float | None = None
    if latest is not None:
        observed_unix = latest.observed_unix or None
    if observed_unix is None and health is not None:
        observed_unix = health.execution.outcome_unix or None
    if observed_unix is None or observed_unix == 0.0:
        return ProgramState.NO_SUPERVISOR
    age = (now if now is not None else time.time()) - observed_unix
    if age > 300:  # 5 minutes
        return ProgramState.TERMINAL_STOP
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
    # The JSON boundary lives at _read_json. The typed parse is
    # \`_parse_health\` / \`_parse_latest\` (Pydantic model_validate);
    # a malformed wire document is dropped (the classifier must remain
    # robust-by-default — missing or malformed health.json is "no
    # supervisor", not "raise on transient state corruption").
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
        wake_unix=_wake_unix(health),
        wake_trigger=_wake_trigger(health),
        service_installed=_service_installed(program),
        last_completed_cycle_unix=_last_completed_cycle_unix(health),
    )


def _wake_unix(health: HealthPayload | None) -> float:
    """Wall-clock time the supervisor will next ask the source.

    Prefers ``next_eligible_unix`` (rate-defer deadline) when
    positive; falls back to ``source.wait_next_ask_unix``
    (wait policy). ``0.0`` when no defer / wait is active.
    """
    if health is None:
        return 0.0
    eligible = health.next_eligible_unix or 0.0
    if eligible > 0.0:
        return eligible
    return health.source.wait_next_ask_unix or 0.0


def _wake_trigger(health: HealthPayload | None) -> str:
    """Name the wake source so the operator can read state.

    ``rate_defer`` for a rate-window trip under
    ``wait_until_eligible``; ``source_wait`` for a normal
    source Wait; ``poll_backstop`` for the no-wake poll loop.
    Empty when no defer / wait is active.
    """
    if health is None:
        return ""
    if (health.next_eligible_unix or 0.0) > 0.0:
        return "rate_defer"
    if health.source.last_kind == "wait":
        return "source_wait"
    return "poll_backstop"


def _service_installed(program: str) -> bool:
    """True iff the LaunchAgent plist is on disk.

    Pure path check: ``~/Library/LaunchAgents/<label>.plist``
    exists. The label is the program-owned
    ``com.local.research-institution.<program>`` so two
    programs never share a plist (INV-005).
    """
    from research_institution.cli import _PROGRAM_LAUNCHD_LABEL

    label = _PROGRAM_LAUNCHD_LABEL.get(program)
    if label is None:
        return False
    return (Path.home() / "Library" / "LaunchAgents" / f"{label}.plist").is_file()


def _last_completed_cycle_unix(health: HealthPayload | None) -> float:
    """Wall-clock time of the last completed research cycle.

    A "completed cycle" is a finalized attempt with a
    recorded ``execution.outcome_unix``. ``0.0`` when no
    cycle has completed yet.
    """
    if health is None:
        return 0.0
    return health.execution.outcome_unix or 0.0


def format_headline(headline: StatusHeadline) -> str:
    """Format one StatusHeadline as a single-line string for `typer.echo`.

    The new fields the brief introduces are rendered when set:

      * ``service-installed`` flag is shown as a prefix
        (``installed: <label>``) when the plist is on disk,
        so the operator can see deployment + liveness at a
        glance.
      * ``wake_unix`` is rendered as
        ``next ask: <unix> (<delta from now>, trigger=<wake_trigger>)``
        whenever a defer or wait is active.
      * ``last_completed_cycle_unix`` is rendered as
        ``last cycle: <unix> (<delta from now>)`` when
        non-zero.
    """
    parts = [f"{headline.program}: {headline.state}"]
    if headline.service_installed:
        from research_institution.cli import _PROGRAM_LAUNCHD_LABEL

        label = _PROGRAM_LAUNCHD_LABEL.get(headline.program, "")
        if label:
            parts.append(f"[installed: {label}]")
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
        parts.append(f"— last: {headline.last_action}")
    if headline.wake_unix > 0.0:
        from datetime import datetime as _dt

        when = _dt.fromtimestamp(headline.wake_unix).strftime("%Y-%m-%d %H:%M:%S")
        parts.append(
            f"[next ask: {when} (trigger={headline.wake_trigger or 'poll_backstop'})]"
        )
    if headline.last_completed_cycle_unix > 0.0:
        from datetime import datetime as _dt

        when = _dt.fromtimestamp(
            headline.last_completed_cycle_unix
        ).strftime("%Y-%m-%d %H:%M:%S")
        parts.append(f"[last cycle: {when}]")
    return " ".join(parts)


__all__ = ["StatusHeadline", "format_headline", "read_status_headline"]
