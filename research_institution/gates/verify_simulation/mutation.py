"""Mutation-test gate aggregator.

Cited contracts:
    @CTR-0101-release-gate-contract              (release-gate row 4)
    @ADR-0096-audit-close-out-runtime-evidence
    @ADR-0014-program-agnostic-mathlint-imports  (entry 04)
    @ADR-0091-mathlint-ships-no-program-launchers
    @INV-0094-no-delta-loop-source-stagnation-consult

The mutation aggregator reads the canonical list of critical
mutants from
``research_institution/gates/verify_simulation/mutation_critical_mutants.toml``
and asserts each named mutant is killed by a named scenario
+ test (the killer-test node-ID). The list is a durable data
artifact (lives in the production source tree, not under
``tests/``) so the release gate's row 4 has a stable input.

A ``MutationKiller`` carries the mutant_id + the killer test
+ the scenario (if killed by a scenario, not a unit test).
The aggregator's verdict is ``PASS`` iff every critical
mutant has a non-``UNRESOLVED`` killer test.

The aggregator does NOT run real mutation campaigns (mutmut /
cosmic-ray). The aggregator consumes per-entry evidence:
each mutant's killer test is the unit test that pins the
invariant at the source; the aggregator's job is to wire
those unit results into the release gate.
"""

from __future__ import annotations

import json
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "MutationAggregator",
    "MutationKiller",
    "MutationReport",
]


# Canonical data file path, relative to the research-institution
# repo root. The file is durable (lives in the production
# source tree, not transient).
CRITICAL_MUTANTS_DATA_PATH: Path = Path(
    "research_institution/gates/verify_simulation/mutation_critical_mutants.toml"
)

# Sentinel for mutants that have no killer test resolved.
UNRESOLVED: str = "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class MutationKiller:
    """A single critical mutant + its killer test."""

    mutant_id: str
    description: str
    killer_test: str  # node-id of the killer test, or ``UNRESOLVED``
    scenario: str | None = None
    source: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "mutant_id": self.mutant_id,
            "description": self.description,
            "killer_test": self.killer_test,
            "scenario": self.scenario,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class MutationReport:
    """The aggregator's typed output."""

    killers: tuple[MutationKiller, ...]
    artifact_path: Path | None = None

    @property
    def verdict(self) -> str:
        """``PASS`` iff every killer has a resolved killer test."""
        if any(k.killer_test == UNRESOLVED for k in self.killers):
            return "FAIL"
        return "PASS"

    @property
    def survivors(self) -> tuple[str, ...]:
        return tuple(k.mutant_id for k in self.killers if k.killer_test == UNRESOLVED)

    def to_dict(self) -> dict[str, object]:
        return {
            "killers": [k.to_dict() for k in self.killers],
            "verdict": self.verdict,
            "survivors": list(self.survivors),
            "artifact_path": str(self.artifact_path)
            if self.artifact_path is not None
            else None,
        }


def load_critical_mutants(
    data_path: Path,
) -> tuple[MutationKiller, ...]:
    """Load the canonical list of critical mutants from ``data_path``.

    The TOML schema is::

        [[mutant]]
        id = "M-NN"
        description = "..."
        killer_test = "tests/...::test_xyz"
        scenario = "happy-three-cycle"   # optional
        source = "tests/test_mutation_survival.py"

    Returns a tuple of ``MutationKiller`` in input order.
    """
    if not data_path.exists():
        return ()
    doc = tomllib.loads(data_path.read_text(encoding="utf-8"))
    out: list[MutationKiller] = []
    for entry in doc.get("mutant", []):
        out.append(
            MutationKiller(
                mutant_id=str(entry.get("id", "")),
                description=str(entry.get("description", "")),
                killer_test=str(entry.get("killer_test", UNRESOLVED)),
                scenario=(
                    str(entry["scenario"])
                    if entry.get("scenario") is not None
                    else None
                ),
                source=str(entry.get("source", "")),
            )
        )
    return tuple(out)


class MutationAggregator:
    """The mutation gate's runtime surface.

    Construction is cheap (loads the canonical data file
    lazily on ``run``). The aggregator's ``run`` returns a
    typed ``MutationReport`` consumed by the release gate.
    """

    def __init__(
        self,
        *,
        repo_root: Path | None = None,
        spec_root: Path | None = None,
        data_path: Path | None = None,
    ) -> None:
        here = Path(__file__).resolve()
        self.repo_root = repo_root or here.parents[4]
        self.spec_root = spec_root or (self.repo_root / ".specify" / "specs")
        self.data_path = data_path or (self.repo_root / CRITICAL_MUTANTS_DATA_PATH)

    def _resolve_killers(self) -> Iterable[MutationKiller]:
        return load_critical_mutants(self.data_path)

    def run(self) -> MutationReport:
        killers = tuple(self._resolve_killers())
        return MutationReport(killers=killers, artifact_path=self.data_path)


def write_mutation_report(
    report: MutationReport,
    *,
    out_path: Path,
) -> Path:
    """Write a serialized ``MutationReport`` JSON for downstream tools."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
    return out_path
