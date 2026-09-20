"""Typed dispatch envelope shared across the institution.

This module carries zero runtime logic. Its sole purpose is to provide
typed-only re-exports so that the math kernel, the institution's OS
provider, and any research program can share a single statically
typed view of the dispatch envelope without crossing runtime import
boundaries (`@ADR-0014`, `@ADR-0006`).

The runtime definitions live in `pi_monitor.work_source`. They are
re-exported here under :data:`TYPE_CHECKING` so that pyright/pylance
can resolve symbols, but the module remains runtime-free — meaning
a downstream package can import these types without paying any
runtime cost.

Wire-shape enforcement happens in two places:

* the dataclass field declarations themselves (compile-time check);
* the runtime codec in :mod:`pi_monitor.source_wire` (deserialisation
  rejects anything not declared in the dataclass).

The canonical reason-code vocabulary is exposed as a
:class:`ReasonCode` literal type so the dispatch surface cannot drift
to free-form strings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

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


if TYPE_CHECKING:
    # Runtime-free re-exports. These imports are evaluated by pyright
    # only; no runtime module is loaded by importing this package.
    # Per @ADR-0014 the math kernel must not import siblings at
    # runtime, but `TYPE_CHECKING` is a compile-time-only construct.
    from pi_monitor.work_source import (
        Dispatch,
        OperatorRequired,
        SourceRevision,
        Stop,
        Wait,
        WorkRequest,
    )

    #: One of the four sealed decision variants a work source may emit.
    #:
    #: This is a literal discriminator used by the runtime codec and the
    #: typed envelope package alike. The string values match the ``kind``
    #: field that appears on the wire.
    type DECISION_KIND = Literal["dispatch", "wait", "operator_required", "stop"]

    #: Canonical reason codes that dispatch envelopes may declare.
    #:
    #: These values are the ones recognised by built-in adapters
    #: (:data:`pi_monitor.work_source.REASON_*`). Program-specific codes
    #: are tolerated as opaque strings, but the canonical names are
    #: declared here as the type-level truth.
    type ReasonCode = Literal[
        "work_available",
        "wait_requested",
        "operator_required",
        "stop_requested",
    ]

    #: The sealed union of dispatch envelope variants. A
    #: :class:`WorkSourceProvider` always returns one of these; pyright
    #: will refuse to accept any other shape.
    type SourceDecision = "Dispatch | Wait | OperatorRequired | Stop"

    #: Convenience alias matching the field name on ``pi_monitor.work_source``.
    type WorkSourceDecision = SourceDecision
