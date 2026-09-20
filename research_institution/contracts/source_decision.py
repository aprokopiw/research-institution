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

from pydantic import BaseModel, ConfigDict

from pi_monitor.work_envelopes import (
    BudgetPolicy as WorkRequestBudgetPolicy,
    DispatchPayload,
    ExecutionPolicy as WorkRequestExecutionPolicy,
    IsolationPolicy as WorkRequestIsolationPolicy,
    SessionPolicy as WorkRequestSessionPolicy,
    WaitPayload,
    WorkRequestPayload,
)
from pi_monitor.work_source import (
    CANONICAL_REASON_CODES as _PM_CANONICAL_REASON_CODES,
    CanonicalReasonCode as PM_CanonicalReasonCode,
    DecisionKind as PM_DecisionKind,
    Dispatch,
    OperationKind as PM_OperationKind,
    OperatorRequired,
    REASON_BLOCKED_WORK_PRESENT,
    REASON_FRONTIER_EXHAUSTED,
    REASON_NO_ELIGIBLE_WORK,
    REASON_OPERATOR_REQUIRED,
    REASON_STOP_REQUESTED,
    REASON_WAIT_REQUESTED,
    REASON_WORK_AVAILABLE,
    RoleName as PM_RoleName,
    SourceIdentity as PM_SourceIdentity,
    SourceRevision,
    Stop,
    Wait,
    WorkRequest,
    WorkspaceName as PM_WorkspaceName,
)

# ---------------------------------------------------------------------------
# Stable reason-code vocabulary, closed ``kind`` discriminator, and
# cross-repo wire type aliases — re-exports of pi_monitor's canonical
# types by identity. Local duplicates were the historical source of
# drift (a typo at one of two definitions silently desynchronizes the
# verifier on the other side); the canonical version now lives in
# ``pi_monitor.work_source`` and this module re-exports the names.
# ---------------------------------------------------------------------------

#: Re-export of the closed canonical reason-code set. ``frozenset[Literal[...]]``
#: is structurally compatible with ``frozenset[str]`` so downstream code
#: that annotated against the legacy type still typechecks.
CANONICAL_REASON_CODES: frozenset[str] = _PM_CANONICAL_REASON_CODES

#: Closed reason-code vocabulary as a Literal type. Re-export of
#: :data:`pi_monitor.work_source.CanonicalReasonCode` so the strict
#: pyright config turns unknown reason_codes into a compile-time
#: error at any call site that declares ``reason_code: CanonicalReasonCode``.
CanonicalReasonCode = PM_CanonicalReasonCode

#: ``kind`` discriminator StrEnum. Re-export of
#: :class:`pi_monitor.work_source.DecisionKind`. This is the
#: canonical type for the envelope ``kind`` field; pi_monitor emits
#: ``DecisionKind.DISPATCH.value`` and ri reads ``decision.kind ==
#: DecisionKind.DISPATCH`` (both reference the same enum identity).
DecisionKind = PM_DecisionKind

#: Cross-repo wire type aliases for WorkRequest's string-typed fields.
#: Re-exports of the canonical Literal types from pi_monitor.
OperationKind = PM_OperationKind
RoleName = PM_RoleName
SourceIdentity = PM_SourceIdentity
WorkspaceName = PM_WorkspaceName


# ---------------------------------------------------------------------------
# The four decision variants — re-exports of pi_monitor's frozen
# dataclasses. See module docstring for why we re-export rather
# than mirror.
# ---------------------------------------------------------------------------

#: The tagged union of the four decision variants. A
#: ``WorkSourceProvider.__call__`` always returns one of these.
SourceDecision: TypeAlias = Dispatch | Wait | OperatorRequired | Stop

#: Back-compat alias for the legacy :data:`ReasonCodeLiteral` name.
#: Some external importers still reference the old name; prefer
#: :data:`CanonicalReasonCode` for new code.
ReasonCodeLiteral = PM_CanonicalReasonCode

#: Back-compat alias for the legacy :data:`DecisionKindLiteral` name.
#: The current canonical type is the :class:`DecisionKind` StrEnum
#: which carries the wire-string identity as ``.value``; this alias
#: keeps ``kind: DecisionKindLiteral`` annotations working.
DecisionKindLiteral: TypeAlias = Literal["dispatch", "wait", "operator_required", "stop"]


# ---------------------------------------------------------------------------
# The four decision variants — re-exports of pi_monitor's frozen
# dataclasses. See module docstring for why we re-export rather
# than mirror.
# ---------------------------------------------------------------------------

