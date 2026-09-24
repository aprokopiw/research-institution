"""Live acceptance command tests.

The brief (Section A) requires:

* A bounded composed live acceptance command under the
  existing gate / application structure (not an ad-hoc shell
  script in a sibling repo).
* Default mode is hermetic and makes zero model calls.
* ``--live`` mode may use real credentials and provider.
  It must print ``BLOCKED`` (not ``PASS``) when credentials
  or service prerequisites are unavailable.
* The command reads durable audit / execution /
  source-report artifacts; it must not infer success from
  process existence.
* A cycle counts only when dispatch + execution start +
  finalized outcome + source report + subsequent source
  decision are all observed in order.
* Emit one row per cycle plus final status. Never expose
  secrets or full prompts.

Tests use copied / minimized event fixtures under a
``tmp_path`` so no live supervisor is required. The
hermetic path must declare BLOCKED when artifacts are
missing or the correlation is incomplete.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from research_institution.live_acceptance import (
    CycleDisposition,
    correlate_cycles,
    main,
)


def _write_jsonl(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line, sort_keys=True, separators=(",", ":")) + "\n")


def _complete_audit_and_reports(state_dir: Path, n: int = 3) -> None:
    """Build a minimal audit + reports pair with ``n`` complete cycles.

    Each cycle carries a unique ``operation_id`` so the
    correlator indexes them independently. The events are in
    order: ``source_dispatch`` < ``execution_attempt_started``
    < ``execution_attempt_terminal`` <
    ``execution_result_reported`` < ``source_decision``.
    """
    audit_events: list[dict] = []
    report_events: list[dict] = []
    base_unix = 1_700_000_000.0
    for i in range(n):
        op = f"K-{i:04d}"
        exec_id = f"exec-{i:04d}"
        ts = base_unix + i * 100.0
        audit_events.extend([
            {
                "event": "source_dispatch",
                "operation_id": op,
                "source_revision": {"label": f"rev-{i}", "fingerprint": "a" * 40},
                "unix": ts + 1.0,
            },
            {
                "event": "execution_attempt_started",
                "operation_id": op,
                "execution_id": exec_id,
                "unix": ts + 2.0,
            },
            {
                "event": "execution_attempt_terminal",
                "operation_id": op,
                "execution_id": exec_id,
                "attempt_ordinal": 1,
                "status": "completed",
                "unix": ts + 50.0,
            },
        ])
        report_events.append({
            "operation_id": op,
            "execution_id": exec_id,
            "report_id": f"r-{i:04d}",
            "envelope_digest": f"d-{i:04d}",
        })
    # Subsequent source decision after every terminal (so
    # the cycle counts as COMPLETE).
    for i in range(n):
        audit_events.append({
            "event": "source_decision",
            "operation_id": "",
            "kind": "wait",
            "unix": base_unix + i * 100.0 + 60.0,
        })
    _write_jsonl(state_dir / "audit.jsonl", audit_events)
    _write_jsonl(state_dir / "source-reports.jsonl", report_events)


class TestCorrelation:
    """The pure correlator indexes events by operation_id."""

    def test_three_complete_cycles_pass(self, tmp_path: Path) -> None:
        _complete_audit_and_reports(tmp_path, n=3)
        report = correlate_cycles(tmp_path, min_complete_cycles=3)
        assert report.ok
        assert report.complete_count == 3
        assert len(report.cycles) == 3
        for c in report.cycles:
            assert c.disposition is CycleDisposition.COMPLETE

    def test_partial_cycle_when_outcome_missing(self, tmp_path: Path) -> None:
        # Build a state with one complete cycle and one
        # partial (execution_attempt_terminal missing).
        audit = [
            {
                "event": "source_dispatch",
                "operation_id": "K-0000",
                "source_revision": {"label": "rev-0", "fingerprint": "a" * 40},
                "unix": 1_700_000_001.0,
            },
            {
                "event": "execution_attempt_started",
                "operation_id": "K-0000",
                "execution_id": "exec-0",
                "unix": 1_700_000_002.0,
            },
            {
                "event": "execution_attempt_terminal",
                "operation_id": "K-0000",
                "execution_id": "exec-0",
                "status": "completed",
                "unix": 1_700_000_050.0,
            },
            {
                "event": "source_dispatch",
                "operation_id": "K-0001",
                "source_revision": {"label": "rev-1", "fingerprint": "a" * 40},
                "unix": 1_700_000_101.0,
            },
            # Missing started / terminal / report -> PARTIAL.
            {
                "event": "source_decision",
                "operation_id": "",
                "kind": "wait",
                "unix": 1_700_000_060.0,
            },
        ]
        _write_jsonl(tmp_path / "audit.jsonl", audit)
        _write_jsonl(
            tmp_path / "source-reports.jsonl",
            [
                {
                    "operation_id": "K-0000",
                    "execution_id": "exec-0",
                    "report_id": "r-0",
                    "envelope_digest": "d-0",
                },
            ],
        )
        report = correlate_cycles(tmp_path, min_complete_cycles=3)
        assert report.complete_count == 1
        assert not report.ok
        assert any(c.disposition is CycleDisposition.PARTIAL for c in report.cycles)

    def test_missing_state_dir_returns_zero_cycles(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        report = correlate_cycles(empty, min_complete_cycles=3)
        assert report.complete_count == 0
        assert not report.ok
        assert "no source_dispatch" in " ".join(report.notes)

    def test_forced_defer_marker_observed(self, tmp_path: Path) -> None:
        _complete_audit_and_reports(tmp_path, n=3)
        # Append a forced-defer marker to the audit.
        with (tmp_path / "audit.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {"event": "rate_limit_deferred", "unix": 1_700_000_500.0}
                )
                + "\n"
            )
        report = correlate_cycles(
            tmp_path, min_complete_cycles=3, forced_defer_marker="rate_limit_deferred"
        )
        assert report.ok


class TestCLI:
    """The CLI is hermetic by default; --live requires credentials."""

    def test_hermetic_returns_2_on_missing_state_dir(self, tmp_path: Path) -> None:
        rc = main(
            [
                "--state-dir",
                str(tmp_path / "missing"),
                "--min-complete-cycles",
                "3",
            ]
        )
        assert rc == 2

    def test_hermetic_passes_on_complete_state(self, tmp_path: Path) -> None:
        _complete_audit_and_reports(tmp_path, n=3)
        rc = main(
            [
                "--state-dir",
                str(tmp_path),
                "--min-complete-cycles",
                "3",
            ]
        )
        assert rc == 0

    def test_hermetic_blocks_on_partial_state(self, tmp_path: Path) -> None:
        _complete_audit_and_reports(tmp_path, n=1)
        rc = main(
            [
                "--state-dir",
                str(tmp_path),
                "--min-complete-cycles",
                "3",
            ]
        )
        assert rc == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
