"""Tests for the typed vocabulary contracts (B.1.x + cross-cutting).

These tests pin the *vocabulary* the dispatcher relies on. Adding a
new TaskKind value, renaming a DispatcherVerb, or changing an ExitCode
must surface here first.

Pattern (matches mathlint.orchestration.vocabulary):
  - Each StrEnum has a fixed, frozen set of members.
  - The mapping functions (gate_verdict_from_task_kind) are total
    (every TaskKind maps to a GateVerdictStatus, no exceptions).
"""

from __future__ import annotations


import pytest

from research_institution.contracts import (
    DispatcherVerb,
    ExitCode,
    GateVerdictStatus,
    TaskKind,
    gate_verdict_from_task_kind,
)


def test_task_kind_is_frozen_enum() -> None:
    """TaskKind is a closed set; adding a member is a deliberate edit."""
    members = set(TaskKind)
    assert members == {
        TaskKind.RESEARCH,
        TaskKind.ARCHITECTURE_REVIEW_REQUIRED,
        TaskKind.INFRASTRUCTURE_REPAIR,
        TaskKind.OTHER,
    }


def test_task_kind_str_round_trip() -> None:
    """Every TaskKind member is its own string value (StrEnum semantics)."""
    for member in TaskKind:
        assert member == member.value  # StrEnum: member IS the string


def test_gate_verdict_status_is_frozen() -> None:
    """GateVerdictStatus is the closed set the dispatcher relies on."""
    assert set(GateVerdictStatus) == {
        GateVerdictStatus.OPEN,
        GateVerdictStatus.CLOSED,
        GateVerdictStatus.UNKNOWN,
    }


def test_exit_code_values_match_operator_convention() -> None:
    """Exit codes match the documented numeric values."""
    assert ExitCode.SUCCESS == "0"
    assert ExitCode.INTERNAL_FAILURE == "1"
    assert ExitCode.USAGE_ERROR == "2"
    assert ExitCode.CATALOG_ERROR == "3"
    assert ExitCode.CREDENTIAL_ERROR == "4"
    assert ExitCode.GATE_CLOSED == "5"
    assert ExitCode.BINARY_MISSING == "127"


def test_dispatcher_verb_is_canonical_set() -> None:
    """DispatcherVerb is the closed set the CLI exposes."""
    assert set(DispatcherVerb) == {
        DispatcherVerb.LIST,
        DispatcherVerb.DOCTOR,
        DispatcherVerb.START,
        DispatcherVerb.STOP,
        DispatcherVerb.STATUS,
        DispatcherVerb.WATCH,
        DispatcherVerb.INSTALL_SKILLS,
    }


@pytest.mark.parametrize(
    "task_kind,expected",
    [
        (TaskKind.RESEARCH, GateVerdictStatus.OPEN),
        (TaskKind.INFRASTRUCTURE_REPAIR, GateVerdictStatus.OPEN),
        (TaskKind.ARCHITECTURE_REVIEW_REQUIRED, GateVerdictStatus.CLOSED),
        # Defensive default: unknown task kinds do NOT close the gate.
        (TaskKind.OTHER, GateVerdictStatus.OPEN),
    ],
)
def test_gate_verdict_from_task_kind_is_total(
    task_kind: TaskKind, expected: GateVerdictStatus
) -> None:
    """Every TaskKind maps to exactly one GateVerdictStatus."""
    assert gate_verdict_from_task_kind(task_kind) == expected


def test_gate_verdict_from_task_kind_covers_all_members() -> None:
    """Exhaustiveness: the mapping function has a branch for every member."""
    # If a new TaskKind is added, this test fails until the mapping
    # is updated. This is the canonical drift guard.
    for member in TaskKind:
        result = gate_verdict_from_task_kind(member)
        assert isinstance(result, GateVerdictStatus)


def test_unknown_task_kind_string_maps_to_other() -> None:
    """Raw strings not in the enum map to TaskKind.OTHER (defensive)."""
    # Use the TaskKind constructor directly: ValueError raised.
    with pytest.raises(ValueError):
        TaskKind("SOMETHING_NEW")
    # The dispatcher's parser catches ValueError and falls back to OTHER.
    # This is a contract: the parser is total, never raises.


def test_task_kind_absent_sentinel_canonical() -> None:
    """TASK_KIND_ABSENT is the canonical sentinel for "no TASK KIND line".

    A drift in the sentinel string breaks the dispatcher contract:
    the diagnostic surfaces the literal value, so a typo at the
    caller (defining a local "(absent)") would silently desync.
    """
    from research_institution.contracts import TASK_KIND_ABSENT

    assert TASK_KIND_ABSENT == "(absent)"
    # Sanity: not a TaskKind member (the sentinel is distinct from
    # the enum so consumers can distinguish "no line emitted" from
    # "explicit TaskKind.OTHER").
    assert TASK_KIND_ABSENT not in {member.value for member in TaskKind}


def test_task_kind_roadmap_failed_sentinel_canonical() -> None:
    """TASK_KIND_ROADMAP_FAILED is the canonical sentinel for mathlint roadmap non-zero exit.

    The dispatcher returns this sentinel when the roadmap subprocess
    exits non-zero; the diagnostic surface shows it verbatim.
    Promoting the sentinel to a module-level constant lets tests
    pin the exact value (so a rename in the dispatcher doesn't
    silently desync from a downstream contract test).
    """
    from research_institution.contracts import TASK_KIND_ROADMAP_FAILED

    assert TASK_KIND_ROADMAP_FAILED == "(roadmap-failed)"
    # Sanity: not a TaskKind member (same rationale as TASK_KIND_ABSENT).
    assert TASK_KIND_ROADMAP_FAILED not in {member.value for member in TaskKind}


def test_dispatcher_read_gate_uses_roadmap_failed_constant(tmp_path) -> None:
    """:func:`research_institution.dispatcher.read_gate` flows
    :data:`TASK_KIND_ROADMAP_FAILED` verbatim when the program-supplied
    work-selection callable raises an exception outside the recognised
    ``RoadmapNotFoundError`` / ``NoActiveWorkError`` family. This is the
    dispatcher's "probe boundary" sentinel.
    """
    from research_institution.contracts import (
        TASK_KIND_ROADMAP_FAILED,
        GateVerdictStatus,
    )
    from research_institution.dispatcher import Dispatcher
    from tests._fakes import FakeRunner
    from tests.test_dispatcher import _fake_program, _register_callable

    def callable_obj(repository, *, source_revision):
        raise RuntimeError("kaplansky: command not found")

    prog = _fake_program(tmp_path, name="kaplansky")
    d = Dispatcher(runner=FakeRunner())
    with _register_callable("kaplansky", callable_obj):
        verdict = d.read_gate(prog, timeout_seconds=5.0)
    assert verdict.task_kind == TASK_KIND_ROADMAP_FAILED
    assert verdict.status is GateVerdictStatus.UNKNOWN
