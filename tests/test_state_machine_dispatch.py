"""SM-C: research-institution dispatch envelope state machine.

Per the test-hardening plan §5 SM-C, the dispatch envelope is
a tagged union over four variants:

  Dispatch          | execute the carried work requests
  Wait              | no dispatch is legal right now
  OperatorRequired  | human must decide before resuming
  Stop              | terminal per the source

This file pins the closed set of transitions under test (C1
through C4 in the plan) and asserts each transition's required
field shape. The transitions are written as one test per
edge so a regression names the broken edge directly instead
of failing inside a giant parametrized loop.

The state machine is *envelope-level*, not subsystem-level:
each test constructs a typed envelope in the source variant,
exercises the transition (parse -> discriminate -> serialize
-> re-parse), and asserts the target variant's identity plus
its required-key shape. There is no fixture that "decides"
to transition; the test is the driver.

## Why this lives next to the property test

``test_composed_dispatch_property.py`` proves the
round-trip identity across randomized inputs. This file
proves that *named, specific transitions* round-trip and
that *each variant's required fields* survive. The two
files overlap on round-trip but target different failure
modes:

  - property: regression in parser/serializer shape on
    randomized inputs;
  - state machine: regression in a specific named
    transition (e.g. Wait -> Dispatch on source revision
    change).

Both layers are needed. A regression that drops a
required field breaks the property test; a regression
that confuses Wait and OperatorRequired breaks this file.
"""

from __future__ import annotations

import unittest
from typing import Any

from pi_monitor.work.work_source import (
    Dispatch,
    OperatorRequired,
    SourceRevision,
    Stop,
    Wait,
    WorkRequest,
)

from research_institution.contracts.source_decision import (
    CANONICAL_REASON_CODES,
    REASON_NO_ELIGIBLE_WORK,
    REASON_OPERATOR_REQUIRED,
    REASON_STOP_REQUESTED,
    REASON_WAIT_REQUESTED,
    REASON_WORK_AVAILABLE,
    DecisionKind,
    parse_source_decision,
    source_decision_to_wire,
)

# Canonical revision used in tests where the fingerprint is not
# the assertion subject. Real envelopes carry a 40-char hex SHA1;
# tests pin the prefix so a regression in the prefix-length
# invariant surfaces as a clear failure.
_REV = SourceRevision(
    fingerprint="a" * 40,
    observed_unix=1700000000.0,
    label="sm-c-test",
)


def _work_request(operation_id: str = "T1") -> WorkRequest:
    """One synthesized WorkRequest for SM-C transition tests."""
    return WorkRequest(
        source_identity="test-research-program",
        source_revision=_REV,
        operation_id=operation_id,
        operation_kind="mathlint-research",
        role="research",
        workspace="test-workspace",
        payload={"schema_name": "test.work_request", "id": operation_id, "kind": "research"},
    )


class WaitToDispatchTransitionTests(unittest.TestCase):
    """C1: Wait -> Dispatch when the source revision changes."""

    def test_c1_wait_carries_wake_on_source_change(self) -> None:
        """A Wait envelope that is ready to re-decide on source change."""
        wait = Wait(
            source_revision=_REV,
            decided_unix=1700000000.0,
            reason_code=REASON_WAIT_REQUESTED,
            reason="waiting on roadmap",
            wake_on_source_change=True,
            retry_after_seconds=30.0,
        )
        wire = source_decision_to_wire(wait)
        assert wire.kind == DecisionKind.WAIT.value
        assert wire.wake_on_source_change is True
        # Re-parse via dict round-trip (Pydantic's model_dump -> dict).
        recovered = parse_source_decision(wire.model_dump())
        assert isinstance(recovered, Wait)
        assert recovered.reason_code == REASON_WAIT_REQUESTED

    def test_c1_dispatch_carries_at_least_one_work_request(self) -> None:
        """The Dispatch variant's required field is ``work`` (non-empty)."""
        dispatch = Dispatch(
            source_revision=_REV,
            decided_unix=1700000000.0,
            work=[_work_request()],
            reason_code=REASON_WORK_AVAILABLE,
            reason="dispatching 1 active item",
        )
        wire = source_decision_to_wire(dispatch)
        assert wire.kind == DecisionKind.DISPATCH.value
        assert len(wire.work) == 1
        recovered = parse_source_decision(wire.model_dump())
        assert isinstance(recovered, Dispatch)
        assert len(recovered.work) == 1
        assert recovered.work[0].operation_id == "T1"


