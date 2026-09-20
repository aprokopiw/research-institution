"""Tests for ``research_institution.providers.research_institution_provider``.

Per @ADR-0007, research-institution owns the WorkSourceProvider slot
in mathlint. This file pins the OS-level work-decision contract.

Contract: @CTR-0094 (work-source-provider dispatch envelope).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from research_institution.providers.research_institution_provider import (
    register,
    select_next_work_for_supervisor,
)

# Vocabulary pinned by @CTR-0094. The runtime Literal is enforced by
# the consumer (mathlint's real_source.configured_provider); we pin
# it here so a regression that widens the vocabulary surfaces loudly.
_DISPATCH_KINDS = frozenset({"Dispatch", "Wait", "OperatorRequired", "Stop"})

_REQUIRED_ENVELOPE_KEYS = frozenset({"kind", "reason", "source_revision", "work"})
_REQUIRED_REVISION_KEYS = frozenset({"fingerprint", "observed_unix", "label"})


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
    dict that satisfies @CTR-0094's envelope contract: the four
    required keys with the correct shapes.
    """
    envelope = select_next_work_for_supervisor(tmp_path)
    assert isinstance(envelope, dict), (
        f"envelope is {type(envelope).__name__}; expected dict per @CTR-0094"
    )
    missing = _REQUIRED_ENVELOPE_KEYS - set(envelope.keys())
    assert not missing, (
        f"envelope missing required keys per @CTR-0094: {sorted(missing)}"
    )
    assert envelope["kind"] in _DISPATCH_KINDS, (
        f"envelope['kind'] = {envelope['kind']!r}; must be one of "
        f"{sorted(_DISPATCH_KINDS)} per @CTR-0094"
    )
    assert isinstance(envelope["reason"], str) and envelope["reason"], (
        f"envelope['reason'] must be a non-empty string; got {envelope['reason']!r}"
    )
    assert isinstance(envelope["work"], list), (
        f"envelope['work'] must be a list per @CTR-0094; got {type(envelope['work']).__name__}"
    )

    # source_revision shape per @CTR-0094.
    revision = envelope["source_revision"]
    assert isinstance(revision, dict), (
        f"source_revision is {type(revision).__name__}; expected dict"
    )
    rev_missing = _REQUIRED_REVISION_KEYS - set(revision.keys())
    assert not rev_missing, (
        f"source_revision missing required keys: {sorted(rev_missing)}"
    )
    assert isinstance(revision["fingerprint"], str)
    assert len(revision["fingerprint"]) == 40, (
        f"source_revision.fingerprint must be a 40-char git SHA; got "
        f"len={len(revision['fingerprint'])}"
    )
    assert isinstance(revision["observed_unix"], (int, float))
    assert isinstance(revision["label"], str)


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
    assert envelope["kind"] in _DISPATCH_KINDS
    # The fingerprint is either zeros (fallback) or a real git SHA.
    assert envelope["source_revision"]["fingerprint"] is not None


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
    assert envelope["kind"] == "Wait", (
        f"expected kind='Wait' until a roadmap reader ships; got {envelope['kind']!r}. "
        f"A regression here either: (a) returns Dispatch with no work, which "
        f"silently parks the supervisor, or (b) returns Dispatch with empty "
        f"work, which produces false progress signals."
    )
    assert envelope["work"] == [], (
        f"Wait envelopes MUST have empty work; got {envelope['work']!r}"
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
    label = envelope["source_revision"]["label"]
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
    """
    import inspect

    source = inspect.getsource(select_next_work_for_supervisor)
    # No direct imports of program packages in the function body.
    for module in ("kaplansky", "math-kaplansky"):
        assert module not in source, (
            f"select_next_work_for_supervisor references {module!r}; "
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
        envelope1["source_revision"]["label"]
        != envelope2["source_revision"]["label"]
    ), (
        f"Two consecutive envelopes produced the same label; "
        f"label1={envelope1['source_revision']['label']!r}, "
        f"label2={envelope2['source_revision']['label']!r}. The "
        f"label includes a tick counter that must advance."
    )