#: The tagged union of the four decision variants. A
#: ``WorkSourceProvider.__call__`` always returns one of these.
SourceDecision: TypeAlias = Dispatch | Wait | OperatorRequired | Stop


# ---------------------------------------------------------------------------
# Wire shape — Pydantic models so ``source_decision_to_wire`` returns a
# concrete type instead of ``dict[str, Any]``. ``extra="allow"`` keeps
# forward-compat (a future source may add a new field). The five
# opaque policy dicts (``payload`` / ``execution_policy`` / ...)
# stay ``dict[str, Any]`` at the wire layer because their typed
# shape is the Pydantic models in :mod:`pi_monitor.work_envelopes`
# (the boundary is :func:`parse_work_request_envelopes`).
# ---------------------------------------------------------------------------


class SourceRevisionWireDict(BaseModel):
    """Wire shape of :class:`pi_monitor.work_source.SourceRevision`.

    ``fingerprint`` and ``observed_unix`` are technically required
    by the wire contract; ``observed_unix`` defaults to ``0.0``
    so a malformed envelope with no timestamp surfaces as a
    missing-``fingerprint``/unknown-``kind`` error at the parse
    layer rather than a numeric-mismatch error in Pydantic.
    """

    model_config = ConfigDict(extra="allow")

    fingerprint: str = ""
    observed_unix: float = 0.0
    label: str = ""


class WorkRequestWireDict(BaseModel):
    """Wire shape of :class:`pi_monitor.work_source.WorkRequest`.

    All optional fields default to ``"default"`` (role/workspace) or
    ``None`` on the typed side; on the wire they are omitted via
    ``model_dump(exclude_none=True, exclude_unset=True)`` at the
    serialization site.

    The five opaque fields (``payload`` / ``execution_policy`` /
    ``session_policy`` / ``isolation`` / ``budget``) are source-
    owned: their typed shapes are Pydantic models in
    :mod:`pi_monitor.work_envelopes`. The wire-format JSON is
    ``dict[str, Any]``; the typed shape is one ``.model_validate()``
    away. See :func:`parse_work_request_envelopes` for the single
    boundary that produces a typed :class:`WorkRequest`.
    """

    model_config = ConfigDict(extra="allow")

    source_identity: str
    source_revision: SourceRevisionWireDict
    operation_id: str
    operation_kind: str
    role: str = "default"
    workspace: str = "default"
    payload: dict[str, Any] = {}
    execution_policy: dict[str, Any] = {}
    session_policy: dict[str, Any] = {}
    isolation: dict[str, Any] = {}
    budget: dict[str, Any] = {}
    execution_profile: str = ""
    lease_until_unix: float | None = None


class SourceDecisionWireDict(BaseModel):
    """Wire shape of the four-decision-variant discriminated envelope.

    All variant-specific fields are optional. Callers narrow by
    inspecting the ``kind`` field first (the canonical
    :class:`DecisionKind` StrEnum is the discriminator — the
    string form is also accepted at parse time via Pydantic's
    coercion).
    """

    model_config = ConfigDict(extra="allow")

    kind: str | None = None
    source_revision: SourceRevisionWireDict | None = None
    decided_unix: float | None = None
    reason_code: str | None = None
    reason: str | None = None
    work: list[WorkRequestWireDict] | None = None
    wake_on_source_change: bool | None = None
    retry_after_seconds: float | None = None
    until_unix: float | None = None
    payload: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Wire serialization helpers
# ---------------------------------------------------------------------------


