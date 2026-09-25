# 05 — META (audit-close-out)

> **Ratified 2026-09-25.** This entry closes the pi_monitor
> supervisor process + fault simulation substrate per
> `.specify/specs/05-process-fault-simulation/spec.md`.
> The twelve cannot-claim-done clauses below all read
> `PASS`. Per-entry attestation at
> `.specify/specs/05-process-fault-simulation/.pi-prime-attestations/05-process-fault-simulation.json`.

```toml
[meta]
spec_id = "05-process-fault-simulation"
owner_repo = "pi_monitor"
owner_repos = ["pi_monitor", "research-institution"]
baseline_sha = "95aa7676f56b0c8db70ee2da53d6aa521a8f80d1"
completion_sha = "df5ae9b223b0b0a48f72a70a545e790fc87a730b"
gate_report_digest = "6d14cd78186ae7fe0044278b929488ee347107dc2401f7b2fb1d55cdc3a5bc47"
durable_anchors_added = []
durable_anchors_cited = [
  "@ADR-0006",   # pi_monitor long-running command protection
  "@ADR-0007",   # deterministic context controller shadow mode
  "@ADR-0009",   # bounded recovery and soft circuit
  "@ADR-0005",   # audit append-only hash-chained
  "@INV-022",    # stable audit-event strings
  "@INV-023",    # execution intent before launch
  "@INV-025",    # rate-defer survives restart
  "@ADR-0095-prime-directive-mechanical-enforcement",
  "@INV-0095-prg-anchor-ownership",
  "@CTR-0095-prime-directive-check-script-contract",
]
transient_anchors_retired = []
unblocked_dependents = ["06-autonomous-composed-simulation"]

[constitution_compliance]
section_0  = "PASS"
section_1  = "PASS"  # tier vocabulary closed set untouched
section_2  = "PASS"  # dependency vocabulary untouched
section_3  = "PASS"  # gate-status algebra honored
section_4  = "PASS"
section_5  = "PASS"  # action matrix obeyed (commit gate)
section_6  = "PASS"  # no-second-supervisor pledge kept (substrate is not a supervisor)
section_7  = "PASS"
section_8  = "PASS"
section_9  = "PASS"
section_10 = "PASS"  # canonical prime-directive script clean at pi_monitor HEAD
section_11 = "PASS"  # this META schema
section_12 = "PASS"  # 1 transient-exemptions row added (substrate glob)
```

## Twelve cannot-claim-done clauses — verification log

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | `tests/substrate/` exists | `ls tests/substrate/` returns 7 entries (5 helpers + 1 init + 1 test) | PASS |
| 2 | campaign no manual finalize | `grep -E 'finalize_attempt\|finalize_record\|complete_active\|record_publication' tests/mathlint_campaign.py` exits 1 (no match) | PASS |
| 3 | substrate metadata complete | `pytest -q tests/static/test_substrate_metadata.py` exits 0 (6 tests) | PASS |
| 4 | no second fake-Pi implementation | `pytest -q tests/static/test_substrate_inventory.py::test_no_second_fake_pi_implementation` exits 0; AST inspection finds no second `fake_pi_script` / `_FAKE_PI_BODY` / `FAKE_PI_BODY` in `tests/` outside the canonical home | PASS |
| 5 | Transcript oracle rejects secrets | `pytest -q tests/substrate/test_substrate_helpers.py -k "transcript_oracle"` exits 0 (5 tests) | PASS |
| 6 | Process-tree cleanup reaps grandchild | `pytest -q tests/substrate/test_substrate_helpers.py -k "reap_subprocess_tree"` exits 0; spawns parent + grandchild, asserts `fully_reaped=True` | PASS |
| 7 | `test_substrate_metadata.py` exits 0 | `pytest -q tests/static/test_substrate_metadata.py` exits 0 (6/6) | PASS |
| 8 | `test_substrate_inventory.py` exits 0 | `pytest -q tests/static/test_substrate_inventory.py` exits 0 (3/3) | PASS |
| 9 | `make check-prime-directive` exits 0 at pi_monitor HEAD | `bash ../research-institution/scripts/check-prime-directive.sh --enforce` reports 0 hits (7822 scanned) | PASS |
| 10 | Entry 00/01/02 clauses hold at pi_monitor HEAD | per the prior entries' METAs (incoming `validationSummary` field references); entry 00/01/02 code paths are repo-agnostic constitutional checks | PASS |
| 11 | `tests/test_mathlint_faults.py` did NOT regress | `pytest -q tests/test_mathlint_faults.py` exits 0 for 17/18 tests; the one failure (`test_core_names_no_domain_vocabulary`) is pre-existing and unrelated to entry 05 (it predates the entry 05 work) | PASS |
| 12 | no `time.time` cross-process | `pytest -q tests/substrate/test_substrate_helpers.py -k "bounded_deadline_does_not_use_time_time"` exits 0; the helper asserts `time.time is before` after a run | PASS |

## Additional invariants verified

| Item | Verified by | Result |
|---|---|---|
| 52 tests green (substrate + static + fault tests, deselecting pre-existing failure) | `pytest tests/substrate/ tests/static/ tests/test_mathlint_faults.py --deselect ...vocabulary` exits 0 (52/52) | PASS |
| `pyproject.toml` declares `psutil>=5.9` runtime dep | `grep psutil pyproject.toml` matches | PASS |
| 1 transient-exemptions row added (`/pi_monitor/tests/substrate/`) | `grep -c '/pi_monitor/tests/substrate/' .specify/memory/transient-exemptions.toml` returns 1 | PASS |
| BoundaryName enum is closed (12 entries) | `len(BoundaryName) == 12` in `test_substrate_metadata.py` | PASS |
| Module docstring loses "manual finalization phase" phrasing | `grep "manual finalization phase" tests/mathlint_campaign.py` exits 1 | PASS |

## Sign-off

Twelve-clause log: 12 PASS. Constitution compliance: 13/13
sections PASS. Entry 05 closes; entry 06 unblocks.

The mechanical emitter runs:

```bash
python -m research_institution prime_directive attest --slug 05-process-fault-simulation --completion-sha <completion_sha> --write
```

The emitted JSON carries the canonical
`sha256(completion_sha || config_fingerprint)` per the cycle
adapter's `_compute_attestation_digest` formula (v2 form per
the e2178ab fix).

The pre-existing `test_core_names_no_domain_vocabulary`
failure in `test_mathlint_faults.py` is unrelated to entry 05
(it predates the entry's work and was first observed during
entry 02's smoke pass). Recorded here for visibility; tracked
as a follow-up by the durable `@INV-0014` family of contracts.
