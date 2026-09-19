"""Contract tests for the institution green gate.

Per @CTR-0088 and the green-gate pattern documented in
plan-011 §1.3, the aggregator must exist, delegate correctly,
and default to --hermetic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "green-gate" / "check-institution.sh"


def test_check_institution_aggregator_exists() -> None:
    assert GATE.exists(), f"missing {GATE}"
    assert GATE.stat().st_mode & 0o111, f"{GATE} not executable"


def test_check_institution_delegates_correctly() -> None:
    text = GATE.read_text()
    # Aggregator dispatches to math-engine's check-local-system-readiness.sh
    assert "check-local-system-readiness.sh" in text
    # And iterates the catalog.
    assert "programs.toml" in text
    # And supports the two modes.
    assert "--hermetic" in text
    assert "--live" in text


def test_hermetic_uses_sample_program() -> None:
    text = GATE.read_text()
    # The hermetic default routes math-engine to the bundled sample program.
    assert "--use-program=self_test-sample" in text


def test_live_requires_credentials_warning() -> None:
    """Live mode prints a credential warning but does NOT exit nonzero."""
    text = GATE.read_text()
    # No "exit 1" / "die" / hard-fail path tied to missing creds.
    # The aggregator aggregates failures; missing creds surface as a
    # WARN-level skip, not a fatal.
    assert "exit 1" not in text or text.count("exit 1") <= 1  # only the final verdict
    assert "WARN" in text
