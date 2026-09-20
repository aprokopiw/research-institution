"""Closed stringly-typed vocabularies for research-institution DTOs.

Public-surface re-export façade. The actual enum definitions live in
`vocabulary.py`; the gate-verdict parser lives in `gate_verdict.py`.
Splitting these keeps each module single-purpose (vocabularies are
pure data, gate_verdict has parsing logic) and breaks the circular
import that would otherwise arise (gate_verdict → vocab → __init__).

Every string that crosses a boundary lives here as a `StrEnum`. New
values require adding a member to the enum (single-place edit,
exhaustively checked by type checkers and runtime guards).
"""

from __future__ import annotations

# Vocabularies: pure-data StrEnums.
from research_institution.contracts.vocabulary import (  # noqa: E402
    DispatcherVerb,
    ExitCode,
    GateVerdictStatus,
    TaskKind,
    gate_verdict_from_task_kind,
)

# Architecture-review gate verdict (pure domain type + parser).
from research_institution.contracts.gate_verdict import (  # noqa: E402
    GateVerdict,
    TASK_KIND_ABSENT,
    TASK_KIND_ROADMAP_FAILED,
)

__all__ = [
    "DispatcherVerb",
    "ExitCode",
    "GateVerdict",
    "GateVerdictStatus",
    "TASK_KIND_ABSENT",
    "TASK_KIND_ROADMAP_FAILED",
    "TaskKind",
    "gate_verdict_from_task_kind",
]
