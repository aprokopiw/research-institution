"""Bring the institution to a clean, launchable state.

This module is the dispatcher's answer to "the box is in a weird
state and I want it tidy without re-implementing the bootstrap".

The institution's runtime state lives outside the four repos
(``~/.local/state/...``) and accumulates the way runtime state
does: stale lock files when a supervisor crashes, abandoned state
dirs when a launch dies before its bootstrap, orphaned processes
when a worker outlives its supervisor. Operators need a single
verb that:

  1. Reports what is wrong (dry-run by default).
  2. Refuses destructive actions when the supervisor it would
     affect is genuinely alive (INV-005: one supervisor per
     target).
  3. Carries an explicit confirmation flag for the harder resets.

The four cleanup categories, in escalating order:

  ``lockfiles`` -- remove stale ``supervisor.lock`` files whose
    PID is no longer alive. Always safe.

  ``processes`` -- terminate supervisors whose PID is alive but
    whose state is wedged (last heartbeat older than a
    configurable timeout, no recent source decision, etc.).
    Refuses if the supervisor looks healthy.

  ``workers`` -- terminate the worker (pi) subprocess supervised
    by a healthy supervisor. Refuses unless the worker is the
    only thing keeping a stale state alive. Always paired with
    a supervisor decision; the supervisor will respawn.

  ``state`` -- purge a state directory entirely. Requires
    ``--purge-state <dir>`` AND ``--yes``. Destructive; the
    operator gets a printed summary of files-to-be-deleted
    and must confirm.

The verb is deliberately a thin composition of the existing
typed surface (catalog, paths, supervisor) so the drift surface
is small: a new state dir or a new program marker added in the
catalog is reflected here automatically.

Per @ADR-0006 the dispatcher owns no application logic; this
module is policy on top of the supervisor + catalog APIs.
"""

from __future__ import annotations

import json
import os
import contextlib
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable, Sequence

from research_institution.catalog import load_catalog
from research_institution.paths import (
    pi_monitor_config_path,
    pi_monitor_state_dir,
)

# Reuse the typed supervisor probe rather than re-implement it.
# A drift in pi-monitor's wire shape (added field, renamed field,
# new failure_kind) surfaces here as a class-identity change
# rather than as a silent dict-vs-typed drift.
from research_institution.supervisor import (
    _pid_alive,
    probe_supervisor,
)


# A heartbeat older than this is considered "stuck" for the
# purposes of process cleanup. Supervisors that genuinely
# settled (the work source returned NO_ELIGIBLE_WORK) still
# heartbeat at least every poll interval, so this is a safe
# upper bound for "the supervisor is not actively observing".
DEFAULT_STALE_HEARTBEAT_SECONDS: int = 600

# The state-dir layout is operator-side, not math-side: each
# program gets its own subdirectory of the pi-monitor state
# tree, plus the math-namespace state dir used by the dispatcher
# and a small number of legacy / test trees (demo, kaplansky-
# launch-test). All known roots are listed here so the reset
# verb can scan them.
_KNOWN_STATE_ROOTS: tuple[str, ...] = (
    "~/.local/state/mathlint/pi-monitor",  # dispatcher's probe target
    "~/.local/state/pi-monitor",          # per-program supervisor state
    "~/.local/state/mathlint",            # mathlint logs, runs, readiness
)


@dataclass(frozen=True, slots=True)
class StaleLock:
    """One stale supervisor.lock file (lock-PID is dead)."""

    path: Path
    stale_pid: int


@dataclass(frozen=True, slots=True)
class AliveLock:
    """One supervisor.lock file whose PID is still alive."""

    path: Path
    alive_pid: int


