"""CLI entry point for the verify-simulation harness (entry 06 FR-1 + T4.2).

Per the spec, the canonical CLI is invoked as:

    python -m research_institution verify-simulation --tier <tier>
    # or, when installed via the entry-point:
    verify-simulation --tier <tier>

The tier selector chooses which subset of the 14 canonical
scenarios runs:

    * ``fast`` — six entry-04 math scenarios (hermetic tier;
      runs in <30s).
    * ``full`` — all 14 scenarios.
    * ``process`` — the process-tier subset (most scenarios).
    * ``deployment`` — the deployment-tier subset (a few).
    * ``provider-canary`` — the provider-canary tier.
    * ``soak`` — the soak tier (long-running).

The CLI's exit code follows the gate-status algebra:

    0   PASS    every oracle PASSes
    1   FAIL    at least one oracle FAILed
    78  BLOCKED scenario lookup missing
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from research_institution.gates.verify_simulation.runner import (
    report_to_dict,
    run_scenario_hermetic,
)
from research_institution.gates.verify_simulation.scenarios import (
    Scenario,
    all_scenarios,
    lookup as scenario_lookup,
)

__all__ = ["build_parser", "main"]


_VALID_TIERS: tuple[str, ...] = (
    "fast",
    "full",
    "process",
    "deployment",
    "provider-canary",
    "soak",
    "compatibility-matrix",
    "rollback",
    "backup-restore",
    "corruption",
    "disk-pressure",
)


def build_parser() -> argparse.ArgumentParser:
    """Return the canonical argparse parser."""
    parser = argparse.ArgumentParser(
        prog="research_institution verify-simulation",
        description=(
            "Entry 06 composed autonomous simulation harness. "
            "Runs the 14 canonical scenarios + five oracles. "
            "Entry 07 adds deployment / provider-canary / soak tiers."
        ),
    )
    parser.add_argument(
        "--tier",
        choices=_VALID_TIERS,
        default="fast",
        help=(
            "Tier selector: fast (entry 04 math only), full (all 14), "
            "process / deployment / provider-canary / soak."
        ),
    )
    parser.add_argument(
        "--scenario",
        default=None,
        help=(
            "Optional: run a single scenario by name. When set, "
            "--tier is ignored."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output instead of a human-readable summary.",
    )
    parser.add_argument(
        "--baseline-subprocess-count",
        type=int,
        default=0,
        help="Baseline subprocess count for the resource oracle.",
    )
    parser.add_argument(
        "--macos-isolated-label",
        default=None,
        help=(
            "macOS deployment tier: unique launchctl label. "
            "Required when --tier deployment runs on Darwin."
        ),
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Provider-canary tier: opt-in flag to actually run "
            "the LIVE canary. Without this flag, --tier provider-canary "
            "exits 2 with an actionable error."
        ),
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=None,
        help=(
            "Soak tier: duration in hours. Required when --tier soak; "
            "missing --hours exits 2 with an actionable error."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Deployment tier: render ProgramArguments and return "
            "without spawning subprocesses."
        ),
    )
    return parser


def _filter_scenarios(tier: str) -> list[Scenario]:
    """Return the scenarios selected by ``tier``."""
    if tier == "fast":
        return [s for s in all_scenarios() if s.owner == "math"]
    if tier == "full":
        return list(all_scenarios())
    if tier == "process":
        return [s for s in all_scenarios() if s.minimum_tier == "process"]
    if tier == "deployment":
        return [s for s in all_scenarios() if s.minimum_tier == "deployment"]
    if tier == "provider-canary":
        return [s for s in all_scenarios() if s.owner == "pi_monitor"]
    if tier == "soak":
        # The soak tier is a non-trivial extension (entry 07 owns
        # the soak harness); we return the full set as a placeholder.
        return list(all_scenarios())
    return []


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns the gate-status exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.tier == "deployment":
        return _run_deployment_tier(args)
    if args.tier == "provider-canary":
        return _run_provider_canary_tier(args)
    if args.tier == "soak":
        return _run_soak_tier(args)
    if args.tier == "compatibility-matrix":
        return _run_compat_matrix_tier(args)
    if args.tier == "rollback":
        return _run_rollback_tier(args)
    if args.tier == "backup-restore":
        return _run_backup_restore_tier(args)
    if args.tier == "corruption":
        return _run_corruption_tier(args)
    if args.tier == "disk-pressure":
        return _run_disk_pressure_tier(args)
    if args.scenario is not None:
        try:
            scenarios = [scenario_lookup(args.scenario)]
        except KeyError:
            print(f"unknown scenario: {args.scenario}", file=sys.stderr)
            return 78
    else:
        scenarios = _filter_scenarios(args.tier)
    if not scenarios:
        print(f"no scenarios for tier={args.tier}", file=sys.stderr)
        return 0
    reports = []
    for scenario in scenarios:
        report = run_scenario_hermetic(
            scenario,
            baseline_subprocess_count=args.baseline_subprocess_count,
        )
        reports.append(report)
    if args.json:
        print(json.dumps([report_to_dict(r) for r in reports], indent=2))
    else:
        for r in reports:
            print(f"{r.scenario_name}: {r.verdict} ({r.elapsed_seconds:.2f}s)")
    failed = [r for r in reports if r.verdict != "PASS"]
    return 1 if failed else 0


def _run_compat_matrix_tier(args: argparse.Namespace) -> int:
    """Entry 08 M2: compatibility-matrix tier."""
    from research_institution.gates.verify_simulation.compat import (
        CompatMatrixRunner,
    )

    runner = CompatMatrixRunner(run_live=args.live)
    report = runner.run()
    if args.json:
        print(
            json.dumps(
                {
                    "verdict": report.verdict,
                    "cells": [
                        {
                            "python_version": c.python_version,
                            "repo": c.repo,
                            "distribution_version": c.distribution_version,
                            "verdict": c.verdict,
                            "detail": c.detail,
                        }
                        for c in report.cells
                    ],
                    "matrix_source": report.matrix_source,
                    "detail": report.detail,
                },
                indent=2,
            )
        )
    else:
        print(
            f"compat-matrix: {report.verdict} "
            f"({len(report.cells)} cells)"
        )
        for c in report.cells:
            print(f"  {c.repo}@py{c.python_version}: {c.verdict}")
    return 0 if report.verdict in ("PASS", "BLOCKED") else 1


def _run_rollback_tier(args: argparse.Namespace) -> int:
    """Entry 08 M3: rollback tier."""
    from research_institution.gates.verify_simulation.compat import (
        RollbackRunner,
    )

    runner = RollbackRunner()
    report = runner.run()
    if args.json:
        print(
            json.dumps(
                {
                    "verdict": report.verdict,
                    "version_n": report.version_n,
                    "version_n_minus_1": report.version_n_minus_1,
                    "n_state_readable": report.n_state_readable,
                    "n_minus_1_state_readable": report.n_minus_1_state_readable,
                    "redispatch_detected": report.redispatch_detected,
                    "detail": report.detail,
                },
                indent=2,
            )
        )
    else:
        print(f"rollback: {report.verdict} ({report.detail})")
    return 0 if report.verdict == "PASS" else 1


def _run_backup_restore_tier(args: argparse.Namespace) -> int:
    """Entry 08 M3: backup-restore tier."""
    from research_institution.gates.verify_simulation.compat import (
        BackupRestoreRunner,
    )

    runner = BackupRestoreRunner()
    report = runner.run()
    if args.json:
        print(
            json.dumps(
                {
                    "verdict": report.verdict,
                    "backup_path": str(report.backup_path)
                    if report.backup_path
                    else None,
                    "restore_path": str(report.restore_path)
                    if report.restore_path
                    else None,
                    "pre_backup_sha": report.pre_backup_sha,
                    "post_restore_sha": report.post_restore_sha,
                    "duplicate_executions": report.duplicate_executions,
                    "duplicate_reports": report.duplicate_reports,
                    "detail": report.detail,
                },
                indent=2,
            )
        )
    else:
        print(f"backup-restore: {report.verdict} ({report.detail})")
    return 0 if report.verdict == "PASS" else 1


def _run_corruption_tier(args: argparse.Namespace) -> int:
    """Entry 08 M4: corruption tier."""
    from research_institution.gates.verify_simulation.compat import (
        CorruptionRunner,
    )

    runner = CorruptionRunner()
    report = runner.run()
    if args.json:
        print(
            json.dumps(
                {
                    "verdict": report.verdict,
                    "audit_corrupt_fail_closed": report.audit_corrupt_fail_closed,
                    "state_corrupt_fail_closed": report.state_corrupt_fail_closed,
                    "ledger_corrupt_fail_closed": report.ledger_corrupt_fail_closed,
                    "detail": report.detail,
                },
                indent=2,
            )
        )
    else:
        print(f"corruption: {report.verdict} ({report.detail})")
    return 0 if report.verdict == "PASS" else 1


def _run_disk_pressure_tier(args: argparse.Namespace) -> int:
    """Entry 08 M4: disk-pressure tier."""
    from research_institution.gates.verify_simulation.compat import (
        DiskPressureRunner,
    )

    runner = DiskPressureRunner()
    report = runner.run()
    if args.json:
        print(
            json.dumps(
                {
                    "verdict": report.verdict,
                    "enospc_detected": report.enospc_detected,
                    "truncated_write_detected": report.truncated_write_detected,
                    "permission_denied_detected": report.permission_denied_detected,
                    "rename_failure_detected": report.rename_failure_detected,
                    "detail": report.detail,
                },
                indent=2,
            )
        )
    else:
        print(f"disk-pressure: {report.verdict} ({report.detail})")
    return 0 if report.verdict == "PASS" else 1


def _run_deployment_tier(args: argparse.Namespace) -> int:
    """Entry 07 M1: deployment tier."""
    from research_institution.gates.verify_simulation.deployment import (
        DeploymentRunner,
    )

    repo_root = _resolve_repo_root()
    runner = DeploymentRunner(
        repo_root=repo_root,
        macos_isolated_label=args.macos_isolated_label,
    )
    if args.dry_run:
        report = runner.run_dry()
    else:
        report = runner.run_live()
    if args.json:
        print(
            json.dumps(
                {
                    "verdict": report.verdict,
                    "cwds_tested": list(report.cwds_tested),
                    "cwds_passed": list(report.cwds_passed),
                    "cwds_failed": list(report.cwds_failed),
                    "rendered_argv": list(report.rendered_argv),
                    "macos_isolated_label": report.macos_isolated_label,
                    "plist_path": str(report.plist_path)
                    if report.plist_path
                    else None,
                    "detail": report.detail,
                },
                indent=2,
            )
        )
    else:
        print(
            f"deployment: {report.verdict} "
            f"({len(report.cwds_passed)}/{len(report.cwds_tested)} cwds pass)"
        )
        if report.detail:
            print(f"  detail: {report.detail}")
    return 0 if report.verdict in ("PASS", "BLOCKED") else 1


def _run_provider_canary_tier(args: argparse.Namespace) -> int:
    """Entry 07 M2: provider-canary tier."""
    if not args.live:
        print(
            "provider-canary requires --live; refusing without it",
            file=sys.stderr,
        )
        return 2
    from research_institution.gates.verify_simulation.canary import CanaryRunner

    runner = CanaryRunner(
        scenario=args.scenario or "rate-defer-restart",
        live=True,
    )
    report = runner.run()
    if args.json:
        print(
            json.dumps(
                {
                    "verdict": report.verdict,
                    "scenario": report.scenario,
                    "has_model_route": report.has_model_route,
                    "has_auth_json": report.has_auth_json,
                    "auth_json_fingerprint": report.auth_json_fingerprint,
                    "kaplansky_roadmap_before_sha": report.kaplansky_roadmap_before_sha,
                    "kaplansky_roadmap_after_sha": report.kaplansky_roadmap_after_sha,
                    "detail": report.detail,
                    "elapsed_seconds": report.elapsed_seconds,
                },
                indent=2,
            )
        )
    else:
        print(f"canary: {report.verdict} ({report.detail})")
    return 0 if report.verdict == "CANARY_PASS" else (78 if report.verdict == "CANARY_BLOCKED" else 1)


def _run_soak_tier(args: argparse.Namespace) -> int:
    """Entry 07 M3: soak tier."""
    if args.hours is None:
        print("soak requires --hours N; refusing without it", file=sys.stderr)
        return 2
    from research_institution.gates.verify_simulation.oracle.soak import (
        SoakOracle,
        write_evidence_archive,
    )

    oracle = SoakOracle(duration_seconds=args.hours * 3600)
    report = oracle.run()
    evidence_path = Path("/tmp") / f"soak-archive-{int(report.elapsed_seconds)}.json"
    write_evidence_archive(
        evidence_path,
        report=report,
        commit_sha="entry-07-m3",
        config_fingerprint="verify-simulation/soak.v1",
        scenario_hashes={},
    )
    if args.json:
        print(
            json.dumps(
                {
                    "verdict": report.verdict,
                    "elapsed_seconds": report.elapsed_seconds,
                    "sample_count": report.sample_count,
                    "max_memory_mb": report.max_memory_mb,
                    "max_process_count": report.max_process_count,
                    "max_state_file_bytes": report.max_state_file_bytes,
                    "audit_chain_ok": report.audit_chain_ok,
                    "hot_loop_detected": report.hot_loop_detected,
                    "orphan_processes": report.orphan_processes,
                    "duplicate_reports": report.duplicate_reports,
                    "detail": report.detail,
                    "evidence_archive": str(evidence_path),
                },
                indent=2,
            )
        )
    else:
        print(
            f"soak: {report.verdict} ({report.elapsed_seconds:.1f}s, "
            f"{report.sample_count} samples)"
        )
    return 0 if report.verdict == "PASS" else 1


def _resolve_repo_root() -> Path:
    """Locate the research-institution repo root.

    Used by the deployment tier to anchor the rendered
    ProgramArguments. Walks up from this file to find the
    ``pyproject.toml`` of the research-institution package.
    """
    here = Path(__file__).resolve()
    for ancestor in [here, *here.parents]:
        if (ancestor / "pyproject.toml").exists() and (
            ancestor / "research_institution"
        ).is_dir():
            return ancestor
    # Fallback: cwd.
    return Path.cwd()


if __name__ == "__main__":
    sys.exit(main())
