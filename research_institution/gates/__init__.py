"""Canonical institution gates, implemented in Python.

This package replaces the previous shell-script aggregation. Every
gate is a pure-Python function with testable inputs and outputs,
delegating to subprocess only when a sibling-repo CLI is the
genuine seam (mathlint, pi_monitor, kaplansky).

Re-exports:
    bootstrap_install   - clone + pip-install every catalog entry
                          + dev deps (mathlint, pi_monitor)
    check_institution   - run every gate in the catalog; return
                          an aggregated GateReport
    RunResult           - subprocess outcome dataclass
    GateReport          - aggregated gate verdict dataclass
"""

from research_institution.gates.bootstrap import bootstrap_install
from research_institution.gates.aggregate import (
    GateReport,
    GateStatus,
    check_institution,
)
from research_institution.gates.runner import RunResult, run

__all__ = [
    "GateReport",
    "GateStatus",
    "RunResult",
    "bootstrap_install",
    "check_institution",
    "run",
]
