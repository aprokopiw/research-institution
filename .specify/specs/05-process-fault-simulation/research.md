# 05 — Research

## Existing assets reused

- `pi_monitor/tests/helpers.py::make_fake_pi` (consolidated
  by 02).
- `pi_monitor/tests/mathlint_campaign.py` — campaign harness.
- `pi_monitor/tests/test_mathlint_faults.py` — fault tests.
- `pi_monitor/tests/mathlint_fixture/` — fault controls
  (frozen; not touched).
- `pi_monitor/src/pi_monitor/state/execution_records.py` —
  reconcile verdict table.
- `pi_monitor/src/pi_monitor/protocol/source_wire.py`.
- `pi_monitor/AGENTS.md` INV-022…INV-025.
- `.specify/memory/constitution-verify.md` §3, §5, §8, §10.

## Rejected parallel approaches (with reasons)

- **R1.** Pickle/deepcopy supervisor state for restart. REJECTED:
  violates §3.5.e (process restart required).
- **R2.** Time.sleep across processes for timing seams.
  REJECTED: cross-process monkeypatch forbidden (§6.4).
- **R3.** Inline `start_new_session`/`killpg` calls. REJECTED:
  substrate helpers are the canonical owners (FR-4, FR-10).

## Unresolved questions resolved before implementation

| Question | Resolution |
|---|---|
| Does this entry produce `provider_live` evidence? | No; entry 07 owns. |
| Does the campaign harness need full removal of `mathlint_campaign.py`? | No — entry 02 preserved it; entry 05 only removes manual finalize hooks. |

## Open risks

- **R-A.** Existing tests reference manual finalize hooks
  indirectly via fixtures. Substrate helpers replaced; entry's
  verify steps catch.

## Cross-references

- Entry 02's `fake_pi_rpc.py` (closed action vocabulary).
- `pi_monitor/src/pi_monitor/state/execution_records.py`
  (reconcile verdict table — substrate reads from here).
