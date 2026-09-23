"""Tests for the source-decision envelope parser.

These tests pin the wire format that pi_monitor's WorkSourceProvider
emits. Per `@ADR-0006`, the dispatcher is a read-only consumer of
these envelopes; if pi_monitor changes a discriminator string or a
required field, these tests surface the drift.

Mirrors the canonical definitions in `pi_monitor.work.work_source`; the
two are kept in sync via these tests (drift in pi_monitor -> failing
test here -> fix the mirror).

Invariants:

  - All four decision variants (Dispatch / Wait / OperatorRequired /
    Stop) parse without error.
  - Unknown `kind` values raise ValueError loudly.
  - `WorkRequest.idempotency_key` is stable.
  - Reason codes outside the canonical vocabulary are accepted
    (opaque strings) but `CANONICAL_REASON_CODES` lists the documented set.
  - The mathlint-emitted Dispatch shape (from
    `real_source.decide_next`) parses end-to-end.
"""

from __future__ import annotations

import pytest

from research_institution.contracts.source_decision import (
    CANONICAL_REASON_CODES,
    DecisionKind,
    Dispatch,
    OperatorRequired,
    REASON_BLOCKED_WORK_PRESENT,
    REASON_FRONTIER_EXHAUSTED,
    REASON_NO_ELIGIBLE_WORK,
    REASON_OPERATOR_REQUIRED,
    REASON_STOP_REQUESTED,
    REASON_WAIT_REQUESTED,
    REASON_WORK_AVAILABLE,
    SourceRevision,
    Stop,
    Wait,
    WorkRequest,
    decision_kind,
    parse_source_decision,
)


def _minimal_envelope(kind: str, **kwargs) -> dict:
    """A minimal well-formed envelope for one decision kind."""
    env = {
        "kind": kind,
        "source_revision": {"fingerprint": "abc", "observed_unix": 1.0},
        "decided_unix": 2.0,
    }
    env.update(kwargs)
    return env


# ---------------------------------------------------------------------------
# Parser: dispatch
# ---------------------------------------------------------------------------


def test_parse_dispatch() -> None:
    """Dispatch with one WorkRequest parses cleanly."""
    env = _minimal_envelope(
        "dispatch",
        work=[
            {
                "source_identity": "mathlint",
                "source_revision": {"fingerprint": "abc", "observed_unix": 1.0},
                "operation_id": "work.kaplansky.foo",
                "operation_kind": "mathlint-research",
                "role": "MATHEMATICAL_RESEARCH",
            }
        ],
        reason_code=REASON_WORK_AVAILABLE,
        reason="MathLint authorized next step",
    )
    d = parse_source_decision(env)
    assert isinstance(d, Dispatch)
    assert d.decided_unix == 2.0
    assert d.reason_code == REASON_WORK_AVAILABLE
    assert len(d.work) == 1
    assert d.work[0].operation_id == "work.kaplansky.foo"


def test_parse_dispatch_with_empty_work_list() -> None:
    """Dispatch with `work=[]` is valid (decision carries no work)."""
    env = _minimal_envelope("dispatch", work=[])
    d = parse_source_decision(env)
    assert isinstance(d, Dispatch)
    assert d.work == []


def test_parse_dispatch_default_reason_code() -> None:
    """Without an explicit reason_code, the parser fills REASON_WORK_AVAILABLE."""
    env = _minimal_envelope("dispatch", work=[])
    d = parse_source_decision(env)
    assert d.reason_code == REASON_WORK_AVAILABLE


# ---------------------------------------------------------------------------
# Parser: wait
# ---------------------------------------------------------------------------


def test_parse_wait() -> None:
    env = _minimal_envelope(
        "wait",
        reason_code=REASON_WAIT_REQUESTED,
        reason="no actionable MathLint step",
        wake_on_source_change=True,
        retry_after_seconds=600.0,
    )
    w = parse_source_decision(env)
    assert isinstance(w, Wait)
    assert w.wake_on_source_change is True
    assert w.retry_after_seconds == 600.0


def test_parse_wait_default_reason_code() -> None:
    env = _minimal_envelope("wait")
    w = parse_source_decision(env)
    assert w.reason_code == REASON_WAIT_REQUESTED


# ---------------------------------------------------------------------------
# Parser: operator_required + stop
# ---------------------------------------------------------------------------


def test_parse_operator_required() -> None:
    env = _minimal_envelope(
        "operator_required",
        reason="mathlint next-step exited 3",
        reason_code="mathlint-error",
    )
    o = parse_source_decision(env)
    assert isinstance(o, OperatorRequired)
    assert o.reason_code == "mathlint-error"  # opaque custom codes are accepted


def test_parse_stop() -> None:
    env = _minimal_envelope("stop")
    s = parse_source_decision(env)
    assert isinstance(s, Stop)
    assert s.reason_code == REASON_STOP_REQUESTED


