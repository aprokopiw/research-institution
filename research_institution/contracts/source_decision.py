"""Typed view of the WorkSourceProvider source-decision envelope.

Per `@ADR-0006`, research-institution does NOT own the source-decision
contract — pi_monitor (`pi_monitor.work_source`) is the canonical
authority. Math emits one of the four decision variants; pi_monitor
serializes them on the wire; research-institution parses them on
read paths (status, observability, test surfaces).

This module is the *single* typed-envelope surface for the
research-institution side of the boundary. It re-exports pi_monitor's
frozen dataclasses by identity, so:

  - ``isinstance(x, contracts.source_decision.Dispatch)`` is the
    same check as ``isinstance(x, pi_monitor.work_source.Dispatch)``;
    there is exactly one class, not two.
  - Pyright sees one type across both sides; a drift in pi_monitor
    surfaces at every call site in research-institution.
  - Tests can import the canonical names from
    ``research_institution.contracts.source_decision`` without
    reaching into pi_monitor's import graph.

Why re-export rather than mirror: ADR-0007 + ADR-0009 commit the
institution to a single source of truth for the wire envelope.
Mirrored dataclasses drift; re-exports can't.

The four decision variants are:

  - :class:`Dispatch` -- execute the carried work requests.
  - :class:`Wait` -- no dispatch is legal right now.
  - :class:`OperatorRequired` -- human must decide before resuming.
  - :class:`Stop` -- terminal per the source.

The envelope's `kind` field is the discriminator. ``SourceDecision``
is a tagged union over these four types.

Read-side: ``parse_source_decision(envelope_dict)`` parses a wire
dict into the typed variant; ``decision_kind(decision)`` returns the
discriminator; ``source_decision_to_wire(decision)`` serializes a
typed decision back to a wire dict. The three together round-trip
typed envelopes through the wire boundary.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, TypeAlias, cast

from pi_monitor.work_source import (
    Dispatch,
    OperatorRequired,
    SourceRevision,
    Stop,
    Wait,
    WorkRequest,
)

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

#: Closed reason-code vocabulary as a Literal type. The strict
#: pyright config in pyproject.toml turns unknown reason_codes into
#: a compile-time error at any call site that declares
#: ``reason_code: ReasonCodeLiteral``.
ReasonCodeLiteral: TypeAlias = Literal[
    "no_eligible_work",
    "frontier_exhausted",
    "blocked_work_present",
    "work_available",
    "wait_requested",
    "operator_required",
    "stop_requested",
]


class DecisionKind(StrEnum):
    """The `kind` discriminator in a source-decision envelope.

    Mirrors pi_monitor.work_source.KIND_* constants.
    """

    DISPATCH = "dispatch"
    WAIT = "wait"
    OPERATOR_REQUIRED = "operator_required"
    STOP = "stop"
    UNKNOWN = "UNKNOWN"  # defensive default for unrecognized values


#: Closed ``kind`` discriminator as a Literal type. Use this for
#: write-side paths that declare the envelope shape statically.
DecisionKindLiteral: TypeAlias = Literal[
    "dispatch", "wait", "operator_required", "stop"
]


# ---------------------------------------------------------------------------
# The four decision variants — re-exports of pi_monitor's frozen
# dataclasses. See module docstring for why we re-export rather
# than mirror.
# ---------------------------------------------------------------------------

#: The tagged union of the four decision variants. A
#: ``WorkSourceProvider.__call__`` always returns one of these.
SourceDecision: TypeAlias = Dispatch | Wait | OperatorRequired | Stop


# ---------------------------------------------------------------------------
# Wire serialization helpers
# ---------------------------------------------------------------------------


def source_decision_to_wire(decision: SourceDecision) -> dict[str, Any]:
    """Serialize a typed ``SourceDecision`` back to the wire dict shape.

    The reverse of :func:`parse_source_decision`. Both helpers stay
    colocated with the type so the round-trip is auditable in one
    place. Constitution Principle VII.
    """
    rev = decision.source_revision
    rev_dict = {
        "fingerprint": rev.fingerprint,
        "observed_unix": rev.observed_unix,
        "label": rev.label,
    }
    kind = decision_kind(decision)
    if kind is DecisionKind.DISPATCH:
        dispatch = cast("Dispatch", decision)
        return {
            "kind": "dispatch",
            "source_revision": rev_dict,
            "decided_unix": dispatch.decided_unix,
            "reason_code": dispatch.reason_code,
            "reason": dispatch.reason,
            "work": [_work_request_to_wire(w) for w in dispatch.work],
        }
    if kind is DecisionKind.WAIT:
        wait = cast("Wait", decision)
        result: dict[str, Any] = {
            "kind": "wait",
            "source_revision": rev_dict,
            "decided_unix": wait.decided_unix,
            "reason_code": wait.reason_code,
            "reason": wait.reason,
        }
        if wait.wake_on_source_change:
            result["wake_on_source_change"] = True
        if wait.retry_after_seconds is not None:
            result["retry_after_seconds"] = wait.retry_after_seconds
        if wait.until_unix is not None:
            result["until_unix"] = wait.until_unix
        if wait.payload:
            result["payload"] = dict(wait.payload)
        return result
    if kind is DecisionKind.OPERATOR_REQUIRED:
        op = cast("OperatorRequired", decision)
        return {
            "kind": "operator_required",
            "source_revision": rev_dict,
            "decided_unix": op.decided_unix,
            "reason_code": op.reason_code,
            "reason": op.reason,
        }
    # DecisionKind.STOP — narrowing by elimination.
    stop = cast("Stop", decision)
    return {
        "kind": "stop",
        "source_revision": rev_dict,
        "decided_unix": stop.decided_unix,
        "reason_code": stop.reason_code,
        "reason": stop.reason,
    }


def _work_request_to_wire(req: WorkRequest) -> dict[str, Any]:
    """Serialize one ``WorkRequest`` to its wire-dict shape."""
    result: dict[str, Any] = {
        "source_identity": req.source_identity,
        "source_revision": {
            "fingerprint": req.source_revision.fingerprint,
            "observed_unix": req.source_revision.observed_unix,
            "label": req.source_revision.label,
        },
        "operation_id": req.operation_id,
        "operation_kind": req.operation_kind,
    }
    if req.role != "default":
        result["role"] = req.role
    if req.workspace != "default":
        result["workspace"] = req.workspace
    if req.payload:
        result["payload"] = dict(req.payload)
    if req.execution_policy:
        result["execution_policy"] = dict(req.execution_policy)
    if req.session_policy:
        result["session_policy"] = dict(req.session_policy)
    if req.isolation:
        result["isolation"] = dict(req.isolation)
    if req.budget:
        result["budget"] = dict(req.budget)
    if req.execution_profile:
        result["execution_profile"] = req.execution_profile
    if req.lease_until_unix is not None:
        result["lease_until_unix"] = req.lease_until_unix
    return result


# ---------------------------------------------------------------------------
# Read-side parsing
# ---------------------------------------------------------------------------


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
            work=[_parse_work_request(w) for w in envelope.get("work", [])],
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
    """Return the DecisionKind discriminator for a typed decision.

    Uses chained ``isinstance`` narrowing; the final member is
    reached by exhaustiveness (the ``SourceDecision`` union has only
    four members; a future fifth would surface here as a type error).
    """
    if isinstance(decision, Dispatch):
        return DecisionKind.DISPATCH
    if isinstance(decision, Wait):
        return DecisionKind.WAIT
    if isinstance(decision, OperatorRequired):
        return DecisionKind.OPERATOR_REQUIRED
    # Exhaustiveness: at this point the union has narrowed to Stop.
    return DecisionKind.STOP


__all__ = [
    "CANONICAL_REASON_CODES",
    "DecisionKind",
    "DecisionKindLiteral",
    "Dispatch",
    "OperatorRequired",
    "REASON_BLOCKED_WORK_PRESENT",
    "REASON_FRONTIER_EXHAUSTED",
    "REASON_NO_ELIGIBLE_WORK",
    "REASON_OPERATOR_REQUIRED",
    "REASON_STOP_REQUESTED",
    "REASON_WAIT_REQUESTED",
    "REASON_WORK_AVAILABLE",
    "ReasonCodeLiteral",
    "SourceDecision",
    "SourceRevision",
    "Stop",
    "Wait",
    "WorkRequest",
    "decision_kind",
    "parse_source_decision",
    "source_decision_to_wire",
]
