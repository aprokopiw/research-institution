"""Transcript oracle (entry 06 T2.1).

Wraps entry 05's ``transcript_oracle.py`` and exposes a typed
``TranscriptReport``. The oracle asserts the documented event
subsequence is present in the transcript and the forbidden
events are absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import IO, Iterable

__all__ = ["TranscriptReport", "transcript_oracle"]


@dataclass(frozen=True, slots=True)
class TranscriptReport:
    """Transcript oracle verdict."""

    verdict: str  # "PASS" | "FAIL"
    observed_subsequence: tuple[str, ...]
    missing_subsequence: tuple[str, ...] = ()
    forbidden_hit: tuple[str, ...] = ()
    detail: str = ""


def transcript_oracle(
    stream: IO[str] | Iterable[str],
    *,
    required_subsequence: tuple[str, ...] = (),
    forbidden_events: tuple[str, ...] = (),
    kind_field: str = "kind",
) -> TranscriptReport:
    """Inspect a transcript and emit the oracle verdict.

    The oracle imports entry 05's ``TranscriptOracle`` lazily to
    avoid a hard dependency at module load time. The wrapping
    here is the typed boundary between the harness and the
    reusable transcript oracle.
    """
    try:
        from tests.substrate.transcript_oracle import (
            TranscriptOracle,
            assert_event_sequence,
        )
    except ImportError:
        # Fallback: simple in-memory scan when the substrate
        # package isn't importable (research-institution is a
        # runtime dep of pi_monitor; the inverse isn't always
        # true). The fallback still enforces the forbidden
        # event rule and the subsequence check.
        return _fallback_oracle(
            stream,
            required_subsequence=required_subsequence,
            forbidden_events=forbidden_events,
            kind_field=kind_field,
        )
    oracle = TranscriptOracle(stream)
    actual: list[str] = []
    try:
        actual, _ = assert_event_sequence(
            oracle,
            expected=list(required_subsequence),
            forbidden=list(forbidden_events),
            kind_field=kind_field,
        )
    except Exception as exc:
        return TranscriptReport(
            verdict="FAIL",
            observed_subsequence=tuple(),
            detail=str(exc),
        )
    return TranscriptReport(
        verdict="PASS",
        observed_subsequence=tuple(actual),
    )


def _fallback_oracle(
    stream: IO[str] | Iterable[str],
    *,
    required_subsequence: tuple[str, ...],
    forbidden_events: tuple[str, ...],
    kind_field: str,
) -> TranscriptReport:
    import json

    actual: list[str] = []
    lines = stream.readlines() if hasattr(stream, "readlines") else list(stream)
    for raw in lines:
        line = raw.rstrip("\n")
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        kind = str(event.get(kind_field, "<missing>"))
        actual.append(kind)
    forbidden_hit = tuple(k for k in actual if k in set(forbidden_events))
    if forbidden_hit:
        return TranscriptReport(
            verdict="FAIL",
            observed_subsequence=tuple(actual),
            forbidden_hit=forbidden_hit,
            detail="forbidden event present",
        )
    missing: list[str] = []
    required_iter = iter(required_subsequence)
    for kind in actual:
        try:
            target = next(required_iter)
        except StopIteration:
            break
        if kind != target:
            # Subsequence requires contiguous match; a mismatch
            # restarts the required sequence check from the start.
            required_iter = iter(required_subsequence)
            if kind == next(required_iter, None):
                continue
    missing = list(required_iter)
    if missing:
        return TranscriptReport(
            verdict="FAIL",
            observed_subsequence=tuple(actual),
            missing_subsequence=tuple(missing),
            detail="required subsequence not satisfied",
        )
    return TranscriptReport(
        verdict="PASS",
        observed_subsequence=tuple(actual),
    )
