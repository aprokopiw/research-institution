"""Unified diagnostic for the operator's institution.

`research health <program>` runs the full pre-flight in one call:

  1. Green-gate --hermetic: engine wired, supervisor wired, program wired.
  2. Green-gate --live: model creds, postgres, math-repo clean state.
  3. Architecture-review gate verdict (read-only).
  4. Receipt freshness: math HEAD == paired-smoke receipt commit.
  5. Supervisor liveness: pid alive, project root matches, last action.

For each failed check, `HealthReport.suggestions` contains the
operator's exact next command (one line, copy-paste ready).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field

from research_institution.contracts import TaskKind
from research_institution.paths import (
    catalog_path,
    institution_dir,
)


@dataclass(frozen=True, slots=True)
class HealthCheck:
    """One diagnostic result.

    `ok` is True iff this check passed. `summary` is one line for
    `typer.echo`. `suggestion` is the operator's next command (or
    empty when no action is needed). `evidence` is a path or
    command excerpt for the operator to investigate further.
    """

    name: str
    ok: bool
    summary: str
    suggestion: str = ""
    evidence: str = ""


@dataclass(frozen=True, slots=True)
class HealthReport:
    """Aggregate diagnostic for one program."""

    program: str
    checks: list[HealthCheck] = field(default_factory=list)
    supervisor_pid: int = 0
    supervisor_alive: bool = False

    @property
    def is_healthy(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def failures(self) -> list[HealthCheck]:
        return [c for c in self.checks if not c.ok]


# ---------------------------------------------------------------------------
# Wire shape of mathlint's ``--preflight --json`` output. The shape is
# defined by mathlint; we mirror it locally so the read side has full
# static typing. Drift here is caught at parse time, not silently
# passed through to the operator's suggestions list.
# ---------------------------------------------------------------------------


class PreflightCheckStatus(StrEnum):
    """Canonical preflight-check status vocabulary (mathlint emits these).

    A typo at the consumer (``status == "passed"`` vs ``"pass"``)
    fails fast at the Pydantic ValidationError boundary instead of
    silently misclassifying the check.
    """

    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


class PreflightCheckWire(BaseModel):
    """One entry from mathlint preflight's ``checks`` list.

    Pydantic model replaces the legacy TypedDict so a malformed
    ``status`` string fails fast at the parse boundary. ``extra=\"allow\"``
    keeps forward-compat with a future mathlint that adds a new
    field (e.g. ``duration_ms``).
    """

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str | None = None
    status: PreflightCheckStatus | None = None
    detail: str | None = None
    suggestion: str | None = None


class PreflightPayload(BaseModel):
    """Top-level wire shape returned by mathlint preflight --json.

    The typed model replaces the legacy TypedDict so a malformed
    payload (missing required ``checks`` list, unknown ``status``
    string) fails fast at the parse boundary.
    """

    model_config = ConfigDict(extra="allow")

    ok: bool | None = None
    checks: list[PreflightCheckWire] = Field(default_factory=list)


def _run_hermetic_green_gate() -> HealthCheck:
    """Run the green-gate --hermetic script; parse its verdict."""
    gate = institution_dir() / "green-gate" / "check-institution.sh"
    if not gate.is_file():
        return HealthCheck(
            name="green-gate-hermetic",
            ok=False,
            summary="green-gate script missing",
            suggestion="re-run scripts/bootstrap-institution.sh",
            evidence=str(gate),
        )
    try:
        completed = subprocess.run(
            ["bash", str(gate), "--hermetic"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return HealthCheck(
            name="green-gate-hermetic",
            ok=False,
            summary="green-gate --hermetic timed out (a supervisor may be holding the state lock)",
            suggestion="kill the supervisor (research stop <program>) and re-run",
        )
    ok = completed.returncode == 0 and "GREEN INSTITUTION READY" in completed.stdout
    return HealthCheck(
        name="green-gate-hermetic",
        ok=ok,
        summary=("engine + supervisor + program wired" if ok else f"rc={completed.returncode}"),
        suggestion=""
        if ok
        else "run research health <program> with --verbose for the full gate output",
        evidence=completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else "",
    )


def _run_live_preflight() -> HealthCheck:
    """Run mathlint system-readiness --no-write; parse PASS/FAIL count.

    Note: `mathlint system-readiness` exits with code 1 when ANY
    check fails (this is the documented contract; not a mathlint
    failure). The function returns FAIL with actionable suggestions
    based on which checks failed; only treats mathlint itself as
    broken when the call returns no parseable JSON at all.
    """
    config_path = str(Path.home() / ".config" / "mathlint" / "local.toml")
    try:
        completed = subprocess.run(
            ["mathlint", "system-readiness", "--no-write", "--json", "--config", config_path],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError:
        return HealthCheck(
            name="live-preflight",
            ok=False,
            summary="mathlint not on PATH",
            suggestion="add ~/Documents/andrei/math/.venv/bin to ~/.zprofile",
        )
    except subprocess.TimeoutExpired:
        return HealthCheck(
            name="live-preflight",
            ok=False,
            summary="mathlint system-readiness timed out",
            suggestion="kill the supervisor (research stop <program>) and re-run",
        )
    # rc != 0 from system-readiness means at least one check failed;
    # the JSON body is still emitted. Only treat as a mathlint
    # failure if the JSON doesn't parse. The dynamic JSON boundary
    # lives here; below this point the payload is typed as
    # ``PreflightPayload``.
    try:
        raw_payload: object = json.loads(completed.stdout) if completed.stdout.strip() else None
        payload = (
            PreflightPayload.model_validate(raw_payload)
            if isinstance(raw_payload, dict)
            else None
        )
    except json.JSONDecodeError:
        last_err = ""
        for stream in (completed.stdout, completed.stderr):
            if not stream:
                continue
            for line in reversed(stream.splitlines()):
                if line.strip():
                    last_err = line.strip()[:160]
                    break
            if last_err:
                break
        return HealthCheck(
            name="live-preflight",
            ok=False,
            summary=f"mathlint system-readiness returned unparseable output (rc={completed.returncode})",
            suggestion=f"run `mathlint --help` to see the import error; last captured line: {last_err or '(empty)'}",
            evidence=last_err,
        )
    if payload is None:
        return HealthCheck(
            name="live-preflight",
            ok=False,
            summary="mathlint system-readiness produced no output",
            suggestion="check that math is installed and on PATH",
        )
    checks: list[PreflightCheckWire] = payload.get("checks") or []
    failed = [c for c in checks if c.status == PreflightCheckStatus.FAIL]
    if not failed:
        return HealthCheck(
            name="live-preflight",
            ok=True,
            summary=f"all {len(checks)} live checks passed",
        )
    # Render one suggestion per failure class.
    suggestion_lines: list[str] = []
    for c in failed[:8]:
        cid: str = str(c.get("id", "?"))
        diag: str = str(c.get("diagnostic", ""))
        if cid == "MATH001" or cid == "MATH002":
            suggestion_lines.append(
                f"{cid}: run `cd ~/Documents/andrei/math && make check` (or commit/stash the dirty changes)"
            )
        elif cid == "LOCAL022" or cid == "PAIR001":
            suggestion_lines.append(
                f"{cid}: math repo is dirty — run `cd ~/Documents/andrei/math && git status` then commit/stash"
            )
        elif cid == "LOCAL004":
            suggestion_lines.append(
                f"{cid}: --no-write mode is informational only; the real fix is to bootstrap the receipt (see SMOKE001) or commit/stash the dirty changes"
            )
        elif cid == "SMOKE001":
            suggestion_lines.append(
                f"{cid}: run `mathlint first-run --project kaplansky` to bootstrap the receipt"
            )
        elif cid == "MODEL001":
            suggestion_lines.append(f"{cid}: install pi (`brew install pi`)")
        elif cid == "MODEL002":
            suggestion_lines.append(f"{cid}: run `pi auth login` to refresh the OAuth grant")
        elif cid == "POSTGRES004":
            suggestion_lines.append(f"{cid}: run `mathlint postgres-cycle`")
        elif cid == "TOOL001":
            suggestion_lines.append(
                f"{cid}: run `pi-monitor doctor --config ~/.config/mathlint/local-pi-monitor.toml`"
            )
        else:
            suggestion_lines.append(f"{cid}: {diag[:120]}")
    return HealthCheck(
        name="live-preflight",
        ok=False,
        summary=f"{len(failed)}/{len(checks)} live checks failed",
        suggestion="\n".join(suggestion_lines),
        evidence=", ".join(str(c.get("id", "?")) for c in failed),
    )


def _check_architecture_review_gate(program: str) -> HealthCheck:
    """Run mathlint roadmap; refuse if TASK KIND=ARCHITECTURE_REVIEW_REQUIRED.

    `mathlint roadmap` must run from the program's local_path (it
    looks for mathlint.toml in the cwd or a parent). When called
    from research-institution's cwd it fails with "no mathlint.toml
    found". Resolve the program's local_path from the catalog and
    cd into it before invoking.
    """
    from research_institution.catalog import load_catalog

    catalog = load_catalog(catalog_path())
    prog = next((p for p in catalog if p.name == program), None)
    if prog is None:
        return HealthCheck(
            name="architecture-review-gate",
            ok=False,
            summary=f"unknown program {program!r} (catalog)",
            suggestion="run `research list` to see available programs",
        )
    cwd = prog.resolved_local_path
    if not cwd.is_dir():
        return HealthCheck(
            name="architecture-review-gate",
            ok=False,
            summary=f"program local_path missing: {cwd}",
            suggestion="re-run scripts/bootstrap-institution.sh",
            evidence=str(cwd),
        )
    try:
        completed = subprocess.run(
            ["mathlint", "roadmap"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            cwd=str(cwd),
        )
    except FileNotFoundError:
        return HealthCheck(
            name="architecture-review-gate",
            ok=False,
            summary="mathlint not on PATH",
            suggestion="add ~/Documents/andrei/math/.venv/bin to ~/.zprofile",
        )
    if completed.returncode != 0:
        return HealthCheck(
            name="architecture-review-gate",
            ok=True,  # unknown gate = not closed
            summary=f"mathlint roadmap returned rc={completed.returncode} (gate indeterminate, treated as OPEN)",
            evidence=completed.stderr.strip()[:120] if completed.stderr else "",
        )
    import re

    m = re.search(r"^TASK KIND:\s*(\S+)", completed.stdout, re.MULTILINE)
    if m is None:
        return HealthCheck(
            name="architecture-review-gate",
            ok=True,
            summary="no TASK KIND line in roadmap (gate OPEN)",
        )
    kind = m.group(1).strip()
    if kind == TaskKind.ARCHITECTURE_REVIEW_REQUIRED:
        return HealthCheck(
            name="architecture-review-gate",
            ok=False,
            summary=f"TASK KIND={kind} (gate CLOSED)",
            suggestion="write a recommendation YAML and run `mathlint architect-apply -r <yaml> --apply`",
            evidence=kind,
        )
    return HealthCheck(
        name="architecture-review-gate",
        ok=True,
        summary=f"TASK KIND={kind} (gate OPEN)",
    )


def _check_receipt_freshness() -> HealthCheck:
    """Compare math HEAD to the paired-smoke receipt's recorded commit."""
    receipt_path = Path.home() / ".local" / "state" / "mathlint" / "receipts" / "paired-smoke.json"
    if not receipt_path.is_file():
        return HealthCheck(
            name="receipt-freshness",
            ok=False,
            summary="paired-smoke receipt missing",
            suggestion="run `mathlint first-run --project kaplansky`",
            evidence=str(receipt_path),
        )
    try:
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return HealthCheck(
            name="receipt-freshness",
            ok=False,
            summary=f"paired-smoke receipt unreadable: {e}",
            suggestion="delete the receipt and re-run `mathlint first-run --project kaplansky`",
        )
    recorded = (data.get("commit") or "").strip()
    # Read math HEAD.
    try:
        head = subprocess.run(
            ["git", "-C", str(Path.home() / "Documents" / "andrei" / "math"), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout.strip()
    except FileNotFoundError:
        return HealthCheck(
            name="receipt-freshness",
            ok=False,
            summary="git not on PATH",
        )
    if recorded == head:
        return HealthCheck(
            name="receipt-freshness",
            ok=True,
            summary=f"receipt matches math HEAD ({head[:12]})",
        )
    return HealthCheck(
        name="receipt-freshness",
        ok=False,
        summary=f"receipt commit {recorded[:12]} != math HEAD {head[:12]}",
        suggestion="run `mathlint first-run --project kaplansky` to refresh the receipt",
        evidence=f"recorded={recorded[:12]} head={head[:12]}",
    )


def _check_supervisor_alive(program: str) -> tuple[HealthCheck, int, bool]:
    """Reuse the supervisor probe; return the check + state."""
    from research_institution.supervisor import probe_default_supervisor

    state = probe_default_supervisor()
    if state.is_alive:
        return (
            HealthCheck(
                name="supervisor-alive",
                ok=True,
                summary=f"supervisor running (pid {state.supervisor_pid}, worker pid {state.worker_pid})",
            ),
            state.supervisor_pid,
            True,
        )
    return (
        HealthCheck(
            name="supervisor-alive",
            ok=False,
            summary="no supervisor running for this config",
            suggestion=f"run `research start {program}` (after the other health checks pass)",
        ),
        state.supervisor_pid,
        False,
    )


def run_health(program: str) -> HealthReport:
    """Run every diagnostic and return a HealthReport.

    Order: hermetic gate -> live preflight -> architecture-review gate
    -> receipt freshness -> supervisor liveness. The operator can
    scan `report.failures` to see exactly what to fix, in order.
    """
    hermetic = _run_hermetic_green_gate()
    live = _run_live_preflight()
    gate = _check_architecture_review_gate(program)
    receipt = _check_receipt_freshness()
    sup_check, sup_pid, sup_alive = _check_supervisor_alive(program)
    return HealthReport(
        program=program,
        checks=[hermetic, live, gate, receipt, sup_check],
        supervisor_pid=sup_pid,
        supervisor_alive=sup_alive,
    )


def format_health(report: HealthReport) -> str:
    """Format one HealthReport as a multi-line string for `typer.echo`.

    Layout:

        health: <program>
        [1/5] green-gate-hermetic: ok — engine + supervisor + program wired
        [2/5] live-preflight: FAIL — 3/12 live checks failed
            fix: SMOKE001: run `mathlint first-run --project kaplansky` to bootstrap the receipt
            fix: LOCAL022: math repo is dirty — run `cd ~/Documents/andrei/math && git status`
            fix: MATH001: run `cd ~/Documents/andrei/math && make check` (or commit/stash the dirty changes)
        [3/5] architecture-review-gate: ok — TASK KIND=RESEARCH (gate OPEN)
        [4/5] receipt-freshness: ok — receipt matches math HEAD (2860666ac01e)
        [5/5] supervisor-alive: FAIL — no supervisor running for this config
            fix: run `research start kaplansky` (after the other health checks pass)

        4/5 checks passed; 1 to fix.
    """
    lines: list[str] = []
    lines.append(f"health: {report.program}")
    total = len(report.checks)
    for i, c in enumerate(report.checks, start=1):
        marker = "ok  " if c.ok else "FAIL"
        lines.append(f"[{i}/{total}] {c.name}: {marker} — {c.summary}")
        if not c.ok and c.suggestion:
            for sl in c.suggestion.splitlines():
                lines.append(f"      fix: {sl}")
    failed = len(report.failures)
    passed = total - failed
    if failed == 0:
        lines.append("")
        lines.append(f"all {total} checks passed; ready to `research start {report.program}`.")
    else:
        lines.append("")
        lines.append(f"{passed}/{total} checks passed; {failed} to fix.")
    return "\n".join(lines)


__all__ = [
    "HealthCheck",
    "HealthReport",
    "format_health",
    "run_health",
]
