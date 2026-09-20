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
) -> None:
    """Start one program.

    Per @ADR-0006 + B.1.2, refuses to launch while the architecture-review
    gate is closed. The gate verdict is read from `mathlint roadmap`
    output (`TASK KIND: ARCHITECTURE_REVIEW_REQUIRED` ⇒ closed).
    Override with `--skip-gate` (logged).

    Dry-run (`--dry-run`) skips BOTH the gate check and credential check;
    it only shows what would happen.
    """
    prog = _require_program(program)
    if not prog.resolved_local_path.is_dir():
        typer.echo(f"FATAL: program local_path missing: {prog.resolved_local_path}", err=True)
        raise typer.Exit(code=3)

    if dry_run:
        typer.echo(f"would launch: {prog.name} (local_path={prog.resolved_local_path})")
        typer.echo("would delegate to: mathlint live-run --confirm-live")
        typer.echo(f"would require credentials: {[v for v in prog.live_credential_env_vars] or '(none)'}")
        typer.echo("would check architecture-review gate: yes (read-only roadmap parse)")
        return

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

    # Credential check.
    if prog.live_credentials_required:
        missing = missing_credentials(prog)
        if missing:
            typer.echo(f"FATAL: missing credential env var(s): {', '.join(missing)}", err=True)
            raise typer.Exit(code=4)

    mathlint = _which_or_die("mathlint")
    rc = subprocess.call([mathlint, "live-run", "--confirm-live"])
    raise typer.Exit(code=rc)


@app.command("stop")
def stop(
    program: str = typer.Argument(..., help="Program name from the catalog."),
) -> None:
    """Stop one program. Delegates to mathlint research-stop."""
    _require_program(program)
    mathlint = _which_or_die("mathlint")
    rc = subprocess.call([mathlint, "research-stop"])
    raise typer.Exit(code=rc)


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
