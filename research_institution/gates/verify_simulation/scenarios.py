"""Scenario registry for the verify-simulation harness (entry 06 T3.1).

Per FR-6, every scenario carries a metadata dict with the canonical
keys. Per T3.3, scenarios are referenced (NOT copied) from entry 04
(math self_test sample) and entry 05 (pi_monitor substrate). The
registry's ``register`` + ``lookup`` are the canonical surface.

The 14 canonical scenarios ship in this module:

  Six from entry 04:
    happy-three-cycle, no-delta-redirect, blocked-alternate-route,
    source-wait-then-work, operator-required, stop-completion

  Eight from entry 05:
    rate-defer-restart, worker-very-fast, worker-slow-but-active,
    malformed-result, worker-crash-before-publication,
    source-crash-before-report-ack, execution-restart-after-publication,
    duplicate-conflicting-report
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["Scenario", "lookup", "register", "all_scenarios"]


@dataclass(frozen=True, slots=True)
class Scenario:
    """A canonical scenario + its metadata (FR-6)."""

    name: str
    owner: str  # "math" | "pi_monitor"
    minimum_tier: str  # "process" | "deployment" | etc.
    maximum_runtime_seconds: int
    fault_injection_point: str
    expected_final_state: str
    required_event_subsequence: tuple[str, ...]
    forbidden_events: tuple[str, ...]
    cleanup_expectations: tuple[str, ...] = (
        "temp_root_cleanup_on_success",
        "preserve_on_failure",
    )
    source_path: Path | None = None
    notes: str = ""


# ---------------------------------------------------------------------------
# Built-in scenarios (the 14 canonical).
# ---------------------------------------------------------------------------

_BUILTIN_SCENARIOS: dict[str, Scenario] = {}


def register(
    name: str,
    *,
    owner: str,
    minimum_tier: str = "process",
    maximum_runtime_seconds: int = 90,
    fault_injection_point: str = "",
    expected_final_state: str = "",
    required_event_subsequence: tuple[str, ...] = (),
    forbidden_events: tuple[str, ...] = (),
    cleanup_expectations: tuple[str, ...] = (
        "temp_root_cleanup_on_success",
        "preserve_on_failure",
    ),
    source_path: Path | None = None,
    notes: str = "",
) -> Scenario:
    """Register a canonical scenario under ``name``.

    Returns the registered ``Scenario`` so the caller can also
    hold a direct reference. Re-registering the same name overwrites
    the prior registration (the harness treats re-registration as a
    test-only override).
    """
    scenario = Scenario(
        name=name,
        owner=owner,
        minimum_tier=minimum_tier,
        maximum_runtime_seconds=maximum_runtime_seconds,
        fault_injection_point=fault_injection_point,
        expected_final_state=expected_final_state,
        required_event_subsequence=required_event_subsequence,
        forbidden_events=forbidden_events,
        cleanup_expectations=cleanup_expectations,
        source_path=source_path,
        notes=notes,
    )
    _BUILTIN_SCENARIOS[name] = scenario
    return scenario


def lookup(name: str) -> Scenario:
    """Return the scenario registered under ``name``.

    Raises :class:`KeyError` if the scenario is unknown. The
    verify-simulation runner catches ``KeyError`` and emits a
    typed error in the report.
    """
    return _BUILTIN_SCENARIOS[name]


def all_scenarios() -> tuple[Scenario, ...]:
    """Return all registered scenarios (deterministic order)."""
    return tuple(_BUILTIN_SCENARIOS[n] for n in sorted(_BUILTIN_SCENARIOS))


def _register_builtins() -> None:
    """Register the 14 canonical scenarios.

    The metadata is the canonical source-of-truth for FR-6. The
    underlying scenario JSON lives at entry 04's
    ``math/src/mathlint/self_test/sample_program/scenarios/``;
    this registry references them by relative path (T3.3).
    """
    base = Path("math/src/mathlint/self_test/sample_program/scenarios")
    entry04 = [
        Scenario(
            name="happy-three-cycle",
            owner="math",
            minimum_tier="process",
            maximum_runtime_seconds=30,
            fault_injection_point="none",
            expected_final_state="stop",
            required_event_subsequence=("dispatch", "dispatch", "dispatch", "stop"),
            forbidden_events=("operator_required",),
            source_path=base / "happy-three-cycle.json",
            notes="entry 04 sample; reference-by-path per T3.3",
        ),
        Scenario(
            name="no-delta-redirect",
            owner="math",
            minimum_tier="process",
            maximum_runtime_seconds=30,
            fault_injection_point="no-delta-after-2-cycles",
            expected_final_state="stop",
            required_event_subsequence=("dispatch", "dispatch", "dispatch", "stop"),
            forbidden_events=(),
            source_path=base / "no-delta-redirect.json",
            notes="entry 04 sample; reference-by-path per T3.3",
        ),
        Scenario(
            name="blocked-alternate-route",
            owner="math",
            minimum_tier="process",
            maximum_runtime_seconds=30,
            fault_injection_point="block-cycle-0",
            expected_final_state="stop",
            required_event_subsequence=("dispatch", "dispatch", "dispatch", "stop"),
            forbidden_events=(),
            source_path=base / "blocked-alternate-route.json",
            notes="entry 04 sample; reference-by-path per T3.3",
        ),
        Scenario(
            name="source-wait-then-work",
            owner="math",
            minimum_tier="process",
            maximum_runtime_seconds=60,
            fault_injection_point="wait-cycle-1",
            expected_final_state="stop",
            required_event_subsequence=("dispatch", "wait", "dispatch", "stop"),
            forbidden_events=(),
            source_path=base / "source-wait-then-work.json",
            notes="entry 04 sample; reference-by-path per T3.3",
        ),
        Scenario(
            name="operator-required",
            owner="math",
            minimum_tier="process",
            maximum_runtime_seconds=30,
            fault_injection_point="operator-required-cycle-1",
            expected_final_state="stop",
            required_event_subsequence=(
                "dispatch",
                "operator_required",
                "dispatch",
                "dispatch",
                "stop",
            ),
            forbidden_events=(),
            source_path=base / "operator-required.json",
            notes="entry 04 sample; reference-by-path per T3.3",
        ),
        Scenario(
            name="stop-completion",
            owner="math",
            minimum_tier="process",
            maximum_runtime_seconds=30,
            fault_injection_point="none",
            expected_final_state="stop",
            required_event_subsequence=("dispatch", "dispatch", "dispatch", "stop"),
            forbidden_events=(),
            source_path=base / "stop-completion.json",
            notes="entry 04 sample; reference-by-path per T3.3",
        ),
    ]
    entry05 = [
        Scenario(
            name="rate-defer-restart",
            owner="pi_monitor",
            minimum_tier="process",
            maximum_runtime_seconds=60,
            fault_injection_point="rate_defer_after_decision",
            expected_final_state="dispatch-after-wait",
            required_event_subsequence=("rate_defer", "wait", "dispatch"),
            forbidden_events=(),
            notes="entry 05 substrate; rate-defer path",
        ),
        Scenario(
            name="worker-very-fast",
            owner="pi_monitor",
            minimum_tier="process",
            maximum_runtime_seconds=15,
            fault_injection_point="fast_worker",
            expected_final_state="report-and-continue",
            required_event_subsequence=("dispatch", "report", "dispatch"),
            forbidden_events=(),
            notes="entry 05 substrate; fast-worker path",
        ),
        Scenario(
            name="worker-slow-but-active",
            owner="pi_monitor",
            minimum_tier="process",
            maximum_runtime_seconds=60,
            fault_injection_point="slow_worker",
            expected_final_state="report-and-continue",
            required_event_subsequence=("dispatch", "report", "dispatch"),
            forbidden_events=(),
            notes="entry 05 substrate; slow-worker path",
        ),
        Scenario(
            name="malformed-result",
            owner="pi_monitor",
            minimum_tier="process",
            maximum_runtime_seconds=30,
            fault_injection_point="malformed_report",
            expected_final_state="supervisor-rejected-malformed",
            required_event_subsequence=("dispatch", "report_malformed"),
            forbidden_events=(),
            notes="entry 05 substrate; malformed-report path",
        ),
        Scenario(
            name="worker-crash-before-publication",
            owner="pi_monitor",
            minimum_tier="process",
            maximum_runtime_seconds=30,
            fault_injection_point="crash_before_publication",
            expected_final_state="replay-on-restart",
            required_event_subsequence=("dispatch", "worker_crashed", "report_replay"),
            forbidden_events=(),
            notes="entry 05 substrate; worker-crash-before-publication path",
        ),
        Scenario(
            name="source-crash-before-report-ack",
            owner="pi_monitor",
            minimum_tier="process",
            maximum_runtime_seconds=30,
            fault_injection_point="source_crash_before_ack",
            expected_final_state="replay-on-restart",
            required_event_subsequence=("dispatch", "report", "source_crashed"),
            forbidden_events=(),
            notes="entry 05 substrate; source-crash-before-ack path",
        ),
        Scenario(
            name="execution-restart-after-publication",
            owner="pi_monitor",
            minimum_tier="process",
            maximum_runtime_seconds=60,
            fault_injection_point="restart_after_publication",
            expected_final_state="resume-without-replay",
            required_event_subsequence=("dispatch", "report", "restart", "dispatch"),
            forbidden_events=("duplicate_report",),
            notes="entry 05 substrate; restart-after-publication path",
        ),
        Scenario(
            name="duplicate-conflicting-report",
            owner="pi_monitor",
            minimum_tier="process",
            maximum_runtime_seconds=30,
            fault_injection_point="conflicting_duplicate",
            expected_final_state="idempotent-absorbing",
            required_event_subsequence=("dispatch", "report", "report_conflict"),
            forbidden_events=("redispatch",),
            notes="entry 05 substrate; idempotency + conflict path",
        ),
    ]
    for s in entry04 + entry05:
        register(
            s.name,
            owner=s.owner,
            minimum_tier=s.minimum_tier,
            maximum_runtime_seconds=s.maximum_runtime_seconds,
            fault_injection_point=s.fault_injection_point,
            expected_final_state=s.expected_final_state,
            required_event_subsequence=s.required_event_subsequence,
            forbidden_events=s.forbidden_events,
            cleanup_expectations=s.cleanup_expectations,
            source_path=s.source_path,
            notes=s.notes,
        )


_register_builtins()


def clear_registry() -> None:
    """Reset the registry (test seam)."""
    _BUILTIN_SCENARIOS.clear()
    _register_builtins()


def metadata_dict(scenario: Scenario) -> dict[str, Any]:
    """Return the metadata as a plain dict (FR-6)."""
    return {
        "name": scenario.name,
        "owner": scenario.owner,
        "minimum_tier": scenario.minimum_tier,
        "maximum_runtime_seconds": scenario.maximum_runtime_seconds,
        "fault_injection_point": scenario.fault_injection_point,
        "expected_final_state": scenario.expected_final_state,
        "required_event_subsequence": list(scenario.required_event_subsequence),
        "forbidden_events": list(scenario.forbidden_events),
        "cleanup_expectations": list(scenario.cleanup_expectations),
        "source_path": str(scenario.source_path) if scenario.source_path else None,
        "notes": scenario.notes,
    }
