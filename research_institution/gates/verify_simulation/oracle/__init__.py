"""Independent oracles for the verify-simulation harness (entry 06 M2).

The five oracles are independent by construction — each oracle
inspects a different facet of the run:

    * ``transcript`` — event subsequence + forbidden events.
    * ``audit`` — hash chain verification.
    * ``exactly_once`` — per (source_identity, operation_id,
      revision_fingerprint) invariants.
    * ``frontier`` — frontier revision changes at expected events.
    * ``resource`` — subprocess count returns to baseline.

A scenario PASSES only when every oracle reports ``PASS``. A
single ``FAIL`` is sufficient to flag the run.
"""

from research_institution.gates.verify_simulation.oracle.transcript import (
    TranscriptReport,
    transcript_oracle,
)
from research_institution.gates.verify_simulation.oracle.audit import (
    AuditReport,
    audit_oracle,
)
from research_institution.gates.verify_simulation.oracle.exactly_once import (
    ExactlyOnceReport,
    exactly_once_oracle,
)
from research_institution.gates.verify_simulation.oracle.frontier import (
    FrontierReport,
    frontier_oracle,
)
from research_institution.gates.verify_simulation.oracle.resource import (
    ResourceReport,
    resource_oracle,
)

OracleReport = (
    TranscriptReport
    | AuditReport
    | ExactlyOnceReport
    | FrontierReport
    | ResourceReport
)

__all__ = [
    "AuditReport",
    "ExactlyOnceReport",
    "FrontierReport",
    "OracleReport",
    "ResourceReport",
    "TranscriptReport",
    "audit_oracle",
    "exactly_once_oracle",
    "frontier_oracle",
    "resource_oracle",
    "transcript_oracle",
]
