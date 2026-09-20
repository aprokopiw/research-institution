"""Typed wire-shape tests for ``SourceDecisionWireDict`` and friends.

The TypedDict wire shapes in :mod:`research_institution.contracts.source_decision`
were replaced with Pydantic models (``SourceDecisionWireDict``,
``WorkRequestWireDict``, ``SourceRevisionWireDict``). The Pydantic
models own the wire shape; ``model_dump(exclude_none=True)`` gives
the dict shape legacy callers expect.

Why Pydantic and not TypedDict:
- TypedDict doesn't enforce required fields at runtime; a missing
  ``fingerprint`` in ``SourceRevisionWireDict`` would slip through
  to the downstream consumer.
- Pydantic's ``model_validate`` is the typed parse boundary;
  ``extra="allow"`` preserves forward-compat with future fields.
- TypedDict's optional-key semantics (``total=False``) leak
  through ``.get(key, default)`` at every read site; Pydantic's
  field declarations enforce the typed shape at the source.
"""

from __future__ import annotations

import unittest

from pi_monitor.work.work_source import (
    DecisionKind,
    Dispatch,
    OperatorRequired,
    SourceRevision,
    Stop,
    Wait,
)

from research_institution.contracts.source_decision import (
    REASON_NO_ELIGIBLE_WORK,
    REASON_STOP_REQUESTED,
    REASON_WAIT_REQUESTED,
    REASON_WORK_AVAILABLE,
    SourceDecisionWireDict,
    SourceRevisionWireDict,
    WorkRequestWireDict,
    decision_kind,
    parse_source_decision,
    source_decision_to_wire,
)


class SourceRevisionWireDictTests(unittest.TestCase):
    def test_required_fields_have_defaults_for_backcompat(self) -> None:
        """A bare revision round-trips with default fingerprint/observed_unix."""
        rev = SourceRevisionWireDict()
        self.assertEqual(rev.fingerprint, "")
        self.assertEqual(rev.observed_unix, 0.0)
        self.assertEqual(rev.label, "")

    def test_extra_fields_pass_through(self) -> None:
        """``extra="allow"`` keeps forward-compat with future fields."""
        rev = SourceRevisionWireDict.model_validate(
            {"fingerprint": "fp-1", "observed_unix": 1000.0, "future_field": "x"}
        )
        self.assertEqual(rev.fingerprint, "fp-1")
        self.assertEqual(rev.model_extra, {"future_field": "x"})

    def test_to_dataclass_round_trip(self) -> None:
        wire = SourceRevisionWireDict(
            fingerprint="fp-X", observed_unix=42.5, label="rev-X"
        )
        # The wire model is ri-internal; the canonical dataclass
        # is pi_monitor's ``SourceRevision``.
        from pi_monitor.work.work_source import SourceRevision

        d = SourceRevision(
            fingerprint=wire.fingerprint,
            observed_unix=wire.observed_unix,
            label=wire.label,
        )
        self.assertEqual(d.fingerprint, "fp-X")
        self.assertEqual(d.observed_unix, 42.5)


class WorkRequestWireDictTests(unittest.TestCase):
    def test_required_fields_have_sensible_defaults(self) -> None:
        """All fields except the three required have defaults."""
        req = WorkRequestWireDict.model_validate(
            {
                "source_identity": "mathlint-research-program",
                "source_revision": {
                    "fingerprint": "fp",
                    "observed_unix": 1.0,
                },
                "operation_id": "op-1",
                "operation_kind": "mathlint-research",
            }
        )
        self.assertEqual(req.role, "default")
        self.assertEqual(req.workspace, "default")
        self.assertEqual(req.payload, {})
        self.assertEqual(req.execution_policy, {})
        self.assertIsNone(req.lease_until_unix)

    def test_extra_fields_pass_through(self) -> None:
        req = WorkRequestWireDict.model_validate(
            {
                "source_identity": "x",
                "source_revision": {"fingerprint": "fp", "observed_unix": 1.0},
                "operation_id": "op",
                "operation_kind": "mathlint-research",
                "future_field": "y",
            }
        )
        self.assertEqual(req.model_extra, {"future_field": "y"})

    def test_missing_required_field_rejected(self) -> None:
        """Missing ``source_identity`` fails fast at the parse boundary."""
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            WorkRequestWireDict.model_validate(
                {
                    "source_revision": {
                        "fingerprint": "fp",
                        "observed_unix": 1.0,
                    },
                    "operation_id": "op",
                    "operation_kind": "mathlint-research",
                }
            )


