"""Typer CLI: catalog-driven dispatcher over mathlint + pi_monitor.

Per @ADR-0006, every command is a thin subprocess wrapper around a
sibling-repo CLI. No data parsing. No persistence boundary crossings.

The one piece of application logic this CLI owns is the
architecture-review gate refusal in `research start` (B.1.2). The
gate verdict is read from `mathlint roadmap` output — a structured
text stream mathlint already produces. We parse ONE line
(`TASK KIND: ARCHITECTURE_REVIEW_REQUIRED`) and refuse to launch when
it appears. This is the smallest defensible refusal check that does
not require a cross-repo mathlint change.
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from research_institution.catalog import Program, load_catalog
from research_institution.dispatcher import MATHLINT_BIN
from research_institution.contracts import (
    ExitCode,
    GateVerdictStatus,
    TaskKind,
    gate_verdict_from_task_kind,
)
from research_institution.prime_directive import app as prime_directive_app
from research_institution.gates.verify_simulation.cli import main as verify_simulation_main
from research_institution.contracts.skill_template import render_skill
from research_institution.paths import (
    agent_skills_dir,
    catalog_path,
    green_gate_path,
    institution_dir,
    missing_credentials,
    pi_monitor_config_path,
    pi_monitor_repo,
    pi_monitor_start_script,
    pi_monitor_state_dir,
)
from research_institution.status import (
    format_headline,
    read_status_headline,
)
from research_institution.supervisor import (
    probe_default_supervisor,
)
from research_institution.health import (
    format_health,
    run_health,
)

app = typer.Typer(
    name="research",
    help="research-institution dispatcher: catalog-driven CLI over mathlint + pi_monitor.",
    no_args_is_help=True,
)


def _load() -> list[Program]:
    return load_catalog(catalog_path())


def _require_program(name: str) -> Program:
    for p in _load():
        if p.name == name:
            return p
    available = ", ".join(p.name for p in _load()) or "(none)"
    raise typer.BadParameter(f"unknown program {name!r}; available: {available}")


def _which_or_die(binary: str) -> str:
    path = shutil.which(binary)
    if path is None:
        raise typer.Exit(code=127)
    return path


# ---------------------------------------------------------------------------
# Architecture-review gate (B.1.2).
# ---------------------------------------------------------------------------
#
# Rationale: the dispatcher must refuse to launch while the gate is
# unresolved (the 187-attempt bug). mathlint does not yet expose a
# programmatic gate verdict (cross-repo ask @ADR-0007), so we read
# `mathlint roadmap` output and parse one structured line:
#
#   TASK KIND: ARCHITECTURE_REVIEW_REQUIRED
#
# This is the smallest defensible refusal check. Roadmap is read-only
# (does not lock-wait on the active supervisor), runs in ~0.6s, and
# has a stable line format across mathlint revisions.

_TASK_KIND_RE = re.compile(r"^TASK KIND:\s*(\S+)\s*$", re.MULTILINE)
_REASON_LINE_RE = re.compile(r"^REASON:\s*(.+?)$", re.MULTILINE)


#: Canonical LaunchAgent label per program. Distinct from
#: pi-monitor's self-supervision label so two supervisors never
#: collide on a single target (INV-005 one supervisor per
#: target). The label is rendered into the plist at install
#: time so a future program only has to declare its label
#: here (and the OS never hardcodes program-specific
#: identity in source).
_PROGRAM_LAUNCHD_LABEL: dict[str, str] = {
    "kaplansky": "com.local.research-institution.kaplansky",
}

# Sentinel used when roadmap produced no TASK KIND line at all.
# Not a member of TaskKind so consumers can distinguish "explicit
# TaskKind.OTHER" from "no line emitted" — useful for diagnostics.
TASK_KIND_ABSENT = "(absent)"


@dataclass(frozen=True, slots=True)
class GateVerdict:
    """The result of one architecture-review gate check.

    `task_kind` is the parsed value of the `TASK KIND:` line in
    `mathlint roadmap` output, mapped to a `TaskKind` enum member
    (unknown values -> `TaskKind.OTHER`). The literal string
    `(absent)` is used when no TASK KIND line appears at all.

    `status` is the dispatcher-side verdict enum: `OPEN`, `CLOSED`,
    or `UNKNOWN`. The check `status == GateVerdictStatus.OPEN` is
    the canonical "safe to launch" predicate.

    `reason` is the parsed value of the `REASON:` line, if present.
    `raw_excerpt` is the last 400 chars of roadmap output for the
    operator's diagnostic when the gate is closed.
    """

    task_kind: str
    status: str  # GateVerdictStatus value; string for dataclass slot-compat
    reason: str = ""
    raw_excerpt: str = ""

    def __post_init__(self) -> None:
        # Runtime guard: status must be a GateVerdictStatus value.
        # Catches typos at construction time, not at the call site.
        valid = {s.value for s in GateVerdictStatus}
        if self.status not in valid:
            raise ValueError(f"GateVerdict.status must be one of {valid}; got {self.status!r}")

    @property
    def gate_open(self) -> bool:
        """Backwards-compat predicate for the dispatcher CLI."""
        return self.status == GateVerdictStatus.OPEN

    @classmethod
    def from_text(cls, text: str) -> GateVerdict:
        """Parse a `mathlint roadmap` output string into a verdict.

        Pure function (no subprocess, no I/O). Use this in tests with
        golden roadmap snapshots; use :func:`check_gate` for the
        live subprocess wrapper.
        """
        kind_match = _TASK_KIND_RE.search(text)
        reason_match = _REASON_LINE_RE.search(text)
        if kind_match is None:
            return cls(
                task_kind=TASK_KIND_ABSENT,
                status=GateVerdictStatus.OPEN,
                raw_excerpt=text[-400:],
            )
        raw_kind = kind_match.group(1).strip()
        try:
            task_kind = TaskKind(raw_kind)
        except ValueError:
            task_kind = TaskKind.OTHER
        return cls(
            task_kind=task_kind.value,
            status=gate_verdict_from_task_kind(task_kind),
            reason=reason_match.group(1).strip() if reason_match else "",
            raw_excerpt=text[-400:],
        )


def check_gate(
    prog: Program, mathlint_bin: str = MATHLINT_BIN, cwd: Path | None = None
) -> GateVerdict:
    """Probe the program-supplied work-selection callable and return
    the architecture-review gate verdict.

    The architecture-review gate is owned by the OS layer; it
    probes the program-supplied ``next_active_work`` callable
    through the kernel-blessed ``mathlint.program_work_selection``
    entry-point registry. It does NOT invoke ``mathlint roadmap``
    as a subprocess against the program repo: that would invert
    the kernel/OS/program layering (per @ADR-0014). ``mathlint
    roadmap`` is math's *internal* project tool; using it to
    decide whether to launch a *program* is a category error.

    Returns a :class:`GateVerdict` with `status=OPEN` when the
    program has active work; `status=CLOSED` when the program
    has no active work or its roadmap is missing; `status=UNKNOWN`
    with a diagnostic when the registry lookup fails.

    The legacy ``mathlint_bin`` argument is accepted but unused;
    it pins the previous subprocess-API contract so callers do
    not need to update.

    Raises :class:`FileNotFoundError` only if the kernel module
    (``mathlint``) is not importable — the operator's env is
    broken; the CLI surfaces this as exit 127.
    """
    # Delegate to the in-process dispatcher so the CLI surface and
    # the programmatic surface share one probe implementation.
    #
    # The CLI subprocess starts cold — the kernel registry must be
    # populated from entry points before the dispatcher reads it.
    # Production callers (``research-institution``) trigger
    # ``discover_work_selection_programs`` at module import time
    # (``mathlint.cli``); the CLI is a fresh process so we run it
    # defensively when the registry is still empty. We do NOT call
    # discover unconditionally — that would clobber tests that
    # inject a fake callable into the registry.
    try:
        from mathlint.program_providers import (
            discover_work_selection_programs as _discover_ws,
            work_selection_callables as _callables,
        )
        if not _callables():
            _discover_ws()
    except ImportError:
        pass
    from research_institution.dispatcher import Dispatcher

    return Dispatcher().read_gate(prog, mathlint_bin=mathlint_bin, cwd=cwd)


#: Exit codes for the dispatcher CLI. Mirrored from
#: :class:`research_institution.contracts.ExitCode` so the canonical
#: vocabulary (used by operators, CI, tests) stays the single source
#: of truth. Typer's ``Exit(code=)`` accepts int — coerce from the
#: StrEnum at the call site.
EXIT_GATE_CLOSED = int(ExitCode.GATE_CLOSED)
EXIT_ALREADY_RUNNING = int(ExitCode.ALREADY_RUNNING)


@app.command("list")
def list_cmd() -> None:
    """List every program in the catalog."""
    programs = _load()
    if not programs:
        typer.echo("(catalog is empty)")
        raise typer.Exit()
    typer.echo(f"{'NAME':<20} {'REPOSITORY':<50} {'LOCAL_PATH'}")
    for p in programs:
        typer.echo(f"{p.name:<20} {p.repository:<50} {p.local_path}")


@app.command("doctor")
def doctor(
    live: bool = typer.Option(
        False, "--live", help="Run the operator-live gate (requires credentials)."
    ),
    program: str | None = typer.Option(None, "--program", help="Scope the gate to one program."),
) -> None:
    """Run the canonical institution green gate. Delegates to green-gate/check-institution.sh."""
    gate = green_gate_path()
    if not gate.is_file():
        typer.echo(f"FATAL: green gate missing at {gate}", err=True)
        raise typer.Exit(code=2)
    flags = ["--live"] if live else ["--hermetic"]
    if program is not None:
        flags.append(f"--skip-program={program}")
    rc = subprocess.call([str(gate), *flags])
    raise typer.Exit(code=rc)


@app.command("reset")
def reset(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Mutate state (default: dry-run, print only). Always required for destructive actions.",
    ),
    kill_processes: bool = typer.Option(
        False,
        "--kill-processes",
        help="Terminate wedged supervisors (refuses if any look healthy).",
    ),
    purge_state: Annotated[list[Path] | None, typer.Option("--purge-state", help="Purge a state directory entirely (repeatable). Requires --apply.")] = None,
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Required confirmation for --purge-state. The CLI prints a summary and asks; --yes skips the ask.",
    ),
) -> None:
    """Bring the institution to a clean, launchable state.

    The default pass is a SAFE DRY-RUN: it discovers stale
    supervisor.lock files (whose PIDs are dead) and prints what
    it would remove. Pass ``--apply`` to actually mutate.

    Cleanup tiers, escalating order:

    \b
    - stale locks: always removed when --apply is set (safe).
    - wedged supervisors: only with --kill-processes (refuses
      if any look healthy; use ``research stop`` for those).
    - state directories: only with --purge-state AND --apply AND
      --yes. The dispatcher prints the dirs + their size and
      asks; --yes skips the ask. Always paired with a final
      liveness check at delete time.

    Per INV-005 (one supervisor per target), the verb refuses to
    touch any lock whose PID is alive and refuses to delete any
    state dir whose owning supervisor came back to life between
    discovery and delete.

    Dry-run exit code is 0 (success, just informative) when no
    refusals occur, and 1 when there are refusals the operator
    needs to address before launch.
    """
    from research_institution.reset import reset as do_reset

    # ``Annotated[..., typer.Option()] = None`` is the canonical
    # B008-safe default for a list option (mutable defaults +
    # function-call defaults are both flagged). The list is
    # never mutated by callers; the mutator accepts a tuple.
    if purge_state is None:
        purge_state = []

    if purge_state and not apply:
        typer.echo(
            "FATAL: --purge-state requires --apply (destructive action; dry-run is for inspection)",
            err=True,
        )
        raise typer.Exit(code=2)
    if purge_state and not yes:
        typer.echo(
            "FATAL: --purge-state requires --yes confirmation. "
            "Re-run with --yes to confirm; without it, only --kill-processes + stale-lock cleanup will run.",
            err=True,
        )
        raise typer.Exit(code=2)

    report = do_reset(
        purge_state=tuple(purge_state),
        kill_processes=kill_processes,
        dry_run=not apply,
    )
    typer.echo(report.render())
    raise typer.Exit(code=0 if report.ok else 1)


@app.command("start")
def start(
    program: str = typer.Argument(..., help="Program name from the catalog."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would launch; skip gate check + credentials."
    ),
    skip_gate: bool = typer.Option(
        False,
        "--skip-gate",
        help="Skip the architecture-review gate check (operator override; logs the override).",
    ),
    mode: str = typer.Option(
        "autonomous",
        "--mode",
        help=(
            "Launch mode. 'autonomous' spawns `pi-monitor run --config <cfg>` "
            "directly (the long-running supervisor that watches the roadmap and "
            "dispatches workers; no mathlint preflight required). 'durable' spawns "
            "`mathlint live-run --confirm-live` (one bounded paired run that "
            "produces a receipt; requires the live preflight to be green)."
        ),
    ),
) -> None:
    """Start one program.

    Two modes:

    \b
    - autonomous (default): spawn `pi-monitor run --config <cfg>` directly.
      This is the long-running supervisor that monitors the roadmap and
      dispatches workers. It does NOT require the mathlint preflight (no
      paired-smoke receipt, no math check, no model credential). It DOES
      require the architecture-review gate to be OPEN (refuse with --skip-gate).

    \b
    - durable: spawn `mathlint live-run --confirm-live`. One bounded paired
      run that produces a receipt. Requires the full live preflight (gate,
      receipt, model creds, postgres, math check).

    Both modes refuse to spawn a duplicate when a supervisor is already
    running for this config (idempotency). Use `research stop <program>`
    first if you want to restart.

    Per @ADR-0006 + B.1.2, refuses to launch while the architecture-review
    gate is closed. Override with `--skip-gate` (logged).
    """
    if mode not in {"autonomous", "durable"}:
        typer.echo(f"FATAL: --mode must be 'autonomous' or 'durable'; got {mode!r}", err=True)
        raise typer.Exit(code=2)
    prog = _require_program(program)
    if not prog.resolved_local_path.is_dir():
        typer.echo(f"FATAL: program local_path missing: {prog.resolved_local_path}", err=True)
        raise typer.Exit(code=3)

    if dry_run:
        typer.echo(
            f"would launch: {prog.name} (mode={mode}, local_path={prog.resolved_local_path})"
        )
        if mode == "autonomous":
            cfg = pi_monitor_config_path()
            typer.echo(f"would delegate to: pi-monitor run --config {cfg}")
            typer.echo("(no mathlint preflight; this is the autonomous-supervision path)")
        else:
            typer.echo("would delegate to: mathlint live-run --confirm-live")
            typer.echo(
                f"would require credentials: {[v for v in prog.live_credential_env_vars] or '(none)'}"
            )
        typer.echo("would check architecture-review gate: yes (read-only roadmap parse)")
        # For --dry-run, also surface whether a supervisor is already
        # up so the operator sees the full picture without spawning.
        state = probe_default_supervisor()
        if state.is_alive:
            typer.echo(f"current state: supervisor already running (pid {state.supervisor_pid})")
        else:
            typer.echo("current state: no supervisor running")
        return

    # Idempotency: if a supervisor is already up for this config,
    # refuse to spawn a duplicate. `mathlint live-run` does NOT
    # check for an existing supervisor (postmortem B.1.2 risk).
    # Detect via `pi-monitor status --config <cfg>` + PID liveness.
    state = probe_default_supervisor()
    if state.is_alive:
        typer.echo(
            f"supervisor already running (pid {state.supervisor_pid}); "
            f"refusing to spawn a duplicate.",
            err=True,
        )
        typer.echo(
            "  hint: research status <program> for the headline; "
            "research stop <program> to shut it down.",
            err=True,
        )
        raise typer.Exit(code=EXIT_ALREADY_RUNNING)

    # Architecture-review gate (B.1.2). Skipped only with explicit
    # --skip-gate. The verdict is read-only and lock-free; safe to run
    # while the supervisor is active.
    if not skip_gate:
        mathlint_bin = _which_or_die("mathlint")
        verdict = check_gate(prog, mathlint_bin=mathlint_bin)
        if not verdict.gate_open:
            typer.echo(
                f"GATE NOT OPEN: mathlint roadmap reports TASK KIND={verdict.task_kind}",
                err=True,
            )
            if verdict.reason:
                typer.echo(f"  reason: {verdict.reason}", err=True)
            typer.echo(
                "  fix: run `mathlint architect-apply --recommendation <yaml>` and retry.", err=True
            )
            typer.echo("  override: pass --skip-gate to launch anyway (logged).", err=True)
            raise typer.Exit(code=EXIT_GATE_CLOSED)
        typer.echo(f"gate OK (TASK KIND={verdict.task_kind})", err=True)
    else:
        typer.echo("WARN: --skip-gate passed; architecture-review gate bypassed", err=True)

    # Credential check is required for BOTH modes (the worker + judge
    # both call `pi` which needs OAuth via @ADR-0001). When the only
    # missing credential is MATHLINT_MODEL_ROUTE, fall back to the
    # configured route in ~/.config/mathlint/local.toml so the
    # operator doesn't have to `export` per-shell.
    if prog.live_credentials_required:
        from research_institution.paths import resolve_model_route

        missing = missing_credentials(prog)
        if "MATHLINT_MODEL_ROUTE" in missing:
            inferred = resolve_model_route()
            if inferred is not None:
                os.environ["MATHLINT_MODEL_ROUTE"] = inferred
                missing = [v for v in missing if v != "MATHLINT_MODEL_ROUTE"]
        if missing:
            typer.echo(f"FATAL: missing credential env var(s): {', '.join(missing)}", err=True)
            raise typer.Exit(code=4)

    if mode == "durable":
        mathlint = _which_or_die("mathlint")
        rc = subprocess.call([mathlint, "live-run", "--confirm-live"])
        raise typer.Exit(code=rc)

    # mode == autonomous: spawn the supervisor directly. This is the
    # long-running path that monitors the roadmap and dispatches
    # workers; the mathlint preflight is irrelevant here because
    # we are NOT producing a paired receipt.
    pi_monitor = _which_or_die("pi-monitor")
    cfg = pi_monitor_config_path()
    typer.echo(f"spawning pi-monitor run --config {cfg}", err=True)
    # Re-check immediately before spawn to close the small race window.
    if probe_default_supervisor().is_alive:
        typer.echo(
            "(a supervisor started between the initial check and the spawn; reusing it)", err=True
        )
        raise typer.Exit(code=0)
    rc = subprocess.call([pi_monitor, "run", "--config", str(cfg)])
    raise typer.Exit(code=rc)


@app.command("stop")
def stop(
    program: str = typer.Argument(..., help="Program name from the catalog."),
    force: bool = typer.Option(
        False,
        "--force",
        help="Send SIGKILL to the supervisor if SIGTERM does not stop it within 5s.",
    ),
) -> None:
    """Stop one program's supervisor.

    Two-step process:

    1. Ask mathlint to persist an operator stop (`mathlint research-stop`).
    2. If a supervisor is still running, send SIGTERM (or SIGKILL with --force).

    Safe to run when no supervisor is active (no-op with a clear message).
    """
    _require_program(program)
    mathlint_bin = _which_or_die("mathlint")
    subprocess.call([mathlint_bin, "research-stop"])
    state = probe_default_supervisor()
    if not state.is_alive:
        typer.echo("no supervisor running; nothing to stop.", err=True)
        raise typer.Exit(code=0)
    pid = state.supervisor_pid
    typer.echo(f"stopping supervisor (pid {pid}) via SIGTERM", err=True)
    try:
        os.kill(pid, 15)  # SIGTERM
    except ProcessLookupError as err:
        typer.echo(f"  pid {pid} already exited", err=True)
        raise typer.Exit(code=0) from err
    # Wait up to 5s for clean exit.
    import time as _time

    for _ in range(50):
        _time.sleep(0.1)
        if not _pid_alive_quick(pid):
            typer.echo(f"  pid {pid} stopped", err=True)
            raise typer.Exit(code=0)
    if force:
        typer.echo(f"  pid {pid} did not stop; sending SIGKILL", err=True)
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, 9)  # SIGKILL
        raise typer.Exit(code=0)
    typer.echo(f"  pid {pid} did not stop within 5s; retry with --force", err=True)
    raise typer.Exit(code=1)


def _pid_alive_quick(pid: int) -> bool:
    """Cheap PID liveness probe for the stop loop (signal 0, no error handling)."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


