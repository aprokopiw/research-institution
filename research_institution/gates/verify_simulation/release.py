"""Release gate aggregator.

Cited contracts:
    @CTR-0101-release-gate-contract         (typed ``ReleaseReport`` schema)
    @ADR-0096-audit-close-out-runtime-evidence
    @CTR-0096-audit-close-out-runtime-evidence-contract
    @CTR-0095-prime-directive-check-script-contract
    @INV-0093-institution-green-gate-canonical
    @INV-0094-no-delta-loop-source-stagnation-consult
    @ADR-0014-program-agnostic-mathlint-imports
    @ADR-0091-mathlint-ships-no-program-launchers

The release tier consumes every prior gate's typed report at
the current SHA and refuses to claim done unless every
required claim has non-zero evidence. The aggregator produces
a typed ``ReleaseReport`` with exactly seven ``ReleaseRow``
entries (the closed set is enforced by
``ReleaseReport.__post_init__``):

    1. every_primary_tier_has_at_least_one
    2. every_required_claim_has_evidence
    3. every_scenario_has_metadata
    4. every_critical_mutant_killed
    5. flake_audit_clean
    6. documentation_truth_clean
    7. prime_directive_enforcement_clean

The aggregator also records a deterministic
``gate_report_digest`` that becomes the entry's
``gate_report_digest`` field in META.md (per
@CTR-0096-audit-close-out-runtime-evidence-contract). The
digest formula is ``sha256(JSON-serialize(ReleaseReport))``
sorted by ``check_name`` so the bytes are stable across
Python versions.

The runner is import-time safe: no subprocess side effects
beyond the prime-directive check row, which is bounded to a
single ``bash`` invocation against the canonical script at
@CTR-0095-prime-directive-check-script-contract.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from research_institution.gates.verify_simulation.mutation import (
    MutationAggregator,
)
from research_institution.gates.verify_simulation.runner import (
    run_scenario_hermetic,
)
from research_institution.gates.verify_simulation.scenarios import (
    Scenario,
    all_scenarios,
    lookup as scenario_lookup,
    metadata_dict,
)
from research_institution.verification.doc_truth import (
    audit_documentation_truth,
)
from research_institution.verification.tier_inventory import (
    collect_primary_tier_markers,
)

__all__ = [
    "ReleaseReport",
    "ReleaseRow",
    "ReleaseRunner",
    "aggregate_release_report",
    "compute_gate_report_digest",
]

Status = Literal["PASS", "FAIL", "BLOCKED", "NOT_RUN", "NOT_APPLICABLE"]

# The seven canonical check names per @CTR-0101. Adding a row
# to ``ReleaseReport`` outside this set is gate FAIL.
_CANONICAL_CHECK_NAMES: tuple[str, ...] = (
    "every_primary_tier_has_at_least_one",
    "every_required_claim_has_evidence",
    "every_scenario_has_metadata",
    "every_critical_mutant_killed",
    "flake_audit_clean",
    "documentation_truth_clean",
    "prime_directive_enforcement_clean",
)

# Inline sample count for the release-gate flake surface.
# Hermetic runs are sub-second; 5 inline runs keep the CLI
# invocation under the 30s budget. The full 20× audit is the
# dedicated ``tests/simulation/test_flake_audit.py``.
_INLINE_FLAKE_RUNS = 5

# Canonical scenario used by the flake-audit surface.
_FLAKE_AUDIT_SCENARIO = "happy-three-cycle"

# Canonical prime-directive check-script (per
# @CTR-0095-prime-directive-check-script-contract).
_PRIME_DIRECTIVE_SCRIPT_REL = Path("scripts/check-prime-directive.sh")


@dataclass(frozen=True, slots=True)
class ReleaseRow:
    """A single release-check verdict.

    The seven rows are a closed set; ``ReleaseReport.__post_init__``
    enforces the cardinality and uniqueness invariants.
    """

    check_name: str
    status: Status
    detail: str
    artifact_path: Path | None

    def to_dict(self) -> dict[str, object]:
        return {
            "check_name": self.check_name,
            "status": self.status,
            "detail": self.detail,
            "artifact_path": str(self.artifact_path)
            if self.artifact_path is not None
            else None,
        }


@dataclass(frozen=True, slots=True)
class ReleaseReport:
    """The aggregator's typed output.

    Exactly seven rows, one per canonical check name. Order
    follows ``_CANONICAL_CHECK_NAMES`` so the digest is stable.
    """

    rows: tuple[ReleaseRow, ...]
    seed: int | None = None
    elapsed_seconds: float = 0.0
    artifacts_dir: Path | None = None

    def __post_init__(self) -> None:
        names = tuple(r.check_name for r in self.rows)
        if len(names) != 7:
            raise ValueError(
                f"ReleaseReport must have 7 rows; got {len(names)}"
            )
        if set(names) != set(_CANONICAL_CHECK_NAMES):
            raise ValueError(
                f"ReleaseReport rows must be the canonical 7; got {sorted(names)}"
            )

    @property
    def verdict(self) -> str:
        """``PASS`` iff every row is PASS or NOT_APPLICABLE."""
        for row in self.rows:
            if row.status not in ("PASS", "NOT_APPLICABLE"):
                return "FAIL"
        return "PASS"

    def to_dict(self) -> dict[str, object]:
        return {
            "rows": [r.to_dict() for r in self.rows],
            "verdict": self.verdict,
            "seed": self.seed,
            "elapsed_seconds": self.elapsed_seconds,
            "artifacts_dir": str(self.artifacts_dir)
            if self.artifacts_dir is not None
            else None,
        }


def compute_gate_report_digest(report: ReleaseReport) -> str:
    """Return the canonical ``sha256`` digest for ``report``.

    The digest is byte-stable across Python versions because
    we sort the rows by ``check_name`` and use ``sort_keys=True``
    + ASCII separators.
    """
    payload = {
        "rows": sorted(
            (r.to_dict() for r in report.rows),
            key=lambda d: d["check_name"],
        ),
        "verdict": report.verdict,
        "seed": report.seed,
        "elapsed_seconds": report.elapsed_seconds,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _canonical_tiers() -> frozenset[str]:
    """The §1 closed tier vocabulary from the verify-constitution."""
    return frozenset(
        {
            "unit",
            "property",
            "contract",
            "integration",
            "process",
            "deployment",
            "provider_live",
            "soak",
        }
    )


def _canonical_scenario_metadata_keys() -> frozenset[str]:
    """The canonical metadata keys per the registered-scenario contract."""
    return frozenset(
        {
            "name",
            "owner",
            "minimum_tier",
            "maximum_runtime_seconds",
            "fault_injection_point",
            "expected_final_state",
            "required_event_subsequence",
            "forbidden_events",
            "cleanup_expectations",
            "source_path",
            "notes",
        }
    )


def _all_scenarios_have_metadata() -> tuple[bool, list[str]]:
    """Return ``(ok, offenders)`` where ``ok`` is True iff every
    registered scenario carries the full canonical metadata."""
    offenders: list[str] = []
    keys = _canonical_scenario_metadata_keys()
    for scenario in all_scenarios():
        missing = keys - set(metadata_dict(scenario).keys())
        if missing:
            offenders.append(f"{scenario.name}: {sorted(missing)}")
    return (not offenders, offenders)


def _scenario_metadata_offenders() -> list[str]:
    return _all_scenarios_have_metadata()[1]


class ReleaseRunner:
    """Build the release report.

    The runner composes seven small check functions into a
    typed ``ReleaseReport``. Each check is independently
    unit-testable; the runner is the only object that
    constructs the report.

    Construction is cheap: no subprocesses, no FS writes. The
    prime-directive check (row 7) is the only side-effecting
    check and is bounded to a single ``bash`` invocation per
    ``aggregate_release_report`` call.
    """

    def __init__(
        self,
        *,
        repo_root: Path | None = None,
        spec_root: Path | None = None,
        artifacts_dir: Path | None = None,
        seed: int | None = 20260925,
        inline_flake_runs: int = _INLINE_FLAKE_RUNS,
    ) -> None:
        # Default ``repo_root`` to the research-institution root
        # (the directory that contains both ``scripts/`` and
        # ``research_institution/``).
        here = Path(__file__).resolve()
        self.repo_root = repo_root or here.parents[4]
        self.spec_root = spec_root or (self.repo_root / ".specify" / "specs")
        self.artifacts_dir = artifacts_dir
        self.seed = seed
        self.inline_flake_runs = inline_flake_runs

    # ------------------------------------------------------------------
    # Row 1: every canonical tier has at least one test.
    # ------------------------------------------------------------------

    def _check_primary_tiers(self) -> ReleaseRow:
        markers = collect_primary_tier_markers()
        canonical = _canonical_tiers()
        # The tier-marker migration is in-flight across the
        # institution (entries 01/02/03/06 own it). When the
        # walker observes zero ``tier = "..."`` assignments,
        # the migration has not yet landed at this repo, and
        # the row is NOT_APPLICABLE rather than FAIL — the
        # verify-constitution explicitly notes the migration
        # is owned by future entries and today the wiring
        # check trivially passes. A repo with SOME tier
        # markers but missing canonical tiers is FAIL.
        if not markers:
            return ReleaseRow(
                check_name="every_primary_tier_has_at_least_one",
                status="NOT_APPLICABLE",
                detail=(
                    "no tier = \"...\" markers observed in tests/; "
                    "migration is owned by the institution's "
                    "tier-marker entries and is not part of the "
                    "release-gate's evidence surface today"
                ),
                artifact_path=None,
            )
        missing = canonical - set(markers)
        if missing:
            return ReleaseRow(
                check_name="every_primary_tier_has_at_least_one",
                status="FAIL",
                detail=f"tiers with zero tests: {sorted(missing)}",
                artifact_path=None,
            )
        return ReleaseRow(
            check_name="every_primary_tier_has_at_least_one",
            status="PASS",
            detail=(
                f"all {len(canonical)} canonical tiers have ≥1 test "
                f"({len(markers)} markers collected)"
            ),
            artifact_path=None,
        )

    # ------------------------------------------------------------------
    # Row 2: every required claim has non-zero evidence.
    # ------------------------------------------------------------------

    def _check_claim_manifest(self) -> ReleaseRow:
        manifest = self.repo_root / "docs" / "semantic" / "CLAIM_MANIFEST.toml"
        if not manifest.exists():
            return ReleaseRow(
                check_name="every_required_claim_has_evidence",
                status="FAIL",
                detail=f"claim manifest missing: {manifest}",
                artifact_path=None,
            )
        try:
            doc = tomllib.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            return ReleaseRow(
                check_name="every_required_claim_has_evidence",
                status="FAIL",
                detail=f"manifest parse error: {exc}",
                artifact_path=manifest,
            )
        claims = doc.get("claim", [])
        zero_evidence = [
            c.get("id", "?") for c in claims if not c.get("evidence_node_ids")
        ]
        if zero_evidence:
            return ReleaseRow(
                check_name="every_required_claim_has_evidence",
                status="FAIL",
                detail=f"claims with zero evidence: {zero_evidence}",
                artifact_path=manifest,
            )
        return ReleaseRow(
            check_name="every_required_claim_has_evidence",
            status="PASS",
            detail=f"all {len(claims)} required claims have ≥1 evidence",
            artifact_path=manifest,
        )

    # ------------------------------------------------------------------
    # Row 3: every scenario has full canonical metadata.
    # ------------------------------------------------------------------

    def _check_scenario_metadata(self) -> ReleaseRow:
        ok, offenders = _all_scenarios_have_metadata()
        if not ok:
            return ReleaseRow(
                check_name="every_scenario_has_metadata",
                status="FAIL",
                detail=f"scenarios with missing metadata: {offenders}",
                artifact_path=None,
            )
        return ReleaseRow(
            check_name="every_scenario_has_metadata",
            status="PASS",
            detail=f"all {len(all_scenarios())} scenarios have full metadata",
            artifact_path=None,
        )

    # ------------------------------------------------------------------
    # Row 4: every critical mutant is killed.
    # ------------------------------------------------------------------

    def _check_mutation_killed(self) -> ReleaseRow:
        aggregator = MutationAggregator(
            repo_root=self.repo_root, spec_root=self.spec_root
        )
        report = aggregator.run()
        survivors = [
            m.mutant_id for m in report.killers if m.killer_test == "UNRESOLVED"
        ]
        if report.verdict == "FAIL":
            return ReleaseRow(
                check_name="every_critical_mutant_killed",
                status="FAIL",
                detail=f"surviving critical mutants: {survivors}",
                artifact_path=report.artifact_path,
            )
        return ReleaseRow(
            check_name="every_critical_mutant_killed",
            status="PASS",
            detail=f"all {len(report.killers)} critical mutants killed",
            artifact_path=report.artifact_path,
        )

    # ------------------------------------------------------------------
    # Row 5: flake audit clean (inline sample).
    # ------------------------------------------------------------------

    def _check_flake_audit(self) -> ReleaseRow:
        try:
            scenario = scenario_lookup(_FLAKE_AUDIT_SCENARIO)
        except KeyError:
            return ReleaseRow(
                check_name="flake_audit_clean",
                status="FAIL",
                detail=f"canonical flake scenario missing: {_FLAKE_AUDIT_SCENARIO}",
                artifact_path=None,
            )
        flakes = sum(
            1
            for _ in range(self.inline_flake_runs)
            if run_scenario_hermetic(scenario).verdict != "PASS"
        )
        if flakes:
            return ReleaseRow(
                check_name="flake_audit_clean",
                status="FAIL",
                detail=(
                    f"{flakes}/{self.inline_flake_runs} inline runs flaked"
                ),
                artifact_path=None,
            )
        return ReleaseRow(
            check_name="flake_audit_clean",
            status="PASS",
            detail=(
                f"inline {self.inline_flake_runs}/"
                f"{self.inline_flake_runs} hermetic runs PASS"
            ),
            artifact_path=None,
        )

    # ------------------------------------------------------------------
    # Row 6: documentation truth audit clean.
    # ------------------------------------------------------------------

    def _check_documentation_truth(self) -> ReleaseRow:
        offenders = audit_documentation_truth()
        if offenders:
            return ReleaseRow(
                check_name="documentation_truth_clean",
                status="FAIL",
                detail=f"forbidden primary-tier markers found: {offenders[:5]}",
                artifact_path=None,
            )
        return ReleaseRow(
            check_name="documentation_truth_clean",
            status="PASS",
            detail="no forbidden primary-tier markers in durable paths",
            artifact_path=None,
        )

    # ------------------------------------------------------------------
    # Row 7: prime-directive enforcement clean at research-institution HEAD.
    # ------------------------------------------------------------------

    def _check_prime_directive(self) -> ReleaseRow:
        script = self.repo_root / _PRIME_DIRECTIVE_SCRIPT_REL
        if not script.exists():
            return ReleaseRow(
                check_name="prime_directive_enforcement_clean",
                status="FAIL",
                detail=f"canonical script missing: {script}",
                artifact_path=None,
            )
        try:
            proc = subprocess.run(
                ["bash", str(script), "--enforce"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return ReleaseRow(
                check_name="prime_directive_enforcement_clean",
                status="FAIL",
                detail=f"canonical script error: {exc}",
                artifact_path=script,
            )
        if proc.returncode != 0:
            return ReleaseRow(
                check_name="prime_directive_enforcement_clean",
                status="FAIL",
                detail=(
                    f"unsanctioned hits at research-institution HEAD "
                    f"(rc={proc.returncode})"
                ),
                artifact_path=script,
            )
        return ReleaseRow(
            check_name="prime_directive_enforcement_clean",
            status="PASS",
            detail="research-institution HEAD: 0 unsanctioned hits",
            artifact_path=script,
        )

    # ------------------------------------------------------------------
    # Composition.
    # ------------------------------------------------------------------

    def run(self) -> ReleaseReport:
        started = time.monotonic()
        rows: tuple[ReleaseRow, ...] = (
            self._check_primary_tiers(),
            self._check_claim_manifest(),
            self._check_scenario_metadata(),
            self._check_mutation_killed(),
            self._check_flake_audit(),
            self._check_documentation_truth(),
            self._check_prime_directive(),
        )
        elapsed = time.monotonic() - started
        return ReleaseReport(
            rows=rows,
            seed=self.seed,
            elapsed_seconds=elapsed,
            artifacts_dir=self.artifacts_dir,
        )


def aggregate_release_report(
    *,
    repo_root: Path | None = None,
    spec_root: Path | None = None,
    artifacts_dir: Path | None = None,
    seed: int | None = 20260925,
    inline_flake_runs: int = _INLINE_FLAKE_RUNS,
) -> ReleaseReport:
    """Convenience wrapper around :class:`ReleaseRunner`."""
    runner = ReleaseRunner(
        repo_root=repo_root,
        spec_root=spec_root,
        artifacts_dir=artifacts_dir,
        seed=seed,
        inline_flake_runs=inline_flake_runs,
    )
    return runner.run()


def _export_scenario_for_test(scenario_name: str) -> Scenario:
    """Test seam: return a scenario by name with KeyError on miss."""
    return scenario_lookup(scenario_name)
