# 02 — Research

## Existing assets reused

- `pi_monitor/tests/helpers.py::make_fake_pi` — the inline
  generator body. Substrate for `fake_pi_rpc.py`.
- `pi_monitor/tests/mathlint_fixture/{server.py,protocol.py,matrix.py}`
  — scenario vocabulary precedents; **exempt** from migration per
  AGENTS §22 BC-4 carve-out, frozen in
  `transient-exemptions.toml`.
- `pi_monitor/tests/mathlint_campaign.py` — campaign harness with
  manual finalize hooks. Preserved at call sites; documented in META.
- `pi_monitor/Makefile` + `.py` test patterns under
  `tests/{compose_*,state_machine_*,mathlint_campaign.py,mathlint_faults.py}`
  — happy-path tests that MUST remain green.
- `pi_monitor/src/pi_monitor/protocol/source_wire.py` —
  immutable wire vocabulary.
- `pi_monitor/src/pi_monitor/work/external_source.py` —
  subprocess adapter; consumes the fake-Pi as a black box.
- `pi_monitor/AGENTS.md` INV-001…INV-025; INV-024 is the PRIME
  DIRECTIVE's local-name variant (synonym of institution-wide
  prevention layer).
- `research-institution/.specify/memory/transient-exemptions.toml`
  — appended with pi_monitor rows.
- `research-institution/scripts/check-prime-directive.sh` —
  used at pi_monitor HEAD.

## Rejected parallel approaches (with reasons)

- **R1.** Keep `unittest discover` as the only runner. REJECTED:
  documents and CI cannot agree on one; parity test would expose
  it anyway. Makefile's primary command IS the canonical commander.
- **R2.** Embed the fake-Pi protocol in
  `pi_monitor.protocol.source_wire.py`. REJECTED: production
  source_wire is the wire authority; the fake-Pi lives in tests
  (per pi_monitor AGENTS Working rules "Tests must not make real
  model calls").
- **R3.** Move fake-Pi into a separate package
  (`fake_pi`, `fake_pi_rpc`). REJECTED: cross-repo import of fake-Pi
  would create a sixth sibling package. The fake lives at
  `pi_monitor/tests/support/fake_pi_rpc.py` and is consumed as a
  **subprocess** by entry 06 (per §8.1).
- **R4.** Generate fake-Pi at test runtime into a tmp dir each call.
  REJECTED: the existing `make_fake_pi` already does this; the
  entry's job is to **factor the body into a module**, not to
  re-invent the generator.

## Unresolved questions resolved before implementation

| Question | Resolution |
|---|---|
| Should `make_fake_pi`'s signature change? | No — preserved; entry 02 is a refactor, not an API change. |
| What happens if a scenario uses an unknown action? | `ScenarioParseError` with file + line + action + suggestion ("see closed action vocabulary in fake_pi_rpc.py"). |
| Is the spoof environment a strict-mode failure? | Yes — `fake_pi_rpc.py --selftest` exits 78 ("EX_CONFIG") if known real creds are present. |
| Is `make_fake_pi` deprecated? | No — remains the canonical wrapping helper for in-process callers. |

## Open risks

- **R-A.** A test suite in the wild uses the inline `make_fake_pi`
  body to fork a child. The thin wrapper preserves the body
  signature; preserved callers see no diff.
- **R-B.** A user-defined scenario from outside pi_monitor enters
  via subprocess with no JSON validation. Mitigation: `parse_scenario`
  called both in-process and as CLI arg.

## Cross-references

- `pi_monitor/AGENTS.md` PRIME DIRECTIVE + INV-024 + Working Rules.
- `.specify/memory/constitution-verify.md` §8 (fake-Pi ownership).
- `pi_monitor/src/pi_monitor/protocol/source_wire.py` (wire
  authority).
- `@ADR-0007` (deterministic context controller shadow mode).
- `@ADR-0009` (bounded recovery and soft circuit).
