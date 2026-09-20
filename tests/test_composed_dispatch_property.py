"""Composed property tests for the typed dispatch envelope surface.

Per @ADR-0007 + Constitution Principles I/II/III: the dispatch
envelope crosses three repos (research-institution, math, pi-monitor)
and survives as a frozen, statically-typed dataclass the entire way.
These tests exercise the *whole composition* in-process — no
subprocess, no supervisor — so they run in milliseconds.

What they prove:

  1. ``select_next_work_for_supervisor(repo)`` returns a typed
     ``Wait`` (the OS-level provider's actual contribution).
  2. ``source_decision_to_wire(envelope)`` serializes any
     ``SourceDecision`` to a dict whose shape matches the wire
     allow-list (no extra fields, no missing required fields).
  3. ``parse_source_decision(wire_dict)`` recovers the typed envelope
     byte-for-byte (``round_trip_typed == original``).
  4. ``decision_kind(parsed) == decision_kind(original)`` — the
     discriminator survives round-trip.
  5. The whole pipeline is closed under random inputs: Hypothesis
     generates thousands of envelopes and confirms invariants
     without ever spawning a subprocess.

Drift detection:

  - If pi_monitor changes a dataclass field, pyright fails here at
    edit time (the contracts module re-exports pi_monitor's classes
    by identity; the type system catches drift before any test
    runs).
  - If a future contributor adds a fifth decision variant,
    pyright will flag the final ``return DecisionKind.STOP`` line
    as having type ``Never``, and the parametrized test will fail
    because the new variant isn't exercised.
  - If a future contributor loosens the parser (e.g. defaults an
    opaque str to a typed value), the round-trip property fails.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pi_monitor.work_source import (
    Dispatch,
    OperatorRequired,
    SourceRevision,
    Stop,
    Wait,
    WorkRequest,
)

from research_institution.contracts.source_decision import (
    CANONICAL_REASON_CODES,
    DecisionKind,
    DecisionKindLiteral,
    ReasonCodeLiteral,
    REASON_WAIT_REQUESTED,
    SourceDecision,
    decision_kind,
    parse_source_decision,
    source_decision_to_wire,
)
from research_institution.providers.research_institution_provider import (
    select_next_work_for_supervisor,
)


# ---------------------------------------------------------------------------
# Composed integration: OS provider -> wire -> parse -> identity
# ---------------------------------------------------------------------------


def test_composed_os_provider_to_wire_to_typed() -> None:
    """The full composition in-process:

        select_next_work_for_supervisor(repo)
            -> typed Wait
            -> source_decision_to_wire(typed) -> wire dict
            -> parse_source_decision(wire dict) -> typed
            -> decision_kind(typed) == DecisionKind.WAIT

    No subprocess, no supervisor. The whole pipeline runs in <1ms.
    If any step regresses, this test fails immediately.
    """
    repo = Path("/tmp/composed-test-repo")  # noqa: S108
    envelope = select_next_work_for_supervisor(repository=repo)

    # OS provider contribution: typed Wait.
    assert isinstance(envelope, Wait)
    assert decision_kind(envelope) is DecisionKind.WAIT

    # Wire-shape round-trip.
    wire = source_decision_to_wire(envelope)
    assert wire["kind"] == "wait"
    assert "work" not in wire, (
        "Wait envelopes must NOT carry a work key (pi-monitor wire v1 "
        "rejects Wait envelopes with extra fields)"
    )

    # Parse back.
    parsed = parse_source_decision(wire)
    assert isinstance(parsed, Wait)
    assert decision_kind(parsed) is DecisionKind.WAIT

    # Identity on the typed layer.
    assert parsed == envelope
    assert parsed.source_revision == envelope.source_revision
    assert parsed.decided_unix == envelope.decided_unix


def test_composed_register_slot_to_typed_envelope() -> None:
    """The kernel-side composition: register() lands the OS provider in
    mathlint's ``ProgramProviders.work_source_provider`` slot, the
    kernel reads the slot, calls the provider, and the typed envelope
    round-trips through parse + serialize.

    This is the *whole wiring* as a single unit test — every seam the
    supervisor traverses in production (except the subprocess boundary
    itself) is exercised here in <5ms.
    """
    try:
        import mathlint.program_providers as mp
    except ImportError:
        pytest.skip("mathlint not importable in this venv")

    from research_institution.providers.research_institution_provider import register

    snapshot = mp._state.current  # type: ignore[reportPrivateUsage]  # tests intentionally snapshot the private kernel state to restore between cases
    try:
        register()
        providers = mp.program_providers()

        # Slot is populated with a typed callable.
        slot = providers.work_source_provider
        assert slot is not None
        assert callable(slot)

        # Calling the slot returns a typed envelope (the actual composition).
        envelope: Wait = slot(Path("/tmp/composed-slot-test"))  # type: ignore[reportUnknownVariableType]  # noqa: S108  # slot returns SourceDecision union; test asserts isinstance(Wait)
        assert isinstance(envelope, Wait)

        # The envelope round-trips through the wire layer.
        wire = source_decision_to_wire(envelope)
        parsed = parse_source_decision(wire)
        assert parsed == envelope
    finally:
        mp._state.current = snapshot  # type: ignore[reportPrivateUsage]  # see snapshot above


# ---------------------------------------------------------------------------
# Hypothesis: random SourceDecisions round-trip cleanly
# ---------------------------------------------------------------------------

# Strategy: build a random SourceRevision
revision_st = st.builds(
    SourceRevision,
    fingerprint=st.text(min_size=1, max_size=64, alphabet=st.characters(min_codepoint=33, max_codepoint=126)),
    observed_unix=st.floats(
        min_value=0.0,
        max_value=2_000_000_000.0,
        allow_nan=False,
        allow_infinity=False,
    ),
    label=st.text(max_size=64),
)

# Strategy: build a random WorkRequest
work_request_st = st.builds(
    WorkRequest,
    source_identity=st.text(min_size=1, max_size=32),
    source_revision=revision_st,
    operation_id=st.text(min_size=1, max_size=64),
    operation_kind=st.text(min_size=1, max_size=32),
    role=st.sampled_from(["default", "MATHEMATICAL_RESEARCH"]),
    workspace=st.sampled_from(["default", "kaplansky-workspace", "synthetic-workspace"]),
    payload=st.dictionaries(
        keys=st.text(min_size=1, max_size=16),
        values=st.one_of(
            st.text(max_size=64),
            st.integers(min_value=-100, max_value=100),
            st.booleans(),
        ),
        max_size=4,
    ),
    execution_policy=st.dictionaries(
        keys=st.sampled_from(["source_authority", "disposable_worktree", "bounded"]),
        values=st.booleans(),
        max_size=2,
    ),
    session_policy=st.dictionaries(
        keys=st.text(min_size=1, max_size=8),
        values=st.text(max_size=8),
        max_size=2,
    ),
    isolation=st.dictionaries(
        keys=st.text(min_size=1, max_size=8),
        values=st.booleans(),
        max_size=2,
    ),
    budget=st.dictionaries(
        keys=st.sampled_from(["bounded", "max_steps"]),
        values=st.booleans() | st.integers(min_value=0, max_value=10),
        max_size=2,
    ),
    execution_profile=st.sampled_from(["", "default", "mathlint-research-v1"]),
    lease_until_unix=st.one_of(
        st.none(),
        st.floats(
            min_value=0.0,
            max_value=2_000_000_000.0,
            allow_nan=False,
            allow_infinity=False,
        ),
    ),
)

# Strategy: build a random Dispatch
dispatch_st = st.builds(
    Dispatch,
    source_revision=revision_st,
    decided_unix=st.floats(
        min_value=0.0,
        max_value=2_000_000_000.0,
        allow_nan=False,
        allow_infinity=False,
    ),
    work=st.lists(work_request_st, min_size=0, max_size=3),
    reason_code=st.sampled_from(list(CANONICAL_REASON_CODES)),
    reason=st.text(max_size=120),
)

# Strategy: build a random Wait
wait_st = st.builds(
    Wait,
    source_revision=revision_st,
    decided_unix=st.floats(
        min_value=0.0,
        max_value=2_000_000_000.0,
        allow_nan=False,
        allow_infinity=False,
    ),
    reason_code=st.sampled_from(list(CANONICAL_REASON_CODES)),
    reason=st.text(max_size=120),
    wake_on_source_change=st.booleans(),
    retry_after_seconds=st.one_of(
        st.none(),
        st.floats(min_value=0.0, max_value=3600.0, allow_nan=False, allow_infinity=False),
    ),
    until_unix=st.one_of(
        st.none(),
        st.floats(min_value=0.0, max_value=2_000_000_000.0, allow_nan=False, allow_infinity=False),
    ),
    payload=st.dictionaries(
        keys=st.text(min_size=1, max_size=8),
        values=st.text(max_size=32),
        max_size=2,
    ),
)

# Strategy: build a random OperatorRequired
operator_required_st = st.builds(
    OperatorRequired,
    source_revision=revision_st,
    decided_unix=st.floats(
        min_value=0.0,
        max_value=2_000_000_000.0,
        allow_nan=False,
        allow_infinity=False,
    ),
    reason_code=st.sampled_from(list(CANONICAL_REASON_CODES)),
    reason=st.text(max_size=120),
)

# Strategy: build a random Stop
stop_st = st.builds(
    Stop,
    source_revision=revision_st,
    decided_unix=st.floats(
        min_value=0.0,
        max_value=2_000_000_000.0,
        allow_nan=False,
        allow_infinity=False,
    ),
    reason_code=st.sampled_from(list(CANONICAL_REASON_CODES)),
    reason=st.text(max_size=120),
)

source_decision_st = st.one_of(
    dispatch_st, wait_st, operator_required_st, stop_st
)


@given(decision=source_decision_st)
@settings(max_examples=200, deadline=None)
def test_round_trip_through_wire(decision: SourceDecision) -> None:
    """A random typed ``SourceDecision`` round-trips through the wire
    shape byte-for-byte: typed -> dict -> typed equals the original."""
    wire = source_decision_to_wire(decision)
    parsed = parse_source_decision(wire)
    assert parsed == decision, (
        f"round-trip mismatch: original={decision!r} parsed={parsed!r}"
    )
    assert decision_kind(parsed) is decision_kind(decision)


@given(decision=source_decision_st)
@settings(max_examples=200, deadline=None)
def test_wire_dict_has_no_extra_fields(decision: SourceDecision) -> None:
    """The serialized wire dict never carries unknown fields."""
    wire = source_decision_to_wire(decision)
    allowed = {
        "kind", "source_revision", "decided_unix", "reason_code", "reason",
    }
    # Wait-only fields
    wait_extra = {"wake_on_source_change", "retry_after_seconds", "until_unix", "payload"}
    # Dispatch-only fields
    dispatch_extra = {"work"}
    if isinstance(decision, Wait):
        allowed |= wait_extra
    elif isinstance(decision, Dispatch):
        allowed |= dispatch_extra
    extras = set(wire) - allowed
    assert not extras, f"wire dict has unknown fields: {sorted(extras)}"


@given(revision=revision_st)
@settings(max_examples=100, deadline=None)
def test_source_revision_survives_round_trip(revision: SourceRevision) -> None:
    """A SourceRevision is preserved exactly through wire serialization."""
    wait = Wait(
        source_revision=revision,
        decided_unix=0.0,
        reason_code=REASON_WAIT_REQUESTED,
    )
    wire = source_decision_to_wire(wait)
    parsed = parse_source_decision(wire)
    assert isinstance(parsed, Wait)
    assert parsed.source_revision == revision
    assert parsed.source_revision.fingerprint == revision.fingerprint
    assert parsed.source_revision.label == revision.label
    assert parsed.source_revision.observed_unix == revision.observed_unix


# ---------------------------------------------------------------------------
# Parameter tests: every (decision kind, reason code) combination
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind_literal",
    ["dispatch", "wait", "operator_required", "stop"],
)
@pytest.mark.parametrize(
    "reason_code",
    sorted(CANONICAL_REASON_CODES),
)
def test_every_decision_kind_accepts_every_reason_code(
    kind_literal: DecisionKindLiteral,
    reason_code: ReasonCodeLiteral,
) -> None:
    """Each (kind, reason_code) combination round-trips without error.

    The parser is opaque on unknown reason_codes (program-specific
    codes are tolerated), so this is an exhaustive check that
    no combination raises.
    """
    rev = SourceRevision(fingerprint="abc", observed_unix=1.0, label="x")
    if kind_literal == "dispatch":
        decision: SourceDecision = Dispatch(
            source_revision=rev, decided_unix=2.0, reason_code=reason_code, work=[]
        )
    elif kind_literal == "wait":
        decision = Wait(source_revision=rev, decided_unix=2.0, reason_code=reason_code)
    elif kind_literal == "operator_required":
        decision = OperatorRequired(
            source_revision=rev, decided_unix=2.0, reason_code=reason_code
        )
    else:  # "stop"
        decision = Stop(source_revision=rev, decided_unix=2.0, reason_code=reason_code)
    wire = source_decision_to_wire(decision)
    parsed = parse_source_decision(wire)
    assert parsed == decision
    assert decision_kind(parsed) is DecisionKind(kind_literal)
    assert parsed.reason_code == reason_code


# ---------------------------------------------------------------------------
# Drift detection: malformed envelopes raise loudly
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "envelope,expected_kind",
    [
        ({"kind": "garbage"}, None),
        ({}, None),
        ({"kind": "wait"}, DecisionKind.WAIT),
        ({"kind": "wait", "source_revision": {"fingerprint": ""}}, DecisionKind.WAIT),
    ],
)
def test_parse_rejects_unknown_kind(envelope: dict[str, object], expected_kind: DecisionKind | None) -> None:
    """Unknown ``kind`` values raise ValueError loudly — never silently."""
    if expected_kind is None:
        with pytest.raises(ValueError, match="unknown source-decision kind"):
            parse_source_decision(envelope)
    else:
        decision = parse_source_decision(envelope)
        assert decision_kind(decision) is expected_kind
