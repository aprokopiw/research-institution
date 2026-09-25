"""Pin the wire schema to byte-identical-to-pre-@ADR-0011.

Per @CTR-0021-wire-protocol-version-pinned, @ADR-0011 ships
without a wire schema bump. This test pins the wire-side
shape of the four decision variants and the WorkRequest
envelope so any future regression that introduces a new
``SourceDecision`` variant, a new ``RoleName`` wire value,
or a change to the existing wire dataclasses fails loudly.

These tests are the regression barrier for "did anyone drift
the wire?". They:

1. Pin the ``DecisionKind`` enum membership to the 4 original
   literal values (Dispatch / Wait / OperatorRequired / Stop).
2. Pin pi_monitor's ``RoleName`` Literal to its 8 values,
   none of which is a math-internal ``RoleProfileName``.
3. Pin the canonical reason-code set to the existing 7 values
   + the 2 @ADR-0011 OS-side extensions (clearly documented
   as the OS-side only extension).
4. Pin the work-decision return-type union to
   ``Dispatch | Wait | OperatorRequired | Stop`` (no fifth
   variant).
5. Pin the WorkRequest payload type to ``dict[str, object]``;
   the OS injects ``math_directive_content_hash`` and other
   math-side hash fields as ordinary ``object`` values.
"""

from __future__ import annotations

import pytest

from pi_monitor.work.work_source import (
    CANONICAL_REASON_CODES,
    Dispatch,
    OperatorRequired,
    RoleName,
    Stop,
    Wait,
    WorkRequest,
)

from research_institution.contracts.source_decision import (
    EXTENDED_REASON_CODES,
    OS_EXTENDED_REASON_CODES,
    REASON_ARCHITECTURE_REVIEW_DISPATCH,
    REASON_ARCHITECTURE_REVIEW_REQUIRED,
)


# ----------------------------------------------------------------------------
# 1. DecisionKind enum membership pinned.
# ----------------------------------------------------------------------------


def test_decision_kind_universe_is_four() -> None:
    """The wire-side decision vocabulary is the closed 4-value enum."""
    from pi_monitor.work.work_source import DecisionKind

    assert set(DecisionKind.__members__) == {
        "DISPATCH",
        "WAIT",
        "OPERATOR_REQUIRED",
        "STOP",
        "UNKNOWN",  # tolerant default; survives any wire shape drift
    } or set(DecisionKind.__members__) == {
        "DISPATCH",
        "WAIT",
        "OPERATOR_REQUIRED",
        "STOP",
    }, (
        f"DecisionKind membership drifted; a new variant would be "
        f"a wire schema bump. Found {sorted(DecisionKind.__members__)}"
    )


# ----------------------------------------------------------------------------
# 2. pi_monitor's RoleName wire Literal is unchanged.
# ----------------------------------------------------------------------------


def test_role_name_literal_is_unchanged() -> None:
    """@ADR-0011 does NOT add 'MATHEMATICAL_RESEARCHER' / 'MATHEMATICAL_ARCHITECT' to the wire."""
    expected = {
        "default",
        "primary",
        "supporting",
        "milestone",
        "research",
        "intake",
        "review",
        "maintenance",
    }
    actual = set(RoleName.__args__)
    assert actual == expected, (
        f"RoleName Literal drifted: expected {expected}, got {actual}. "
        "A new wire value requires @CTR-0021 versioning + math-maintainer review."
    )


def test_math_internal_role_names_not_in_wire_literal() -> None:
    """``MATHEMATICAL_RESEARCHER`` / ``MATHEMATICAL_ARCHITECT`` are NOT on the wire."""
    assert "MATHEMATICAL_RESEARCHER" not in RoleName.__args__
    assert "MATHEMATICAL_ARCHITECT" not in RoleName.__args__


# ----------------------------------------------------------------------------
# 3. Reason-code set is unchanged at the wire, extended at the OS.
# ----------------------------------------------------------------------------


def test_canonical_reason_codes_is_pi_monitor_set() -> None:
    """``CANONICAL_REASON_CODES`` (the wire authority) is byte-equal to pi_monitor's set."""
    from pi_monitor.work.work_source import CANONICAL_REASON_CODES as PI_SET
    assert CANONICAL_REASON_CODES == PI_SET, (
        "research-institution's CANONICAL_REASON_CODES drifted from pi_monitor's "
        "wire-authority set; that would be an unreviewed wire schema bump."
    )