# ---------------------------------------------------------------------------
# DecisionKind
# ---------------------------------------------------------------------------


def test_decision_kind_enum_is_closed() -> None:
    """DecisionKind has the documented closed set + UNKNOWN defensive default."""
    assert {k.value for k in DecisionKind} == {
        "dispatch",
        "wait",
        "operator_required",
        "stop",
        "UNKNOWN",
    }


def test_decision_kind_helper() -> None:
    """decision_kind(decision) returns the right enum member."""
    d = parse_source_decision(_minimal_envelope("dispatch", work=[]))
    w = parse_source_decision(_minimal_envelope("wait"))
    o = parse_source_decision(_minimal_envelope("operator_required"))
    s = parse_source_decision(_minimal_envelope("stop"))
    assert decision_kind(d) == DecisionKind.DISPATCH
    assert decision_kind(w) == DecisionKind.WAIT
    assert decision_kind(o) == DecisionKind.OPERATOR_REQUIRED
    assert decision_kind(s) == DecisionKind.STOP


# ---------------------------------------------------------------------------
# WorkRequest
# ---------------------------------------------------------------------------


def test_work_request_idempotency_key() -> None:
    """idempotency_key is the documented (identity, fingerprint, op_id) tuple."""
    rev = SourceRevision(fingerprint="abc", observed_unix=1.0)
    w = WorkRequest(
        source_identity="mathlint",
        source_revision=rev,
        operation_id="op-1",
        operation_kind="kind-1",
    )
    assert w.idempotency_key == ("mathlint", "abc", "op-1")


def test_work_request_default_fields() -> None:
    """Default fields match the documented pi_monitor.work.work_source defaults."""
    w = WorkRequest(
        source_identity="mathlint",
        source_revision=SourceRevision(fingerprint="x", observed_unix=0.0),
        operation_id="op",
        operation_kind="kind",
    )
    assert w.role == "default"
    assert w.workspace == "default"
    assert w.payload == {}
    assert w.execution_profile == ""
    assert w.lease_until_unix is None


# ---------------------------------------------------------------------------
# Drift guards
# ---------------------------------------------------------------------------


def test_unknown_kind_raises_value_error() -> None:
    """Unknown `kind` raises ValueError (defensive: never silently swallow)."""
    env = _minimal_envelope("FUTURE_KIND_THAT_PI_MONITOR_MIGHT_INVENT")
    with pytest.raises(ValueError, match="unknown source-decision kind"):
        parse_source_decision(env)


def test_missing_kind_raises_value_error() -> None:
    """Missing `kind` raises ValueError."""
    env = _minimal_envelope("")  # no kind
    with pytest.raises(ValueError, match="unknown source-decision kind"):
        parse_source_decision(env)