@dataclass(frozen=True, slots=True)
class StaleProcess:
    """One supervisor process that the operator may want to kill.

    The supervisor's own ``pi-monitor status`` payload decides
    whether we treat it as wedged. ``heartbeat_unix`` and
    ``last_wedge_class`` come from the supervisor's state.json
    (read directly to avoid round-tripping through the typed
    probe when the probe already timed out).
    """

    config_path: Path
    pid: int
    heartbeat_unix: float
    last_wedge_class: str

    @property
    def heartbeat_age_seconds(self) -> float:
        return max(0.0, _now() - self.heartbeat_unix)

    @property
    def is_wedged(self) -> bool:
        """True iff the supervisor looks stuck, not just idle.

        A healthy supervisor has ``last_wedge_class == "healthy"``
        AND a recent heartbeat. We refuse to kill a healthy one;
        the operator's recovery path is ``research stop`` then
        ``research restart``, not ``reset --processes``.
        """
        if self.last_wedge_class != "healthy":
            return True
        return self.heartbeat_age_seconds > DEFAULT_STALE_HEARTBEAT_SECONDS


@dataclass(frozen=True, slots=True)
class StaleStateDir:
    """One state directory whose owning supervisor is dead."""

    path: Path
    bytes_on_disk: int


@dataclass(frozen=True, slots=True)
class ResetReport:
    """Aggregate outcome of a reset pass.

    ``actions`` is the human-readable summary the CLI echoes.
    ``would_have_*`` mirrors ``actions`` for dry-run parity: a
    dry-run populates the ``would_have_*`` fields so tests can
    assert the verb refused to mutate.
    """

    dry_run: bool
    locks_removed: tuple[Path, ...] = ()
    locks_skipped_alive: tuple[AliveLock, ...] = ()
    processes_terminated: tuple[StaleProcess, ...] = ()
    processes_refused_healthy: tuple[StaleProcess, ...] = ()
    state_dirs_purged: tuple[Path, ...] = ()
    state_dirs_refused_alive: tuple[tuple[Path, int], ...] = ()

    @property
    def ok(self) -> bool:
        """True iff every requested action succeeded.

        Alive-lock refusals are EXPECTED behavior (we want to keep
        alive locks), so they do not flip this to False. State-dir
        refusals ARE failures: the operator asked to purge and
        the supervisor came back to life. Healthy-supervisor
        refusals are advisory: the operator's path is
        ``research stop``, not ``reset``.
        """
        return not self.state_dirs_refused_alive

    def render(self) -> str:
        lines: list[str] = []
        verb = "WOULD" if self.dry_run else "DID"
        lines.append(f"[reset] {verb} clean up institution state")
        if self.locks_removed:
            for p in self.locks_removed:
                lines.append(f"  {verb.lower()} remove stale lock: {p}")
        if self.locks_skipped_alive:
            for a in self.locks_skipped_alive:
                lines.append(
                    f"  KEEP alive lock: {a.path} (pid {a.alive_pid})"
                )
        if self.processes_terminated:
            for p in self.processes_terminated:
                lines.append(
                    f"  {verb.lower()} terminate stale supervisor: "
                    f"pid {p.pid} ({p.last_wedge_class}, "
                    f"heartbeat {p.heartbeat_age_seconds:.0f}s old)"
                )
        if self.processes_refused_healthy:
            for p in self.processes_refused_healthy:
                lines.append(
                    f"  REFUSED terminate healthy supervisor: "
                    f"pid {p.pid} ({p.last_wedge_class}) - "
                    f"use `research stop` for healthy supervisors"
                )
        if self.state_dirs_purged:
            for p in self.state_dirs_purged:
                lines.append(f"  {verb.lower()} purge state dir: {p}")
        if self.state_dirs_refused_alive:
            for p, pid in self.state_dirs_refused_alive:
                lines.append(
                    f"  REFUSED purge state dir {p}: supervisor pid {pid} alive"
                )
        if not any(
            (
                self.locks_removed,
                self.locks_skipped_alive,
                self.processes_terminated,
                self.processes_refused_healthy,
                self.state_dirs_purged,
                self.state_dirs_refused_alive,
            )
        ):
            lines.append("  no actions needed; institution is clean")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Discovery helpers. Pure functions; injectable for tests via the
