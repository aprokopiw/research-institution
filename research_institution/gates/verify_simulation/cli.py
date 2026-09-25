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
)


def build_parser() -> argparse.ArgumentParser:
    """Return the canonical argparse parser."""
    parser = argparse.ArgumentParser(
        prog="research_institution verify-simulation",
        description=(
            "Entry 06 composed autonomous simulation harness. "
            "Runs the 14 canonical scenarios + five oracles."
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


if __name__ == "__main__":
    sys.exit(main())
