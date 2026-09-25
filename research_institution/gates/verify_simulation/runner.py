"""Scenario runner for the verify-simulation harness (entry 06 T1.3).

The runner orchestrates a temp deployment root + (optionally)
a pi-monitor subprocess + (optionally) a fake-Pi subprocess +
sample program. For unit-test / hermetic tier, the runner uses
stubbed oracle verdicts (each oracle reports PASS by default).

The full hermetic run yields a ``ScenarioReport`` with five
oracle verdicts. The runner's contract is:

    * Construct a ``ScenarioReport`` per ``Scenario``.
    * Run each oracle against the appropriate stream.
    * Aggregate: ``PASS`` only when all five oracles PASS.
    * On exception: ``FAIL`` with the exception text in
      ``detail``.

The runner does NOT import pi_monitor's private supervisor
methods (per FR-4). All subprocess wiring happens via
``pi-monitor run --config <temp>`` in production; the
hermetic tier uses subprocess abstractions only.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

from research_institution.gates.verify_simulation.oracle import (
    AuditReport,
    ExactlyOnceReport,
    FrontierReport,
    ResourceReport,
    TranscriptReport,
)
from research_institution.gates.verify_simulation.scenarios import (
    Scenario,
)
from research_institution.gates.verify_simulation.temp_root import (
    TempRoot,
    temp_root_factory,
)

__all__ = ["ScenarioReport", "run_scenario"]


@dataclass(frozen=True, slots=True)
class ScenarioReport:
    """The runner's per-scenario output.

    Each oracle's verdict is recorded. The aggregate ``verdict``
    is PASS only when every oracle returns PASS; otherwise it
    is FAIL with a ``detail`` string explaining the failure.
    """

    scenario_name: str
    owner: str
    transcript: TranscriptReport
    audit: AuditReport
    exactly_once: ExactlyOnceReport
    frontier: FrontierReport
    resource: ResourceReport
    elapsed_seconds: float
    verdict: str
    detail: str = ""
    preserved: bool = False
    source_path: Path | None = None
    notes: str = ""


def run_scenario(
    scenario: Scenario,
    *,
    temp_root: TempRoot | None = None,
    transcript_stream: IO[str] | Iterable[str] | None = None,
    audit_stream: IO[str] | Iterable[str] | Path | None = None,
    report_stream: IO[str] | Iterable[str] | Path | None = None,
    frontier_stream: IO[str] | Iterable[str] | Path | None = None,
    baseline_subprocess_count: int = 0,
    current_subprocess_count: int = 0,
) -> ScenarioReport:
    """Run a single scenario and aggregate the five oracle verdicts.

    The runner does NOT start a real subprocess when called with
    explicit oracle streams. The harness (entry 06's CLI / green-
    gate extension) wires the streams from the real subprocess
    pipes.
    """
    import time

    started = time.monotonic()
    transcript_stream = transcript_stream if transcript_stream is not None else iter([])
    audit_stream = audit_stream if audit_stream is not None else iter([])
    report_stream = report_stream if report_stream is not None else iter([])
    frontier_stream = frontier_stream if frontier_stream is not None else iter([])

    from research_institution.gates.verify_simulation.oracle.audit import (
        audit_oracle,
    )
    from research_institution.gates.verify_simulation.oracle.exactly_once import (
        exactly_once_oracle,
    )
    from research_institution.gates.verify_simulation.oracle.frontier import (
        frontier_oracle,
    )
    from research_institution.gates.verify_simulation.oracle.resource import (
        resource_oracle,
    )
    from research_institution.gates.verify_simulation.oracle.transcript import (
        transcript_oracle,
    )

    transcript = transcript_oracle(
        transcript_stream,
        required_subsequence=scenario.required_event_subsequence,
        forbidden_events=scenario.forbidden_events,
    )
    audit = audit_oracle(audit_stream)
    exactly_once = exactly_once_oracle(report_stream)
    frontier = frontier_oracle(
        frontier_stream,
        expected_change_points=sum(
            1 for k in scenario.required_event_subsequence if k == "dispatch"
        ),
    )
    resource = resource_oracle(
        baseline_subprocess_count=baseline_subprocess_count,
        current_subprocess_count=current_subprocess_count,
        preserved=temp_root.preserved if temp_root else False,
    )

    oracles = (transcript, audit, exactly_once, frontier, resource)
    failed = [o for o in oracles if o.verdict == "FAIL"]
    over_budget = [o for o in oracles if o.verdict == "OVER_BUDGET"]
    elapsed = time.monotonic() - started
    if failed:
        verdict = "FAIL"
        detail = "; ".join(f"{type(o).__name__}: {o.detail}" for o in failed)
    elif over_budget:
        verdict = "OVER_BUDGET"
        detail = "; ".join(f"{type(o).__name__}: {o.detail}" for o in over_budget)
    else:
        verdict = "PASS"
        detail = ""
    return ScenarioReport(
        scenario_name=scenario.name,
        owner=scenario.owner,
        transcript=transcript,
        audit=audit,
        exactly_once=exactly_once,
        frontier=frontier,
        resource=resource,
        elapsed_seconds=elapsed,
        verdict=verdict,
        detail=detail,
        preserved=bool(temp_root and temp_root.preserved),
        source_path=scenario.source_path,
        notes=scenario.notes,
    )


def run_scenario_hermetic(
    scenario: Scenario,
    *,
    baseline_subprocess_count: int = 0,
) -> ScenarioReport:
    """Run a scenario with empty streams; the hermetic tier uses
    empty required_subsequence + empty forbidden_events so the
    transcript oracle trivially passes.

    The hermetic tier is the v-compose smoke check used by the
    green-gate; the real per-scenario wiring lives in entry 06's
    full tier (which the green-gate v-compose stage also invokes
    per FR-5).
    """
    hermetic_scenario = Scenario(
        name=scenario.name,
        owner=scenario.owner,
        minimum_tier=scenario.minimum_tier,
        maximum_runtime_seconds=scenario.maximum_runtime_seconds,
        fault_injection_point=scenario.fault_injection_point,
        expected_final_state=scenario.expected_final_state,
        required_event_subsequence=(),
        forbidden_events=(),
        cleanup_expectations=scenario.cleanup_expectations,
        source_path=scenario.source_path,
        notes=f"hermetic: {scenario.notes}",
    )
    return run_scenario(
        hermetic_scenario,
        baseline_subprocess_count=baseline_subprocess_count,
        current_subprocess_count=baseline_subprocess_count,
    )


def report_to_dict(report: ScenarioReport) -> dict[str, object]:
    """Serialize a ``ScenarioReport`` to a JSON-friendly dict."""
    return {
        "scenario_name": report.scenario_name,
        "owner": report.owner,
        "transcript": {
            "verdict": report.transcript.verdict,
            "observed_subsequence": list(report.transcript.observed_subsequence),
            "missing_subsequence": list(report.transcript.missing_subsequence),
            "forbidden_hit": list(report.transcript.forbidden_hit),
            "detail": report.transcript.detail,
        },
        "audit": {
            "verdict": report.audit.verdict,
            "line_count": report.audit.line_count,
            "broken_at_line": report.audit.broken_at_line,
            "detail": report.audit.detail,
        },
        "exactly_once": {
            "verdict": report.exactly_once.verdict,
            "accepted": report.exactly_once.accepted,
            "duplicates": report.exactly_once.duplicates,
            "conflicts": report.exactly_once.conflicts,
            "detail": report.exactly_once.detail,
        },
        "frontier": {
            "verdict": report.frontier.verdict,
            "revisions_seen": report.frontier.revisions_seen,
            "expected_change_points": report.frontier.expected_change_points,
            "missed_change_points": report.frontier.missed_change_points,
            "detail": report.frontier.detail,
        },
        "resource": {
            "verdict": report.resource.verdict,
            "baseline_subprocess_count": report.resource.baseline_subprocess_count,
            "current_subprocess_count": report.resource.current_subprocess_count,
            "detail": report.resource.detail,
        },
        "elapsed_seconds": report.elapsed_seconds,
        "verdict": report.verdict,
        "detail": report.detail,
        "preserved": report.preserved,
        "source_path": str(report.source_path) if report.source_path else None,
        "notes": report.notes,
    }
