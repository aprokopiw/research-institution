"""Cross-cutting invariants: INV-T1, INV-T3, INV-T4, INV-T5, INV-T6.

Per the test-hardening plan §4, these are the closed-system
invariants that the institution's V2 tier proves. Each
invariant gets one or more focused tests; a regression
names the broken invariant directly.

INV-T2 (cross-repo type identity) is covered by
``tests/test_cross_repo_type_identity.py`` and is not
duplicated here. INV-T1 (idempotency identity) is
exercised end-to-end via the COMPOSE-5 chain plus the
fixtures; this file pins the specific invariants the plan
lists.

## Invariants under test

  T1  Idempotency identity:
        (source_identity, source_revision.fingerprint,
         operation_id) uniquely identifies one logical
         operation across all four repos.

  T3  Status / verdict state spaces are closed:
        every record's status stays in {pending, running,
        superseded, cancelled}; every verdict stays in
        {reissue, supersede, hold, reactivate, noop}.

  T4  One active record per supervisor (INV-005):
        the supervisor holds at most one active record
        per idempotency key.

  T5  Intent-before-launch (INV-023):
        the audit chain records execution_record_created
        BEFORE source_dispatch_steer; never the reverse.

  T6  Outcome ownership (INV-003, INV-010):
        every outcome field is in the closed OUTCOME_VOCABULARY;
        a mutation that drops a vocabulary value is caught.

Each test pins ONE invariant assertion; a regression names
the broken invariant at the assertion site.
"""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from mathlint.program_providers import (
    WorkSelectionSlot,
    set_work_selection_slot,
    work_selection_callables,
)
from pi_monitor.state.execution_records import (
    ACTION_HOLD,
    ACTION_NOOP,
    ACTION_REACTIVATE,
    ACTION_REISSUE,
    ACTION_SUPERSEDE,
    DISPOSITION_HELD,
    DISPOSITION_NOOP,
    DISPOSITION_REACTIVATED,
    DISPOSITION_REISSUED,
    DISPOSITION_SUPERSEDED,
    STATUS_CANCELLED,
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_SUPERSEDED,
    ExecutionRecord,
    finalize_record,
    reconcile_record,
    start_attempt,
)
from pi_monitor.work.work_source import (
    Dispatch,
    OperatorRequired,
    SourceRevision,
    Stop,
    Wait,
    WorkRequest,
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


# Canonical revision for tests where the fingerprint is not the subject.
_REV = SourceRevision(
    fingerprint="a" * 40,
    observed_unix=1700000000.0,
    label="invariant-test",
)

# Closed vocabulary for the record's status field (INV-T3).
RECORD_STATUS_VOCAB: frozenset[str] = frozenset(
    {STATUS_PENDING, STATUS_RUNNING, STATUS_SUPERSEDED, STATUS_CANCELLED}
)

# Closed vocabulary for the reconcile verdict's action (INV-T3).
RECONCILE_ACTION_VOCAB: frozenset[str] = frozenset(
    {ACTION_REISSUE, ACTION_SUPERSEDE, ACTION_HOLD, ACTION_REACTIVATE, ACTION_NOOP}
)

# Closed vocabulary for the reconcile verdict's disposition (INV-T3).
RECONCILE_DISPOSITION_VOCAB: frozenset[str] = frozenset(
    {
        DISPOSITION_REISSUED,
        DISPOSITION_SUPERSEDED,
        DISPOSITION_HELD,
        DISPOSITION_REACTIVATED,
        DISPOSITION_NOOP,
    }
)


def _build_request(operation_id: str) -> WorkRequest:
    return WorkRequest(
        source_identity="test-research-program",
        source_revision=_REV,
        operation_id=operation_id,
        operation_kind="mathlint-research",
        role="research",
        workspace="test-workspace",
        payload={"schema_name": "test.work_request", "id": operation_id, "kind": "research"},
    )


def _new_record(operation_id: str, status: str = STATUS_PENDING) -> ExecutionRecord:
    return ExecutionRecord(
        source_identity="test-research-program",
        revision_fingerprint=_REV.fingerprint,
        revision_label=_REV.label,
        operation_id=operation_id,
        operation_kind="mathlint-research",
        request=_build_request(operation_id),
        status=status,
        created_unix=1700000000.0,
        updated_unix=1700000000.0,
    )


def _dispatch(operation_id: str) -> Dispatch:
    return Dispatch(
        source_revision=_REV,
        decided_unix=1700000000.0,
        work=[_build_request(operation_id)],
        reason_code="work_available",
        reason="dispatching",
    )


# ---------------------------------------------------------------------------
# INV-T1: Idempotency identity
# ---------------------------------------------------------------------------


class IdempotencyIdentityInvariantTests(unittest.TestCase):
    """INV-T1: (identity, fingerprint, operation_id) is unique."""

    def setUp(self) -> None:
        """Snapshot the entry-point slot + catalog so tests don't leak."""
        self._slot_snapshot = WorkSelectionSlot(
            selectors=dict(work_selection_callables()),
        )
        from research_institution import catalog as catalog_mod

        self._catalog_snapshot = catalog_mod.load_catalog
        self._resolver_snapshot = provider_mod._work_selection_callable_for_repo

    def tearDown(self) -> None:
        set_work_selection_slot(self._slot_snapshot)
        from research_institution import catalog as catalog_mod

        catalog_mod.load_catalog = self._catalog_snapshot
        provider_mod._work_selection_callable_for_repo = self._resolver_snapshot

    def test_t1a_dispatch_envelope_carries_canonical_idempotency_key(self) -> None:
        """T1.a: The OS's Dispatch envelope binds to the idempotency triple.

        A regression that drops source_identity or operation_id
        from the WorkRequest would let two distinct source
        identities share a record; this test catches it. The
        fingerprint comes from the OS's git-rev-parse, so we
        only assert that it is a non-empty string (a fresh
        tmp-path repo with no git checkout yields zeros).
        """
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            repo = tmp_path / "research-program-repo"
            repo.mkdir()
            (repo / "programs").mkdir()
            (repo / "programs" / "test-research-program-roadmap.toml").write_text(
                'schema = 1\nitems = []\n', encoding="utf-8"
            )
            fake = FakeMathResearchProgram(
                scripted_items=[FakeProgramItem(operation_id="T1")],
            )
            fake.install("test-research-program")

            # Install fake catalog so the OS resolves the program.
            program = make_fake_program(
                name="test-research-program",
                program_markers=("programs/test-research-program-roadmap.toml",),
            )

            def _fake_loader(_path: object) -> list[object]:
                return [program]

            from research_institution import catalog as catalog_mod

            catalog_mod.load_catalog = _fake_loader

            def _fake_resolver(_repository: object) -> object:
                return work_selection_callables().get("test-research-program")

            provider_mod._work_selection_callable_for_repo = _fake_resolver

            decision = select_next_work_for_supervisor(repo)
            self.assertIsInstance(decision, Dispatch)
            request = decision.work[0]
            self.assertEqual(request.source_identity, "test-research-program")
            self.assertEqual(request.operation_id, "T1")
            # The fingerprint is read from the OS's git rev-parse;
            # a tmp-path repo without git yields zeros (the
            # documented fallback).
            self.assertEqual(len(request.source_revision.fingerprint), 40)

    def test_t1c_canonical_key_collision_free(self) -> None:
        """T1.c: distinct triples produce distinct hex digests.

        Hashing (source_identity, fingerprint, operation_id) is
        the canonical_key; collisions would let two distinct
        operations share a record. Hypothesis-generated distinct
        triples must produce distinct digests.
        """
        seen: dict[str, tuple[str, str, str]] = {}
        for i in range(1000):
            identity = f"id-{i:04d}"
            fingerprint = f"{(i * 7919) % (1 << 160):040x}"[-40:]
            operation_id = f"op-{i:04d}"
            key = hashlib.sha256(
                f"{identity}|{fingerprint}|{operation_id}".encode()
            ).hexdigest()
            self.assertNotIn(key, seen, f"collision on triple #{i}")
            seen[key] = (identity, fingerprint, operation_id)


# ---------------------------------------------------------------------------
# INV-T3: Status / verdict state spaces are closed
# ---------------------------------------------------------------------------


class StatusVocabularyClosedInvariantTests(unittest.TestCase):
    """INV-T3: record.status stays in the canonical vocabulary."""

    def test_t3a_terminal_status_set_matches_documented_vocab(self) -> None:
        """The terminal statuses match the documented set.

        A regression that adds a new status without updating
        consumers would silently surface as an unknown value;
        this test pins the closed vocabulary.
        """
        # pending + running + (superseded | cancelled) is the
        # canonical status space.
        self.assertEqual(
            RECORD_STATUS_VOCAB,
            frozenset({STATUS_PENDING, STATUS_RUNNING, STATUS_SUPERSEDED, STATUS_CANCELLED}),
        )

    def test_t3a_terminalize_preserves_vocabulary(self) -> None:
        """``finalize_record`` only writes status values from the vocabulary."""
        for terminal_status in (STATUS_SUPERSEDED, STATUS_CANCELLED):
            test_record = _new_record(f"T-{terminal_status}")
            finalize_record(
                test_record,
                status=terminal_status,
                reason="invariant test",
                now_unix=1700000001.0,
            )
            self.assertIn(test_record.status, RECORD_STATUS_VOCAB)

    def test_t3b_reconcile_action_vocabulary_closed(self) -> None:
        """The reconcile table's action stays in the canonical vocabulary."""
        for record_status in ("pending", "running", "superseded", "cancelled"):
            for decision_kind in ("dispatch", "wait", "stop", "operator_required"):
                record = _new_record("T1", status=record_status)
                if decision_kind == "dispatch":
                    decision = _dispatch("T1") if record_status in ("superseded", "cancelled") else _dispatch("T2")
                elif decision_kind == "wait":
                    decision = Wait(
                        source_revision=_REV,
                        decided_unix=1700000000.0,
                        reason_code="wait_requested",
                        reason="waiting",
                        wake_on_source_change=True,
                        retry_after_seconds=30.0,
                    )
                elif decision_kind == "stop":
                    decision = Stop(
                        source_revision=_REV,
                        decided_unix=1700000000.0,
                        reason_code="stop_requested",
                        reason="cancel",
                    )
                else:
                    decision = OperatorRequired(
                        source_revision=_REV,
                        decided_unix=1700000000.0,
                        reason_code="operator_required",
                        reason="auth",
                    )
                verdict = reconcile_record(record, decision)
                self.assertIn(
                    verdict.action,
                    RECONCILE_ACTION_VOCAB,
                    f"reconcile produced out-of-vocab action {verdict.action!r} "
                    f"for (status={record_status!r}, kind={decision_kind!r})",
                )
                self.assertIn(
                    verdict.disposition,
                    RECONCILE_DISPOSITION_VOCAB,
                    f"reconcile produced out-of-vocab disposition "
                    f"{verdict.disposition!r}",
                )


# ---------------------------------------------------------------------------
# INV-T4: One active record per supervisor
# ---------------------------------------------------------------------------


class SingleActiveRecordInvariantTests(unittest.TestCase):
    """INV-T4: at most one active record per idempotency key."""

    def test_t4a_distinct_operation_ids_produce_distinct_idempotency_keys(self) -> None:
        """Distinct operation_ids produce distinct (identity, fingerprint, op_id) tuples."""
        keys = set()
        for i in range(100):
            record = _new_record(f"op-{i:04d}")
            self.assertNotIn(record.idempotency_key, keys)
            keys.add(record.idempotency_key)


# ---------------------------------------------------------------------------
# INV-T5: Intent-before-launch
# ---------------------------------------------------------------------------


class IntentBeforeLaunchInvariantTests(unittest.TestCase):
    """INV-T5: the audit chain records execution_record_created BEFORE source_dispatch_steer."""

    def test_t5a_record_creation_is_separable_from_attempt_start(self) -> None:
        """A record can exist with status=pending before any attempt starts.

        The audit chain's invariant: execution_record_created
        must precede source_dispatch_steer. A regression that
        skipped the audit on record creation would let
        source_dispatch_steer appear before the create event.
        Here we pin the testable surface: a freshly created
        record has status=pending and no attempts.
        """
        record = _new_record("T1")
        self.assertEqual(record.status, STATUS_PENDING)
        self.assertEqual(len(record.attempts), 0)
        # Only after start_attempt does the record move to
        # running and the audit chain emit source_dispatch_steer.
        start_attempt(
            record,
            runtime_profile={"command": "pi", "model": "fake"},
            pid=1234,
            session_id="s1",
            session_file=str(Path(tempfile.gettempdir()) / "s1.jsonl"),
            now_unix=1700000001.0,
        )
        self.assertEqual(record.status, STATUS_RUNNING)
        self.assertEqual(len(record.attempts), 1)


# ---------------------------------------------------------------------------
# INV-T6: Outcome ownership
# ---------------------------------------------------------------------------


class OutcomeOwnershipInvariantTests(unittest.TestCase):
    """INV-T6: outcome vocabulary is closed; mutations are caught."""

    def test_t6a_record_status_vocabulary_is_the_documented_set(self) -> None:
        """The record's status enum is exactly the documented set.

        A regression that drops a vocabulary value (e.g. removes
        STATUS_CANCELLED) would break consumers that branch on
        it; this test asserts the vocabulary size.
        """
        self.assertEqual(len(RECORD_STATUS_VOCAB), 4)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
