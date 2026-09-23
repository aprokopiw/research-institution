"""Acceptance tests for plan-013 (no-delta loop fix).

Per `@ADR-0011-stagnation-handling-is-a-source-decision` and
`@INV-0094-no-delta-loop-is-broken-by-source-side-stagnation-consult`,
``select_next_work_for_supervisor`` consults math's stagnation
triggers + scheduler verdict before dispatching, and translates
the verdict into the existing ``Dispatch`` / ``Wait`` envelope.

These tests pin:

1. **0/1/2/3 no-delta cases** in the four
   ``LiveSourceSnapshot.verdict_kind`` shapes.
2. **Role-aware payload compilation**:
   ``WorkRequest.payload[PAYLOAD_KEY_MATH_DIRECTIVE_CONTENT_HASH]`` is
   the byte-stable output of math's
   ``compute_directive_content_hash(compile_*_directive(...))``.
3. **Wire discipline**: the ``role`` field stays inside
   pi_monitor's existing 8-value ``RoleName`` Literal; the math
   internal ``MATHEMATICAL_RESEARCHER`` / ``MATHEMATICAL_ARCHITECT``
   ``RoleProfileName`` values NEVER cross the wire.
4. **Authority boundary**:
   ``select_next_work_for_supervisor`` never emits a ``SourceDecision``
   variant outside the existing ``Dispatch | Wait | OperatorRequired |
   Stop`` set; the ``reason_code`` field is one of the canonical
   values (existing 7 + the 2 new plan-013 additions).
"""

from __future__ import annotations

import tempfile

from mathlint.orchestration.live_source_snapshot import (
    VERDICT_ARCHITECTURE_REVIEW_REQUIRED,
    VERDICT_DISPATCH_ARCHITECT,
    VERDICT_DISPATCH_RESEARCH,
    VERDICT_NO_ELIGIBLE_WORK,
)
from pathlib import Path
from unittest.mock import patch

import pytest
from pi_monitor.work.work_source import (
    Dispatch,
    OperatorRequired,
    SourceRevision,
    Stop,
    Wait,
    WorkRequest,
)

from research_institution.contracts.source_decision import (
    EXTENDED_REASON_CODES,
    PAYLOAD_KEY_MATH_DIRECTIVE_CONTENT_HASH,
    PAYLOAD_KEY_MATH_DIRECTIVE_TEMPLATE_HASH,
    PAYLOAD_KEY_STAGNATION_SESSION_COUNT,
    REASON_ARCHITECTURE_REVIEW_DISPATCH,
    REASON_ARCHITECTURE_REVIEW_REQUIRED,
    REASON_NO_ELIGIBLE_WORK,
    REASON_WORK_AVAILABLE,
)
from research_institution.providers.research_institution_provider import (
    select_next_work_for_supervisor,
)


# ----------------------------------------------------------------------------
# Wire-legal ``RoleName`` values per pi_monitor (the wire authority).
# These are the closed 8-value Literal at
# ``pi_monitor.work.work_source.RoleName``; the OS-side narrowing
# type ``WorkRequestRoleAlias`` (in
# ``research_institution.contracts.source_decision``) is a subset
# of these.
# ----------------------------------------------------------------------------
WIRE_LEGAL_ROLES: frozenset[str] = frozenset({
    "default",
    "primary",
    "supporting",
    "milestone",
    "research",
    "intake",
    "review",
    "maintenance",
})


def _write_mathlint_toml(tmp: Path) -> None:
    """Write a minimal valid mathlint.toml at ``tmp``."""
    (tmp / "mathlint.toml").write_text(
        """schema = 1
source_roots = []
build_dir = "build"
max_module_lines = 180
max_work_item_lines = 260
max_direct_uses = 8
max_scope_depth = 6
max_ready_work_items = 3

[identifiers]
pattern = "^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$"

[toolchain]
python_version = "3.14.0"
required_commands = ["uv"]
optional_commands = ["gap", "sage"]
""",
        encoding="utf-8",
    )
    (tmp / "docs" / "deltas").mkdir(parents=True, exist_ok=True)


def _write_program_marker(tmp: Path, *, marker: str = "PROGRAMS.toml") -> None:
    """Write the program marker so the OS can identify the catalog program."""
    (tmp / marker).write_text("placeholder = true\n", encoding="utf-8")


def _make_candidate_work(operation_id: str = "K4-characteristic-two-restriction-obstruction",
                         *, role: str = "primary",
                         workspace: str = "workspace",
                         payload: dict | None = None) -> WorkRequest:
    """A WorkRequest shaped like one returned by a program work-selection callable."""
    return WorkRequest(
        source_identity="research-program",
        source_revision=SourceRevision("fingerprint-" + operation_id, 1.0),
        operation_id=operation_id,
        operation_kind="mathlint-research",
        role=role,
        workspace=workspace,
        payload=payload if payload is not None else {"next_action": "apply K-RIGIDITY"},
    )


