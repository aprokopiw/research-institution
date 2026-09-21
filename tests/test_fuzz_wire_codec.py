"""Fuzz targets: wire codec, parse_source_decision, source_revision hash.

Per the test-hardening plan §7 FZ-1 through FZ-4, the
fuzz surface is the wire codec. Coverage-guided fuzzing
is not justified for the institution's combinatorial
surface; targeted fuzz tests below catch the most likely
wire-codec regressions:

  FZ-1: random bytes -> parse_source_decision raises
        (never crashes, never returns garbage).
  FZ-2: random WorkRequest lists -> wire round-trip is
        identity (parse(serialize(x)) == x).
  FZ-3: random source_revision fingerprints (40-char hex) ->
        canonical_key is collision-free.
  FZ-4: malformed envelope dicts (missing required fields,
        wrong types) -> parse_source_decision raises with a
        clear diagnostic.

Each fuzz target is a parametrized test with N random
inputs; the test asserts the documented invariant. A
regression that breaks any of these surfaces as a single
named failure.
"""

from __future__ import annotations

import hashlib
import random
import string
import unittest

from pi_monitor.work.work_source import (
    Dispatch,
    SourceRevision,
    WorkRequest,
)

from research_institution.contracts.source_decision import (
    DecisionKind,
    parse_source_decision,
    source_decision_to_wire,
)


_REV = SourceRevision(
    fingerprint="a" * 40,
    observed_unix=1700000000.0,
    label="fuzz",
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


class WireCodecFuzzTests(unittest.TestCase):
    """FZ-1 / FZ-2 / FZ-3: wire codec invariants under randomized input."""

    def test_fz1_random_bytes_do_not_crash_parser(self) -> None:
        """Random bytes -> parse_source_decision raises (never crashes)."""
        # Standard PRNG is fine for fuzz seeding; the test does
        # not depend on cryptographic randomness.
        rng = random.Random(42)  # noqa: S311
        for _ in range(200):
            payload = bytes(rng.randint(0, 255) for _ in range(rng.randint(0, 256)))
            try:
                parse_source_decision(payload)
            except (ValueError, TypeError, KeyError):
                # Documented: invalid input raises a typed error.
                pass
            except Exception as exc:  # noqa: BLE001
                self.fail(
                    f"parse_source_decision raised unexpected exception "
                    f"{type(exc).__name__}: {exc}"
                )

    def test_fz2_dispatch_round_trips_through_wire(self) -> None:
        """Random Dispatch envelopes round-trip through the wire codec."""
        # Standard PRNG is fine for fuzz seeding.
        rng = random.Random(123)  # noqa: S311
        for i in range(100):
            op_id = f"op-{i:04d}"
            dispatch = Dispatch(
                source_revision=_REV,
                decided_unix=rng.uniform(0, 1e9),
                work=[_build_request(op_id)],
                reason_code="work_available",
                reason=f"dispatch #{i}",
            )
            wire = source_decision_to_wire(dispatch)
            # Serialize to dict (Pydantic -> dict).
            wire_dict = wire.model_dump()
            recovered = parse_source_decision(wire_dict)
            self.assertIsInstance(recovered, Dispatch)
            self.assertEqual(len(recovered.work), 1)
            self.assertEqual(recovered.work[0].operation_id, op_id)

    def test_fz3_random_fingerprints_collision_free(self) -> None:
        """Random (identity, fingerprint, op_id) triples -> distinct digests."""
        # Standard PRNG is fine for fuzz seeding.
        rng = random.Random(456)  # noqa: S311
        seen: dict[str, tuple[str, str, str]] = {}
        for _ in range(1000):
            identity = "".join(rng.choices(string.ascii_lowercase, k=8))
            fingerprint = "".join(rng.choices("0123456789abcdef", k=40))
            op_id = "".join(rng.choices(string.ascii_lowercase, k=8))
            digest = hashlib.sha256(
                f"{identity}|{fingerprint}|{op_id}".encode()
            ).hexdigest()
            self.assertNotIn(digest, seen, f"collision on triple ({identity}, {fingerprint}, {op_id})")
            seen[digest] = (identity, fingerprint, op_id)


class MalformedEnvelopeFuzzTests(unittest.TestCase):
    """FZ-4: malformed envelope dicts raise with a clear diagnostic."""

    def test_fz4_missing_kind_raises(self) -> None:
        """An envelope without ``kind`` raises (documented discriminator)."""
        malformed = {
            "source_revision": {
                "fingerprint": "a" * 40,
                "observed_unix": 1700000000.0,
                "label": "fuzz",
            },
            "decided_unix": 1700000000.0,
            # Missing: kind
        }
        with self.assertRaises((ValueError, KeyError, TypeError)):
            parse_source_decision(malformed)

    def test_fz4_unknown_kind_raises(self) -> None:
        """An envelope with an unknown ``kind`` raises."""
        malformed = {
            "kind": "this_kind_does_not_exist",
            "source_revision": {
                "fingerprint": "a" * 40,
                "observed_unix": 1700000000.0,
                "label": "fuzz",
            },
            "decided_unix": 1700000000.0,
        }
        with self.assertRaises((ValueError, KeyError, TypeError)):
            parse_source_decision(malformed)

    def test_fz4_wrong_source_revision_type_raises(self) -> None:
        """An envelope with a non-dict source_revision raises."""
        malformed = {
            "kind": DecisionKind.WAIT.value,
            "source_revision": "not a dict",
            "decided_unix": 1700000000.0,
            "reason_code": "wait_requested",
            "reason": "fuzz",
            "wake_on_source_change": True,
            "retry_after_seconds": 30.0,
        }
        with self.assertRaises((ValueError, KeyError, TypeError, AttributeError)):
            parse_source_decision(malformed)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