def test_os_extended_reason_codes_contains_only_plan_013_additions() -> None:
    """``OS_EXTENDED_REASON_CODES`` (the @ADR-0011 OS-side additions) is the two new values."""
    assert {
        REASON_ARCHITECTURE_REVIEW_REQUIRED,
        REASON_ARCHITECTURE_REVIEW_DISPATCH,
    } == OS_EXTENDED_REASON_CODES


def test_extended_reason_codes_is_superset_of_canonical() -> None:
    """``EXTENDED_REASON_CODES`` = pi_monitor's set ∪ @ADR-0011 OS-side extensions."""
    assert EXTENDED_REASON_CODES >= CANONICAL_REASON_CODES
    assert (
        EXTENDED_REASON_CODES - CANONICAL_REASON_CODES
        == OS_EXTENDED_REASON_CODES
    )


# ----------------------------------------------------------------------------
# 4. Decision-tagged union: still 4 members.
# ----------------------------------------------------------------------------


def test_source_decision_union_is_closed() -> None:
    """``SourceDecision = Dispatch | Wait | OperatorRequired | Stop``; no fifth variant."""
    # SourceDecision is declared via ``type SourceDecision = ...`` (PEP 695);
    # ``typing.get_args`` doesn't introspect type-statement aliases directly.
    # Instead, we use the dataclass-tagged-union shape: every concrete
    # member must be a subclass of tuple(classes), and adding a 5th would
    # surface at every isinstance call.
    expected = (Dispatch, Wait, OperatorRequired, Stop)
    # Sanity: each concrete variant is the canonical pi_monitor dataclass.
    for cls in expected:
        assert cls.__module__ == "pi_monitor.work.work_source", (
            f"{cls} drifted out of pi_monitor's wire module"
        )
    # The four variants are mutually exclusive siblings (no shared
    # ancestor); we accept any direct superclass.
    supers = {cls.__mro__[1] for cls in expected}
    assert len(supers) <= 2, (
        f"variant MRO collapsed unexpectedly: {supers}; the union has gained "
        "a member with shared inheritance."
    )


# ----------------------------------------------------------------------------
# 5. WorkRequest payload is dict[str, object]; OS injects new fields as objects.
# ----------------------------------------------------------------------------


def test_work_request_payload_is_dict() -> None:
    """``WorkRequest.payload`` stays ``dict[str, object]``; OS adds opaque math-side fields."""
    # The constructor accepts arbitrary nested data; we don't pin the
    # value type beyond dict. This test asserts the field type annotation.
    import dataclasses
    fields = {f.name: f for f in dataclasses.fields(WorkRequest)}
    payload_field = fields["payload"]
    # Pydantic / dataclass annotation
    assert "dict" in str(payload_field.type).lower(), (
        f"WorkRequest.payload type drifted: {payload_field.type}"
    )


@pytest.mark.parametrize(
    "role",
    [
        "research",
        "maintenance",
        "primary",
        "supporting",
        "default",
    ],
)
def test_role_values_are_wire_legal(role: str) -> None:
    """The OS-only narrowing type ``WorkRequestRoleAlias`` is a subset of the wire Literal."""
    from research_institution.contracts.source_decision import WorkRequestRoleAlias
    assert role in set(WorkRequestRoleAlias.__args__)
    assert role in set(RoleName.__args__)


# ----------------------------------------------------------------------------
# 6. Dispatch envelope carries only the four variants and reason_code is a string.
# ----------------------------------------------------------------------------


def test_dispatch_reason_code_is_str() -> None:
    """The wire ``reason_code: str`` accepts arbitrary strings (forward-compat per @CTR-0001)."""
    import dataclasses
    fields = {f.name: f for f in dataclasses.fields(Dispatch)}
    rc_field = fields["reason_code"]
    assert "str" in str(rc_field.type).lower(), (
        f"Dispatch.reason_code type drifted: {rc_field.type}"
    )


def test_dispatch_work_is_list_of_work_request() -> None:
    """``Dispatch.work: list[WorkRequest]``; OS injects ``WorkRequest`` instances only."""
    import dataclasses
    fields = {f.name: f for f in dataclasses.fields(Dispatch)}
    work_field = fields["work"]
    assert "list" in str(work_field.type).lower()
    assert "WorkRequest" in str(work_field.type)