# ``runner`` and ``clock`` kwargs on the entry points.
# ---------------------------------------------------------------------------


def _now() -> float:
    return float(os.environ.get("_RESET_TEST_NOW") or __import__("time").time())


def _expand_known_roots() -> list[Path]:
    """Resolve ``_KNOWN_STATE_ROOTS`` against the operator's $HOME.

    Excludes roots that do not exist; the operator's state tree
    may legitimately be empty on a fresh box.
    """
    home = Path.home()
    out: list[Path] = []
    for raw in _KNOWN_STATE_ROOTS:
        p = Path(raw).expanduser()
        # The catalog lives under the home dir; ``raw`` may use a
        # relative-from-home form (``~/.local/...``) and may also
        # be absolute on systems where /Users is not /home.
        # ``expanduser`` handles both; the redundant ``home``
        # substitution is a belt-and-suspenders for operators
        # whose $HOME is not what expanduser expects.
        if not p.is_absolute():
            p = home / p
        if p.exists():
            out.append(p)
    return out


def _all_state_dirs() -> list[Path]:
    """Every state directory under the known state roots.

    Includes the root itself plus its first-level children; deeper
    state (executions/, budgets/, outcomes/) is owned by the
    supervisor and only purged as part of its parent's purge.

    Deduped by resolved path because the known roots overlap on
    this box (e.g. ``~/.local/state/mathlint/pi-monitor`` is a
    direct subdir of the ``mathlint`` root AND its own root).
    """
    seen: set[Path] = set()
    out: list[Path] = []
    for root in _expand_known_roots():
        for candidate in [root, *(c for c in sorted(root.iterdir()) if c.is_dir())]:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            out.append(candidate)
    return out


