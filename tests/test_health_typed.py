"""Typed ``PreflightPayload`` wire contract.

The mathlint preflight command emits JSON; this module reads
that JSON through :class:`PreflightPayload` (Pydantic). A
malformed ``status`` string (``\"passed\"`` vs ``\"pass\"``)
fails fast at the Pydantic ValidationError boundary instead
of silently misclassifying the check.

These tests pin:

  - Canonical ``PreflightCheckStatus`` enum rejects unknown values.
  - The Pydantic wire model parses the canonical emit shape.
  - ``extra=\"allow\"`` keeps forward-compat with a future
    mathlint that adds a new field.
"""

from __future__ import annotations

import json
import unittest

from pydantic import ValidationError

from research_institution.health import (
    PreflightCheckStatus,
    PreflightCheckWire,
    PreflightPayload,
)


class PreflightCheckStatusTests(unittest.TestCase):
    """The canonical preflight-status vocabulary."""

    def test_canonical_values(self) -> None:
        self.assertEqual(PreflightCheckStatus.PASS.value, "pass")
        self.assertEqual(PreflightCheckStatus.FAIL.value, "fail")
        self.assertEqual(PreflightCheckStatus.SKIP.value, "skip")

    def test_unknown_value_rejected(self) -> None:
        with self.assertRaises(ValueError):
            PreflightCheckStatus("passed")


class PreflightCheckWireTests(unittest.TestCase):
    """Single-check Pydantic model."""

    def test_canonical_shape(self) -> None:
        check = PreflightCheckWire(
            id="check-1",
            name="green-gate",
            status="pass",
            detail="ok",
            suggestion="",
        )
        self.assertEqual(check.status, PreflightCheckStatus.PASS)
        self.assertEqual(check.id, "check-1")

    def test_unknown_status_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            PreflightCheckWire(status="passed")

    def test_extra_field_survives(self) -> None:
        # Forward-compat: a future mathlint adds a new field.
        check = PreflightCheckWire.model_validate(
            {"id": "x", "status": "pass", "duration_ms": 123.0}
        )
        self.assertEqual(check.model_extra.get("duration_ms"), 123.0)


class PreflightPayloadTests(unittest.TestCase):
    """Top-level payload round-trip."""

    def test_canonical_shape(self) -> None:
        payload = PreflightPayload(
            ok=True,
            checks=[
                PreflightCheckWire(
                    id="check-1",
                    name="green-gate",
                    status=PreflightCheckStatus.PASS,
                ),
                PreflightCheckWire(
                    id="check-2",
                    name="creds",
                    status=PreflightCheckStatus.FAIL,
                    detail="missing MATHLINT_*",
                ),
            ],
        )
        self.assertTrue(payload.ok)
        self.assertEqual(len(payload.checks), 2)
        self.assertEqual(payload.checks[0].status, PreflightCheckStatus.PASS)
        self.assertEqual(payload.checks[1].status, PreflightCheckStatus.FAIL)

    def test_empty_payload(self) -> None:
        payload = PreflightPayload.model_validate({})
        self.assertIsNone(payload.ok)
        self.assertEqual(payload.checks, [])

    def test_json_round_trip(self) -> None:
        text = json.dumps(
            {
                "ok": False,
                "checks": [
                    {"id": "x", "status": "fail", "detail": "broken"},
                ],
            }
        )
        payload = PreflightPayload.model_validate_json(text)
        self.assertFalse(payload.ok)
        self.assertEqual(payload.checks[0].status, PreflightCheckStatus.FAIL)


if __name__ == "__main__":
    unittest.main()