# ----------------------------------------------------------------------------
# Mathematical delegate. The OS module imports
# ``mathlint.project.MathProject`` /
# ``mathlint.orchestration.live_source_snapshot.consult`` lazily inside
# the consult-and-translate function. The patch decorator (or
# ``unittest.mock.patch``) hooks both at the test-time import location
# so the runtime imports resolve to our fakes.
# ----------------------------------------------------------------------------


def _stub_global_action(*, kind, item_id: str = "op-A", title: str = "stub",
                        reason: str = "stub") -> object:
    """Build a stand-in GlobalAction. The wrapper only reads the four named fields."""
    return _FakeGlobalAction(kind=kind, item_id=item_id, title=title, reason=reason)


class _FakeGlobalAction:
    """A duck-typed stand-in for mathlint.scheduler.GlobalAction."""

    def __init__(self, *, kind, item_id: str, title: str, reason: str) -> None:
        self.kind = kind
        self.item_id = item_id
        self.title = title
        self.reason = reason


class _FakeStagnationTrigger:
    """A duck-typed stand-in for mathlint.deltas.StagnationTrigger."""

    def __init__(self, *, no_delta_count: int) -> None:
        self.no_delta_count = no_delta_count


class _FakeMathProject:
    """A minimal duck-typed stand-in for MathProject for the consult path."""

    def __init__(self, root: Path) -> None:
        self.root = root


def _install_consult_patches(
    *,
    math_project: _FakeMathProject,
    action_kind,
    stagnation_count: int,
):
    """Wire the imports the consult function will resolve to fakes."""
    return [
        patch(
            "research_institution.providers.research_institution_provider._consult_math_and_translate.__globals__",
            new={},  # placeholder; replaced below
        ),
    ]


def _mock_consult_for_action(action_kind, stagnation_count: int = 0, *,
                              directive_hash: str = "sha256:fake-directive-content-hash",
                              template_hash: str = "sha256:fake-directive-template-hash") -> object:
    """Build a callable that mimics ``consult(math_project, candidate, t)``."""
    class _Snapshot:
        verdict_kind = action_kind  # one of the 4 closed literals
        target = "op-A"
        stagnation_session_count = stagnation_count
        directive_content_hash = directive_hash
        directive_template_hash = template_hash
    return lambda *args, **kwargs: _Snapshot()


# ----------------------------------------------------------------------------
# 1. The four stagnation cases.
# ----------------------------------------------------------------------------


@pytest.fixture
def tmp_math_repo(tmp_path: Path) -> Path:
    """A tmp dir that is BOTH a mathlint project AND has a program marker."""
    _write_mathlint_toml(tmp_path)
    _write_program_marker(tmp_path)
    return tmp_path


def _stub_consult(action_kind: str, *, no_delta_count: int = 0):
    """Build a context manager that mocks the math side to drive a verdict."""
    import mathlint.orchestration.live_source_snapshot as lss
    import mathlint.project as project_mod

    class _Snapshot:
        def __init__(self) -> None:
            self.verdict_kind = action_kind
            self.target = "op-A"
            self.stagnation_session_count = no_delta_count
            self.directive_content_hash = "sha256:fakehash" + action_kind
            self.directive_template_hash = "sha256:tplhash" + action_kind

    fake_snapshot = _Snapshot()

    # Stub MathProject.load to return a project whose root is the tmp_path.
    def _fake_load(start=None, **_):
        class _Project:
            root = start if start is not None else Path(tempfile.gettempdir())
        return _Project()

    return [
        patch.object(project_mod.MathProject, "load", side_effect=_fake_load),
        patch.object(lss, "consult", return_value=fake_snapshot),
    ]


def _run_provider_consult(
    tmp_path: Path,
    candidate: WorkRequest,
    *consult_patches,
):
    """Apply the consult patches, call the provider, return the envelope."""
    from research_institution.providers import research_institution_provider as p

    def callable_obj(repository, *, source_revision):
        return [candidate]
    with patch.object(p, "_work_selection_callable_for_repo", return_value=callable_obj):
        from contextlib import ExitStack
        with ExitStack() as stack:
            for ctx in consult_patches:
                stack.enter_context(ctx)
            envelope = select_next_work_for_supervisor(tmp_path)
    return envelope


# ----------------------------------------------------------------------------
# 1a. 0 no-delta -> DISPATCH_RESEARCH
# ----------------------------------------------------------------------------


