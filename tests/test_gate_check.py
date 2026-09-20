"""Tests for the architecture-review gate (B.1.2).

The gate check is the only piece of application logic the dispatcher
owns (per @ADR-0006). These tests prove:

  - It parses `mathlint roadmap` output correctly when the gate is open.
  - It refuses to launch when TASK KIND = ARCHITECTURE_REVIEW_REQUIRED.
  - It handles missing-task-kind (legacy/empty roadmap) as gate-open.
  - It handles non-zero roadmap exit as gate-closed with a diagnostic.
  - The CLI end-to-end refuses to start when the gate is closed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from research_institution.catalog import Program
from research_institution.cli import (
    EXIT_GATE_CLOSED,
    TASK_KIND_ABSENT,
    check_gate,
)
from research_institution.contracts import (
    GateVerdictStatus,
    TaskKind,
    gate_verdict_from_task_kind,
)

# A realistic roadmap excerpt with the gate CLOSED.
ROADMAP_CLOSED = """\
GLOBAL EXECUTION SCHEDULER
==========================
RESEARCH FRONTIER: K-RIGIDITY-OVERLAP-EXTRACTION
PRIMARY ACTION: K-RIGIDITY-OVERLAP-EXTRACTION
TASK KIND: ARCHITECTURE_REVIEW_REQUIRED
REASON: completed outcome has no unique approved on_failure edge (absent); run
@proof-architecture-review and explicitly apply a program decision
ACTIVE LEASE PRESERVED: NO