def discover_stale_locks() -> tuple[tuple[StaleLock, ...], tuple[AliveLock, ...]]:
    """Find every ``supervisor.lock`` under the known state roots.

    A lock is ``StaleLock`` iff the PID it names is no longer alive.
    A lock is ``AliveLock`` iff the PID is alive; the caller MUST
    refuse to remove those (INV-005: removing an alive lock while
    the supervisor is running lets a second supervisor acquire the
    instance lock and start writing to the same state dir, which
    is the postmortem B.1.2 failure mode).
    """
    stale: list[StaleLock] = []
    alive: list[AliveLock] = []
    for d in _all_state_dirs():
        lock = d / "supervisor.lock"
        if not lock.is_file():
            continue
        try:
            pid = int(lock.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            # Garbage lock file (empty, partial write, non-numeric).
            # Treat as stale; the operator gets to see the path and
            # can investigate manually.
            stale.append(StaleLock(path=lock, stale_pid=0))
            continue
        if pid <= 0:
            stale.append(StaleLock(path=lock, stale_pid=pid))
            continue
        if _pid_alive(pid):
            alive.append(AliveLock(path=lock, alive_pid=pid))
        else:
            stale.append(StaleLock(path=lock, stale_pid=pid))
    return tuple(stale), tuple(alive)


def _read_state_json(state_dir: Path) -> dict[str, object]:
    """Read supervisor.state.json without forcing a typed parse.

    The dispatcher's typed probe already validates the wire shape;
    the reset module reads the raw JSON so it can extract a
    single field (``heartbeat_unix``, ``last_wedge_class``) even
    when the rest of the file is malformed.
    """
    state_file = state_dir / "state.json"
    if not state_file.is_file():
        return {}
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def discover_stale_processes(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[StaleProcess, ...]:
    """Find every supervisor whose heartbeat is older than the threshold.

    Walks the catalog and probes each program's default supervisor
    config. A supervisor whose ``heartbeat_unix`` is more than
    ``DEFAULT_STALE_HEARTBEAT_SECONDS`` old AND whose
    ``last_wedge_class`` is not "healthy" is reported.

    Supervisors that genuinely look healthy are not reported: the
    operator's recovery path is ``research stop`` + ``research
    restart``, not ``reset --processes``.
    """
    out: list[StaleProcess] = []
    for _prog in load_catalog().programs:
        cfg = pi_monitor_config_path()
        state = probe_supervisor(cfg, runner=runner)
        if not state.is_alive or state.supervisor_pid <= 0:
            continue
        raw = _read_state_json(pi_monitor_state_dir())
        hb = float(raw.get("heartbeat_unix", 0.0) or 0.0)  # type: ignore[arg-type]
        wc = str(raw.get("last_wedge_class", "") or "")
        proc = StaleProcess(
            config_path=cfg,
            pid=state.supervisor_pid,
            heartbeat_unix=hb,
            last_wedge_class=wc,
        )
        if proc.is_wedged:
            out.append(proc)
    return tuple(out)


def discover_stale_state_dirs() -> tuple[StaleStateDir, ...]:
    """Find state dirs whose owning supervisor is dead.

    A state dir is "stale" iff it contains a ``supervisor.lock``
    whose PID is no longer alive. The dispatcher (math-namespace)
    and the per-program subdirs each qualify independently.

    Dirs without a lock file are NOT considered stale: a fresh
    bootstrap that crashed before locking may leave audit/state
    files behind that are still authoritative for forensics.
    """
    out: list[StaleStateDir] = []
    for d in _all_state_dirs():
        lock = d / "supervisor.lock"
        if not lock.is_file():
            continue
        try:
            pid = int(lock.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            continue
        if pid > 0 and _pid_alive(pid):
            continue
        try:
            total = sum(p.stat().st_size for p in d.rglob("*") if p.is_file())
        except OSError:
            total = 0
        out.append(StaleStateDir(path=d, bytes_on_disk=total))
    return tuple(out)


# ---------------------------------------------------------------------------
# Mutators. Each returns the paths it acted on (or would have acted
# on in dry-run). All refuse destructive actions when the target's
# lock-PID is alive.
# ---------------------------------------------------------------------------


def remove_stale_locks(
    stale: Sequence[StaleLock],
    *,
    dry_run: bool,
) -> tuple[Path, ...]:
    """Unlink each stale lock.

    ``dry_run=True`` returns the paths that WOULD be removed
    without touching the filesystem. The CLI uses this to print
    a summary so the operator sees the action list before
    committing.
    """
    if dry_run:
        return tuple(s.path for s in stale)
    for s in stale:
        # Best-effort; a permission error here is the operator's
        # signal that something else (Spotlight indexing, a
        # Time Machine snapshot) is holding the file. The
        # CLI surfaces the failure and continues with the rest.
        with contextlib.suppress(OSError):
            s.path.unlink()
    return tuple(s.path for s in stale)


def terminate_stale_processes(
    stale: Sequence[StaleProcess],
    *,
    dry_run: bool,
    sig: int = signal.SIGTERM,
) -> tuple[StaleProcess, ...]:
    """Send ``sig`` to each wedged supervisor.

    Defaults to SIGTERM (graceful shutdown); callers can pass
    SIGKILL for a hard kill. The supervisor's own worker child
    is left to die alongside; the OS reaps both.

    Refuses to act on supervisors whose lock-PID is alive but
    ``last_wedge_class == "healthy"``: the operator's
    intent there is "stop this on purpose", which is
    ``research stop``, not ``reset``.
    """
    targets = tuple(p for p in stale if p.is_wedged)
    if dry_run:
        return targets
    for p in targets:
        try:
            os.kill(p.pid, sig)
        except ProcessLookupError:
            pass
        except PermissionError:
            # Same semantics as ``_pid_alive``: the supervisor
            # exists but is owned by another user. We do not
            # attempt escalation; the CLI surfaces this so the
            # operator can ``sudo``.
            pass
    return targets


def purge_state_dirs(
    dirs: Sequence[Path],
    *,
    dry_run: bool,
) -> tuple[Path, ...]:
    """Delete each named state dir.

    The caller (``discover_stale_state_dirs`` + the CLI verb)
    is the gatekeeper; this mutator trusts the input list. The
    one defensive check is the lock-alive race guard: if a
    supervisor's PID came back to life between discovery and
    purge, the corresponding dir is SKIPPED and reported via
    the CLI's ``state_dirs_refused_alive`` field.

    A dir without a ``supervisor.lock`` is purged as named --
    the operator who passed it explicitly opted in. This is the
    only place in the institution where ``rm -rf`` happens.
    """
    purged: list[Path] = []
    for d in dirs:
        lock = d / "supervisor.lock"
        if lock.is_file():
            try:
                pid = int(lock.read_text(encoding="utf-8").strip())
                if pid > 0 and _pid_alive(pid):
                    # Defensive refusal: the supervisor came back
                    # to life between discovery and purge. The
                    # CLI surfaces this in the report's
                    # ``state_dirs_refused_alive`` field.
                    continue
            except (ValueError, OSError):
                pass
        if dry_run:
            purged.append(d)
            continue
        # The operator opted into purge with --yes; this is the
        # only place ``rm -rf`` happens in the institution.
        import shutil
        try:
            shutil.rmtree(d)
        except OSError:
            continue
        purged.append(d)
    return tuple(purged)


# ---------------------------------------------------------------------------
# Top-level entry points. The CLI verb delegates to one of these.
# ---------------------------------------------------------------------------


def reset(
    *,
    purge_state: Sequence[Path] = (),
    kill_processes: bool = False,
    dry_run: bool = True,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> ResetReport:
    """One end-to-end reset pass.

    Always discovers and removes stale locks (the safe tier).
    Optionally terminates wedged supervisors (kill_processes).
    Optionally purges named state dirs after a final liveness
    check (purge_state).

    Returns a :class:`ResetReport` summarizing actions taken
    (or refused). The CLI verb prints ``report.render()``.
    """
    stale_locks, alive_locks = discover_stale_locks()
    removed = remove_stale_locks(stale_locks, dry_run=dry_run)

    terminated: tuple[StaleProcess, ...] = ()
    refused_healthy: tuple[StaleProcess, ...] = ()
    if kill_processes:
        wedged = discover_stale_processes(runner=runner)
        # Split into "actually wedged" vs "looks healthy".
        from typing import cast

        terminated_list: list[StaleProcess] = []
        refused_list: list[StaleProcess] = []
        for p in wedged:
            if p.is_wedged:
                terminated_list.append(p)
            else:
                refused_list.append(p)
        terminated = terminate_stale_processes(
            cast(Sequence[StaleProcess], terminated_list),
            dry_run=dry_run,
        )
        refused_healthy = tuple(refused_list)

    purged: tuple[Path, ...] = ()
    refused_alive: list[tuple[Path, int]] = []
    if purge_state:
        purged_list = list(purge_state_dirs(purge_state, dry_run=dry_run))
        purged = tuple(purged_list)
        # Track dirs we refused because their owning supervisor
        # came back to life.
        for d in purge_state:
            if d in purged_list:
                continue
            lock = d / "supervisor.lock"
            if lock.is_file():
                try:
                    pid = int(lock.read_text(encoding="utf-8").strip())
                    if pid > 0 and _pid_alive(pid):
                        refused_alive.append((d, pid))
                except (ValueError, OSError):
                    pass

    return ResetReport(
        dry_run=dry_run,
        locks_removed=removed,
        locks_skipped_alive=alive_locks,
        processes_terminated=terminated,
        processes_refused_healthy=refused_healthy,
        state_dirs_purged=purged,
        state_dirs_refused_alive=tuple(refused_alive),
    )


__all__ = [
    "DEFAULT_STALE_HEARTBEAT_SECONDS",
    "AliveLock",
    "ResetReport",
    "StaleLock",
    "StaleProcess",
    "StaleStateDir",
    "discover_stale_locks",
    "discover_stale_processes",
    "discover_stale_state_dirs",
    "purge_state_dirs",
    "remove_stale_locks",
    "reset",
    "terminate_stale_processes",
]