def test_no_stagnation_returns_dispatch_research(tmp_path: Path) -> None:
    """0 no-delta on the target -> Dispatch(role='research')."""
    candidate = _make_candidate_work()
    patches = _stub_consult(VERDICT_DISPATCH_RESEARCH, no_delta_count=0)
    envelope = _run_provider_consult(tmp_path, candidate, *patches)
    assert isinstance(envelope, Dispatch)
    assert len(envelope.work) == 1
    dispatched = envelope.work[0]
    assert dispatched.role == "research"
    assert dispatched.role in WIRE_LEGAL_ROLES
    assert envelope.reason_code == REASON_WORK_AVAILABLE
    # The directive content hash is injected into the payload.
    assert PAYLOAD_KEY_MATH_DIRECTIVE_CONTENT_HASH in dispatched.payload
    assert dispatched.payload[PAYLOAD_KEY_MATH_DIRECTIVE_CONTENT_HASH].startswith("sha256:")


# ----------------------------------------------------------------------------
# 1b. 1 no-delta (still dispatch).
# ----------------------------------------------------------------------------


def test_one_no_delta_returns_dispatch_research(tmp_path: Path) -> None:
    """1 no-delta is not yet stagnation; still dispatch researcher."""
    candidate = _make_candidate_work()
    patches = _stub_consult(VERDICT_DISPATCH_RESEARCH, no_delta_count=1)
    envelope = _run_provider_consult(tmp_path, candidate, *patches)
    assert isinstance(envelope, Dispatch)
    assert envelope.work[0].role == "research"
    assert envelope.work[0].payload[PAYLOAD_KEY_STAGNATION_SESSION_COUNT] == 1


# ----------------------------------------------------------------------------
# 1c. 2+ no-delta -> Wait(architecture_review_required).
# ----------------------------------------------------------------------------


def test_two_no_delta_returns_wait_architecture_review(tmp_path: Path) -> None:
    """2+ no-delta flips to Wait(reason_code='architecture_review_required')."""
    candidate = _make_candidate_work()
    patches = _stub_consult(VERDICT_ARCHITECTURE_REVIEW_REQUIRED, no_delta_count=2)
    envelope = _run_provider_consult(tmp_path, candidate, *patches)
    assert isinstance(envelope, Wait)
    assert envelope.reason_code == REASON_ARCHITECTURE_REVIEW_REQUIRED
    assert envelope.wake_on_source_change is True
    assert envelope.retry_after_seconds == 300.0


# ----------------------------------------------------------------------------
# 1d. architect round mid-flight -> Dispatch with role='maintenance'.
# ----------------------------------------------------------------------------


def test_three_no_delta_returns_dispatch_architect(tmp_path: Path) -> None:
    """Admitted architect round -> Dispatch(role='maintenance')."""
    candidate = _make_candidate_work()
    patches = _stub_consult(VERDICT_DISPATCH_ARCHITECT, no_delta_count=3)
    envelope = _run_provider_consult(tmp_path, candidate, *patches)
    assert isinstance(envelope, Dispatch)
    assert envelope.reason_code == REASON_ARCHITECTURE_REVIEW_DISPATCH
    assert envelope.work[0].role == "maintenance"
    assert envelope.work[0].role in WIRE_LEGAL_ROLES


# ----------------------------------------------------------------------------
# 1e. NO_ELIGIBLE_WORK -> Wait(no_eligible_work).
# ----------------------------------------------------------------------------


def test_no_eligible_work_returns_wait(tmp_path: Path) -> None:
    """NO_ELIGIBLE_WORK from the consult -> Wait(reason_code='no_eligible_work')."""
    candidate = _make_candidate_work()
    patches = _stub_consult(VERDICT_NO_ELIGIBLE_WORK, no_delta_count=0)
    envelope = _run_provider_consult(tmp_path, candidate, *patches)
    assert isinstance(envelope, Wait)
    assert envelope.reason_code == REASON_NO_ELIGIBLE_WORK
    assert envelope.wake_on_source_change is True


# ----------------------------------------------------------------------------
# 2. Role-aware payload compilation.
# ----------------------------------------------------------------------------


def test_role_aware_payload_includes_math_directive_hashes(tmp_path: Path) -> None:
    """For DISPATCH_RESEARCH, the WorkRequest payload carries the math directive hashes."""
    candidate = _make_candidate_work()
    test_directive_hash = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    test_template_hash = "sha256:fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
    _write_mathlint_toml(tmp_path)
    _write_program_marker(tmp_path)
    # Override the directive hashes via direct snapshot substitution.
    import mathlint.orchestration.live_source_snapshot as lss
    import mathlint.project as project_mod

    class _Project:
        root = tmp_path

    class _Snapshot:
        verdict_kind = VERDICT_DISPATCH_RESEARCH
        target = "op-A"
        stagnation_session_count = 0
        directive_content_hash = test_directive_hash
        directive_template_hash = test_template_hash

    patches = [
        patch.object(project_mod.MathProject, "load", return_value=_Project()),
        patch.object(lss, "consult", return_value=_Snapshot()),
    ]
    envelope = _run_provider_consult(tmp_path, candidate, *patches)
    assert isinstance(envelope, Dispatch)
    dispatched = envelope.work[0]
    assert dispatched.payload[PAYLOAD_KEY_MATH_DIRECTIVE_CONTENT_HASH] == test_directive_hash
    assert dispatched.payload[PAYLOAD_KEY_MATH_DIRECTIVE_TEMPLATE_HASH] == test_template_hash


