"""OS-layer no-delta loop guard tests.

The brief's Section D requires that the same (operation_id,
directive hash, outcome=no_delta) tuple cannot dispatch
indefinitely. math's ``live_source_snapshot.consult`` enforces
this via the ``deltas`` ledger; when the program repo is not a
math project (e.g. kaplansky), the OS needs a defensive layer
that scans ``source-reports.jsonl`` directly.

Tests pin:

* Empty / missing ledger returns ``None`` (no escalation).
* Single no-delta report does not trigger the guard.
* Threshold-many consecutive no-delta reports for the same
  operation trigger the Wait envelope with the right
  ``reason_code`` and ``wake_on_source_change``.
* A success outcome breaks the trailing no-delta run.
* Different operation IDs are tracked independently.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_institution.contracts.source_decision import (
    Dispatch,
    SourceRevision,
    Wait,
    WorkRequest,
)
from research_institution.providers.research_institution_provider import (
    NO_DELTA_LOOP_THRESHOLD,
    REASON_NO_DELTA_LOOP_GUARD,
    _check_no_delta_loop,
    _consecutive_no_deltas,
    _read_source_reports,
)


def _write_reports(path: Path, reports: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in reports:
            fh.write(json.dumps(r) + "\n")


def _make_work_request(operation_id: str = "K4") -> WorkRequest:
    """Build a minimal typed WorkRequest for the guard tests."""
    return WorkRequest(
        operation_id=operation_id,
        role="research",
        source_revision=SourceRevision(
            fingerprint="a" * 40,
            observed_unix=1_700_000_000.0,
            label="kaplansky-tick-test",
        ),
        payload={},
        source_identity="kaplansky-research-program",
        operation_kind="mathlint-research",
    )


def _no_delta_report(op: str, digest: str = "") -> dict:
    return {
        "operation_id": op,
        "outcome": "no_delta",
        "status": "completed",
        "digest": digest or f"d-{op}-0001",
        "report_id": f"r-{op}",
        "attempt_ordinal": 1,
        "source_identity": "kaplansky-research-program",
    }


def _success_report(op: str) -> dict:
    return {
        "operation_id": op,
        "outcome": "completed",
        "status": "completed",
        "digest": "success-digest",
        "report_id": f"r-{op}-s",
        "attempt_ordinal": 1,
        "source_identity": "kaplansky-research-program",
    }


class TestReadSourceReports:
    """The ledger reader is tolerant of missing / malformed files."""

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        result = _read_source_reports(tmp_path)
        assert result == []

    def test_malformed_lines_skipped(self, tmp_path: Path) -> None:
        log = tmp_path / "source-reports.jsonl"
        log.write_text('{"operation_id": "K4", "outcome": "no_delta"}\nGARBAGE\n', encoding="utf-8")
        result = _read_source_reports(tmp_path)
        assert len(result) == 1
        assert result[0]["operation_id"] == "K4"


class TestConsecutiveNoDeltas:
    """Trailing-run counter."""

    def test_empty_returns_zero(self) -> None:
        assert _consecutive_no_deltas([], operation_id="K4") == 0

    def test_single_no_delta(self) -> None:
        assert _consecutive_no_deltas([_no_delta_report("K4")], operation_id="K4") == 1

    def test_three_consecutive_no_deltas(self) -> None:
        reports = [_no_delta_report("K4") for _ in range(3)]
        assert _consecutive_no_deltas(reports, operation_id="K4") == 3

    def test_success_breaks_run(self) -> None:
        reports = [
            _no_delta_report("K4"),
            _no_delta_report("K4"),
            _success_report("K4"),
        ]
        # Trailing run is 0 (success is last).
        assert _consecutive_no_deltas(reports, operation_id="K4") == 0

    def test_different_operations_independent(self) -> None:
        # The trailing-run counter is anchored at the most
        # recent report; K3 in the middle of the sequence does
        # NOT count toward K4's trailing run, and K4 in the
        # middle does NOT count toward K3's trailing run.
        reports = [
            _no_delta_report("K4"),
            _no_delta_report("K3"),
            _no_delta_report("K4"),
            _no_delta_report("K4"),
        ]
        # K4's trailing run: starts at the most recent K4
        # (last entry) and walks backward; hits K3 → break.
        assert _consecutive_no_deltas(reports, operation_id="K4") == 2
        # K3 is not in the trailing position (the most recent
        # report is K4), so K3's trailing run is 0.
        assert _consecutive_no_deltas(reports, operation_id="K3") == 0


class TestCheckNoDeltaLoop:
    """The guard returns a Wait envelope at threshold."""

    def test_threshold_default_is_three(self) -> None:
        """The default threshold matches math's STAGNATION_THRESHOLD."""
        assert NO_DELTA_LOOP_THRESHOLD == 3

    def test_below_threshold_returns_none(self, tmp_path: Path) -> None:
        reports = [_no_delta_report("K4") for _ in range(NO_DELTA_LOOP_THRESHOLD - 1)]
        _write_reports(tmp_path / "source-reports.jsonl", reports)
        result = _check_no_delta_loop(
            work=[_make_work_request("K4")],
            state_dir=tmp_path,
        )
        assert result is None

    def test_at_threshold_returns_wait(self, tmp_path: Path) -> None:
        reports = [_no_delta_report("K4") for _ in range(NO_DELTA_LOOP_THRESHOLD)]
        _write_reports(tmp_path / "source-reports.jsonl", reports)
        result = _check_no_delta_loop(
            work=[_make_work_request("K4")],
            state_dir=tmp_path,
        )
        assert result is not None
        assert isinstance(result, Wait)
        assert result.reason_code == REASON_NO_DELTA_LOOP_GUARD
        assert result.wake_on_source_change is True

    def test_missing_ledger_returns_none(self, tmp_path: Path) -> None:
        # tmp_path exists but contains no source-reports.jsonl.
        result = _check_no_delta_loop(
            work=[_make_work_request("K4")],
            state_dir=tmp_path,
        )
        assert result is None

    def test_success_breaks_run_for_dispatch(self, tmp_path: Path) -> None:
        reports = [
            _no_delta_report("K4"),
            _no_delta_report("K4"),
            _no_delta_report("K4"),
            _success_report("K4"),  # breaks the run
        ]
        _write_reports(tmp_path / "source-reports.jsonl", reports)
        result = _check_no_delta_loop(
            work=[_make_work_request("K4")],
            state_dir=tmp_path,
        )
        assert result is None  # trailing run is 0 (success is last)

    def test_wait_envelope_carries_operation_id_in_reason(self, tmp_path: Path) -> None:
        reports = [_no_delta_report("K5") for _ in range(NO_DELTA_LOOP_THRESHOLD)]
        _write_reports(tmp_path / "source-reports.jsonl", reports)
        result = _check_no_delta_loop(
            work=[_make_work_request("K5")],
            state_dir=tmp_path,
        )
        assert result is not None
        assert "op-K5" in result.reason
        assert "no_delta" in result.reason


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
