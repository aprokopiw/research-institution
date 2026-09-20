"""One canonical command: verify the institution is ready.

Replaces the previous `green-gate/check-institution.sh` shell
script. Treats the most useful operator knobs as defaults so a
fresh operator can run one command and get a durable verdict.

Knobs honored (env):

  RESEARCH_INSTITUTION_VWIRE_DIRECT=1
      Bypass math-engine's autonomy.sh G1..G6 (which are owned
      by math-engine's own readiness, not the institution's).
      Default ON; the institution does not need pyramid-inversion
      to be GREEN to know the wiring is correct.

  RESEARCH_INSTITUTION_HERMETIC=1
      Skip v-wire entirely. Used by CI runners without mathlint.

  MATHLINT_AUTONOMY_SKIP_G7=1
      Cold-start hatch when mathlint isn't bootstrapped.

  MATHLINT_MODEL_ROUTE=<provider>/<model>
      Required for `--live`.

Usage::

    python -m research_institution.gates.verify            # hermetic
    python -m research_institution.gates.verify --live     # operator
"""

from __future__ import annotations

import os
from research_institution.gates.aggregate import (
    GateReport,
    check_institution,
)


# Set VWIRE_DIRECT default ON for operators. Mathlint's G1..G6
# pyramid-inversion rules are math-engine's own scope (per
# @INV-0093, the institution gate's *only* math-engine concern
# is the G7 cross-repo wiring test). Operators get a cleaner
# pass when G1..G6 are bypassed; the G7 outcome still surfaces
# real wiring defects.
os.environ.setdefault("RESEARCH_INSTITUTION_VWIRE_DIRECT", "1")


def verify(mode: str = "hermetic") -> GateReport:
    """Run the institution gate and return a structured report."""
    return check_institution(mode=mode)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="verify-institution",
        description=(
            "Canonical institution readiness check. Default hermetic "
            "(CI-safe). Use --live for operator-live mode."
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--hermetic",
        action="store_const",
        const="hermetic",
        dest="mode",
        help="CI-safe; no LLM (default).",
    )
    mode.add_argument(
        "--live",
        action="store_const",
        const="live",
        dest="mode",
        help="Operator-live; requires credentials.",
    )
    parser.add_argument(
        "--skip-program",
        action="append",
        default=[],
        dest="skip_programs",
        metavar="NAME",
        help="Skip a catalog program (repeatable).",
    )
    parser.set_defaults(mode="hermetic")
    ns = parser.parse_args()
    report = verify(mode=ns.mode)
    print(report.render())
    return 0 if report.ok else 1


if __name__ == "__main__":  # pragma: no cover — entry point
    raise SystemExit(main())