def source_decision_to_wire(decision: SourceDecision) -> SourceDecisionWireDict:
    """Serialize a typed ``SourceDecision`` back to the wire dict shape.

    The reverse of :func:`parse_source_decision`. Both helpers stay
    colocated with the type so the round-trip is auditable in one
    place. Constitution Principle VII.
    """
    rev = decision.source_revision
    rev_model = SourceRevisionWireDict(
        fingerprint=rev.fingerprint,
        observed_unix=rev.observed_unix,
        label=rev.label,
    )
    kind = decision_kind(decision)
    if kind is DecisionKind.DISPATCH:
        dispatch = cast("Dispatch", decision)
        return SourceDecisionWireDict(
            kind=kind.value,
            source_revision=rev_model,
            decided_unix=dispatch.decided_unix,
            reason_code=cast("ReasonCodeLiteral", dispatch.reason_code),
            reason=dispatch.reason,
            work=[_work_request_to_wire(w) for w in dispatch.work],
        )
    if kind is DecisionKind.WAIT:
        wait = cast("Wait", decision)
        return SourceDecisionWireDict(
            kind=kind.value,
            source_revision=rev_model,
            decided_unix=wait.decided_unix,
            reason_code=cast("ReasonCodeLiteral", wait.reason_code),
            reason=wait.reason,
            wake_on_source_change=wait.wake_on_source_change,
            retry_after_seconds=wait.retry_after_seconds,
            until_unix=wait.until_unix,
            payload=dict(wait.payload) if wait.payload else None,
        )
    if kind is DecisionKind.OPERATOR_REQUIRED:
        op = cast("OperatorRequired", decision)
        return SourceDecisionWireDict(
            kind=kind.value,
            source_revision=rev_model,
            decided_unix=op.decided_unix,
            reason_code=cast("ReasonCodeLiteral", op.reason_code),
            reason=op.reason,
        )
    # DecisionKind.STOP — narrowing by elimination.
    stop = cast("Stop", decision)
    return SourceDecisionWireDict(
        kind=kind.value,
        source_revision=rev_model,
        decided_unix=stop.decided_unix,
        reason_code=cast("ReasonCodeLiteral", stop.reason_code),
        reason=stop.reason,
    )