# ----------------------------------------------------------------------------
# 3. Authority boundary.
# ----------------------------------------------------------------------------


def test_no_source_decision_variant_introduced(tmp_path: Path) -> None:
    """Across all four consult verdicts, the envelope stays inside Dispatch|Wait|...|Stop."""
    for verdict in (
        VERDICT_DISPATCH_RESEARCH,
        VERDICT_DISPATCH_ARCHITECT,
        VERDICT_ARCHITECTURE_REVIEW_REQUIRED,
        VERDICT_NO_ELIGIBLE_WORK,
    ):
        candidate = _make_candidate_work()
        patches = _stub_consult(verdict, no_delta_count=2)
        envelope = _run_provider_consult(tmp_path, candidate, *patches)
        assert isinstance(envelope, (Dispatch, Wait, OperatorRequired, Stop)), (
            f"verdict={verdict} emitted {type(envelope).__name__}; "
            "the plan must not introduce a new SourceDecision variant"
        )


def test_dispatched_role_always_in_wire_legal_literal(tmp_path: Path) -> None:
    """Every dispatched WorkRequest.role is inside the wire RoleName Literal."""
    for verdict, expected_role in (
        (VERDICT_DISPATCH_RESEARCH, "research"),
        (VERDICT_DISPATCH_ARCHITECT, "maintenance"),
    ):
        candidate = _make_candidate_work()
        patches = _stub_consult(verdict, no_delta_count=2)
        envelope = _run_provider_consult(tmp_path, candidate, *patches)
        assert isinstance(envelope, Dispatch)
        for wr in envelope.work:
            assert wr.role in WIRE_LEGAL_ROLES, (
                f"verdict={verdict} emitted wire role={wr.role!r}; "
                "the wire RoleName Literal is byte-identical to pre-plan-013"
            )
            assert wr.role == expected_role, (
                f"verdict={verdict} expected role={expected_role!r}; got {wr.role!r}"
            )


def test_no_math_role_profile_names_on_wire(tmp_path: Path) -> None:
    """``MATHEMATICAL_RESEARCHER`` / ``MATHEMATICAL_ARCHITECT`` NEVER on the wire."""
    candidate = _make_candidate_work()
    patches = _stub_consult(VERDICT_DISPATCH_RESEARCH, no_delta_count=0)
    envelope = _run_provider_consult(tmp_path, candidate, *patches)
    assert isinstance(envelope, Dispatch)
    for wr in envelope.work:
        assert wr.role not in ("MATHEMATICAL_RESEARCHER", "MATHEMATICAL_ARCHITECT"), (
            f"Math-internal RoleProfileName {wr.role!r} crossed the wire; "
            "pi_monitor's wire RoleName Literal is unchanged"
        )
        # Also check the reason field doesn't leak them.
        assert "MATHEMATICAL_RESEARCHER" not in envelope.reason
        assert "MATHEMATICAL_ARCHITECT" not in envelope.reason


def test_wait_reason_codes_are_in_extended_set(tmp_path: Path) -> None:
    """Wait envelopes' reason_code is inside the extended reason-code set."""
    candidate = _make_candidate_work()
    for verdict in (VERDICT_ARCHITECTURE_REVIEW_REQUIRED, VERDICT_NO_ELIGIBLE_WORK):
        patches = _stub_consult(verdict, no_delta_count=2)
        envelope = _run_provider_consult(tmp_path, candidate, *patches)
        assert isinstance(envelope, Wait)
        assert envelope.reason_code in EXTENDED_REASON_CODES, (
            f"verdict={verdict} emitted reason_code={envelope.reason_code!r}; "
            f"not in EXTENDED_REASON_CODES"
        )


def test_unknown_verdict_kind_emits_wait_fallback(tmp_path: Path) -> None:
    """An unknown verdict_kind maps to Wait(reason='unknown_math_verdict')."""
    candidate = _make_candidate_work()
    patches = _stub_consult("UNKNOWN_VERDICT_KIND_FROM_FUTURE", no_delta_count=0)
    envelope = _run_provider_consult(tmp_path, candidate, *patches)
    assert isinstance(envelope, Wait)
    assert "unknown_math_verdict" in envelope.reason or envelope.reason_code == "wait_requested", (
        f"unknown verdict emitted envelope={envelope!r}; expected Wait fallback"
    )
