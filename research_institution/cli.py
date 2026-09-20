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

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import typer

from research_institution.catalog import Program, load_catalog
from research_institution.contracts import (
    GateVerdictStatus,
    TaskKind,
    gate_verdict_from_task_kind,
)
from research_institution.contracts.skill_template import render_skill
from research_institution.paths import (
    agent_skills_dir,
    catalog_path,
    green_gate_path,
    institution_dir,
    missing_credentials,
    pi_monitor_config_path,
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
            raise ValueError(
                f"GateVerdict.status must be one of {valid}; got {self.status!r}"
            )

    @property
    def gate_open(self) -> bool:
        """Backwards-compat predicate for the dispatcher CLI."""
        return self.status == GateVerdictStatus.OPEN

    @classmethod
    def from_text(cls, text: str) -> "GateVerdict":
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


def check_gate(prog: Program, mathlint_bin: str = "mathlint", cwd: Optional[Path] = None) -> GateVerdict:
    """Read `mathlint roadmap` and return the architecture-review gate verdict.

    Runs `mathlint roadmap` in the program's resolved_local_path.
    Returns a :class:`GateVerdict` with `status=CLOSED` when the gate
    is closed (TASK KIND=ARCHITECTURE_REVIEW_REQUIRED); `status=OPEN`
    otherwise. Returns `status=UNKNOWN` with reason naming the exit
    code if mathlint fails to run.

    Raises `FileNotFoundError` if mathlint is not on PATH (operator's
    env is broken; the dispatcher CLI surfaces this as exit 127).
    """
    workdir = cwd or prog.resolved_local_path
    completed = subprocess.run(
        [mathlint_bin, "roadmap"],
        capture_output=True,
        text=True,
        timeout=15,
        cwd=str(workdir),
        check=False,
    )
    if completed.returncode != 0:
        return GateVerdict(
            task_kind="(roadmap-failed)",
            status=GateVerdictStatus.UNKNOWN,
            reason=f"mathlint roadmap exited {completed.returncode}",
            raw_excerpt=(completed.stderr or completed.stdout or "")[-400:],
        )
    return GateVerdict.from_text(completed.stdout or "")


# Exit code for `research start` when the gate is closed.
EXIT_GATE_CLOSED = 5

# Exit code for `research start` when a supervisor is already
# running for this config (idempotent refusal; see supervisor probe).
EXIT_ALREADY_RUNNING = 6


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
    live: bool = typer.Option(False, "--live", help="Run the operator-live gate (requires credentials)."),
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


@app.command("start")
def start(
    program: str = typer.Argument(..., help="Program name from the catalog."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would launch; skip gate check + credentials."),
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
        typer.echo(f"would launch: {prog.name} (mode={mode}, local_path={prog.resolved_local_path})")
        if mode == "autonomous":
            cfg = pi_monitor_config_path()
            typer.echo(f"would delegate to: pi-monitor run --config {cfg}")
            typer.echo("(no mathlint preflight; this is the autonomous-supervision path)")
        else:
            typer.echo("would delegate to: mathlint live-run --confirm-live")
            typer.echo(f"would require credentials: {[v for v in prog.live_credential_env_vars] or '(none)'}")
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
            typer.echo("  fix: run `mathlint architect-apply --recommendation <yaml>` and retry.", err=True)
            typer.echo("  override: pass --skip-gate to launch anyway (logged).", err=True)
            raise typer.Exit(code=EXIT_GATE_CLOSED)
        typer.echo(f"gate OK (TASK KIND={verdict.task_kind})", err=True)
    else:
        typer.echo("WARN: --skip-gate passed; architecture-review gate bypassed", err=True)

    # Credential check is required for BOTH modes (the worker + judge
    # both call `pi` which needs OAuth via @ADR-0001).
    if prog.live_credentials_required:
        missing = missing_credentials(prog)
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
        typer.echo("(a supervisor started between the initial check and the spawn; reusing it)", err=True)
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
    except ProcessLookupError:
        typer.echo(f"  pid {pid} already exited", err=True)
        raise typer.Exit(code=0)
    # Wait up to 5s for clean exit.
    import time as _time
    for _ in range(50):
        _time.sleep(0.1)
        if not _pid_alive_quick(pid):
            typer.echo(f"  pid {pid} stopped", err=True)
            raise typer.Exit(code=0)
    if force:
        typer.echo(f"  pid {pid} did not stop; sending SIGKILL", err=True)
        try:
            os.kill(pid, 9)  # SIGKILL
        except ProcessLookupError:
            pass
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
        try:
            os.kill(state.supervisor_pid, 15)
        except ProcessLookupError:
            pass
        import time as _time
        for _ in range(50):
            _time.sleep(0.1)
            if not _pid_alive_quick(state.supervisor_pid):
                break
        if _pid_alive_quick(state.supervisor_pid):
            typer.echo(f"  pid {state.supervisor_pid} did not stop; sending SIGKILL", err=True)
            try:
                os.kill(state.supervisor_pid, 9)
            except ProcessLookupError:
                pass
        typer.echo("restart: stop done; starting", err=True)
    # Now call start with the same args. We invoke the function
    # directly (rather than shelling out) so the operator's shell
    # sees consistent stdout/stderr.
    start(
        program=program, dry_run=False, skip_gate=skip_gate, mode=mode,
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
    rc = subprocess.call([pi_monitor, "watch", "--config", str(config), "--script", str(start_script), "--interval", str(interval)])
    raise typer.Exit(code=rc)


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
    app()


if __name__ == "__main__":
    sys.exit(main())
