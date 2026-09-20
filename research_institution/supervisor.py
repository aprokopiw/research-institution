"""Pi-monitor supervisor lifecycle helpers.

The dispatcher's `research start` / `stop` / `restart` / `health`
verbs need a reliable "is the supervisor running?" check. The
pi-monitor design is intentionally lock-free: there's no
``state.lock`` file. Instead, ``pi-monitor status --config <path>``
returns JSON with a ``supervisor_pid`` field, and the canonical
"is it alive?" check is whether that PID responds to
``os.kill(pid, 0)`` (signal 0 = "existence probe", no actual signal
sent).

This module wraps that probe so the dispatcher's start command can:

  - refuse to spawn a duplicate supervisor (the postmortem B.1.2 case)
  - hand off to the existing supervisor if one is already up
  - report a stable view of state without parsing the supervisor's
    own state.json (which lives under the same dir as health.json)

All public functions are pure: they take an `Environment`-style
abstraction or a `Path`/`subprocess.run`-style runner, both
injectable from tests via ``tests/_fakes.py``.

Spec 014 (typed-contract consolidation): ``status_payload`` is
the typed :class:`pi_monitor.operator.supervisor_status.SupervisorStatusPayload`
re-exported here as :class:`SupervisorStatusPayload`. The
dispatcher imports the canonical Pydantic model so a drift in
pi-monitor's wire shape surfaces at every call site (the typed
parse fails fast) rather than as a silent dict-vs-typed drift
deep in a downstream consumer.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable

from pi_monitor.operator.supervisor_status import (
    SupervisorStatusPayload as _TypedSupervisorStatusPayload,
    parse_supervisor_status_payload as _parse_typed_status,
)
from research_institution.paths import pi_monitor_config_path

#: Re-export of :class:`pi_monitor.operator.supervisor_status.SupervisorStatusPayload`
#: so research-institution consumers import the canonical type from a
#: single name. Both sides see the same class identity; a drift in
#: pi-monitor's wire shape surfaces here as a class-identity change
#: that pyright flags at every import site.
SupervisorStatusPayload = _TypedSupervisorStatusPayload

__all__ = [
    "SupervisorState",
    "SupervisorStatusPayload",
    "probe_default_supervisor",
    "probe_supervisor",
]


@dataclass(frozen=True, slots=True)
class SupervisorState:
    """Snapshot of one pi-monitor supervisor's runtime state.

    `is_alive` is the truth: it is True iff the supervisor PID
    from `pi-monitor status --config` actually responds to
    `os.kill(pid, 0)`. `status_payload` is the typed view of
    `pi-monitor status` (the supervisor's own view of itself),
    or None if the status command failed. Callers branch on
    ``status_payload is None`` to detect a failed probe; the
    typed model exposes typed fields when the probe succeeded.
    """

    config_path: Path
    supervisor_pid: int
    worker_pid: int
    is_alive: bool
    status_payload: SupervisorStatusPayload | None = None


def _pid_alive(pid: int) -> bool:
    """Return True iff `os.kill(pid, 0)` succeeds.

    Signal 0 is a pure existence probe; no signal is delivered.
    EACCES (process exists but owned by another user) is treated
    as alive — the supervisor is running, the operator just
    shouldn't kill it.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def probe_supervisor(
    config_path: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> SupervisorState:
    """Probe the pi-monitor supervisor's state via `pi-monitor status`.

    Tolerant: missing binary, malformed JSON, missing fields, and
    dead supervisor all map to a sensible default state. The
    dispatcher's contract is "return a SupervisorState", not
    "raise on transient state corruption".

    `runner` is injectable so tests can substitute a FakeRunner
    without spawning real subprocesses.
    """
    try:
        completed = runner(
            ["pi-monitor", "status", "--config", str(config_path)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return SupervisorState(
            config_path=config_path,
            supervisor_pid=0,
            worker_pid=0,
            is_alive=False,
            status_payload=None,
        )
    if completed.returncode != 0 or not completed.stdout.strip():
        return SupervisorState(
            config_path=config_path,
            supervisor_pid=0,
            worker_pid=0,
            is_alive=False,
            status_payload=None,
        )
    try:
        raw_payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return SupervisorState(
            config_path=config_path,
            supervisor_pid=0,
            worker_pid=0,
            is_alive=False,
            status_payload=None,
        )
    # Spec 014: typed-contract consolidation. Parse the raw dict
    # through the canonical Pydantic model so the dispatcher sees
    # a strict shape. ``extra="allow"`` preserves any forward-
    # compatible field pi-monitor may add; a malformed field
    # surfaces here as a ValidationError that we coerce to a
    # clean "no data" state so the dispatcher's hot path is
    # never crashed by a supervisor wire drift.
    try:
        typed_payload = _parse_typed_status(raw_payload)
    except Exception:
        return SupervisorState(
            config_path=config_path,
            supervisor_pid=0,
            worker_pid=0,
            is_alive=False,
            status_payload=None,
        )
    supervisor_pid = int(typed_payload.supervisor_pid or 0)
    worker_pid = int(typed_payload.worker_pid or 0)
    return SupervisorState(
        config_path=config_path,
        supervisor_pid=supervisor_pid,
        worker_pid=worker_pid,
        is_alive=_pid_alive(supervisor_pid),
        status_payload=typed_payload,
    )


def probe_default_supervisor(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> SupervisorState:
    """Probe the supervisor using the dispatcher's configured config path.

    Convenience wrapper that resolves the config via
    `paths.pi_monitor_config_path()` (which honors
    `MATHLINT_PI_MONITOR_CONFIG`).
    """
    return probe_supervisor(pi_monitor_config_path(), runner=runner)


__all__ = [
    "SupervisorState",
    "probe_default_supervisor",
    "probe_supervisor",
]
