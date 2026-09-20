"""Typed-envelope contract on the WorkRequest opaque fields.

The five opaque fields on a ``WorkRequest`` (``payload`` /
``execution_policy`` / ``session_policy`` / ``isolation`` /
``budget``) are source-owned. This test pins the typed-shape
boundary at the research-institution side: the OS imports the
Pydantic models from ``pi_monitor.protocol.work_envelopes`` via
``contracts.source_decision`` and exposes a one-shot parser
(:func:`parse_work_request_envelopes`) so every consumer sees a
strict shape, not ``dict[str, object]``.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from pi_monitor.work.work_source import SourceRevision, WorkRequest

from research_institution.contracts.source_decision import (
    TypedBudgetPolicy,
    TypedExecutionPolicy,
    TypedIsolationPolicy,
    TypedSessionPolicy,
    TypedWorkRequestPayload,
    parse_work_request_envelopes,
)


def _work_request(**overrides: object) -> WorkRequest:
    """Build a synthetic WorkRequest with overridable opaque fields.

    Default fields are exercised on every call so the parser must
    handle ``{}``-style defaults without raising.
    """
    fields: dict[str, object] = {
        "source_identity": "test-source",
        "source_revision": SourceRevision(
            fingerprint="fp-1",
            observed_unix=datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp(),
            label="rev-fp-1",
        ),
        "operation_id": "op-1",
        "operation_kind": "test-kind",
    }
    fields.update(overrides)
    return WorkRequest(**fields)  # type: ignore[arg-type]


class TypedEnvelopeReExportsTests(unittest.TestCase):
    """The re-exported typed models are the canonical Pydantic models."""

    def test_re_exports_match_canonical_models(self) -> None:
        # The five typed models in research-institution are the
        # same class objects as the canonical ones in pi_monitor.
        # A drift in pi_monitor's wire shape surfaces at every
        # import site in research-institution.
        from pi_monitor.protocol.work_envelopes import (
            BudgetPolicy as PM_Budget,
            ExecutionPolicy as PM_Execution,
            IsolationPolicy as PM_Isolation,
            SessionPolicy as PM_Session,
            WorkRequestPayload as PM_Payload,
        )
        self.assertIs(TypedBudgetPolicy, PM_Budget)
        self.assertIs(TypedExecutionPolicy, PM_Execution)
        self.assertIs(TypedIsolationPolicy, PM_Isolation)
        self.assertIs(TypedSessionPolicy, PM_Session)
        self.assertIs(TypedWorkRequestPayload, PM_Payload)


class ParseWorkRequestEnvelopesTests(unittest.TestCase):
    """parse_work_request_envelopes is the single typed boundary."""

    def test_default_opaque_fields_parse_to_all_none(self) -> None:
        # A WorkRequest with no populated opaque fields is the
        # common case in non-research deployments. The parser must
        # produce typed envelopes with all-None defaults, not
        # crash on the missing keys.
        request = _work_request()
        payload, exec_p, sess_p, isol_p, budget_p = parse_work_request_envelopes(request)
        # Each envelope is the canonical Pydantic model.
        self.assertIsInstance(payload, TypedWorkRequestPayload)
        self.assertIsInstance(exec_p, TypedExecutionPolicy)
        self.assertIsInstance(sess_p, TypedSessionPolicy)
        self.assertIsInstance(isol_p, TypedIsolationPolicy)
        self.assertIsInstance(budget_p, TypedBudgetPolicy)
        # All fields default to None.
        self.assertIsNone(payload.schema_name)
        self.assertIsNone(exec_p.max_attempts)
        self.assertIsNone(exec_p.max_cost)
        self.assertIsNone(sess_p.fresh_session)
        self.assertIsNone(isol_p.no_network)
        self.assertIsNone(budget_p.max_cost_usd)

    def test_populated_opaque_fields_parse_strictly(self) -> None:
        request = _work_request(
            payload={
                "schema_name": "kaplansky-roadmap-item/v1",
                "item_id": "K5",
                "title": "Weighted relation-kernel descent",
            },
            execution_policy={"max_attempts": 3, "max_cost": 5.0},
            session_policy={"fresh_session": True},
            isolation={"no_network": True, "git_branch": "main"},
            budget={"max_cost_usd": 1.50, "max_wall_seconds": 7200.0},
        )
        payload, exec_p, sess_p, isol_p, budget_p = parse_work_request_envelopes(request)
        self.assertEqual(payload.item_id, "K5")
        self.assertEqual(payload.title, "Weighted relation-kernel descent")
        self.assertEqual(payload.schema_name, "kaplansky-roadmap-item/v1")
        self.assertEqual(exec_p.max_attempts, 3)
        self.assertEqual(exec_p.max_cost, 5.0)
        self.assertTrue(sess_p.fresh_session)
        self.assertTrue(isol_p.no_network)
        self.assertEqual(isol_p.git_branch, "main")
        self.assertEqual(budget_p.max_cost_usd, 1.50)
        self.assertEqual(budget_p.max_wall_seconds, 7200.0)

    def test_extra_allow_contract_survives_parse(self) -> None:
        # A future source may add a new field on any envelope. The
        # wire-compat contract is ``extra="allow"``: an older
        # consumer's parser must NOT reject the unknown field, and
        # must keep it round-trippable via ``.model_dump()``.
        request = _work_request(
            payload={
                "schema_name": "kaplansky-roadmap-item/v1",
                "future_field_unknown_to_this_consumer": "future_value",
            },
        )
        payload, _exec, _sess, _isol, _budget = parse_work_request_envelopes(request)
        self.assertEqual(
            payload.model_dump()["future_field_unknown_to_this_consumer"],
            "future_value",
        )


if __name__ == "__main__":
    unittest.main()
