"""Typed view of the WorkSourceProvider source-decision envelope.

Per `@ADR-0006`, research-institution does NOT own the source-decision
contract — pi_monitor (`pi_monitor.work.work_source`) is the canonical
authority. Math emits one of the four decision variants; pi_monitor
serializes them on the wire; research-institution parses them on
read paths (status, observability, test surfaces).

This module is the *single* typed-envelope surface for the
research-institution side of the boundary. It re-exports pi_monitor's
frozen dataclasses by identity, so:

  - ``isinstance(x, contracts.source_decision.Dispatch)`` is the
    same check as ``isinstance(x, pi_monitor.work.work_source.Dispatch)``;
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

from typing import Any, Final, Literal

from pi_monitor.protocol.wire_models import (
    SourceDecisionWireModel as SourceDecisionWireDict,
    SourceRevisionWireModel as SourceRevisionWireDict,
    WorkRequestWireModel as WorkRequestWireDict,
)
from pi_monitor.protocol.work_envelopes import (
    BudgetPolicy as WorkRequestBudgetPolicy,
    ExecutionPolicy as WorkRequestExecutionPolicy,
    IsolationPolicy as WorkRequestIsolationPolicy,
    SessionPolicy as WorkRequestSessionPolicy,
    WorkRequestPayload,
)
from pi_monitor.work.work_source import (
    CANONICAL_REASON_CODES as _PM_CANONICAL_REASON_CODES,
    CanonicalReasonCode as PM_CanonicalReasonCode,
    DecisionKind as PM_DecisionKind,
    Dispatch,
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
)

# ---------------------------------------------------------------------------
# Stable reason-code vocabulary, closed ``kind`` discriminator, and
# cross-repo wire type aliases — re-exports of pi_monitor's canonical
# types by identity. Local duplicates were the historical source of
# drift (a typo at one of two definitions silently desynchronizes the
# verifier on the other side); the canonical version now lives in
# ``pi_monitor.work.work_source`` and this module re-exports the names.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# @ADR-0011 (no-delta loop fix) additions.
#
# These two reason codes ride along on the existing ``reason_code: str``
# field — the wire schema is byte-identical to pre-plan-013. They are
# not yet inside pi_monitor's ``CanonicalReasonCode`` Literal because
# @ADR-0011 ships without touching pi_monitor; research-institution
# emits them and the supervisor's wire codec accepts them as opaque
# strings. Per @CTR-0001's forward-compat note, codes outside the
# canonical set are tolerated by the supervisor and flagged by the
# paired-receipt verifier for the operator. A future math-maintainer
# review may extend pi_monitor's Literal to include these; the
# research-institution contracts module is the documented home for
# @ADR-0011 reason codes regardless.
# ---------------------------------------------------------------------------

#: ``Wait`` reason when the kernel's stagnation trigger has fired on
#: the candidate ``operation_id`` but the architecture-review horizon
#: admission has not yet completed. The supervisor emits this once 2+
#: consecutive no-delta outcomes accumulate against the same target.
REASON_ARCHITECTURE_REVIEW_REQUIRED: Final[str] = "architecture_review_required"

#: ``Dispatch`` reason when the kernel emits ``DISPATCH_ARCHITECT``
#: (admission complete; architect round mid-flight). The wire
#: ``role`` is overridden to ``"maintenance"`` (a value already in
#: pi_monitor's wire ``RoleName`` Literal) so the wire schema stays
#: byte-identical.
REASON_ARCHITECTURE_REVIEW_DISPATCH: Final[str] = "architecture_review_dispatch"

#: Re-export of the closed canonical reason-code set. Kept byte-equal
#: to pi_monitor's wire-authority set so the cross-repo parity test
#: in ``tests/test_cross_repo_type_identity.py`` stays green. The
#: @ADR-0011 OS-side additions live in :data:`OS_EXTENDED_REASON_CODES`
#: below; both sets together are the documented OS reason-code union.
CANONICAL_REASON_CODES: frozenset[str] = _PM_CANONICAL_REASON_CODES

#: @ADR-0011 OS-side reason-code additions. These ride along on the
#: existing ``reason_code: str`` field — the wire schema is byte-
#: identical to pre-plan-013 because pi_monitor's wire codec accepts
#: any string. They are documented in this module until a future
#: math-maintainer review lifts them into pi_monitor's wire Literal
#: under ``@CTR-0021-wire-protocol-version-pinned``.
OS_EXTENDED_REASON_CODES: frozenset[str] = frozenset(
    {
        REASON_ARCHITECTURE_REVIEW_REQUIRED,
        REASON_ARCHITECTURE_REVIEW_DISPATCH,
    }
)

#: Combined OS reason-code union (pi_monitor's canonical set plus
#: the @ADR-0011 OS-side additions). The dispatcher accepts reasons
#: from this combined set; the supervisor's wire codec accepts any
#: string per ``@CTR-0001`` forward-compat.
EXTENDED_REASON_CODES: frozenset[str] = (
    CANONICAL_REASON_CODES | OS_EXTENDED_REASON_CODES
)

#: Closed reason-code vocabulary as a Literal type. Re-export of
#: :data:`pi_monitor.work.work_source.CanonicalReasonCode` so the strict
#: pyright config turns unknown reason_codes into a compile-time
#: error at any call site that declares ``reason_code: CanonicalReasonCode``.
CanonicalReasonCode = PM_CanonicalReasonCode

#: Workload-side role alias for @ADR-0011 dispatch paths. The
#: ``RoleName`` field is pi_monitor's wire vocabulary; @ADR-0011 only
#: emits a NARROWING subset (``research`` / ``maintenance`` /
#: ``primary`` / ``supporting`` / ``default``) so a typo at the OS
#: composition root is caught at the import boundary. The 5
#: wire-allowed values are the ones the OS actually injects on the
#: ``dataclasses.replace(candidate, role=...)`` path. Other wire values
#: (``intake``, ``review``, ``milestone``) are not used by @ADR-0011;
#: reserving them for future plan-* work keeps the Literal closed.
WorkRequestRoleAlias = Literal[
    "research",
    "maintenance",
    "primary",
    "supporting",
    "default",
]

# ---------------------------------------------------------------------------
# @ADR-0011 OS-side WorkRequest payload keys.
#
# The OS consults math's live-source snapshot and injects the typed
# identity fields (``directive_content_hash``, ``directive_template_hash``,
# ``stagnation_session_count``, ``math_target``) into the dispatched
# ``WorkRequest.payload`` as opaque fields. pi_monitor's wire codec
# treats the payload as opaque per `@CTR-0001`; the worker reads the
# fields and uses the directive content hash as the math-side typed
# identity. Documenting them as constants keeps the provider, the
# tests, and the docs in sync (one source of truth per key).
# ---------------------------------------------------------------------------

PAYLOAD_KEY_MATH_DIRECTIVE_CONTENT_HASH: Final[str] = "math_directive_content_hash"
PAYLOAD_KEY_MATH_DIRECTIVE_TEMPLATE_HASH: Final[str] = "math_directive_template_hash"
PAYLOAD_KEY_STAGNATION_SESSION_COUNT: Final[str] = "stagnation_session_count"
PAYLOAD_KEY_MATH_TARGET: Final[str] = "math_target"
PAYLOAD_KEY_PREVIOUS_PAYLOAD: Final[str] = "previous_payload"

#: Closed Literal of the four OS-injected payload keys (plus the
#: optional ``previous_payload`` for architect-round carry-over).
#: Use this type for code that iterates or asserts on the payload
#: keys (e.g., tests, validators, supervisor-side audit consumers).
PayloadKeyPlan013 = Literal[
    "math_directive_content_hash",
    "math_directive_template_hash",
    "stagnation_session_count",
    "math_target",
    "previous_payload",
]

#: ``kind`` discriminator StrEnum. Re-export of
#: :class:`pi_monitor.work.work_source.DecisionKind`. This is the
#: canonical type for the envelope ``kind`` field; pi_monitor emits
#: ``DecisionKind.DISPATCH.value`` and ri reads ``decision.kind ==
#: DecisionKind.DISPATCH`` (both reference the same enum identity).
DecisionKind = PM_DecisionKind

#: Cross-repo wire type aliases for WorkRequest's string-typed fields.
#: Re-exports of the canonical Literal types from pi_monitor.
#:
#: ``OperationKind`` and ``WorkspaceName`` are owned by the OS layer
#: (this module) per @ADR-0092 — pi_monitor only carries the wire
#: type (``str``) and forwards verbatim; the canonical vocabulary
#: lives here as a Literal so the OS validator can enforce it.
#: ``SourceIdentity`` is fully opaque (pi-monitor never enumerates it).
#: ``RoleName`` stays a closed Literal in pi-monitor because its
#: values are generic domain role labels, not program identities.
OperationKind = Literal[
    "mathlint-research",
    "mathlint-verify",
    "mathlint-build",
    "speckit-task",
]
RoleName = PM_RoleName
SourceIdentity = PM_SourceIdentity
WorkspaceName = Literal[
    "default",
    "kaplansky-workspace",
    "math-workspace",
]


# ---------------------------------------------------------------------------
# The four decision variants — re-exports of pi_monitor's frozen
# dataclasses. See module docstring for why we re-export rather
# than mirror.
# ---------------------------------------------------------------------------

#: The tagged union of the four decision variants. A
#: ``WorkSourceProvider.__call__`` always returns one of these.
type SourceDecision = Dispatch | Wait | OperatorRequired | Stop

#: Back-compat alias for the legacy :data:`ReasonCodeLiteral` name.
#: Some external importers still reference the old name; prefer
#: :data:`CanonicalReasonCode` for new code.
ReasonCodeLiteral = PM_CanonicalReasonCode

#: Back-compat alias for the legacy :data:`DecisionKindLiteral` name.
#: The current canonical type is the :class:`DecisionKind` StrEnum
#: which carries the wire-string identity as ``.value``; this alias
#: keeps ``kind: DecisionKindLiteral`` annotations working.
type DecisionKindLiteral = Literal["dispatch", "wait", "operator_required", "stop"]


# ---------------------------------------------------------------------------
# Canonical wire models — re-exports of pi_monitor's wire models.
# Imported at top of module (see ``from pi_monitor.protocol.wire_models import ...``).
#
# The OS layer is the canonical owner of the program-identity
# vocabularies (``OperationKind``, ``WorkspaceName``); the wire
# shape itself lives in pi_monitor. RI re-exports under stable
# local names for back-compat with consumers that imported the
# prior ``SourceRevisionWireDict`` / ``WorkRequestWireDict`` /
# ``SourceDecisionWireDict`` re-declarations.
#
# Per the cross-repo rule: pi_monitor owns the wire protocol;
# math re-exports; kaplansky and ri import from one of those
# two. A drift in any of the four canonical wire models now
# surfaces at every import site via pyright.
# ---------------------------------------------------------------------------
# Wire serialization helpers
# ---------------------------------------------------------------------------


def source_decision_to_wire(decision: SourceDecision) -> SourceDecisionWireDict:
    """Serialize a typed ``SourceDecision`` back to the wire dict shape.

    The reverse of :func:`parse_source_decision`. Both helpers stay
    colocated with the type so the round-trip is auditable in one
    place. Constitution Principle VII.

    Uses ``isinstance`` (which pyright narrows) instead of
    ``kind is DecisionKind.X`` + cast — eliminates the dishonest
    ``cast("Dispatch", decision)`` calls where pyright can't see
    through the discriminator branch.
    """
    rev = decision.source_revision
    rev_model = SourceRevisionWireDict(
        fingerprint=rev.fingerprint,
        observed_unix=rev.observed_unix,
        label=rev.label,
    )
    if isinstance(decision, Dispatch):
        return SourceDecisionWireDict(
            kind=DecisionKind.DISPATCH.value,
            source_revision=rev_model,
            decided_unix=decision.decided_unix,
            reason_code=decision.reason_code,
            reason=decision.reason,
            work=[_work_request_to_wire(w) for w in decision.work],
        )
    if isinstance(decision, Wait):
        return SourceDecisionWireDict(
            kind=DecisionKind.WAIT.value,
            source_revision=rev_model,
            decided_unix=decision.decided_unix,
            reason_code=decision.reason_code,
            reason=decision.reason,
            wake_on_source_change=decision.wake_on_source_change,
            retry_after_seconds=decision.retry_after_seconds,
            until_unix=decision.until_unix,
            payload=dict(decision.payload) if decision.payload else {},
        )
    if isinstance(decision, OperatorRequired):
        return SourceDecisionWireDict(
            kind=DecisionKind.OPERATOR_REQUIRED.value,
            source_revision=rev_model,
            decided_unix=decision.decided_unix,
            reason_code=decision.reason_code,
            reason=decision.reason,
        )
    # Exhaustiveness: at this point the union has narrowed to Stop.
    assert isinstance(decision, Stop)
    return SourceDecisionWireDict(
        kind=DecisionKind.STOP.value,
        source_revision=rev_model,
        decided_unix=decision.decided_unix,
        reason_code=decision.reason_code,
        reason=decision.reason,
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
#: from :mod:`pi_monitor.protocol.work_envelopes` so consumers do not need to
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
    each envelope has ``extra="allow"`` (per @INV-0007 wire-compat
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
    "CanonicalReasonCode",
    "EXTENDED_REASON_CODES",
    "OS_EXTENDED_REASON_CODES",
    "DecisionKind",
    "DecisionKindLiteral",
    "Dispatch",
    "OperationKind",
    "OperatorRequired",
    "PAYLOAD_KEY_MATH_DIRECTIVE_CONTENT_HASH",
    "PAYLOAD_KEY_MATH_DIRECTIVE_TEMPLATE_HASH",
    "PAYLOAD_KEY_MATH_TARGET",
    "PAYLOAD_KEY_PREVIOUS_PAYLOAD",
    "PAYLOAD_KEY_STAGNATION_SESSION_COUNT",
    "PayloadKeyPlan013",
    "REASON_ARCHITECTURE_REVIEW_DISPATCH",
    "REASON_ARCHITECTURE_REVIEW_REQUIRED",
    "REASON_BLOCKED_WORK_PRESENT",
    "REASON_FRONTIER_EXHAUSTED",
    "REASON_NO_ELIGIBLE_WORK",
    "REASON_OPERATOR_REQUIRED",
    "REASON_STOP_REQUESTED",
    "REASON_WAIT_REQUESTED",
    "REASON_WORK_AVAILABLE",
    "ReasonCodeLiteral",
    "RoleName",
    "SourceDecision",
    "SourceDecisionWireDict",
    "SourceIdentity",
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
    "WorkRequestRoleAlias",
    "WorkRequestWireDict",
    "WorkspaceName",
    "decision_kind",
    "parse_source_decision",
    "parse_work_request_envelopes",
    "source_decision_to_wire",
]
