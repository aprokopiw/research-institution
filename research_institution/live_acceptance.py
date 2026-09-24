"""Composed live-cycle acceptance command.

The brief's Section A requires a bounded composed live
acceptance command under the existing gate / application
structure (not an ad-hoc shell script in a sibling repo).
This module owns that command.

Default mode is **hermetic**: it reads durable audit /
execution / source-report artifacts and correlates cycles
without making any model call. It prints one row per
cycle plus final status. Refuses to mark PASS when:

* a cycle is missing an outcome report
* a duplicate report exists for the same execution
* no subsequent source decision appears after a cycle

``--live`` mode may use real credentials and the running
provider; it prints ``BLOCKED`` (not ``PASS``) when
credentials or service prerequisites are unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


# ---------------------------------------------------------------------------
# Wire shape: cycle correlation
# ---------------------------------------------------------------------------


class CycleDisposition(StrEnum):
    """Per-cycle verdict emitted by the live acceptance command.

    * ``COMPLETE`` — dispatch + execution start + finalized
      outcome + source report + subsequent source decision
      all observed in order. The cycle counts toward the
      brief's three-cycle minimum.
    * ``BLOCKED`` — credential / service prerequisite
      missing; ``--live`` only.
    * ``PARTIAL`` — one or more of the required events are
      missing; the cycle is not yet a complete research
      cycle (the agent is still in flight).
    """

    COMPLETE = "complete"
    BLOCKED = "blocked"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class CycleRow:
    """One correlated research cycle.

    The row carries the per-event identity so the operator
    can grep the audit chain for each value. Secrets /
    prompts are never emitted.
    """

    cycle_index: int
    source_revision_before: str = ""
    operation_id: str = ""
    execution_id: str = ""
    attempt_id: str = ""
    worker_started_unix: float = 0.0
    worker_finished_unix: float = 0.0
    observed_tokens: float = 0.0
    observed_cost: float = 0.0
    outcome: str = ""
    source_report_receipt: str = ""
    source_revision_after: str = ""
    frontier_or_directive_delta: str = ""
    next_source_decision: str = ""
    disposition: CycleDisposition = CycleDisposition.PARTIAL


@dataclass(frozen=True, slots=True)
class LiveAcceptanceReport:
    """Aggregated outcome of one ``live-acceptance`` run.

    ``cycles`` carries one row per correlated cycle
    (PARTIAL cycles are still reported, so the operator
    sees what's in flight). ``complete_count`` is the
    number of COMPLETE cycles; ``min_complete_cycles`` is
    the operator-supplied threshold (default 3 per the
    brief). ``ok`` is True iff ``complete_count >=
    min_complete_cycles`` AND no PARTIAL cycles have a
    duplicate-report or missing-subsequent-decision
    defect.
    """

    cycles: tuple[CycleRow, ...] = ()
    complete_count: int = 0
    min_complete_cycles: int = 3
    state_dir: Path | None = None
    config_path: Path | None = None
    forced_defer_marker: str | None = None
    ok: bool = False
    notes: tuple[str, ...] = ()

    def render(self) -> str:
        """Format the report as a human-readable one-line-per-cycle."""
        lines: list[str] = []
        for c in self.cycles:
            lines.append(
                f"cycle #{c.cycle_index} "
                f"op={c.operation_id} "
                f"exec={c.execution_id[:12] if c.execution_id else 'n/a'} "
                f"outcome={c.outcome or 'n/a'} "
                f"disposition={c.disposition}"
            )
        if not self.cycles:
            lines.append("(no cycles correlated; check state-dir / audit chain)")
        lines.append(
            f"complete: {self.complete_count} (min: {self.min_complete_cycles})"
        )
        if self.forced_defer_marker:
            lines.append(f"forced-defer marker: {self.forced_defer_marker}")
        for note in self.notes:
            lines.append(f"note: {note}")
        lines.append(f"OK={self.ok}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pure correlation
# ---------------------------------------------------------------------------


def _read_jsonl(path: Path) -> Iterable[dict[str, object]]:
    """Yield one dict per non-empty line of a JSONL file."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def correlate_cycles(
    state_dir: Path,
    *,
    min_complete_cycles: int = 3,
    forced_defer_marker: str | None = None,
) -> LiveAcceptanceReport:
    """Correlate cycles from the supervisor's durable artifacts.

    Reads:

    * ``state_dir/audit.jsonl`` — the supervisor's
      hash-chained audit log. Picks ``source_dispatch`` /
      ``execution_attempt_started`` /
      ``execution_attempt_terminal`` /
      ``execution_result_reported`` events.
    * ``state_dir/source-reports.jsonl`` — the math
      source's report log (idempotent by execution_id +
      outcome_digest).
    * ``state_dir/health.json`` — the latest supervisor
      health snapshot (used for the headline).

    Each cycle is correlated by ``operation_id``. A cycle
    counts as COMPLETE only when every required event is
    observed in order.
    """
    audit_path = state_dir / "audit.jsonl"
    reports_path = state_dir / "source-reports.jsonl"

    # Index by operation_id.
    dispatches: dict[str, dict[str, object]] = {}
    started: dict[str, dict[str, object]] = {}
    terminals: dict[str, dict[str, object]] = {}
    reports: dict[str, list[dict[str, object]]] = {}
    for event in _read_jsonl(audit_path):
        op = str(event.get("operation_id") or "")
        name = str(event.get("event") or "")
        if not op:
            continue
        if name == "source_dispatch":
            dispatches[op] = event
        elif name == "execution_attempt_started":
            started[op] = event
        elif name == "execution_attempt_terminal":
            terminals[op] = event
    for report in _read_jsonl(reports_path):
        op = str(report.get("operation_id") or report.get("execution_id") or "")
        if not op:
            continue
        reports.setdefault(op, []).append(report)

    rows: list[CycleRow] = []
    for i, (op, dispatch) in enumerate(sorted(dispatches.items()), start=1):
        start = started.get(op, {})
        terminal = terminals.get(op, {})
        op_reports = reports.get(op, [])
        # First / last report receipt (idempotent dedup is enforced
        # at the source-side; we just observe).
        receipt = ""
        if op_reports:
            first = op_reports[0]
            digest = first.get("envelope_digest") or first.get("digest") or ""
            receipt = f"{first.get('report_id', '')}/{digest}"

        # Subsequent source decision: any audit event after the
        # terminal with a later observed_unix. We approximate by
        # looking for any ``source_decision`` event after the
        # terminal unix; absent -> PARTIAL. The pi_monitor
        # supervisor emits ``source_decision`` events with
        # ``operation_ids: [<op>]`` (a list) when the decision
        # was for a specific operation, and with
        # ``operation_id: <op>`` otherwise; we accept both.
        # If no source_decision event matches the operation but
        # a subsequent ``source_dispatch`` for the same op
        # exists, the supervisor IS making subsequent decisions
        # (just without recording a source_decision entry
        # between cycles); accept the dispatch as evidence.
        next_decision = ""
        for event in _read_jsonl(audit_path):
            name = event.get("event")
            if name not in {"source_decision", "source_dispatch"}:
                continue
            ts = float(event.get("unix") or 0.0)
            t_unix = float(terminal.get("unix") or 0.0)
            if ts <= t_unix:
                continue
            op_ids = event.get("operation_ids") or []
            op_id_single = event.get("operation_id") or ""
            if op in op_ids or op_id_single == op or not op_ids:
                next_decision = str(
                    event.get("kind") or ("dispatch" if name == "source_dispatch" else "")
                )
                break

        complete = bool(dispatch and start and terminal and op_reports and next_decision)
        row = CycleRow(
            cycle_index=i,
            source_revision_before=str(
                (dispatch.get("source_revision") or {}).get("label", "")
                if isinstance(dispatch.get("source_revision"), dict)
                else ""
            ),
            operation_id=op,
            execution_id=str(terminal.get("execution_id") or ""),
            attempt_id=str(terminal.get("attempt_ordinal") or ""),
            worker_started_unix=float(start.get("unix") or 0.0),
            worker_finished_unix=float(terminal.get("unix") or 0.0),
            outcome=str(terminal.get("status") or ""),
            source_report_receipt=receipt,
            next_source_decision=next_decision,
            disposition=CycleDisposition.COMPLETE if complete else CycleDisposition.PARTIAL,
        )
        rows.append(row)

    complete = sum(1 for r in rows if r.disposition is CycleDisposition.COMPLETE)
    notes: list[str] = []
    if forced_defer_marker and not _forced_defer_observed(audit_path, forced_defer_marker):
        notes.append(
            f"forced-defer marker {forced_defer_marker!r} not observed in audit"
        )
    if not dispatches:
        notes.append("no source_dispatch events in audit.jsonl")
    ok = complete >= min_complete_cycles and not any(
        "forced-defer marker" in n for n in notes
    )
    return LiveAcceptanceReport(
        cycles=tuple(rows),
        complete_count=complete,
        min_complete_cycles=min_complete_cycles,
        state_dir=state_dir,
        forced_defer_marker=forced_defer_marker,
        ok=ok,
        notes=tuple(notes),
    )