@app.command("status")
def status(
    program: str = typer.Argument(..., help="Program name from the catalog."),
    verbose: bool = typer.Option(
        False, "--verbose", help="Delegate to mathlint research-status for full output."
    ),
) -> None:
    """Read one program's status.

    Without --verbose: prints a one-line headline derived from the
    pi_monitor supervisor's runtime state files (B.5.1). Cheap,
    no subprocess, no LLM.

    With --verbose: delegates to `mathlint research-status` for
    the full multi-line output. Use this when investigating a
    specific failure or when the headline is uninformative.
    """
    _require_program(program)
    if verbose:
        mathlint = _which_or_die("mathlint")
        rc = subprocess.call([mathlint, "research-status"])
        raise typer.Exit(code=rc)
    headline = read_status_headline(program, pi_monitor_state_dir())
    typer.echo(format_headline(headline))


@app.command("health")
def health(
    program: str = typer.Argument(..., help="Program name from the catalog."),
    verbose: bool = typer.Option(
        False, "--verbose", help="Print the full green-gate output in addition to the summary."
    ),
) -> None:
    """One-shot diagnostic for the operator's startup readiness.

    Runs every check the operator would otherwise discover by trial:
    green-gate --hermetic (wiring), mathlint system-readiness
    (live preflight), architecture-review gate, paired-smoke
    receipt freshness, supervisor liveness.

    For each failure prints the EXACT next command (copy-paste).
    Exits 0 when fully ready, 1 when any check failed.
    """
    _require_program(program)
    report = run_health(program)
    typer.echo(format_health(report))
    if verbose:
        typer.echo("")
        typer.echo("--- verbose: green-gate --hermetic ---")
        gate = green_gate_path()
        if gate.is_file():
            subprocess.call(["bash", str(gate), "--hermetic"])
        else:
            typer.echo(f"(missing: {gate})")
    raise typer.Exit(code=0 if report.is_healthy else 1)


