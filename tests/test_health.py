"""Tests for the unified diagnostic (B.5.x + health verb).

The dispatcher exposes `research health <program>` as one-shot
readiness. These tests pin the structure of `HealthReport` and the
shape of the operator-facing output.

We don't subprocess to real mathlint/pi-monitor; instead we
patch the per-check functions and verify the aggregator reports
the right number of failures + the right suggestions.
"""

from __future__ import annotations

from research_institution.health import (
    HealthCheck,
    HealthReport,
    format_health,
)


def _check(name: str, ok: bool, summary: str = "x", suggestion: str = "") -> HealthCheck:
    return HealthCheck(name=name, ok=ok, summary=summary, suggestion=suggestion)


def test_format_health_all_ok() -> None:
    report = HealthReport(
        program="kaplansky",
        checks=[
            _check("green-gate-hermetic", True, "wired"),
            _check("live-preflight", True, "all 12 passed"),
            _check("architecture-review-gate", True, "TASK KIND=RESEARCH"),
            _check("receipt-freshness", True, "matches HEAD"),
            _check("supervisor-alive", True, "pid 43960"),
        ],
        supervisor_pid=43960,
        supervisor_alive=True,
    )
    out = format_health(report)
    assert "health: kaplansky" in out
    assert "all 5 checks passed" in out
    assert "ready to" in out
    assert "FAIL" not in out


def test_format_health_one_failure_surfaces_suggestion() -> None:
    report = HealthReport(
        program="kaplansky",
        checks=[
            _check("green-gate-hermetic", True, "wired"),
            _check(
                "receipt-freshness",
                False,
                "receipt commit 921967c != math HEAD 2860666a",
                suggestion="run `mathlint first-run --project kaplansky`",
            ),
            _check("supervisor-alive", True, "pid 43960"),
        ],
    )
    out = format_health(report)
    assert "[2/3]" in out
    assert "FAIL" in out
    assert "first-run" in out
    assert "2/3 checks passed; 1 to fix." in out


def test_format_health_multiple_failures_preserve_order() -> None:
    """The order of checks must match the canonical reading order."""
    report = HealthReport(
        program="kaplansky",
        checks=[
            _check("a", False, "a bad", "fix-a"),
            _check("b", False, "b bad", "fix-b"),
            _check("c", True, "c ok"),
        ],
    )
    out = format_health(report)
    a_pos = out.find("[1/3]")
    b_pos = out.find("[2/3]")
    c_pos = out.find("[3/3]")
    assert a_pos < b_pos < c_pos


def test_report_failures_filters_correctly() -> None:
    report = HealthReport(
        program="kaplansky",
        checks=[_check("a", True), _check("b", False), _check("c", True)],
    )
    assert len(report.failures) == 1
    assert report.failures[0].name == "b"
    assert report.is_healthy is False


def test_report_is_healthy_when_all_ok() -> None:
    report = HealthReport(
        program="kaplansky",
        checks=[_check("a", True), _check("b", True)],
    )
    assert report.is_healthy is True
    assert report.failures == []


def test_format_health_multiline_suggestion() -> None:
    """Suggestions with newlines render each line as its own fix."""
    report = HealthReport(
        program="kaplansky",
        checks=[
            _check(
                "live-preflight",
                False,
                "3/12 failed",
                suggestion="SMOKE001: bootstrap receipt\nLOCAL022: math dirty",
            ),
        ],
    )
    out = format_health(report)
    assert "SMOKE001: bootstrap receipt" in out
    assert "LOCAL022: math dirty" in out
    # Both lines should be prefixed with "      fix:"
    fix_lines = [line for line in out.splitlines() if "fix:" in line]
    assert len(fix_lines) >= 2


def test_health_check_slots_frozen() -> None:
    """HealthCheck is frozen; can't be mutated after creation."""
    c = _check("a", True)
    import dataclasses

    try:
        c.ok = False  # type: ignore[misc]
        # If this doesn't raise, the dataclass isn't frozen.
        raise AssertionError("HealthCheck is not frozen")
    except dataclasses.FrozenInstanceError:
        pass
