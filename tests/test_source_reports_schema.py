"""Tests for the source-reports.jsonl typed parser.

These tests pin the wire format pi_monitor emits to
`~/.local/state/mathlint/pi-monitor/source-reports.jsonl`. If
pi_monitor's emitter changes a field name or adds a required field,
these tests catch it before any future observability surface breaks.

The fixture is a REAL line from the operator's local source-reports
(snapshot at HARDENING-CHECKLIST §E time). The test asserts that:

  - The fixture parses without error.
  - Every documented field is present and typed.
  - Unknown outcome/status values coerce to `OTHER` (defensive).
  - Malformed JSON raises ValueError.
  - Missing required fields raise ValueError.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_institution.contracts.source_reports import (
    Outcome,
    SourceReport,
    WorkStatus,
    parse_source_report,
)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "real_source_report.jsonl"


def test_real_fixture_parses() -> None:
    """The captured real line parses to a SourceReport with all fields."""
    if not FIXTURE_PATH.is_file():
        pytest.skip("real fixture not present (regenerate from source-reports.jsonl)")
    line = FIXTURE_PATH.read_text(encoding="utf-8").strip()
    r = parse_source_report(line)
    assert isinstance(r, SourceReport)
    assert r.attempt_ordinal == 1
    assert r.outcome == "submitted"
    assert r.status == "completed"
    assert r.source_identity == "kaplansky"
    assert r.exit_code is None  # null in the wire, None in Python


def test_required_fields_enforced() -> None:
    """Missing required fields raise ValueError."""
    bad = json.dumps({"attempt_id": "x-1", "attempt_ordinal": 1})  # missing most fields
    with pytest.raises(KeyError):
        parse_source_report(bad)


def test_malformed_json_raises() -> None:
    """Non-JSON input raises ValueError (via json.loads)."""
    with pytest.raises(ValueError):
        parse_source_report("not json at all")


def test_unknown_outcome_coerces_to_other() -> None:
    """Unknown `outcome` value maps to `OTHER` (defensive default)."""
    data = json.dumps({
        "attempt_id": "x-1",
        "attempt_ordinal": 1,
        "digest": "abc",
        "envelope_digest": "abc",
        "operation_id": "op",
        "outcome": "FUTURE_THING_MATHLINT_INVENTED",
        "report_id": "x-1",
        "source_identity": "mathlint",
        "source_revision": "deadbeef",
        "status": "pending",
    })
    r = parse_source_report(data)
    assert r.outcome == "OTHER"


def test_unknown_status_coerces_to_other() -> None:
    """Unknown `status` value maps to `OTHER`."""
    data = json.dumps({
        "attempt_id": "x-1",
        "attempt_ordinal": 1,
        "digest": "abc",
        "envelope_digest": "abc",
        "operation_id": "op",
        "outcome": "dispatch",
        "report_id": "x-1",
        "source_identity": "mathlint",
        "source_revision": "deadbeef",
        "status": "PARTIALLY_COMPLETE_FUTURE_STATE",
    })
    r = parse_source_report(data)
    assert r.status == "OTHER"


def test_known_outcome_round_trip() -> None:
    """Known Outcome values parse to themselves."""
    for outcome in [o for o in Outcome if o != Outcome.OTHER]:
        data = json.dumps({
            "attempt_id": "x-1",
            "attempt_ordinal": 1,
            "digest": "abc",
            "envelope_digest": "abc",
            "operation_id": "op",
            "outcome": outcome.value,
            "report_id": "x-1",
            "source_identity": "mathlint",
            "source_revision": "deadbeef",
            "status": "pending",
        })
        r = parse_source_report(data)
        assert r.outcome == outcome.value


def test_known_work_status_round_trip() -> None:
    """Known WorkStatus values parse to themselves."""
    for status in [s for s in WorkStatus if s != WorkStatus.OTHER]:
        data = json.dumps({
            "attempt_id": "x-1",
            "attempt_ordinal": 1,
            "digest": "abc",
            "envelope_digest": "abc",
            "operation_id": "op",
            "outcome": "dispatch",
            "report_id": "x-1",
            "source_identity": "mathlint",
            "source_revision": "deadbeef",
            "status": status.value,
        })
        r = parse_source_report(data)
        assert r.status == status.value


def test_outcome_enum_is_closed() -> None:
    """The Outcome enum has a known, finite set of values."""
    assert {o.value for o in Outcome} == {
        "dispatch",
        "wait",
        "stop",
        "operator_required",
        "blocked",
        "failed",
        "submitted",
        "counterexample",
        "OTHER",
    }


def test_work_status_enum_is_closed() -> None:
    """The WorkStatus enum has a known, finite set of values."""
    assert {s.value for s in WorkStatus} == {
        "pending",
        "in_progress",
        "completed",
        "failed",
        "blocked",
        "cancelled",
        "stalled",
        "OTHER",
    }


def test_exit_code_can_be_null_or_int() -> None:
    """`exit_code` accepts both null (JSON) and integer."""
    for exit_code in (None, 0, 7):
        data = json.dumps({
            "attempt_id": "x-1",
            "attempt_ordinal": 1,
            "digest": "abc",
            "envelope_digest": "abc",
            "operation_id": "op",
            "outcome": "dispatch",
            "report_id": "x-1",
            "source_identity": "mathlint",
            "source_revision": "deadbeef",
            "status": "pending",
            "exit_code": exit_code,
        })
        r = parse_source_report(data)
        assert r.exit_code == exit_code