@app.command("restart")
def restart(
    program: str = typer.Argument(..., help="Program name from the catalog."),
    mode: str = typer.Option(
        "autonomous",
        "--mode",
        help="See `research start --help` for mode semantics.",
    ),
    skip_gate: bool = typer.Option(False, "--skip-gate", help="Pass through to `research start`."),
) -> None:
    """Atomic restart: stop the supervisor, then start it again.

    Equivalent to `research stop <program>` followed by `research start
    <program>`, but refuses to silently no-op if the stop fails (force
    exit). Use this when you've changed the pi-monitor config and want
    to reload, or when the supervisor has wedged.
    """
    # Use the existing stop logic but force-stop if needed.
    _require_program(program)
    state = probe_default_supervisor()
    if state.is_alive:
        typer.echo(f"restart: stopping supervisor (pid {state.supervisor_pid})", err=True)
        # Inline stop with --force semantics.
        mathlint_bin = _which_or_die("mathlint")
        subprocess.call([mathlint_bin, "research-stop"])
        with contextlib.suppress(ProcessLookupError):
            os.kill(state.supervisor_pid, 15)
        import time as _time

        for _ in range(50):
            _time.sleep(0.1)
            if not _pid_alive_quick(state.supervisor_pid):
                break
        if _pid_alive_quick(state.supervisor_pid):
            typer.echo(f"  pid {state.supervisor_pid} did not stop; sending SIGKILL", err=True)
            with contextlib.suppress(ProcessLookupError):
                os.kill(state.supervisor_pid, 9)
        typer.echo("restart: stop done; starting", err=True)
    # Now call start with the same args. We invoke the function
    # directly (rather than shelling out) so the operator's shell
    # sees consistent stdout/stderr.
    start(
        program=program,
        dry_run=False,
        skip_gate=skip_gate,
        mode=mode,
    )


