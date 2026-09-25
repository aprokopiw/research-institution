"""Audit-chain oracle (entry 06 T2.2).

Verifies the hash chain in a supervisor audit stream. Each
line in the stream is a JSON record with a ``prev_hash`` field
that MUST equal ``sha256(line_text_of_previous_record)`` (per
``pi_monitor.state.store._audit_line_hash``).

The oracle reads the stream line by line and asserts:

    * Every record parses as JSON.
    * Every record's ``prev_hash`` equals the sha256 of the
      previous line's text (or the genesis hash for the first).
    * The hash chain is monotonic (no torn tail).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import IO

__all__ = ["AuditReport", "audit_oracle"]


# Matches pi_monitor's _AUDIT_GENESIS_HASH in state/store.py.
_AUDIT_GENESIS_HASH: str = "0" * 64


@dataclass(frozen=True, slots=True)
class AuditReport:
    """Audit-chain oracle verdict."""

    verdict: str  # "PASS" | "FAIL"
    line_count: int
    broken_at_line: int | None = None
    detail: str = ""


def audit_oracle(
    stream_or_path: IO[str] | Iterable[str] | Path,
) -> AuditReport:
    """Verify the hash chain in a supervisor audit stream."""
    lines = _read_lines(stream_or_path)
    expected_prev = _AUDIT_GENESIS_HASH
    for line_no, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        try:
            doc = json.loads(line)
        except json.JSONDecodeError as exc:
            return AuditReport(
                verdict="FAIL",
                line_count=line_no - 1,
                broken_at_line=line_no,
                detail=f"line {line_no}: malformed JSON ({exc})",
            )
        if not isinstance(doc, dict):
            return AuditReport(
                verdict="FAIL",
                line_count=line_no - 1,
                broken_at_line=line_no,
                detail=f"line {line_no}: not a JSON object",
            )
        prev = doc.get("prev_hash")
        if prev != expected_prev:
            return AuditReport(
                verdict="FAIL",
                line_count=line_no - 1,
                broken_at_line=line_no,
                detail=(
                    f"line {line_no}: prev_hash mismatch "
                    f"(expected {expected_prev[:12]}..., "
                    f"got {str(prev)[:12]}...)"
                ),
            )
        # The canonical line hash uses the line text WITHOUT the
        # trailing newline, matching ``_audit_line_hash``.
        expected_prev = hashlib.sha256(line.encode("utf-8")).hexdigest()
    return AuditReport(verdict="PASS", line_count=len(lines))


def _read_lines(stream_or_path: IO[str] | Iterable[str] | Path) -> list[str]:
    if isinstance(stream_or_path, Path):
        return stream_or_path.read_text(encoding="utf-8").splitlines()
    if hasattr(stream_or_path, "readlines"):
        return stream_or_path.readlines()
    return list(stream_or_path)
