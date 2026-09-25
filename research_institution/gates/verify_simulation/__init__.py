"""verify-simulation package — entry 06 composed autonomous simulation.

Per `.specify/specs/06-autonomous-composed-simulation/spec.md` FR-1,
the package provides:

  * ``cli`` — Typer entry point with verb
    ``--tier {fast|full|process|deployment|provider-canary|soak}``.
  * ``runner`` — orchestrates a temp deployment root + pi-monitor
    subprocess + fake-Pi subprocess + sample program, emitting a
    typed ``ScenarioReport``.
  * ``temp_root`` — disposable temp_root_factory with
    cleanup-on-success + preserve-on-failure semantics.
  * ``scenarios`` — registry of the 14 canonical scenarios
    (six entry-04 + eight entry-05).
  * ``oracle`` — five independent oracles (transcript, audit,
    exactly-once, frontier, resource).

Public API re-exports:

    from research_institution.gates.verify_simulation import (
        cli, runner, temp_root, scenarios, oracle,
        Scenario, ScenarioReport, OracleReport,
    )
"""

from research_institution.gates.verify_simulation.oracle import (
    AuditReport,
    ExactlyOnceReport,
    FrontierReport,
    OracleReport,
    ResourceReport,
    TranscriptReport,
)
from research_institution.gates.verify_simulation.scenarios import (
    Scenario,
    lookup as scenario_lookup,
    register as scenario_register,
)
from research_institution.gates.verify_simulation.temp_root import (
    TempRoot,
    temp_root_factory,
)
from research_institution.gates.verify_simulation.runner import (
    ScenarioReport,
    run_scenario,
    run_scenario_hermetic,
)

__all__ = [
    "AuditReport",
    "ExactlyOnceReport",
    "FrontierReport",
    "OracleReport",
    "ResourceReport",
    "Scenario",
    "ScenarioReport",
    "TempRoot",
    "TranscriptReport",
    "run_scenario",
    "run_scenario_hermetic",
    "scenario_lookup",
    "scenario_register",
    "temp_root_factory",
]