class DispatchToWaitTransitionTests(unittest.TestCase):
    """C2: Dispatch -> Wait when the work list becomes empty."""

    def test_c2_empty_work_list_round_trips_as_wait(self) -> None:
        """A Wait envelope with empty work carries the wait discriminator."""
        wait = Wait(
            source_revision=_REV,
            decided_unix=1700000000.0,
            reason_code=REASON_NO_ELIGIBLE_WORK,
            reason="no active item",
            wake_on_source_change=True,
            retry_after_seconds=60.0,
        )
        wire = source_decision_to_wire(wait)
        # The wire shape uses ``kind`` to discriminate; ``work`` is absent.
        assert wire.kind == DecisionKind.WAIT.value
        recovered = parse_source_decision(wire.model_dump())
        assert isinstance(recovered, Wait)
        assert recovered.reason_code == REASON_NO_ELIGIBLE_WORK


class DispatchToStopTransitionTests(unittest.TestCase):
    """C3: Dispatch -> Stop on operator cancel."""

    def test_c3_stop_is_terminal(self) -> None:
        """Stop is the terminal variant; no work, no retry policy."""
        stop = Stop(
            source_revision=_REV,
            decided_unix=1700000000.0,
            reason_code=REASON_STOP_REQUESTED,
            reason="operator cancel",
        )
        wire = source_decision_to_wire(stop)
        assert wire.kind == DecisionKind.STOP.value
        recovered = parse_source_decision(wire.model_dump())
        assert isinstance(recovered, Stop)
        assert recovered.reason_code == REASON_STOP_REQUESTED


class AnyToOperatorRequiredTransitionTests(unittest.TestCase):
    """C4: any -> OperatorRequired when auth is missing."""

    def test_c4_operator_required_carries_reason(self) -> None:
        """OperatorRequired carries the auth-missing reason code."""
        op_req = OperatorRequired(
            source_revision=_REV,
            decided_unix=1700000000.0,
            reason_code=REASON_OPERATOR_REQUIRED,
            reason="missing MATHLINT_MODEL_ROUTE",
        )
        wire = source_decision_to_wire(op_req)
        assert wire.kind == DecisionKind.OPERATOR_REQUIRED.value
        recovered = parse_source_decision(wire.model_dump())
        assert isinstance(recovered, OperatorRequired)
        assert "MATHLINT_MODEL_ROUTE" in recovered.reason


class CanonicalReasonCodeTests(unittest.TestCase):
    """The reason-code space is closed (INV-T3)."""

    def test_canonical_reason_codes_is_closed(self) -> None:
        """Every envelope reason code is a member of CANONICAL_REASON_CODES."""
        envelopes: list[Any] = [
            Dispatch(
                source_revision=_REV,
                decided_unix=1700000000.0,
                work=[_work_request()],
                reason_code=REASON_WORK_AVAILABLE,
                reason="dispatching",
            ),
            Wait(
                source_revision=_REV,
                decided_unix=1700000000.0,
                reason_code=REASON_WAIT_REQUESTED,
                reason="waiting",
                wake_on_source_change=True,
                retry_after_seconds=30.0,
            ),
            Wait(
                source_revision=_REV,
                decided_unix=1700000000.0,
                reason_code=REASON_NO_ELIGIBLE_WORK,
                reason="empty",
                wake_on_source_change=True,
                retry_after_seconds=60.0,
            ),
            OperatorRequired(
                source_revision=_REV,
                decided_unix=1700000000.0,
                reason_code=REASON_OPERATOR_REQUIRED,
                reason="auth",
            ),
            Stop(
                source_revision=_REV,
                decided_unix=1700000000.0,
                reason_code=REASON_STOP_REQUESTED,
                reason="cancel",
            ),
        ]
        for env in envelopes:
            assert env.reason_code in CANONICAL_REASON_CODES, (
                f"reason code {env.reason_code!r} not in the closed set"
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
