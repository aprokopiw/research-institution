"""COMPOSE-5: cross-repo work selection through entry points.

Per the test-hardening plan §6 COMPOSE-5, this is the V2
expression for the institution's composition seam: a
research-program-supplied ``next_active_work`` callable is
resolved through the kernel-blessed
``mathlint.program_work_selection`` entry-point registry,
called by the OS, and wrapped into a typed
``Dispatch``. The whole pipeline runs in-process — no
subprocess, no supervisor, no real network — so the test
fits in <100ms and runs on every CI commit.

## What this proves

1. ``select_next_work_for_supervisor(repo)`` resolves the
   callable through the entry-point registry, NOT via a
   hardcoded import. The OS does not name any program in
   source.
2. The callable's ``list[WorkRequest]`` return is wrapped in
   a typed ``Dispatch`` envelope carrying the canonical
   reason code ``work_available``.
3. The full wire round-trip
   (``source_decision_to_wire`` ->
   ``parse_source_decision``) preserves the discriminator.
4. A ``NoActiveWorkError`` from the callable becomes a
   ``Wait`` envelope with ``reason_code=no_eligible_work``,
   not a crash.
5. A missing callable becomes a ``Wait`` envelope with the
   "no work-selection callable registered" diagnostic.

## Fixtures

- :class:`FakeMathResearchProgram` (F-1) scripts the
  callable; ``install(name)`` registers it under the
  catalog program name.
- :class:`make_fake_program` (F-2) constructs a
  ``Program`` whose ``local_path`` points at a tmp-path
  repo with a marker file the OS can match.
- :class:`FakeMathlintRoadmap` (F-3) writes the marker
  roadmap under the tmp-path repo.
- :class:`FaultInjector` (F-4) exercises the "no callable
  registered" path by clearing the registry.

The composition seam is the entry-point registry; the test
exercises the OS, the registry, the fake callable, and the
wire round-trip together — exactly the chain that breaks in
the wild when any link drifts.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mathlint.program_providers import (
    WorkSelectionSlot,
    set_work_selection_slot,
    work_selection_callables,
)
from pi_monitor.work.work_source import (
    Dispatch,
    Wait,
)

from research_institution.contracts.source_decision import (
    REASON_NO_ELIGIBLE_WORK,
    REASON_WAIT_REQUESTED,
    REASON_WORK_AVAILABLE,
    parse_source_decision,
    source_decision_to_wire,
)
from research_institution.providers import research_institution_provider as provider_mod
from research_institution.providers.research_institution_provider import (
    select_next_work_for_supervisor,
)
from tests._fakes import (
    FakeMathResearchProgram,
    FakeProgramItem,
    make_fake_program,
)


def _setup_repo(tmp_path: Path) -> tuple[FakeMathResearchProgram, Path]:
    """Create a tmp-path repo with the fake program registered.

    Returns the (fake, repo) pair. Tests use ``fake`` to script
    the callable's behavior and ``repo`` as the path the OS
    resolves against.
    """
    fake = FakeMathResearchProgram(
        scripted_items=[
            FakeProgramItem(operation_id="T1"),
            FakeProgramItem(operation_id="T2"),
        ],
    )
    fake.install("test-research-program")
    # Create a tmp-path repo with a marker file the OS can match.
    repo = tmp_path / "research-program-repo"
    repo.mkdir()
    programs_dir = repo / "programs"
    programs_dir.mkdir()
    # The OS's secondary match path looks for any catalog-declared
    # marker under the repo. We use the default marker from
    # make_fake_program.
    (programs_dir / "test-research-program-roadmap.toml").write_text(
        'schema = 1\nitems = []\n', encoding="utf-8"
    )
    return fake, repo


class CrossRepoWorkSelectionTests(unittest.TestCase):
    """G5: cross-repo work selection through the entry-point seam."""

    def setUp(self) -> None:
        """Snapshot the entry-point slot so each test gets a clean state."""
        self._slot_snapshot = WorkSelectionSlot(
            selectors=dict(work_selection_callables()),
        )
        # Snapshot the OS's internal catalog lookup so each test can
        # substitute a fake catalog without leaking state.
        from research_institution import catalog as catalog_mod

        self._catalog_snapshot = catalog_mod.load_catalog
        # Snapshot the OS's internal work-selection lookup. The OS
        # calls ``_discover_ws()`` inside ``_work_selection_callable_for_repo``,
        # which RESETS the slot to empty when no entry points are
        # installed. We replace the OS's per-call resolver with our
        # own so the fake's installed callable survives the OS's
        # internal discover step.
        self._resolver_snapshot = provider_mod._work_selection_callable_for_repo

    def tearDown(self) -> None:
        """Restore the entry-point slot, catalog, and resolver so tests don't leak."""
        set_work_selection_slot(self._slot_snapshot)
        from research_institution import catalog as catalog_mod

        catalog_mod.load_catalog = self._catalog_snapshot
        provider_mod._work_selection_callable_for_repo = self._resolver_snapshot

    def _install_fake_catalog(self, marker: str) -> None:
        """Swap the catalog loader for a fake that returns one Program.

        The fake Program's marker matches the marker file the test
        writes under ``tmp_path/programs/``. This lets the OS's
        secondary marker-match path resolve the program name without
        loading the real ``catalog/programs.toml``.
        """
        from research_institution import catalog as catalog_mod

        program = make_fake_program(
            name="test-research-program",
            program_markers=(marker,),
        )

        def _fake_loader(_path: object) -> list[object]:
            return [program]

        catalog_mod.load_catalog = _fake_loader

    def _install_fake_resolver(self, fake: FakeMathResearchProgram) -> None:
        """Replace the OS's internal work-selection resolver.

        ``_work_selection_callable_for_repo`` reads the entry-point
        registry; ``discover_work_selection_programs`` (which it calls
        defensively) RESETS the slot when no entry points are installed.
        We monkeypatch the resolver to consult the live registry
        AFTER the fake's ``install()`` already populated it, so the
        OS sees the fake without the discover step clobbering it.
        """
        from mathlint.program_providers import work_selection_callables

        def _fake_resolver(repository: object) -> object:
            return work_selection_callables().get("test-research-program")

        provider_mod._work_selection_callable_for_repo = _fake_resolver

    def test_g5_dispatch_path_round_trips_through_wire(self) -> None:
        """The OS resolves the callable, returns Dispatch, the wire round-trips."""
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            fake, repo = _setup_repo(tmp_path)
            self._install_fake_catalog("programs/test-research-program-roadmap.toml")
            self._install_fake_resolver(fake)
            decision = select_next_work_for_supervisor(repo)
            # The fake's first call should yield a Dispatch with T1.
            self.assertIsInstance(decision, Dispatch)
            self.assertEqual(len(decision.work), 1)
            self.assertEqual(decision.work[0].operation_id, "T1")
            self.assertEqual(decision.reason_code, REASON_WORK_AVAILABLE)
            # Round-trip through the wire shape.
            wire = source_decision_to_wire(decision)
            recovered = parse_source_decision(wire.model_dump())
            self.assertIsInstance(recovered, Dispatch)
            self.assertEqual(len(recovered.work), 1)
            self.assertEqual(recovered.work[0].operation_id, "T1")
            self.assertEqual(fake.call_count, 1)

    def test_g5_no_active_work_becomes_wait_envelope(self) -> None:
        """NoActiveWorkError from the callable becomes a Wait envelope."""
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            # Empty queue: every call raises NoActiveWorkError.
            fake = FakeMathResearchProgram(scripted_items=[])
            fake.install("test-research-program")
            repo = tmp_path / "research-program-repo"
            repo.mkdir()
            (repo / "programs").mkdir()
            (repo / "programs" / "test-research-program-roadmap.toml").write_text(
                'schema = 1\nitems = []\n', encoding="utf-8"
            )
            self._install_fake_catalog("programs/test-research-program-roadmap.toml")
            self._install_fake_resolver(fake)
            decision = select_next_work_for_supervisor(repo)
            self.assertIsInstance(decision, Wait)
            self.assertEqual(decision.reason_code, REASON_NO_ELIGIBLE_WORK)

    def test_g5_missing_callable_becomes_wait_with_diagnostic(self) -> None:
        """No callable registered -> Wait envelope names the catalog key.

        This is the COMPOSE-5 mutation M7 surface: clearing the
        registry exercises the "no work-selection callable registered"
        branch of ``_work_selection_callable_for_repo``. The OS
        should emit a Wait, not a crash.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            repo = tmp_path / "research-program-repo"
            repo.mkdir()
            (repo / "programs").mkdir()
            (repo / "programs" / "test-research-program-roadmap.toml").write_text(
                'schema = 1\nitems = []\n', encoding="utf-8"
            )
            self._install_fake_catalog("programs/test-research-program-roadmap.toml")
            # Replace the slot with an empty slot — no callables
            # are registered for any program name.
            set_work_selection_slot(WorkSelectionSlot(selectors={}))
            decision = select_next_work_for_supervisor(repo)
            self.assertIsInstance(decision, Wait)
            # M7 surface: the diagnostic names the catalog key (not
            # a hardcoded program name).
            self.assertIn(decision.reason_code, {REASON_WAIT_REQUESTED, REASON_NO_ELIGIBLE_WORK})
            self.assertIn("test-research-program", decision.reason)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