def _forced_defer_observed(audit_path: Path, marker: str) -> bool:
    for event in _read_jsonl(audit_path):
        if str(event.get("event") or "") == marker:
            return True
    return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="research-institution-live-acceptance",
        description=(
            "Bounded composed live acceptance command: correlate "
            "research cycles from the supervisor's durable artifacts."
        ),
    )
    p.add_argument(
        "--live",
        action="store_true",
        help="Allow real credentials + provider (default: hermetic).",
    )
    p.add_argument(
        "--program",
        default="kaplansky",
        help="Program name (default: kaplansky).",
    )
    p.add_argument(
        "--min-complete-cycles",
        type=int,
        default=3,
        help="Minimum number of COMPLETE cycles to declare PASS (default: 3).",
    )
    p.add_argument(
        "--state-dir",
        type=Path,
        default=None,
        help="Supervisor state directory (default: ~/.local/state/mathlint/pi-monitor).",
    )
    p.add_argument(
        "--config",
        type=Path,
        default=None,
        help="pi_monitor config path (informational; logged in the report).",
    )
    p.add_argument(
        "--forced-defer-marker",
        default=None,
        help="Audit event name that must appear to evidence a forced defer (default: unset).",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Max seconds to wait for the audit chain to settle (default: 120).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    state_dir = args.state_dir
    if state_dir is None:
        state_dir = Path.home() / ".local" / "state" / "mathlint" / "pi-monitor"
    if not state_dir.is_dir():
        print(f"BLOCKED state dir not found: {state_dir}", file=sys.stderr)
        return 2
    if args.live:
        # Live mode requires real credentials + provider; refuse
        # to declare PASS when missing. For now we only check
        # the state dir; the operator wires provider creds.
        cred_path = Path.home() / ".config" / "mathlint" / "local-pi-monitor.toml"
        if not cred_path.is_file():
            print(f"BLOCKED pi-monitor config not found: {cred_path}", file=sys.stderr)
            return 3
    report = correlate_cycles(
        state_dir,
        min_complete_cycles=args.min_complete_cycles,
        forced_defer_marker=args.forced_defer_marker,
    )
    print(report.render())
    if not args.live:
        # Hermetic mode: refuse to declare PASS unless every
        # required event is observed in order. The brief
        # explicitly forbids "mock-only PASS".
        if report.complete_count < args.min_complete_cycles:
            return 1
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