@app.command("watch")
def watch(
    program: str = typer.Argument(..., help="Program name from the catalog."),
    interval: float = typer.Option(2.0, "--interval", help="TUI refresh seconds (>=0.5)."),
) -> None:
    """Open the live TUI for one program. Delegates to pi-monitor watch.

    Requires the pi_monitor venv to have Textual installed. The TUI
    needs a real TTY; this command exec's the subprocess so the TTY
    passes through directly.
    """
    _require_program(program)
    pi_monitor = _which_or_die("pi-monitor")
    config = pi_monitor_config_path()
    if not config.is_file():
        typer.echo(f"FATAL: pi_monitor config not found at {config}", err=True)
        raise typer.Exit(code=2)
    start_script = pi_monitor_start_script()
    if not start_script.is_file():
        typer.echo(f"FATAL: pi_monitor start script missing at {start_script}", err=True)
        raise typer.Exit(code=3)
    rc = subprocess.call(
        [
            pi_monitor,
            "watch",
            "--config",
            str(config),
            "--script",
            str(start_script),
            "--interval",
            str(interval),
        ]
    )
    raise typer.Exit(code=rc)


@app.command("install")
def install(
    program: str = typer.Argument(..., help="Program name from the catalog."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Render + show the plist; skip writing / loading."
    ),
) -> None:
    """Install the canonical LaunchAgent for one program.

    Renders the per-program plist template under
    ``launchd-templates/`` into
    ``~/Library/LaunchAgents/<label>.plist`` and loads it
    via ``launchctl bootstrap gui/$UID``. Idempotent:
    re-running with the same rendered contents is a no-op;
    a different plist under the same label is refused so
    the operator can never silently overwrite another
    supervisor's launchd entry.

    The label is program-owned (``_PROGRAM_LAUNCHD_LABEL``)
    and distinct from pi-monitor's self-supervision label so
    two supervisors never collide on a single target
    (INV-005 one supervisor per target). Use
    ``research uninstall <program>`` to remove.
    """
    from research_institution.launchd import install_plist, render_plist
    from research_institution.launchd import LaunchAgentTarget

    prog = _require_program(program)
    label = _PROGRAM_LAUNCHD_LABEL.get(prog.name)
    if label is None:
        typer.echo(
            f"FATAL: no LaunchAgent label configured for {prog.name!r}; "
            f"add one to _PROGRAM_LAUNCHD_LABEL in cli.py.",
            err=True,
        )
        raise typer.Exit(code=5)

    template_path = (
        Path(institution_dir()) / "launchd-templates" / f"{prog.name}-pi-monitor.plist.xml"
    )
    if not template_path.is_file():
        typer.echo(f"FATAL: plist template missing: {template_path}", err=True)
        raise typer.Exit(code=6)
    template = template_path.read_text(encoding="utf-8")

    pi_monitor_bin = (
        Path(pi_monitor_repo()) / ".venv" / "bin" / "pi-monitor"
    )
    if not pi_monitor_bin.is_file():
        typer.echo(f"FATAL: pi-monitor binary missing: {pi_monitor_bin}", err=True)
        raise typer.Exit(code=7)

    cfg_path = pi_monitor_config_path()
    if not cfg_path.is_file():
        typer.echo(f"FATAL: pi-monitor config missing: {cfg_path}", err=True)
        raise typer.Exit(code=8)

    inst_dir = Path(institution_dir())
    logs_dir = inst_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    target = LaunchAgentTarget(
        label=label,
        pi_monitor_bin=pi_monitor_bin,
        pi_monitor_config_path=cfg_path,
        institution_dir=inst_dir,
        stdout_path=logs_dir / f"{prog.name}.out.log",
        stderr_path=logs_dir / f"{prog.name}.err.log",
    )
    rendered = render_plist(template, target)
    typer.echo(f"rendered plist: {rendered.path}")
    typer.echo(f"  label: {rendered.label}")
    typer.echo(f"  config fingerprint: {rendered.config_fingerprint}")
    ok, msg = install_plist(rendered, dry_run=dry_run)
    typer.echo(msg)
    raise typer.Exit(code=0 if ok else 9)


