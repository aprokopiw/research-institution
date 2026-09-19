"""Typed view of the WorkSourceProvider source-decision envelope.

Per `@ADR-0006`, research-institution does NOT own the source-decision
contract — pi_monitor (`pi_monitor.work_source`) is the canonical
authority, mathlint emits one of the four decision variants, and
research-institution is a **read-only consumer** when it needs to
parse a decision.

This module mirrors the typed shape so:

  - Operators reading the dispatcher's output can decode the
    envelopes without depending on pi_monitor's import graph.
  - Tests pin the wire format with golden files (drift detection:
    if pi_monitor changes the discriminator strings, the tests fail).
  - A future observability surface in research-institution can
    summarize decisions with full type information.

Mirroring mathlint.orchestration.vocabulary and pi_monitor.work_source
deliberately: the canonical enums live in their respective repos.
This file is the dispatcher's consumer-side mirror.

The four decision variants are:

  - :class:`Dispatch` -- execute the carried work requests.
  - :class:`Wait` -- no dispatch is legal right now.
  - :class:`OperatorRequired` -- human must decide before resuming.
  - :class:`Stop` -- terminal per the source.

The envelope's `kind` field is the discriminator. A SourceDecision is
a tagged union over these four types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Union


# ---------------------------------------------------------------------------
# Stable reason-code vocabulary (mirrored from pi_monitor.work_source).
# Adapters outside this list are tolerated as opaque strings but these
# are the documented canonical set.
# ---------------------------------------------------------------------------

REASON_NO_ELIGIBLE_WORK = "no_eligible_work"
REASON_FRONTIER_EXHAUSTED = "frontier_exhausted"
REASON_BLOCKED_WORK_PRESENT = "blocked_work_present"
REASON_WORK_AVAILABLE = "work_available"
REASON_WAIT_REQUESTED = "wait_requested"
REASON_OPERATOR_REQUIRED = "operator_required"
REASON_STOP_REQUESTED = "stop_requested"

CANONICAL_REASON_CODES: frozenset[str] = frozenset(
    {
        REASON_NO_ELIGIBLE_WORK,
        REASON_FRONTIER_EXHAUSTED,
        REASON_BLOCKED_WORK_PRESENT,
        REASON_WORK_AVAILABLE,
        REASON_WAIT_REQUESTED,
        REASON_OPERATOR_REQUIRED,
        REASON_STOP_REQUESTED,
    }
)


class DecisionKind(StrEnum):
    """The `kind` discriminator in a source-decision envelope.

    Mirrors pi_monitor.work_source.KIND_* constants.
    """

    DISPATCH = "dispatch"
    WAIT = "wait"
    OPERATOR_REQUIRED = "operator_required"
    STOP = "stop"
    UNKNOWN = "UNKNOWN"  # defensive default for unrecognized values


# ---------------------------------------------------------------------------
# SourceRevision + WorkRequest
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SourceRevision:
    """A label on the source's authoritative state.

    Mirrors pi_monitor.work_source.SourceRevision. The fingerprint is
    a content hash; the label is a source-provided id (may be empty).
    """

    fingerprint: str
    observed_unix: float
    label: str = ""


@dataclass(frozen=True, slots=True)
class WorkRequest:
    """One logical unit of work whose meaning only the source understands.

    Mirrors pi_monitor.work_source.WorkRequest. `payload` is opaque to
    consumers and survives serialization byte-for-byte.
    """

    source_identity: str
    source_revision: SourceRevision
    operation_id: str
    operation_kind: str
    role: str = "default"
    workspace: str = "default"
    payload: dict[str, Any] = field(default_factory=dict)
    execution_policy: dict[str, Any] = field(default_factory=dict)
    session_policy: dict[str, Any] = field(default_factory=dict)
    isolation: dict[str, Any] = field(default_factory=dict)
    budget: dict[str, Any] = field(default_factory=dict)
    execution_profile: str = ""
    lease_until_unix: float | None = None

    @property
    def idempotency_key(self) -> tuple[str, str, str]:
        """Stable identity shared by every attempt of this logical operation."""
        return (self.source_identity, self.source_revision.fingerprint, self.operation_id)


# ---------------------------------------------------------------------------
# The four decision variants
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Dispatch:
    """Execute the carried work requests."""

    source_revision: SourceRevision
    decided_unix: float
    work: list[WorkRequest]
    reason_code: str = REASON_WORK_AVAILABLE
    reason: str = ""


@dataclass(frozen=True, slots=True)
class Wait:
    """No dispatch is legal right now -- never treated as completion."""

    source_revision: SourceRevision
    decided_unix: float
    reason_code: str = REASON_WAIT_REQUESTED
    reason: str = ""
    wake_on_source_change: bool = False
    retry_after_seconds: float | None = None
    until_unix: float | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OperatorRequired:
    """A human (or a ControlEnvelope resume) must decide before execution resumes."""

    source_revision: SourceRevision
    decided_unix: float
    reason_code: str = REASON_OPERATOR_REQUIRED
    reason: str = ""


@dataclass(frozen=True, slots=True)
class Stop:
    """Terminal per the source: an intentional clean exit/settle."""

    source_revision: SourceRevision
    decided_unix: float
    reason_code: str = REASON_STOP_REQUESTED
    reason: str = ""


# The tagged union of the four decision variants.
SourceDecision = Union[Dispatch, Wait, OperatorRequired, Stop]


def parse_source_decision(envelope: dict[str, Any]) -> SourceDecision:
    """Parse one source-decision envelope dict into the typed variant.

    Pure function: no I/O. The envelope's `kind` field is the
    discriminator. Unknown `kind` values raise `ValueError` -- callers
    should treat that as a wire-format drift (the dispatcher should
    never silently swallow a malformed envelope; that's what
    defensive parsing is for, but in THIS layer we want a loud
    failure to surface a contract change to its maintainer).
    """
    raw_kind = envelope.get("kind", "")
    try:
        kind = DecisionKind(raw_kind)
    except ValueError as exc:
        raise ValueError(
            f"unknown source-decision kind: {raw_kind!r} "
            f"(known: {[k.value for k in DecisionKind if k != DecisionKind.UNKNOWN]})"
        ) from exc
    rev_dict = envelope.get("source_revision", {})
    rev = SourceRevision(
        fingerprint=rev_dict.get("fingerprint", ""),
        observed_unix=float(rev_dict.get("observed_unix", 0.0)),
        label=rev_dict.get("label", ""),
    )
    decided_unix = float(envelope.get("decided_unix", 0.0))
    if kind == DecisionKind.DISPATCH:
        return Dispatch(
            source_revision=rev,
            decided_unix=decided_unix,
            work=[
                _parse_work_request(w)
                for w in envelope.get("work", [])
            ],
            reason_code=envelope.get("reason_code", REASON_WORK_AVAILABLE),
            reason=envelope.get("reason", ""),
        )
    if kind == DecisionKind.WAIT:
        return Wait(
            source_revision=rev,
            decided_unix=decided_unix,
            reason_code=envelope.get("reason_code", REASON_WAIT_REQUESTED),
            reason=envelope.get("reason", ""),
            wake_on_source_change=bool(envelope.get("wake_on_source_change", False)),
            retry_after_seconds=envelope.get("retry_after_seconds"),
            until_unix=envelope.get("until_unix"),
            payload=envelope.get("payload", {}),
        )
    if kind == DecisionKind.OPERATOR_REQUIRED:
        return OperatorRequired(
            source_revision=rev,
            decided_unix=decided_unix,
            reason_code=envelope.get("reason_code", REASON_OPERATOR_REQUIRED),
            reason=envelope.get("reason", ""),
        )
    if kind == DecisionKind.STOP:
        return Stop(
            source_revision=rev,
            decided_unix=decided_unix,
            reason_code=envelope.get("reason_code", REASON_STOP_REQUESTED),
            reason=envelope.get("reason", ""),
        )
    raise ValueError(f"unreachable: DecisionKind={kind!r}")


def _parse_work_request(raw: dict[str, Any]) -> WorkRequest:
    """Parse one WorkRequest dict from a source-decision envelope."""
    rev_dict = raw.get("source_revision", {})
    rev = SourceRevision(
        fingerprint=rev_dict.get("fingerprint", ""),
        observed_unix=float(rev_dict.get("observed_unix", 0.0)),
        label=rev_dict.get("label", ""),
    )
    return WorkRequest(
        source_identity=raw["source_identity"],
        source_revision=rev,
        operation_id=raw["operation_id"],
        operation_kind=raw["operation_kind"],
        role=raw.get("role", "default"),
        workspace=raw.get("workspace", "default"),
        payload=raw.get("payload", {}),
        execution_policy=raw.get("execution_policy", {}),
        session_policy=raw.get("session_policy", {}),
        isolation=raw.get("isolation", {}),
        budget=raw.get("budget", {}),
        execution_profile=raw.get("execution_profile", ""),
        lease_until_unix=raw.get("lease_until_unix"),
    )


def decision_kind(decision: SourceDecision) -> DecisionKind:
    """Return the DecisionKind discriminator for a typed decision."""
    if isinstance(decision, Dispatch):
        return DecisionKind.DISPATCH
    if isinstance(decision, Wait):
        return DecisionKind.WAIT
    if isinstance(decision, OperatorRequired):
        return DecisionKind.OPERATOR_REQUIRED
    if isinstance(decision, Stop):
        return DecisionKind.STOP
    raise TypeError(f"not a SourceDecision: {decision!r}")


__all__ = [
    "CANONICAL_REASON_CODES",
    "DecisionKind",
    "Dispatch",
    "OperatorRequired",
    "REASON_BLOCKED_WORK_PRESENT",
    "REASON_FRONTIER_EXHAUSTED",
    "REASON_NO_ELIGIBLE_WORK",
    "REASON_OPERATOR_REQUIRED",
    "REASON_STOP_REQUESTED",
    "REASON_WAIT_REQUESTED",
    "REASON_WORK_AVAILABLE",
    "SourceDecision",
    "SourceRevision",
    "Stop",
    "Wait",
    "WorkRequest",
    "decision_kind",
    "parse_source_decision",
]
