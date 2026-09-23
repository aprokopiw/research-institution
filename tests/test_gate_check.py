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

from contextlib import contextmanager
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
#
# These tests pin the ``GateVerdict.from_text`` parser. The parser is
# retained as a public utility (legacy mathlint-roadmap-snapshot
# parsing) but is no longer invoked by ``check_gate``; ``check_gate``
# now probes the program-supplied work-selection callable through
# the kernel-blessed ``mathlint.program_work_selection`` entry-point
# registry. The parser tests below are kept so a future regression in
# the text-based parser surfaces immediately, even though the
# dispatcher's primary path no longer exercises it.
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
# CLI wrapper tests (probe the program-supplied work-selection callable).
# ---------------------------------------------------------------------------


def _make_work_request(operation_id: str = "K4"):
    """Build a minimal WorkRequest for check_gate probe tests."""
    from datetime import UTC, datetime

    from pi_monitor.work.work_source import SourceRevision, WorkRequest

    observed = datetime.now(tz=UTC).timestamp()
    return WorkRequest(
        source_identity="x-test-program",
        source_revision=SourceRevision(
            fingerprint="0" * 40,
            observed_unix=observed,
            label="stub",
        ),
        operation_id=operation_id,
        operation_kind="mathlint-research",
        role="MATHEMATICAL_RESEARCH",
        workspace="stub-workspace",
        payload={},
    )


@contextmanager
def _register_callable(name: str, callable_obj):
    """Install a fake work-selection callable into the kernel registry."""
    from mathlint.program_providers import (
        WorkSelectionSlot,
        set_work_selection_slot,
        work_selection_slot,
    )

    prior = work_selection_slot()
    new_selectors = dict(prior.selectors)
    new_selectors[name] = callable_obj
    set_work_selection_slot(WorkSelectionSlot(selectors=new_selectors))
    try:
        yield
    finally:
        set_work_selection_slot(prior)


class RoadmapNotFoundError(LookupError):
    pass


class NoActiveWorkError(LookupError):
    pass


def _prog(tmp_path: Path, name: str = "kaplansky") -> Program:
    return Program(
        name=name,
        display_name="X",
        repository="https://x/x",
        entry_point="x:r",
        local_path=str(tmp_path),
        mathlint_pin="v0.0.1",
        live_credentials_required=False,
        live_credential_env_vars=(),
        check_program_script="check.sh",
    )


def test_gate_open_when_program_returns_active_work(tmp_path: Path) -> None:
    """Closed-program open gate -> check_gate returns OPEN with the
    active operation_id surfaced as ``task_kind``.
    """
    def callable_obj(repository, *, source_revision):
        return [_make_work_request("K4")]

    with _register_callable("kaplansky", callable_obj):
        v = check_gate(_prog(tmp_path))
    assert v.status == GateVerdictStatus.OPEN
    assert v.task_kind == "K4"
    assert v.gate_open is True


def test_gate_closed_when_no_active_work(tmp_path: Path) -> None:
    """Empty work list -> CLOSED with the canonical ``(no-active-work)`` sentinel."""
    def callable_obj(repository, *, source_revision):
        return []

    with _register_callable("kaplansky", callable_obj):
        v = check_gate(_prog(tmp_path))
    assert v.status == GateVerdictStatus.CLOSED
    assert v.task_kind == "(no-active-work)"
    assert v.gate_open is False


def test_gate_closed_when_roadmap_missing(tmp_path: Path) -> None:
    """RoadmapNotFoundError -> CLOSED with ``(roadmap-missing)``."""
    def callable_obj(repository, *, source_revision):
        raise RoadmapNotFoundError("missing roadmap")

    with _register_callable("kaplansky", callable_obj):
        v = check_gate(_prog(tmp_path))
    assert v.status == GateVerdictStatus.CLOSED
    assert v.task_kind == "(roadmap-missing)"


