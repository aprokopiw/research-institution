"""Canary does-not-mutate-kaplansky test (entry 07 T2.4 / FR-5).

The canary runner must NOT mutate ``kaplansky/programs/
kaplansky-roadmap.toml``. The test snapshots the file's sha256
before and after the runner; mutation is a hard fail.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def test_canary_does_not_mutate_kaplansky_roadmap(tmp_path) -> None:
    """Snap a temp roadmap; run the canary with the temp path;
    assert sha256 unchanged.
    """
    from research_institution.gates.verify_simulation.canary import CanaryRunner

    fake_roadmap = tmp_path / "kaplansky-roadmap.toml"
    fake_roadmap.write_text(
        "# test fixture\nschema = 1\noperations = ()\n", encoding="utf-8"
    )
    runner = CanaryRunner(
        scenario="rate-defer-restart",
        kaplansky_roadmap=fake_roadmap,
        live=True,
    )
    before_sha = hashlib.sha256(fake_roadmap.read_bytes()).hexdigest()
    report = runner.run()
    after_sha = hashlib.sha256(fake_roadmap.read_bytes()).hexdigest()
    assert before_sha == after_sha, (
        f"canary mutated kaplansky-roadmap.toml: "
        f"{before_sha[:12]}... -> {after_sha[:12]}..."
    )
    assert report.kaplansky_roadmap_before_sha == before_sha
    assert report.kaplansky_roadmap_after_sha == after_sha


def test_canary_runner_reports_missing_roadmap(tmp_path) -> None:
    """When the kaplansky roadmap doesn't exist, the runner
    records both before/after as ``None`` and continues.
    """
    from research_institution.gates.verify_simulation.canary import CanaryRunner

    runner = CanaryRunner(
        scenario="rate-defer-restart",
        kaplansky_roadmap=tmp_path / "no-such-file",
        live=True,
    )
    report = runner.run()
    assert report.kaplansky_roadmap_before_sha is None
    assert report.kaplansky_roadmap_after_sha is None