@app.command("uninstall")
def uninstall(
    program: str = typer.Argument(..., help="Program name from the catalog."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Bootout + remove; skip the live launchctl call."
    ),
) -> None:
    """Remove the LaunchAgent for one program (inverse of ``install``).

    Idempotent: a missing plist is a no-op. Boots out via
    ``launchctl bootout`` (tolerating "not loaded" = rc 36)
    and removes the plist from ``~/Library/LaunchAgents/``.
    """
    from research_institution.launchd import uninstall_plist

    _require_program(program)
    label = _PROGRAM_LAUNCHD_LABEL.get(program)
    if label is None:
        typer.echo(
            f"FATAL: no LaunchAgent label configured for {program!r}.",
            err=True,
        )
        raise typer.Exit(code=5)
    ok, msg = uninstall_plist(label, dry_run=dry_run)
    typer.echo(msg)
    raise typer.Exit(code=0 if ok else 9)


@app.command("install-skills")
def install_skills() -> None:
    """Generate per-program pi skill markdown files and symlink them into ~/.pi/agent/skills/.

    Idempotent: re-running refreshes the symlinks without touching
    sibling skill installs.
    """
    agent_skills = agent_skills_dir()
    agent_skills.mkdir(parents=True, exist_ok=True)
    institution_root = institution_dir()
    skills_src = institution_root / "skills"
    skills_src.mkdir(exist_ok=True)

    installed = 0
    for prog in _load():
        skill_md = skills_src / f"{prog.name}.md"
        skill_md.write_text(
            render_skill(prog),
            encoding="utf-8",
        )
        target = agent_skills / prog.name
        if target.is_symlink() or target.exists():
            target.unlink()
        target.symlink_to(skill_md)
        installed += 1
        typer.echo(f"[install] {target} -> {skill_md}")
    typer.echo(f"\nINSTALLED {installed} PROGRAM SKILLS")
    typer.echo(f"discovery root: {agent_skills}")