def test_gate_closed_when_no_active_work_error(tmp_path: Path) -> None:
    """NoActiveWorkError -> CLOSED with ``(no-active-work)``."""
    def callable_obj(repository, *, source_revision):
        raise NoActiveWorkError("no K items active")

    with _register_callable("kaplansky", callable_obj):
        v = check_gate(_prog(tmp_path))
    assert v.status == GateVerdictStatus.CLOSED
    assert v.task_kind == "(no-active-work)"
    assert "no K items active" in v.reason


def test_gate_unknown_when_operator_direction_required(tmp_path: Path) -> None:
    """OperatorDirectionRequiredError -> UNKNOWN with ``(operator-direction-required)`` (per @INV-0094).

    The dispatcher inspects the program's exception class by
    attribute lookup on the callable's module (the OS does not
    hardcode any program in source). This test pins that
    attribute-lookup contract; if the lookup breaks, the
    dispatcher's ``TASK_KIND_ROADMAP_FAILED`` fallback will
    silently misclassify the verdict and the supervisor will
    fall into the no-delta loop this invariant defends against.
    """
    class OperatorDirectionRequiredError(LookupError):
        pass

    def callable_obj(repository, *, source_revision):
        raise OperatorDirectionRequiredError(
            "operator direction required:\n  - K4 (parked)"
        )

    # Make the class discoverable on the callable's __module__.
    import sys
    fake_module = type(sys)("fake_program_module")
    fake_module.OperatorDirectionRequiredError = OperatorDirectionRequiredError
    fake_module.RoadmapNotFoundError = type("RoadmapNotFoundError", (LookupError,), {})
    fake_module.NoActiveWorkError = type("NoActiveWorkError", (LookupError,), {})
    sys.modules["fake_program_module"] = fake_module
    callable_obj.__module__ = "fake_program_module"
    try:
        with _register_callable("kaplansky", callable_obj):
            v = check_gate(_prog(tmp_path))
    finally:
        sys.modules.pop("fake_program_module", None)
    assert v.status == GateVerdictStatus.UNKNOWN
    assert v.task_kind == "(operator-direction-required)"
    assert v.gate_open is False
    assert "K4 (parked)" in v.reason


def test_gate_unknown_when_no_callable_registered(tmp_path: Path, monkeypatch) -> None:
    """No callable registered -> UNKNOWN with ``(no-work-selection-callable)``.

    The ``check_gate`` discovery call is monkey-patched to a no-op
    so the installed kaplansky entry point does not populate the
    registry during this test (the OS-level gate must report
    UNKNOWN when no callable is registered for the program).
    """
    from mathlint.program_providers import (  # noqa: F401  # imported for side effect (work-selection registry)
        discover_work_selection_programs,
    )

    monkeypatch.setattr(
        "research_institution.cli.discover_work_selection_programs",
        lambda: None,
        raising=False,
    )
    # Also stub the import inside ``check_gate`` itself.
    monkeypatch.setattr(
        "mathlint.program_providers.discover_work_selection_programs",
        lambda: None,
    )
    v = check_gate(_prog(tmp_path))
    assert v.status == GateVerdictStatus.UNKNOWN
    assert v.task_kind == "(no-work-selection-callable)"


def test_gate_unknown_when_callable_raises_unexpected(tmp_path: Path) -> None:
    """Unknown exception family -> UNKNOWN with diagnostic + (roadmap-failed) sentinel."""
    def callable_obj(repository, *, source_revision):
        raise RuntimeError("disk on fire")

    with _register_callable("kaplansky", callable_obj):
        v = check_gate(_prog(tmp_path))
    assert v.status == GateVerdictStatus.UNKNOWN
    assert v.task_kind == "(roadmap-failed)"
    assert "disk on fire" in v.reason