NORTH STAR
----------
kaplansky.zero-divisor-conjecture: Kaplansky zero-divisor conjecture
"""

# A realistic roadmap excerpt with the gate OPEN.
ROADMAP_OPEN = """\
GLOBAL EXECUTION SCHEDULER
==========================
RESEARCH FRONTIER: SOMETHING-ELSE
PRIMARY ACTION: SOMETHING-ELSE
TASK KIND: RESEARCH
ACTIVE LEASE PRESERVED: NO
"""

# A legacy/hermetic roadmap with no TASK KIND line.
ROADMAP_NO_TASK_KIND = """\
GLOBAL EXECUTION SCHEDULER
==========================
(empty roadmap)
"""

# Roadmap with a TASK KIND the dispatcher does not recognize.
# Defensive default: treat as OPEN, not as CLOSED.
ROADMAP_UNKNOWN_KIND = """\
GLOBAL EXECUTION SCHEDULER
==========================
TASK KIND: SOME_FUTURE_THING_MATHLINT_INVENTED_LATER
ACTIVE LEASE PRESERVED: NO
"""


def _fake_program(tmp_path: Path) -> Program:
    """Build a minimal Program whose resolved_local_path points at tmp_path."""
    return Program(
        name="x",
        display_name="X",
        repository="https://x/x",
        entry_point="x:r",
        local_path=str(tmp_path),
        mathlint_pin="v0.0.1",
        live_credentials_required=False,
        live_credential_env_vars=(),
        check_program_script="check.sh",
    )


# ---------------------------------------------------------------------------
# Pure parser tests (no subprocess, no I/O).
# ---------------------------------------------------------------------------


def test_pure_parser_closed_when_architecture_review_required() -> None:
    """`GateVerdict.from_text` returns CLOSED for the kaplansky snapshot."""
    from research_institution.cli import GateVerdict

    v = GateVerdict.from_text(ROADMAP_CLOSED)
    assert v.task_kind == TaskKind.ARCHITECTURE_REVIEW_REQUIRED.value
    assert v.status == GateVerdictStatus.CLOSED
    assert v.gate_open is False
    assert "no unique approved" in v.reason


def test_pure_parser_open_when_task_kind_is_research() -> None:
    from research_institution.cli import GateVerdict

    v = GateVerdict.from_text(ROADMAP_OPEN)
    assert v.task_kind == TaskKind.RESEARCH.value
    assert v.status == GateVerdictStatus.OPEN
    assert v.reason == ""


def test_pure_parser_open_when_task_kind_absent() -> None:
    from research_institution.cli import GateVerdict

    v = GateVerdict.from_text(ROADMAP_NO_TASK_KIND)
    assert v.task_kind == TASK_KIND_ABSENT
    assert v.status == GateVerdictStatus.OPEN


def test_pure_parser_open_when_task_kind_unknown() -> None:
    """Defensive: unrecognized task kinds map to TaskKind.OTHER + OPEN."""
    from research_institution.cli import GateVerdict

    v = GateVerdict.from_text(ROADMAP_UNKNOWN_KIND)
    assert v.task_kind == TaskKind.OTHER.value
    assert v.status == GateVerdictStatus.OPEN


def test_gate_verdict_constructor_rejects_invalid_status() -> None:
    """GateVerdict raises ValueError on an invalid status string."""
    from research_institution.cli import GateVerdict

    with pytest.raises(ValueError, match="status"):
        GateVerdict(task_kind="x", status="not-a-real-status")


def test_gate_verdict_status_predicate_matches_mapping_function() -> None:
    """`gate_open` predicate agrees with `gate_verdict_from_task_kind`."""
    from research_institution.cli import GateVerdict

    for kind in TaskKind:
        v = GateVerdict.from_text(f"TASK KIND: {kind.value}\n")
        expected = gate_verdict_from_task_kind(kind) == GateVerdictStatus.OPEN
        assert v.gate_open is expected


# ---------------------------------------------------------------------------
# Subprocess wrapper tests (use monkeypatch on subprocess.run).
# ---------------------------------------------------------------------------


def test_gate_closed_when_architecture_review_required(tmp_path: Path, monkeypatch) -> None:
    """Closed gate -> GateVerdict with status=CLOSED + REASON surfaced."""
    import subprocess as sp

    def fake_run(cmd, **kw):
        return sp.CompletedProcess(cmd, 0, stdout=ROADMAP_CLOSED, stderr="")

    monkeypatch.setattr(sp, "run", fake_run)
    v = check_gate(_fake_program(tmp_path), mathlint_bin="mathlint")
    assert v.task_kind == TaskKind.ARCHITECTURE_REVIEW_REQUIRED.value
    assert v.status == GateVerdictStatus.CLOSED
    assert v.gate_open is False
    assert "no unique approved" in v.reason


def test_gate_open_when_task_kind_is_research(tmp_path: Path, monkeypatch) -> None:
    """Open gate -> GateVerdict with gate_open=True."""
    import subprocess as sp

    def fake_run(cmd, **kw):
        return sp.CompletedProcess(cmd, 0, stdout=ROADMAP_OPEN, stderr="")

    monkeypatch.setattr(sp, "run", fake_run)
    v = check_gate(_fake_program(tmp_path))
    assert v.task_kind == TaskKind.RESEARCH.value
    assert v.gate_open is True
    assert v.reason == ""


def test_gate_open_when_task_kind_absent(tmp_path: Path, monkeypatch) -> None:
    """Legacy/hermetic roadmap (no TASK KIND line) -> gate_open=True."""
    import subprocess as sp

    def fake_run(cmd, **kw):
        return sp.CompletedProcess(cmd, 0, stdout=ROADMAP_NO_TASK_KIND, stderr="")

    monkeypatch.setattr(sp, "run", fake_run)
    v = check_gate(_fake_program(tmp_path))
    assert v.task_kind == TASK_KIND_ABSENT
    assert v.gate_open is True


def test_gate_closed_when_roadmap_fails(tmp_path: Path, monkeypatch) -> None:
    """mathlint roadmap nonzero exit -> status=UNKNOWN with diagnostic."""
    import subprocess as sp

    def fake_run(cmd, **kw):
        return sp.CompletedProcess(cmd, 3, stdout="", stderr="FATAL: no mathlint.toml")

    monkeypatch.setattr(sp, "run", fake_run)
    v = check_gate(_fake_program(tmp_path))
    assert v.status == GateVerdictStatus.UNKNOWN
    assert v.gate_open is False
    assert "(roadmap-failed)" in v.task_kind
    assert "3" in v.reason
    assert "FATAL" in v.raw_excerpt


def test_raw_excerpt_is_last_400_chars(tmp_path: Path, monkeypatch) -> None:
    """raw_excerpt is exactly the last 400 chars of roadmap output.

    Mutation-test oracle (see verification audit): a regression that
    truncates to 100 chars (or any other width) loses diagnostic
    context for operators. The exact-400 invariant is pinned here.
    """
    import subprocess as sp

    long_text = "X" * 600  # 600 chars; only last 400 should survive
    long_text += "\nTASK KIND: ARCHITECTURE_REVIEW_REQUIRED\n"

    def fake_run(cmd, **kw):
        return sp.CompletedProcess(cmd, 0, stdout=long_text, stderr="")

    monkeypatch.setattr(sp, "run", fake_run)
    v = check_gate(_fake_program(tmp_path))
    # Length must be exactly 400 when the source is longer.
    assert len(v.raw_excerpt) == 400, (
        f"raw_excerpt length drifted: got {len(v.raw_excerpt)}, expected 400"
    )
    # And it must be the LAST 400 chars (suffix, not prefix).
    assert v.raw_excerpt == long_text[-400:]


def test_raw_excerpt_short_text_is_verbatim(tmp_path: Path, monkeypatch) -> None:
    """When the source is shorter than 400 chars, raw_excerpt == source."""
    import subprocess as sp

    short_text = "TASK KIND: RESEARCH\n"  # 18 chars

    def fake_run(cmd, **kw):
        return sp.CompletedProcess(cmd, 0, stdout=short_text, stderr="")

    monkeypatch.setattr(sp, "run", fake_run)
    v = check_gate(_fake_program(tmp_path))
    assert v.raw_excerpt == short_text


def test_from_text_raw_excerpt_is_last_400_chars() -> None:
    """Pure-parser path also enforces the 400-char truncation invariant."""
    from research_institution.cli import GateVerdict

    long_text = "Y" * 1000
    long_text += "\nTASK KIND: RESEARCH\n"  # forces non-empty post-truncation
    v = GateVerdict.from_text(long_text)
    assert len(v.raw_excerpt) == 400
    assert v.raw_excerpt == long_text[-400:]


def test_start_refuses_on_closed_gate(cli_runner, tmp_path: Path, monkeypatch) -> None:
    """End-to-end: `research start <prog>` (non-dry-run) refuses on closed gate."""
    import subprocess as sp

    import research_institution.cli as cli_mod

    monkeypatch.setattr(cli_mod, "_require_program", lambda name: _fake_program(tmp_path))
    monkeypatch.setattr(cli_mod, "_load", lambda: [_fake_program(tmp_path)])

    def fake_run(cmd, **kw):
        return sp.CompletedProcess(cmd, 0, stdout=ROADMAP_CLOSED, stderr="")

    monkeypatch.setattr(sp, "run", fake_run)

    result = cli_runner.invoke(args=["start", "x"], catch_exceptions=False)
    assert result.exit_code == EXIT_GATE_CLOSED, (
        f"expected {EXIT_GATE_CLOSED}, got {result.exit_code}; "
        f"stdout={result.stdout!r} stderr={getattr(result, 'stderr', '')!r}"
    )
    combined = (result.stdout or "") + (getattr(result, "stderr", "") or "")
    assert "GATE NOT OPEN" in combined
    assert "ARCHITECTURE_REVIEW_REQUIRED" in combined


def test_start_skip_gate_proceeds(cli_runner, tmp_path: Path, monkeypatch) -> None:
    """`research start <prog> --skip-gate` bypasses the gate + delegates."""
    import subprocess as sp

    import research_institution.cli as cli_mod

    monkeypatch.setattr(cli_mod, "_require_program", lambda name: _fake_program(tmp_path))
    monkeypatch.setattr(cli_mod, "_load", lambda: [_fake_program(tmp_path)])
    monkeypatch.setattr(
        sp, "run", lambda *a, **kw: sp.CompletedProcess(a[0], 0, stdout=ROADMAP_CLOSED, stderr="")
    )
    # Mathlint binary must resolve from PATH; conftest puts a fake one in shims.
    result = cli_runner.invoke(args=["start", "x", "--skip-gate"], catch_exceptions=False)
    # The fake mathlint exits 0; the dispatcher should also exit 0.
    assert result.exit_code == 0, f"got {result.exit_code}; stdout={result.stdout!r}"
    combined = (result.stdout or "") + (getattr(result, "stderr", "") or "")
    assert "--skip-gate" in combined or "bypassed" in combined.lower()