def main() -> None:
    app.add_typer(prime_directive_app, name="prime_directive")
    app()


@app.command("verify-simulation")
def verify_simulation(
    tier: str = typer.Option(
        "fast",
        "--tier",
        help="Tier selector (fast|full|process|deployment|provider-canary|soak).",
    ),
    scenario: str | None = typer.Option(
        None,
        "--scenario",
        help="Run a single scenario by name (overrides --tier).",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit JSON output instead of a human-readable summary.",
    ),
    baseline_subprocess_count: int = typer.Option(
        0,
        "--baseline-subprocess-count",
        help="Baseline subprocess count for the resource oracle.",
    ),
    macos_isolated_label: str | None = typer.Option(
        None,
        "--macos-isolated-label",
        help="macOS deployment tier: unique launchctl label.",
    ),
    live: bool = typer.Option(
        False,
        "--live",
        help="Provider-canary tier: opt-in to actually run the LIVE canary.",
    ),
    hours: float | None = typer.Option(
        None,
        "--hours",
        help="Soak tier: duration in hours (required).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Deployment tier: render ProgramArguments without spawning.",
    ),
) -> None:
    """Run the verify-simulation harness (entry 06 + 07)."""
    argv: list[str] = ["--tier", tier]
    if scenario is not None:
        argv.extend(["--scenario", scenario])
    if json_output:
        argv.append("--json")
    if baseline_subprocess_count:
        argv.extend(["--baseline-subprocess-count", str(baseline_subprocess_count)])
    if macos_isolated_label is not None:
        argv.extend(["--macos-isolated-label", macos_isolated_label])
    if live:
        argv.append("--live")
    if hours is not None:
        argv.extend(["--hours", str(hours)])
    if dry_run:
        argv.append("--dry-run")
    rc = verify_simulation_main(argv)
    raise typer.Exit(code=rc)


if __name__ == "__main__":
    sys.exit(main())
