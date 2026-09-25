"""Exactly-once oracle (entry 06 T2.3).

For every accepted report, asserts the per-idempotency-key
invariant: the (source_identity, operation_id, revision_fingerprint)
tuple appears AT MOST once per attempt ordinal; and EXACTLY one
accepted report per (source_identity, operation_id, revision_fingerprint).

The oracle reads a report stream (one JSON object per line) and
returns a typed ``ExactlyOnceReport`` with the count of accepted
+ duplicate + conflicting reports.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import IO

__all__ = ["ExactlyOnceReport", "exactly_once_oracle"]


@dataclass(frozen=True, slots=True)
class ExactlyOnceReport:
    """Exactly-once oracle verdict."""

    verdict: str  # "PASS" | "FAIL"
    accepted: int
    duplicates: int
    conflicts: int
    detail: str = ""


def exactly_once_oracle(
    stream_or_path: IO[str] | Iterable[str] | Path,
) -> ExactlyOnceReport:
    """Verify per-idempotency-key invariants in a report stream."""
    if isinstance(stream_or_path, Path):
        lines = stream_or_path.read_text(encoding="utf-8").splitlines()
    elif hasattr(stream_or_path, "readlines"):
        lines = stream_or_path.readlines()
    else:
        lines = list(stream_or_path)
    accepted = 0
    duplicates = 0
    conflicts = 0
    seen_keys: dict[tuple[str, str, str], int] = {}
    for raw in lines:
        line = raw.rstrip("\n")
        if not line:
            continue
        try:
            doc = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(doc, dict):
            continue
        key = (
            str(doc.get("source_identity", "")),
            str(doc.get("operation_id", "")),
            str(doc.get("source_revision", {}).get("fingerprint", ""))
            if isinstance(doc.get("source_revision"), dict)
            else str(doc.get("source_revision", "")),
        )
        if not all(key):
            continue
        outcome = doc.get("outcome", "")
        seen = seen_keys.get(key, 0)
        if outcome == "conflict":
            conflicts += 1
            continue
        if seen > 0:
            duplicates += 1
        else:
            accepted += 1
        seen_keys[key] = seen + 1
    if duplicates or conflicts:
        return ExactlyOnceReport(
            verdict="FAIL",
            accepted=accepted,
            duplicates=duplicates,
            conflicts=conflicts,
            detail=(
                f"exactly-once violated: {duplicates} duplicates, "
                f"{conflicts} conflicts"
            ),
        )
    return ExactlyOnceReport(
        verdict="PASS",
        accepted=accepted,
        duplicates=0,
        conflicts=0,
    )
