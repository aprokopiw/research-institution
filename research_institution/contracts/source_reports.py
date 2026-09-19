"""Typed view of pi_monitor's source-reports.jsonl.

Per `@ADR-0006`, research-institution does NOT own the source-reports
format; pi_monitor writes them and mathlint consumes them. This module
is a **read-only consumer** for diagnostics: if a future observability
surface needs to summarize attempts, it can `parse_source_report(line)`
and get a typed `SourceReport` instead of an untyped dict.

The schema here mirrors what mathlint's
`mathlint.orchestration.real_source.record_report` writes; tests pin
the schema via `tests/test_source_reports_schema.py` so any drift in
pi_monitor's emitter surfaces here immediately.

Field semantics (from the real source-reports.jsonl on this machine):

  - `attempt_id`        = f"{execution_id}-{attempt_ordinal}"
  - `attempt_ordinal`   = 1-based counter within the execution
  - `detail`            = human-readable reason
  - `digest`            = SHA-256 of the report envelope
  - `envelope_digest`   = SHA-256 of the outcome envelope
  - `exit_code`         = subprocess exit (None for non-subprocess outcomes)
  - `operation_id`      = mathlint operation identifier
  - `outcome`           = mathlint.orchestration.vocabulary.Outcome value
  - `report_id`         = unique report identifier (== attempt_id today)
  - `source_identity`   = "mathlint" or program name
  - `source_revision`   = git SHA of the source at emit time
  - `status`            = mathlint.orchestration.vocabulary.WorkStatus value

This module is **pure** (no I/O, no subprocess); callers feed it lines.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum


class Outcome(StrEnum):
    """The `outcome` field of a source-report.

    Mirrors mathlint.orchestration.vocabulary.Outcome. We define our
    own copy here to keep the dispatcher self-contained for parsing;
    mathlint remains the canonical source of truth.
    """

    DISPATCH = "dispatch"
    WAIT = "wait"
    STOP = "stop"
    OPERATOR_REQUIRED = "operator_required"
    BLOCKED = "blocked"
    FAILED = "failed"
    SUBMITTED = "submitted"
    COUNTEREXAMPLE = "counterexample"
    OTHER = "OTHER"  # unknown / unrecognized value from the wire


class WorkStatus(StrEnum):
    """The `status` field of a source-report.

    Mirrors mathlint.orchestration.vocabulary.WorkStatus.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    STALLED = "stalled"
    OTHER = "OTHER"  # unknown / unrecognized value from the wire


@dataclass(frozen=True, slots=True)
class SourceReport:
    """One source-report (parsed from one line of source-reports.jsonl).

    All fields are typed; unknown `outcome` / `status` values map to
    `Outcome.OTHER` / `WorkStatus.OTHER` (defensive default).
    """

    attempt_id: str
    attempt_ordinal: int
    detail: str
    digest: str
    envelope_digest: str
    exit_code: int | None
    operation_id: str
    outcome: str
    report_id: str
    source_identity: str
    source_revision: str
    status: str


def parse_source_report(line: str) -> SourceReport:
    """Parse one JSONL line into a typed SourceReport.

    Raises `ValueError` on malformed JSON or missing required fields.
    Unknown outcome/status values are coerced to `OTHER` (defensive;
    the parser is total over the wire format, never raises on unknown
    enum members).
    """
    data = json.loads(line)
    return SourceReport(
        attempt_id=data["attempt_id"],
        attempt_ordinal=int(data["attempt_ordinal"]),
        detail=data.get("detail", ""),
        digest=data["digest"],
        envelope_digest=data["envelope_digest"],
        exit_code=data.get("exit_code"),
        operation_id=data["operation_id"],
        outcome=_coerce_enum(data.get("outcome", ""), Outcome, "outcome"),
        report_id=data["report_id"],
        source_identity=data["source_identity"],
        source_revision=data["source_revision"],
        status=_coerce_enum(data.get("status", ""), WorkStatus, "status"),
    )


def _coerce_enum(value: str, enum_cls: type[StrEnum], field_name: str) -> str:
    """Map a wire-format string to a known enum member, or "OTHER".

    Defensive default: an unrecognized value is mapped to a literal
    "OTHER" rather than raising, so a new value added at the writer
    does not brick the consumer.
    """
    try:
        enum_cls(value)
        return value
    except ValueError:
        return "OTHER"


__all__ = [
    "Outcome",
    "SourceReport",
    "WorkStatus",
    "parse_source_report",
]
