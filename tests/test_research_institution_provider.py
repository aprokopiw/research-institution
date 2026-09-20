"""Tests for ``research_institution.providers.research_institution_provider``.

Per @ADR-0007, research-institution owns the WorkSourceProvider slot
in mathlint. This file pins the OS-level work-decision contract.

Contract: @CTR-0094 (work-source-provider dispatch envelope).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from pi_monitor.work_source import (
    Dispatch,
    OperatorRequired,
    SourceRevision,
    Stop,
    Wait,
)

from research_institution.providers.research_institution_provider import (
    register,
    select_next_work_for_supervisor,
)

# Vocabulary pinned by @CTR-0094. The runtime Literal is enforced by
# the consumer (mathlint's real_source.configured_provider); we pin
# it here so a regression that widens the vocabulary surfaces loudly.
_DISPATCH_KINDS = frozenset({"Dispatch", "Wait", "OperatorRequired", "Stop"})


def test_register_populates_work_source_provider_slot() -> None:
    """`register()` MUST populate the `work_source_provider` slot.

    Defect class: a regression that drops the slot population
    returns the system to the pre-ADR-0007 broken state. The
    operator sees SOURCE_NO_PROVIDER at runtime.
    """
    register()
    from mathlint.program_providers import work_source_provider_slot

    slot = work_source_provider_slot()
    assert slot is not None, (
        "register() didn't populate work_source_provider_slot. "
        "@ADR-0007 requires research-institution to own this slot."
    )
    assert callable(slot), (
        f"work_source_provider_slot is {type(slot).__name__}; expected callable"
    )


def test_register_is_idempotent() -> None:
    """Calling ``register()`` twice MUST NOT raise; the second call
    simply overwrites the slot with the same callable."""
    register()
    register()  # second call: must be safe
    from mathlint.program_providers import work_source_provider_slot

    assert work_source_provider_slot() is not None


def test_select_next_work_returns_dispatch_envelope(tmp_path: Path) -> None:
    """``select_next_work_for_supervisor(repository)`` MUST return a
    typed envelope that satisfies @CTR-0094's contract: one of the
    four dispatch kinds, with a typed ``source_revision`` carrying
    a fingerprint, observed_unix, and label.
    """
    envelope = select_next_work_for_supervisor(tmp_path)
    assert isinstance(
        envelope, (Dispatch, Wait, OperatorRequired, Stop)
    ), f"envelope is {type(envelope).__name__}; expected a typed dispatch envelope"
    assert isinstance(envelope.source_revision, SourceRevision)
    assert isinstance(envelope.source_revision.fingerprint, str)
    assert len(envelope.source_revision.fingerprint) == 40, (
        f"source_revision.fingerprint must be a 40-char git SHA; got "
        f"len={len(envelope.source_revision.fingerprint)}"
    )
    assert isinstance(envelope.source_revision.observed_unix, (int, float))
    assert isinstance(envelope.source_revision.label, str)


def test_select_next_work_handles_non_git_repository(tmp_path: Path) -> None:
    """When ``repository`` is not a git checkout, the provider MUST
    still return a valid envelope (the ``fingerprint`` falls back to
    zeros rather than the function raising).

    Defect class: a regression that raises on a non-git dir would
    crash the supervisor at first decide frame on every fresh
    clone.
    """
    # tmp_path is not a git repo; select_next_work should still succeed.
    envelope = select_next_work_for_supervisor(tmp_path)
    assert isinstance(envelope, (Dispatch, Wait, OperatorRequired, Stop))
    # The fingerprint is either zeros (fallback) or a real git SHA.
    assert envelope.source_revision.fingerprint is not None


def test_select_next_work_returns_wait_when_no_roadmap_reader() -> None:
    """Today (2026-09-20) the OS has no roadmap reader, so the
    envelope MUST be a structured ``Wait`` with an actionable
    diagnostic, NOT a ``Dispatch`` with empty work.

    Defect class: a regression that returns ``Dispatch`` with
    ``work=[]`` would silently park the supervisor with no
    progress signal; the operator wouldn't know whether to fix
    the OS plugin or the program content.
    """
    envelope = select_next_work_for_supervisor(Path("/tmp"))  # noqa: S108
    assert isinstance(envelope, Wait), (
        f"expected a Wait envelope until a roadmap reader ships; got "
        f"{type(envelope).__name__}. A regression here either: (a) returns "
        f"Dispatch with no work, which silently parks the supervisor, or "
        f"(b) returns Dispatch with empty work, which produces false "
        f"progress signals."
    )


def test_select_next_work_resolves_catalog_program_name(tmp_path: Path) -> None:
    """When the repository matches a catalog entry, the label MUST
    include the program name (so dashboards can group envelopes by
    program).
    """
    # Resolve the catalog and pick a real local_path from it.
    catalog_path = Path(__file__).resolve().parents[1] / "catalog" / "programs.toml"
    if not catalog_path.is_file():
        pytest.skip(f"catalog not reachable at {catalog_path}")

    try:
        data = tomllib.loads(catalog_path.read_text(encoding="utf-8"))
        programs = data.get("programs", [])
    except (OSError, tomllib.TOMLDecodeError):
        pytest.skip("catalog unreadable")

    if not programs:
        pytest.skip("catalog has no entries")

    local_path_raw = programs[0]["local_path"]
    # $HOME-expand to match resolved_local_path behavior.
    repo = Path(local_path_raw.replace("$HOME", str(Path.home())))
    if not repo.is_dir():
        pytest.skip(f"catalog local_path {repo} not on this machine")

    envelope = select_next_work_for_supervisor(repo)
    label = envelope.source_revision.label
    expected_program_name = programs[0]["name"]
    assert expected_program_name in label, (
        f"label {label!r} should mention the catalog program name "
        f"{expected_program_name!r} so dashboards can group envelopes"
    )


def test_select_next_work_does_not_import_kaplansky_directly() -> None:
    """The OS provider MUST NOT import any program-named module.

    Per @ADR-0014 (mathlint) + @ADR-0007 (research-institution),
    the OS layer must stay program-agnostic. A regression that
    imports ``kaplansky.*`` here would couple the OS to one
    program.

    We check ``ast`` imports rather than a substring search because
    the OS legitimately references the program's TOML filename
    (``kaplansky-roadmap.toml``) and can mention program names in
    docstrings when explaining what the OS reads.
    """
    import ast
    import inspect

    source = inspect.getsource(select_next_work_for_supervisor)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("kaplansky"), (
                    f"select_next_work_for_supervisor imports {alias.name!r}; "
                    f"OS-level provider must stay program-agnostic per @ADR-0014"
                )
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("kaplansky"), (
                f"select_next_work_for_supervisor imports from {node.module!r}; "
                f"OS-level provider must stay program-agnostic per @ADR-0014"
            )


def test_select_next_work_label_is_unique_per_invocation(tmp_path: Path) -> None:
    """Two consecutive calls MUST produce distinct labels (so the
    supervisor can tell apart envelopes in its event log).
    """
    import time as _time

    envelope1 = select_next_work_for_supervisor(tmp_path)
    # Sleep 1 second so the integer-second timestamp differs.
    _time.sleep(1.0)
    envelope2 = select_next_work_for_supervisor(tmp_path)
    assert (
        envelope1.source_revision.label
        != envelope2.source_revision.label
    ), (
        f"Two consecutive envelopes produced the same label; "
        f"label1={envelope1.source_revision.label!r}, "
        f"label2={envelope2.source_revision.label!r}. The "
        f"label includes a tick counter that must advance."
    )


# ---------------------------------------------------------------------------
# Dispatch-path tests (require a roadmap with active items).
#
# These tests build a real kaplansky-style roadmap in tmp_path and
# verify that ``select_next_work_for_supervisor`` delegates to
# ``kaplansky.work_selection.next_active_work`` correctly:
#
#   - missing roadmap → ``Wait`` with ``reason_code=wait_requested``
#   - roadmap with zero active items → ``Wait`` with
#     ``reason_code=no_eligible_work`` and ``wake_on_source_change``
#   - roadmap with one active item → ``Dispatch`` carrying one
#     ``WorkRequest`` whose ``operation_id`` is the item id
# ---------------------------------------------------------------------------


_ACTIVE_ITEM_ROADMAP = """
schema = 1
id = "kaplansky"
title = "Kaplansky"
north_star = "n/a"
roadmap_version = 1
current_phase = "p9"