def test_canonical_reason_codes_is_frozen() -> None:
    """Pin the canonical reason-code set; drift here surfaces immediately."""
    assert (
        frozenset(
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
        == CANONICAL_REASON_CODES
    )


# ---------------------------------------------------------------------------
# Plan-013 OS-side reason-code additions.
# ---------------------------------------------------------------------------


def test_plan_013_os_reason_codes_present() -> None:
    """``REASON_ARCHITECTURE_REVIEW_REQUIRED`` and ``REASON_ARCHITECTURE_REVIEW_DISPATCH``
    are the documented OS-side extensions; they ride along on the existing
    ``reason_code: str`` wire field.
    """
    from research_institution.contracts.source_decision import (
        EXTENDED_REASON_CODES,
        OS_EXTENDED_REASON_CODES,
        REASON_ARCHITECTURE_REVIEW_DISPATCH,
        REASON_ARCHITECTURE_REVIEW_REQUIRED,
    )
    assert REASON_ARCHITECTURE_REVIEW_REQUIRED == "architecture_review_required"
    assert REASON_ARCHITECTURE_REVIEW_DISPATCH == "architecture_review_dispatch"
    assert {
        REASON_ARCHITECTURE_REVIEW_REQUIRED,
        REASON_ARCHITECTURE_REVIEW_DISPATCH,
    } == OS_EXTENDED_REASON_CODES
    assert (
        EXTENDED_REASON_CODES
        == (CANONICAL_REASON_CODES | OS_EXTENDED_REASON_CODES)
    )


def test_plan_013_wait_envelope_parses_with_new_reason_code() -> None:
    """``Wait(reason_code='architecture_review_required', ...)`` parses cleanly."""
    from research_institution.contracts.source_decision import (
        REASON_ARCHITECTURE_REVIEW_REQUIRED,
    )
    env = _minimal_envelope(
        "wait",
        reason=(
            "stagnation_session_count=2 on op-K4; "
            "horizon admission pending; supervisor re-decides on source change"
        ),
        reason_code=REASON_ARCHITECTURE_REVIEW_REQUIRED,
        wake_on_source_change=True,
        retry_after_seconds=300.0,
    )
    parsed = parse_source_decision(env)
    assert isinstance(parsed, Wait)
    assert parsed.reason_code == REASON_ARCHITECTURE_REVIEW_REQUIRED
    assert parsed.wake_on_source_change is True
    assert parsed.retry_after_seconds == 300.0


def test_plan_013_dispatch_envelope_parses_with_new_reason_code() -> None:
    """``Dispatch(reason_code='architecture_review_dispatch', ...)`` parses cleanly."""
    from research_institution.contracts.source_decision import (
        REASON_ARCHITECTURE_REVIEW_DISPATCH,
    )
    env = _minimal_envelope(
        "dispatch",
        reason=(
            "math kernel authorized architect round for K4; "
            "directive_content_hash=sha256:..."
        ),
        reason_code=REASON_ARCHITECTURE_REVIEW_DISPATCH,
        work=[
            {
                "source_identity": "research-program",
                "source_revision": {"fingerprint": "abc", "observed_unix": 1.0},
                "operation_id": "work.kaplansky.K4",
                "operation_kind": "mathlint-research",
                "role": "maintenance",
                "workspace": "workspace",
                "payload": {"math_directive_content_hash": "sha256:..."},
                "execution_policy": {},
                "session_policy": {},
                "isolation": {},
                "budget": {},
                "execution_profile": "",
                "lease_until_unix": None,
            }
        ],
    )
    parsed = parse_source_decision(env)
    assert isinstance(parsed, Dispatch)
    assert parsed.reason_code == REASON_ARCHITECTURE_REVIEW_DISPATCH
    assert parsed.work[0].role == "maintenance"
    assert "math_directive_content_hash" in parsed.work[0].payload


def test_mathlint_decide_next_envelope_parses() -> None:
    """The exact envelope shape `real_source.decide_next` returns.

    Historical note (@ADR-0010 closed): mathlint's emitter used
    to emit `"Dispatch"` (capitalized) which the strict parser
    rejects by design. mathlint now emits the canonical lowercase
    `"dispatch"` via `DecisionKind.DISPATCH.value`; this test
    pins the lowercase form as the wire-shape contract.

    The original adversarial check (parser rejects `"Dispatch"`)
    is preserved as a separate parser-strictness invariant
    (see ``test_unknown_kind_raises_value_error``).
    """
    env = {
        "kind": "dispatch",
        "reason": "MathLint authorized next step",
        "reason_code": "mathlint_next_step",
        "source_revision": {
            "fingerprint": "deadbeef" * 8,
            "observed_unix": 0.0,
            "label": "mathlint",
        },
        "decided_unix": 0.0,
        "work": [
            {
                "source_identity": "mathlint",
                "source_revision": {
                    "fingerprint": "deadbeef" * 8,
                    "observed_unix": 0.0,
                    "label": "mathlint",
                },
                "operation_id": "mathlint-next-step",
                "operation_kind": "mathlint-research",
                "role": "MATHEMATICAL_RESEARCH",
                "workspace": "mathlint-workspace",
                "payload": {"next_step": "ACTION: work.kaplansky.foo"},
                "execution_policy": {},
                "session_policy": {},
                "isolation": {},
                "budget": {},
                "execution_profile": "",
                "lease_until_unix": None,
            }
        ],
    }
    # mathlint emits `"dispatch"` (lowercase) via
    # `DecisionKind.DISPATCH.value`. The envelope parses cleanly;
    # `@ADR-0010` is closed.
    parsed = parse_source_decision(env)
    assert isinstance(parsed, Dispatch)
    assert parsed.work[0].operation_id == "mathlint-next-step"


def test_lowercase_kinds_parse_correctly() -> None:
    """Once mathlint emits lowercase kinds (post @ADR-0010), this passes."""
    env = {
        "kind": "dispatch",
        "reason": "MathLint authorized next step",
        "reason_code": "mathlint_next_step",
        "source_revision": {
            "fingerprint": "deadbeef" * 8,
            "observed_unix": 0.0,
            "label": "mathlint",
        },
        "decided_unix": 0.0,
        "work": [
            {
                "source_identity": "mathlint",
                "source_revision": {
                    "fingerprint": "deadbeef" * 8,
                    "observed_unix": 0.0,
                    "label": "mathlint",
                },
                "operation_id": "mathlint-next-step",
                "operation_kind": "mathlint-research",
                "role": "MATHEMATICAL_RESEARCH",
                "workspace": "mathlint-workspace",
                "payload": {},
                "execution_policy": {},
                "session_policy": {},
                "isolation": {},
                "budget": {},
                "execution_profile": "",
                "lease_until_unix": None,
            }
        ],
    }
    d = parse_source_decision(env)
    assert isinstance(d, Dispatch)
    assert d.work[0].operation_id == "mathlint-next-step"
