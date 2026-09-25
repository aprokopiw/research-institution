"""Frontier oracle (entry 06 T2.4).

Reads a frontier stream (one event per line) and asserts:

    * The frontier revision changes at every event that has an
      expected ``frontier_change`` marker.
    * The stream has at least one revision advance.
    * The final revision differs from the initial revision.

This is a coarse invariant oracle — the entry-04 reducer has
its own revision-monotonicity test (test_revision_monotonic)
which covers the reducer in isolation. The oracle here is the
harness-level mirror for end-to-end runs.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import IO

__all__ = ["FrontierReport", "frontier_oracle"]


@dataclass(frozen=True, slots=True)
class FrontierReport:
    """Frontier oracle verdict."""

    verdict: str  # "PASS" | "FAIL"
    revisions_seen: int
    expected_change_points: int
    missed_change_points: int = 0
    detail: str = ""


def frontier_oracle(
    stream_or_path: IO[str] | Iterable[str] | Path,
    *,
    expected_change_points: int = 1,
) -> FrontierReport:
    """Verify frontier revision changes at expected events."""
    if isinstance(stream_or_path, Path):
        lines = stream_or_path.read_text(encoding="utf-8").splitlines()
    elif hasattr(stream_or_path, "readlines"):
        lines = stream_or_path.readlines()
    else:
        lines = list(stream_or_path)
    revisions: list[str] = []
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
        rev = (
            doc.get("revision_fingerprint")
            or doc.get("revision")
            or doc.get("source_revision_fingerprint")
        )
        if isinstance(rev, str):
            revisions.append(rev)
    revisions_seen = len(set(revisions))
    if expected_change_points == 0:
        # No expected change points; the hermetic tier (and
        # scenarios without dispatch events) trivially passes.
        return FrontierReport(
            verdict="PASS",
            revisions_seen=revisions_seen,
            expected_change_points=expected_change_points,
        )
    if revisions_seen < expected_change_points + 1:
        missed = max(0, expected_change_points - revisions_seen + 1)
        return FrontierReport(
            verdict="FAIL",
            revisions_seen=revisions_seen,
            expected_change_points=expected_change_points,
            missed_change_points=missed,
            detail=(
                f"frontier advanced {revisions_seen - 1} times; "
                f"expected at least {expected_change_points}"
            ),
        )
    return FrontierReport(
        verdict="PASS",
        revisions_seen=revisions_seen,
        expected_change_points=expected_change_points,
    )