[[items]]
id = "P9.1"
title = "Extract the alternating square"
phase = "p9"
type = "structural-interface-test"
priority = "critical"
status = "active"
role = "mathematical-research"
rationale = "minimal witness must be balance-closed"
exact_target = "kaplansky.minimal-rigidity-overlap-alternating-square"
next_action = "Extract the alternating square from a minimal rigidity overlap."
done_when = ["overlap-witness is balance-closed"]
do_not_conclude = ["no positive assertion without a witness"]
allowed_files = ["src/kaplansky/collision.py"]
success_criteria = ["rank-additive extraction passes falsification"]
verification_requirements = ["model-audited"]
"""


def _write_roadmap(repo: Path, body: str) -> Path:
    programs_dir = repo / "programs"
    programs_dir.mkdir(parents=True, exist_ok=True)
    path = programs_dir / "kaplansky-roadmap.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_dispatch_when_roadmap_has_active_item(tmp_path: Path) -> None:
    """Happy path: the proof program has an active item → Dispatch envelope."""
    pytest.importorskip("kaplansky")  # Skip if kaplansky is not installed
    _write_roadmap(tmp_path, _ACTIVE_ITEM_ROADMAP)

    envelope = select_next_work_for_supervisor(tmp_path)

    assert isinstance(envelope, Dispatch), (
        f"expected Dispatch, got {type(envelope).__name__}: {envelope!r}"
    )
    assert envelope.reason_code == "work_available"
    assert len(envelope.work) == 1
    req = envelope.work[0]
    assert req.operation_id == "P9.1"
    assert req.source_identity == "kaplansky-research-program"
    assert req.operation_kind == "mathlint-research"
    assert req.payload["next_action"].startswith("Extract the alternating square")
    assert req.payload["rationale"] == "minimal witness must be balance-closed"


def test_wait_when_roadmap_has_no_active_item(tmp_path: Path) -> None:
    """No active items → Wait with ``reason_code=no_eligible_work``."""
    pytest.importorskip("kaplansky")
    _write_roadmap(
        tmp_path,
        """
        schema = 1
        id = "kaplansky"
        title = "Kaplansky"
        north_star = "n/a"
        roadmap_version = 1
        current_phase = "p9"

        [[items]]
        id = "P0.1"
        title = "done"
        phase = "p0"
        type = "infrastructure"
        priority = "critical"
        status = "promoted"
        role = "completed"
        rationale = "already done"
        exact_target = "x"
        """,
    )

    envelope = select_next_work_for_supervisor(tmp_path)

    assert isinstance(envelope, Wait)
    assert envelope.reason_code == "no_eligible_work"
    assert envelope.wake_on_source_change is True
    assert envelope.retry_after_seconds == 60.0


def test_wait_when_roadmap_missing(tmp_path: Path) -> None:
    """No roadmap.toml → Wait with ``reason_code=wait_requested``."""
    pytest.importorskip("kaplansky")

    envelope = select_next_work_for_supervisor(tmp_path)

    assert isinstance(envelope, Wait)
    assert envelope.reason_code == "wait_requested"
    assert envelope.wake_on_source_change is True


def test_dispatch_idempotency_key_is_stable(tmp_path: Path) -> None:
    """Two consecutive calls with the same active item MUST produce
    the same idempotency key so the supervisor can dedupe retries.
    """
    pytest.importorskip("kaplansky")
    _write_roadmap(tmp_path, _ACTIVE_ITEM_ROADMAP)

    envelope1 = select_next_work_for_supervisor(tmp_path)
    envelope2 = select_next_work_for_supervisor(tmp_path)

    assert isinstance(envelope1, Dispatch)
    assert isinstance(envelope2, Dispatch)
    # Fingerprint can differ if a git HEAD advances between calls
    # (it doesn't in tmp_path); the operation_id is the stable part.
    assert envelope1.work[0].operation_id == envelope2.work[0].operation_id
    assert envelope1.work[0].idempotency_key[2] == envelope2.work[0].idempotency_key[2]