class SourceDecisionWireDictTests(unittest.TestCase):
    def test_kind_is_open_string_at_wire_layer(self) -> None:
        """The wire model accepts any string for ``kind``; the canonical
        ``DecisionKind`` enum validation happens in the parser."""
        wire = SourceDecisionWireDict.model_validate({"kind": "wait"})
        self.assertEqual(wire.kind, "wait")

    def test_unknown_kind_accepted_by_wire_model(self) -> None:
        """The wire model is forward-compat; an unknown kind only fails
        when the parser tries to dispatch on it."""
        wire = SourceDecisionWireDict.model_validate({"kind": "garbage"})
        self.assertEqual(wire.kind, "garbage")

    def test_missing_source_revision_defaults_to_empty(self) -> None:
        """The wire model accepts a missing ``source_revision`` (legacy
        envelopes omit it); the parser builds an empty dataclass."""
        wire = SourceDecisionWireDict.model_validate({"kind": "wait"})
        self.assertIsNone(wire.source_revision)

    def test_extra_fields_pass_through(self) -> None:
        wire = SourceDecisionWireDict.model_validate(
            {
                "kind": "wait",
                "future_field": "y",
            }
        )
        self.assertEqual(wire.model_extra, {"future_field": "y"})

    def test_model_dump_exclude_none_strips_unset_fields(self) -> None:
        wire = SourceDecisionWireDict(kind="wait", decided_unix=1.0)
        dumped = wire.model_dump(exclude_none=True)
        self.assertEqual(
            set(dumped.keys()),
            {"kind", "decided_unix"},
        )


class WireSerializationTests(unittest.TestCase):
    """End-to-end: typed -> wire model -> parse -> typed."""

    def _wait(self) -> Wait:
        return Wait(
            source_revision=SourceRevision(
                fingerprint="fp-1", observed_unix=1.0, label="rev-1"
            ),
            decided_unix=1.0,
            reason_code=REASON_WAIT_REQUESTED,
            reason="nothing eligible",
            wake_on_source_change=True,
            retry_after_seconds=30.0,
        )

    def _dispatch(self) -> Dispatch:
        return Dispatch(
            source_revision=SourceRevision(
                fingerprint="fp-2", observed_unix=2.0, label="rev-2"
            ),
            decided_unix=2.0,
            reason_code=REASON_WORK_AVAILABLE,
            reason="work available",
            work=[],
        )

    def _stop(self) -> Stop:
        return Stop(
            source_revision=SourceRevision(
                fingerprint="fp-3", observed_unix=3.0, label="rev-3"
            ),
            decided_unix=3.0,
            reason_code=REASON_STOP_REQUESTED,
            reason="stop",
        )

    def _operator_required(self) -> OperatorRequired:
        return OperatorRequired(
            source_revision=SourceRevision(
                fingerprint="fp-4", observed_unix=4.0, label="rev-4"
            ),
            decided_unix=4.0,
            reason_code=REASON_NO_ELIGIBLE_WORK,
            reason="operator",
        )

    def test_wait_round_trips(self) -> None:
        original = self._wait()
        wire = source_decision_to_wire(original)
        dumped = wire.model_dump(exclude_none=True)
        parsed = parse_source_decision(dumped)
        self.assertEqual(parsed, original)
        self.assertIsInstance(parsed, Wait)
        self.assertIs(decision_kind(parsed), DecisionKind.WAIT)

    def test_dispatch_round_trips(self) -> None:
        original = self._dispatch()
        wire = source_decision_to_wire(original)
        dumped = wire.model_dump(exclude_none=True)
        parsed = parse_source_decision(dumped)
        self.assertEqual(parsed, original)
        self.assertIsInstance(parsed, Dispatch)
        self.assertIs(decision_kind(parsed), DecisionKind.DISPATCH)

    def test_stop_round_trips(self) -> None:
        original = self._stop()
        wire = source_decision_to_wire(original)
        dumped = wire.model_dump(exclude_none=True)
        parsed = parse_source_decision(dumped)
        self.assertEqual(parsed, original)
        self.assertIsInstance(parsed, Stop)
        self.assertIs(decision_kind(parsed), DecisionKind.STOP)

    def test_operator_required_round_trips(self) -> None:
        original = self._operator_required()
        wire = source_decision_to_wire(original)
        dumped = wire.model_dump(exclude_none=True)
        parsed = parse_source_decision(dumped)
        self.assertEqual(parsed, original)
        self.assertIsInstance(parsed, OperatorRequired)
        self.assertIs(decision_kind(parsed), DecisionKind.OPERATOR_REQUIRED)

    def test_wire_dumps_match_kind_string(self) -> None:
        """The wire ``kind`` field uses the DecisionKind string form."""
        wire = source_decision_to_wire(self._wait())
        self.assertEqual(wire.kind, "wait")
        wire = source_decision_to_wire(self._dispatch())
        self.assertEqual(wire.kind, "dispatch")
        wire = source_decision_to_wire(self._stop())
        self.assertEqual(wire.kind, "stop")
        wire = source_decision_to_wire(self._operator_required())
        self.assertEqual(wire.kind, "operator_required")


if __name__ == "__main__":
    unittest.main()