def test_from_text_raw_excerpt_is_last_400_chars() -> None:
    """Pure-parser path also enforces the 400-char truncation invariant."""
    from research_institution.cli import GateVerdict

    long_text = "Y" * 1000
    long_text += "\nTASK KIND: RESEARCH\n"  # forces non-empty post-truncation
    v = GateVerdict.from_text(long_text)
    assert len(v.raw_excerpt) == 400
    assert v.raw_excerpt == long_text[-400:]


def test_start_refuses_on_closed_gate(cli_runner, tmp_path: Path, monkeypatch) -> None:
    """End-to-end: `research start <prog>` (non-dry-run) refuses on closed gate.

    The CLI delegates the gate check to ``Dispatcher.read_gate``,
    which probes the program-supplied work-selection callable. Tests
    inject a fake callable that returns an empty list (=> CLOSED).
    """
    import research_institution.cli as cli_mod
    from research_institution.contracts import GateVerdict
    from research_institution.dispatcher import Dispatcher

    prog = _prog(tmp_path, name="x")
    monkeypatch.setattr(cli_mod, "_require_program", lambda name: prog)
    monkeypatch.setattr(cli_mod, "_load", lambda: [prog])

    def fake_read_gate(self, p, **_kw):
        return GateVerdict(
            task_kind="ARCHITECTURE_REVIEW_REQUIRED",
            status=GateVerdictStatus.CLOSED,
            reason="completed outcome has no unique approved on_failure edge.",
        )

    monkeypatch.setattr(Dispatcher, "read_gate", fake_read_gate)

    result = cli_runner.invoke(args=["start", "x"], catch_exceptions=False)
    assert result.exit_code == EXIT_GATE_CLOSED, (
        f"expected {EXIT_GATE_CLOSED}, got {result.exit_code}; "
        f"stdout={result.stdout!r} stderr={getattr(result, 'stderr', '')!r}"
    )
    combined = (result.stdout or "") + (getattr(result, "stderr", "") or "")
    assert "GATE NOT OPEN" in combined
    assert "ARCHITECTURE_REVIEW_REQUIRED" in combined


def test_start_skip_gate_proceeds(cli_runner, tmp_path: Path, monkeypatch) -> None:
    """`research start <prog> --skip-gate` bypasses the gate + delegates.

    The dispatcher layer is fully short-circuited by the CLI's
    ``--skip-gate`` flag — the test does not need to fake the gate.
    The fake mathlint binary is provided by ``conftest``.
    """
    import subprocess as sp

    import research_institution.cli as cli_mod

    prog = _prog(tmp_path, name="x")
    monkeypatch.setattr(cli_mod, "_require_program", lambda name: prog)
    monkeypatch.setattr(cli_mod, "_load", lambda: [prog])
    monkeypatch.setattr(
        sp, "run", lambda *a, **kw: sp.CompletedProcess(a[0], 0, stdout="", stderr="")
    )
    result = cli_runner.invoke(args=["start", "x", "--skip-gate"], catch_exceptions=False)
    assert result.exit_code == 0, f"got {result.exit_code}; stdout={result.stdout!r}"
    combined = (result.stdout or "") + (getattr(result, "stderr", "") or "")
    assert "--skip-gate" in combined or "bypassed" in combined.lower()


# ---------------------------------------------------------------------------
# CROSS_REPO_010 — end-to-end: mathlint roadmap against the operator's
# actual machine produces a recognizable task_kind.
#
# Defect class: mathlint emits a brand-new TASK KIND value (e.g.
# ``REVIEW_PENDING``) that the dispatcher's ``gate_verdict_from_task_kind``
# doesn't enumerate. Today this falls into the OTHER bucket (defensive
# default: gate OPEN) — silently. The dispatcher's silent-open on
# unknown kinds is the *intended* safe behavior (refuse false-GREEN
# bias), but operators need to know when mathlint has introduced a
# new kind so they can decide whether to keep the OPEN default or
# tighten to CLOSED. This oracle surfaces the silent-OTHER mapping
# loudly.
# ---------------------------------------------------------------------------


