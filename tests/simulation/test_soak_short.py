"""Short-soak smoke test (entry 07 T3.3)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def test_soak_oracle_short_smoke_exits_pass() -> None:
    """A 1-second soak (the minimum the oracle accepts) exits PASS
    in well under 90s.
    """
    from research_institution.gates.verify_simulation.oracle.soak import (
        SoakOracle,
    )

    started = time.monotonic()
    oracle = SoakOracle(
        duration_seconds=1.0,
        sample_interval_seconds=0.1,
        hot_loop_window=60,
    )
    report = oracle.run()
    elapsed = time.monotonic() - started
    assert report.verdict == "PASS", f"soak failed: {report.detail}"
    assert elapsed < 5.0, f"soak took {elapsed:.1f}s; budget 5s"
    assert report.sample_count >= 1


def test_soak_oracle_rejects_zero_duration() -> None:
    """``duration_seconds=0`` is rejected (FR-7 budget enforcement)."""
    from research_institution.gates.verify_simulation.oracle.soak import (
        SoakOracle,
    )

    with pytest.raises(ValueError):
        SoakOracle(duration_seconds=0.0)


def test_soak_oracle_writes_evidence_archive(tmp_path) -> None:
    """``write_evidence_archive`` writes a JSON archive."""
    from research_institution.gates.verify_simulation.oracle.soak import (
        SoakOracle,
        SoakReport,
        write_evidence_archive,
    )

    report = SoakReport(
        verdict="PASS",
        elapsed_seconds=1.0,
        sample_count=10,
        max_memory_mb=128.0,
        max_process_count=64,
        max_state_file_bytes=1024,
        audit_chain_ok=True,
        hot_loop_detected=False,
        orphan_processes=0,
        duplicate_reports=0,
    )
    archive = tmp_path / "archive.json"
    write_evidence_archive(
        archive,
        report=report,
        commit_sha="abc123",
        config_fingerprint="cfg",
        scenario_hashes={},
    )
    assert archive.exists()
    import json

    doc = json.loads(archive.read_text(encoding="utf-8"))
    assert doc["report"]["verdict"] == "PASS"
    assert doc["commit_sha"] == "abc123"


def test_cli_soak_without_hours_exits_two() -> None:
    """``--tier soak`` without ``--hours N`` exits 2 with an
    actionable error (FR-7 + T3.2).
    """
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "research_institution",
            "verify-simulation",
            "--tier",
            "soak",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert proc.returncode == 2
    assert "--hours" in proc.stderr
