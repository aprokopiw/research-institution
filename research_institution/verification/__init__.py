"""Production-side verification helpers.

Cited contracts:
    @CTR-0095-prime-directive-check-script-contract
    @INV-0093-institution-green-gate-canonical

This package houses pure-Python verification helpers that
both the release gate (in
``research_institution.gates.verify_simulation.release``) and
the static tests (in ``tests/static/``) import. Production
modules never import from ``tests/``; the dependency flows
the other way: tests import production helpers.
"""

from research_institution.verification.doc_truth import (
    audit_documentation_truth,
)
from research_institution.verification.tier_inventory import (
    collect_primary_tier_markers,
)

__all__ = [
    "audit_documentation_truth",
    "collect_primary_tier_markers",
]