def _resolve_real_mathlint_root(tmp_path: Path) -> Path | None:
    """Resolve the kaplansky project root for the live ``check_gate`` call.

    Order: $KAPLANSKY_REPOSITORY env var, then the canonical operator
    catalog, then skip. Returns a Path that may or may not exist; the
    caller is responsible for the existence check.
    """
    import os as _os

    env_root = _os.environ.get("KAPLANSKY_REPOSITORY")
    if env_root:
        return Path(env_root)
    catalog = Path("~/Documents/andrei/research-institution/catalog/programs.toml").expanduser()
    if not catalog.is_file():
        return None
    import tomllib

    try:
        data = tomllib.loads(catalog.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    for entry in data.get("programs", []):
        if isinstance(entry, dict) and entry.get("name") == "kaplansky":
            local = entry.get("local_path", "")
            if isinstance(local, str) and local:
                return Path(local.replace("$HOME", str(Path.home()))).expanduser()
    return None


def test_cross_repo_010_check_gate_uses_real_catalog_entry(tmp_path: Path) -> None:
    """CROSS_REPO_010 — invoking ``check_gate`` against the operator's
    real catalog entry MUST return a verdict derived from the
    program-supplied work-selection callable (no subprocess; per
    @ADR-0014 the dispatcher does not shell out to ``mathlint
    roadmap`` against a program repo).

    The verdict MUST be one of:

      - status=OPEN + ``task_kind=<operation_id>`` if the program
        has active work,
      - status=CLOSED + ``task_kind=(no-active-work)`` if the
        program has no active item,
      - status=CLOSED + ``task_kind=(roadmap-missing)`` if the
        program's roadmap is missing,
      - status=UNKNOWN + a diagnostic sentinel otherwise.

    Skipped when the catalog isn't reachable (clean CI runner).
    The test runs end-to-end on the operator's wired machine,
    exercising the same code path ``research start`` takes on
    every launch.
    """
    project_root = _resolve_real_mathlint_root(tmp_path)
    if project_root is None:
        pytest.skip("CROSS_REPO_010: cannot resolve kaplansky project root")
    if not project_root.is_dir():
        pytest.skip(f"CROSS_REPO_010: project root {project_root} unreachable")

    try:
        from research_institution.catalog import load_catalog
        from research_institution.paths import catalog_path

        programs = load_catalog(catalog_path())
    except (OSError, ValueError, ImportError, RuntimeError):
        pytest.skip("CROSS_REPO_010: catalog unreadable")

    program = next((p for p in programs if p.name == "kaplansky"), None)
    if program is None:
        pytest.skip("CROSS_REPO_010: catalog has no kaplansky entry")

    try:
        from mathlint.program_providers import (
            discover_work_selection_programs,
            work_selection_callables,
        )
    except ImportError:
        pytest.skip("CROSS_REPO_010: mathlint.program_providers unimportable")
    discover_work_selection_programs()
    if "kaplansky" not in work_selection_callables():
        pytest.skip("CROSS_REPO_010: kaplansky entry point not installed")

    verdict = check_gate(program, mathlint_bin="mathlint")

    valid_kinds = {
        "RESEARCH",
        "(no-active-work)",
        "(roadmap-missing)",
        "(no-work-selection-callable)",
        "(operator-direction-required)",  # @INV-0094
        "(roadmap-failed)",
    }
    if verdict.status == GateVerdictStatus.OPEN and verdict.task_kind not in valid_kinds:
        # OPEN verdicts carry the operation_id verbatim — accept.
        pass
    elif verdict.task_kind not in valid_kinds:
        pytest.fail(
            f"CROSS_REPO_010 FAIL: check_gate returned an unexpected "
            f"verdict kind {verdict.task_kind!r} (status={verdict.status}). "
            f"Expected one of {sorted(valid_kinds)}. reason={verdict.reason!r}"
        )

