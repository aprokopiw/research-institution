"""Typed Pydantic wire-model tests for supervisor status payloads.

The :mod:`research_institution.status` module reads two files
written by the pi_monitor supervisor (``health.json`` and
``latest.json``). Until now these were TypedDicts which gave a
typed shape but didn't enforce it at runtime \u2014 a
``supervisor_pid = \"6339\"`` (string instead of int) would
slip through to the classifier and surface as a confusing
``TypeError`` deep inside the dispatch logic.

The Pydantic models in :mod:`research_institution.status_types`
own the wire shape. This test pins the typed parse boundary:
a malformed field fails fast at ``model_validate``, not deep in
the classifier. ``extra=\"allow\"`` keeps forward-compat.
"""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from research_institution.status import (
    read_status_headline,
)
from research_institution.status_types import (
    AuditSnapshot,
    CircuitSnapshot,
    ExecutionStateSnapshot,
    HealthPayload,
    LatestPayload,
)


class CircuitSnapshotTests(unittest.TestCase):
    def test_defaults(self) -> None:
        circuit = CircuitSnapshot()
        self.assertFalse(circuit.open)
        self.assertEqual(circuit.trip_count, 0)
        self.assertEqual(circuit.soft_until_unix, 0.0)

    def test_typed_attributes(self) -> None:
        circuit = CircuitSnapshot(open=True, trip_count=3, soft_until_unix=42.0)
        self.assertIs(circuit.open, True)
        self.assertEqual(circuit.trip_count, 3)

    def test_extra_fields_pass_through(self) -> None:
        circuit = CircuitSnapshot.model_validate(
            {"open": False, "trip_count": 0, "future_field": "y"}
        )
        self.assertEqual(circuit.model_extra, {"future_field": "y"})


class AuditSnapshotTests(unittest.TestCase):
    def test_default_chain_breaks(self) -> None:
        audit = AuditSnapshot()
        self.assertEqual(audit.chain_breaks, 0)

    def test_typed_chain_breaks(self) -> None:
        audit = AuditSnapshot(chain_breaks=2)
        self.assertEqual(audit.chain_breaks, 2)


class ExecutionStateSnapshotTests(unittest.TestCase):
    def test_defaults(self) -> None:
        ex = ExecutionStateSnapshot()
        self.assertEqual(ex.outcome, "")
        self.assertEqual(ex.attempt_ordinal, 0)
        self.assertEqual(ex.outcome_unix, 0.0)
        self.assertEqual(ex.active_key, "")


class HealthPayloadTests(unittest.TestCase):
    def test_minimal_health_parses(self) -> None:
        """A bare health document (no fields) parses with defaults."""
        h = HealthPayload.model_validate({})
        self.assertIsNone(h.supervisor_pid)
        self.assertEqual(h.audit.chain_breaks, 0)
        self.assertFalse(h.circuit.open)
        self.assertEqual(h.degraded, [])
        self.assertEqual(h.execution.outcome, "")

    def test_full_health_parses(self) -> None:
        h = HealthPayload.model_validate(
            {
                "supervisor_pid": 12345,
                "audit": {"chain_breaks": 1},
                "circuit": {"open": True, "trip_count": 5, "soft_until_unix": 100.0},
                "degraded": ["source_unavailable", "budget_exceeded"],
                "execution": {
                    "outcome": "blocked",
                    "attempt_ordinal": 3,
                    "outcome_unix": 1234567890.0,
                    "active_key": "kaplansky.x",
                },
            }
        )
        self.assertEqual(h.supervisor_pid, 12345)
        self.assertEqual(h.audit.chain_breaks, 1)
        self.assertTrue(h.circuit.open)
        self.assertEqual(h.circuit.trip_count, 5)
        self.assertEqual(h.degraded, ["source_unavailable", "budget_exceeded"])
        self.assertEqual(h.execution.outcome, "blocked")

    def test_extra_fields_pass_through(self) -> None:
        h = HealthPayload.model_validate(
            {"supervisor_pid": 1, "future_field": "y"}
        )
        self.assertEqual(h.model_extra, {"future_field": "y"})

    def test_non_int_supervisor_pid_rejected(self) -> None:
        """A ``supervisor_pid = {\"x\": 1}`` (object instead of int) is
        rejected at parse time. Pydantic v2 coerces ``\"6339\"`` to
        ``6339`` (lax mode) which is fine here — the writer always
        sends an int; the parse layer tolerates JSON's number/string
        ambiguity but rejects genuinely unparseable types."""
        with self.assertRaises(ValidationError):
            HealthPayload.model_validate({"supervisor_pid": {"x": 1}})

    def test_circuit_must_be_object(self) -> None:
        with self.assertRaises(ValidationError):
            HealthPayload.model_validate({"circuit": "not-an-object"})

    def test_degraded_must_be_list(self) -> None:
        with self.assertRaises(ValidationError):
            HealthPayload.model_validate({"degraded": "not-a-list"})


class LatestPayloadTests(unittest.TestCase):
    def test_minimal_latest_parses(self) -> None:
        latest = LatestPayload.model_validate({})
        self.assertEqual(latest.observed_unix, 0.0)

    def test_typed_observed_unix(self) -> None:
        latest = LatestPayload.model_validate({"observed_unix": 1234.5})
        self.assertEqual(latest.observed_unix, 1234.5)


class EndToEndTypedParseTests(unittest.TestCase):
    """End-to-end: malformed JSON \u2192 parse \u2192 classifier \u2192 status."""

    def test_malformed_supervisor_pid_silently_dropped(self) -> None:
        """A malformed ``health.json`` (e.g. ``supervisor_pid = \"x\"``)
        must not crash the classifier; the dispatcher's contract is
        \"one-line headline or 'unknown'\", not \"raise on transient
        state corruption\"."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            state_dir = Path(td)
            (state_dir / "health.json").write_text(
                '{"supervisor_pid": "not-an-int"}', encoding="utf-8"
            )
            # No ``latest.json`` -> NO_SUPERVISOR when health is dropped.
            h = read_status_headline("kaplansky", state_dir, now=1000.0)
            # Malformed health is dropped; classifier still returns
            # a sensible state.
            from research_institution.status import ProgramState
            self.assertIs(h.state, ProgramState.NO_SUPERVISOR)

    def test_real_health_json_parses(self) -> None:
        """The actual ``health.json`` written by pi_monitor must parse."""
        from pathlib import Path
        import json

        real = Path("/Users/erinprokopiw/.local/state/mathlint/pi-monitor/health.json")
        if not real.exists():
            self.skipTest(f"real health.json not found at {real}")
        raw = json.loads(real.read_text(encoding="utf-8"))
        h = HealthPayload.model_validate(raw)
        # Just verify the typed parse succeeded; the live values
        # depend on the supervisor's runtime state.
        self.assertIsInstance(h, HealthPayload)


if __name__ == "__main__":
    unittest.main()
