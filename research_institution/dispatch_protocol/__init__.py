"""Typed-only dispatch envelope package — see :mod:`.envelope` for the contract.

This package re-exports the canonical dispatch envelope types from
:mod:`pi_monitor.work_source` under :data:`TYPE_CHECKING`. It ships a
PEP 561 ``py.typed`` marker so pyright treats its symbols as first-class.

No runtime code lives here. Do not import from this package at runtime;
import :mod:`pi_monitor.work_source` directly if you actually need the
classes. This package exists so the institution's OS-layer code and the
math kernel can share static types without crossing runtime import
boundaries.

The package lives at ``research_institution.dispatch_protocol`` so it
shares the institution's identity. Math-engine, which per `@ADR-0014`
must not runtime-import siblings, references its symbols under
``TYPE_CHECKING`` only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from research_institution.dispatch_protocol.envelope import (
        DECISION_KIND,
        Dispatch,
        OperatorRequired,
        ReasonCode,
        SourceDecision,
        SourceRevision,
        Stop,
        Wait,
        WorkRequest,
        WorkSourceDecision,
    )

__all__ = [
    "DECISION_KIND",
    "Dispatch",
    "OperatorRequired",
    "ReasonCode",
    "SourceDecision",
    "SourceRevision",
    "Stop",
    "Wait",
    "WorkRequest",
    "WorkSourceDecision",
]