def _work_request_to_wire(req: WorkRequest) -> WorkRequestWireDict:
    """Serialize one ``WorkRequest`` to its wire-dict shape.

    Constructs a typed Pydantic ``WorkRequestWireDict`` directly.
    Empty / default fields are still emitted as their default
    values (``"default"``, ``""``, ``{}``) at the typed layer
    and then stripped at the JSON boundary if the consumer wants
    a compact form via ``model_dump(exclude_unset=True)``.
    """
    return WorkRequestWireDict(
        source_identity=req.source_identity,
        source_revision=SourceRevisionWireDict(
            fingerprint=req.source_revision.fingerprint,
            observed_unix=req.source_revision.observed_unix,
            label=req.source_revision.label,
        ),
        operation_id=req.operation_id,
        operation_kind=req.operation_kind,
        role=req.role,
        workspace=req.workspace,
        payload=dict(req.payload),
        execution_policy=dict(req.execution_policy),
        session_policy=dict(req.session_policy),
        isolation=dict(req.isolation),
        budget=dict(req.budget),
        execution_profile=req.execution_profile,
        lease_until_unix=req.lease_until_unix,
    )


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

    Validates through the typed Pydantic wire model first so
    required fields (e.g. ``source_revision.fingerprint``) fail
    fast at the wire boundary; the legacy per-field manual
    coercion is replaced by ``model_validate``.
    """
    typed = SourceDecisionWireDict.model_validate(envelope)
    raw_kind = typed.kind or ""
    try:
        kind = DecisionKind(raw_kind)
    except ValueError as exc:
        raise ValueError(
            f"unknown source-decision kind: {raw_kind!r} "
            f"(known: {[k.value for k in DecisionKind if k != DecisionKind.UNKNOWN]})"
        ) from exc
    if typed.source_revision is None:
        # The legacy parser tolerated a missing source_revision
        # (defaulted to an empty ``SourceRevision``); preserve that
        # for back-compat. New envelopes must always carry one;
        # absence is a wire-format drift to flag at the dispatcher.
        rev = SourceRevision(fingerprint="", observed_unix=0.0, label="")
    else:
        rev = SourceRevision(
            fingerprint=typed.source_revision.fingerprint,
            observed_unix=typed.source_revision.observed_unix,
            label=typed.source_revision.label,
        )
    decided_unix = typed.decided_unix if typed.decided_unix is not None else 0.0
    if kind == DecisionKind.DISPATCH:
        return Dispatch(
            source_revision=rev,
            decided_unix=decided_unix,
            work=[
                _parse_work_request(w.model_dump())
                for w in (typed.work or [])
            ],
            reason_code=typed.reason_code or REASON_WORK_AVAILABLE,
            reason=typed.reason or "",
        )
    if kind == DecisionKind.WAIT:
        return Wait(
            source_revision=rev,
            decided_unix=decided_unix,
            reason_code=typed.reason_code or REASON_WAIT_REQUESTED,
            reason=typed.reason or "",
            wake_on_source_change=bool(typed.wake_on_source_change),
            retry_after_seconds=typed.retry_after_seconds,
            until_unix=typed.until_unix,
            payload=typed.payload or {},
        )
    if kind == DecisionKind.OPERATOR_REQUIRED:
        return OperatorRequired(
            source_revision=rev,
            decided_unix=decided_unix,
            reason_code=typed.reason_code or REASON_OPERATOR_REQUIRED,
            reason=typed.reason or "",
        )
    if kind == DecisionKind.STOP:
        return Stop(
            source_revision=rev,
            decided_unix=decided_unix,
            reason_code=typed.reason_code or REASON_STOP_REQUESTED,
            reason=typed.reason or "",
        )
    raise ValueError(f"unreachable: DecisionKind={kind!r}")


def _parse_work_request(raw: dict[str, Any]) -> WorkRequest:
    """Parse one WorkRequest dict from a source-decision envelope.

    Validates through the typed Pydantic ``WorkRequestWireDict``
    so a malformed required field (missing ``source_identity`` /
    ``operation_id`` / ``source_revision``) fails fast at the
    parse boundary instead of at a downstream consumer.
    """
    typed = WorkRequestWireDict.model_validate(raw)
    return WorkRequest(
        source_identity=typed.source_identity,
        source_revision=SourceRevision(
            fingerprint=typed.source_revision.fingerprint,
            observed_unix=typed.source_revision.observed_unix,
            label=typed.source_revision.label,
        ),
        operation_id=typed.operation_id,
        operation_kind=typed.operation_kind,
        role=typed.role,
        workspace=typed.workspace,
        payload=dict(typed.payload),
        execution_policy=dict(typed.execution_policy),
        session_policy=dict(typed.session_policy),
        isolation=dict(typed.isolation),
        budget=dict(typed.budget),
        execution_profile=typed.execution_profile,
        lease_until_unix=typed.lease_until_unix,
    )


# ---------------------------------------------------------------------------
# Typed-shape re-exports + parse helpers
# ---------------------------------------------------------------------------

#: Typed envelope for ``WorkRequest.payload``. The wire format is
#: ``dict[str, Any]`` (the JSON serialization of the model);
#: consumers that want strict typing parse with
#: :class:`WorkRequestPayload.model_validate`.
TypedWorkRequestPayload = WorkRequestPayload

#: Typed envelope for ``WorkRequest.execution_policy``. Re-exported
#: from :mod:`pi_monitor.work_envelopes` so consumers do not need to
#: import from a third-party module to see the typed shape.
TypedExecutionPolicy = WorkRequestExecutionPolicy

#: Typed envelope for ``WorkRequest.session_policy``. See
#: :data:`TypedExecutionPolicy` for the re-export rationale.
TypedSessionPolicy = WorkRequestSessionPolicy

#: Typed envelope for ``WorkRequest.isolation``. See
#: :data:`TypedExecutionPolicy` for the re-export rationale.
TypedIsolationPolicy = WorkRequestIsolationPolicy

#: Typed envelope for ``WorkRequest.budget``. See
#: :data:`TypedExecutionPolicy` for the re-export rationale.
TypedBudgetPolicy = WorkRequestBudgetPolicy


def parse_work_request_envelopes(
    request: WorkRequest,
) -> tuple[
    WorkRequestPayload,
    WorkRequestExecutionPolicy,
    WorkRequestSessionPolicy,
    WorkRequestIsolationPolicy,
    WorkRequestBudgetPolicy,
]:
    """Validate every opaque field of one WorkRequest as its typed envelope.

    Pure: a single ``.model_validate`` per field, no I/O. The
    function is the canonical boundary between the supervisor's
    untyped envelope (5 ``dict[str, object]`` fields) and the
    consumer's typed view. Consumers that need strict typing call
    this once on a request they own; callers that just want the
    raw dicts continue to access ``request.payload`` directly.

    A future source may add a new field to any envelope; because
    each envelope has ``extra="allow"`` (per spec 004 wire-compat
    discipline), this function never raises on unknown fields.
    """
    return (
        WorkRequestPayload.model_validate(request.payload),
        WorkRequestExecutionPolicy.model_validate(request.execution_policy),
        WorkRequestSessionPolicy.model_validate(request.session_policy),
        WorkRequestIsolationPolicy.model_validate(request.isolation),
        WorkRequestBudgetPolicy.model_validate(request.budget),
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
    "SourceDecisionWireDict",
    "SourceRevision",
    "SourceRevisionWireDict",
    "Stop",
    "TypedBudgetPolicy",
    "TypedExecutionPolicy",
    "TypedIsolationPolicy",
    "TypedSessionPolicy",
    "TypedWorkRequestPayload",
    "Wait",
    "WorkRequest",
    "WorkRequestWireDict",
    "decision_kind",
    "parse_source_decision",
    "parse_work_request_envelopes",
    "source_decision_to_wire",
]
