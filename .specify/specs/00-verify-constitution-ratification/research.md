# 00 — Research

## Existing assets reused (per master guide §1 and entry-local §9)

- **Math self-test program:**
  `math/src/mathlint/self_test/{__init__.py,sample_program/{work_source.py,register.py}}`,
  tests at `math/tests/self_test/{test_sample_work_source.py,test_end_to_end_smoke.py}`,
  ownership docs `math/docs/operations/run-self-test.md`,
  durable records `math/docs/semantic/{adr/adr-0088-…,adr/adr-0089-…,invariants/inv-0088-…,
  contracts/ctr-0085-…}`.
  This entry touches none of those directly; entry 04 extends them.

- **Pi-monitor fake-Pi harness:**
  `pi_monitor/tests/helpers.py::make_fake_pi`,
  `pi_monitor/tests/mathlint_fixture/{server.py,protocol.py,matrix.py}`,
  `pi_monitor/tests/mathlint_campaign.py`.
  Touched only by reading the call site signature for compatibility
  (T2.1 selftest mode must not break any caller); no edits.

- **Pi-monitor supervisor scaffolding:**
  `pi_monitor/src/pi_monitor/{state/execution_records.py,
  supervision/,work/{external_source.py,work_source.py}}`.
  Touched only by inference (entry 05/06 will use them).

- **Research-institution gate and dispatcher:**
  `research-institution/research_institution/gates/{aggregate.py,bootstrap.py,runner.py}`,
  `research-institution/research_institution/{dispatcher.py,cli.py,supervisor.py,status.py,health.py,paths.py,catalog*.py}`,
  `research-institution/green-gate/check-institution.sh` (thin shim).
  This entry touches none directly; the verification CLI scaffolding
  lives in entry 06.

- **Cross-repo durable records** (already cited by this entry's
  constitution):
  research-institution: `@ADR-0001`, `@ADR-0006`, `@ADR-0007`,
  `@ADR-0011`, `@CTR-0088`, `@CTR-0094`, `@CTR-0100`, `@INV-0093`,
  `@INV-0094`. math: `@ADR-0014`, `@ADR-0088`, `@ADR-0089`,
  `@ADR-0091`, `@INV-0088`, `@CTR-0020`, `@CTR-0085`. pi_monitor:
  `@ADR-0001`, `@ADR-0005` (audit hash chain).

- **Prime-directive enforcement:**
  `research-institution/scripts/check-prime-directive.sh`
  (canonical, exists), `math/scripts/check-prime-directive.sh`
  (symlink per the math `AGENTS.md` last paragraph),
  `pi_monitor/scripts/check-prime-directive.sh` (symlink),
  `kaplansky/scripts/check-prime-directive.sh` (symlink), and
  `~/.pi/agent/extensions/prime-directive-guard.ts` (TypeScript,
  exists).

- **Spec Kit 1.0.4 already installed** (`specify check` confirms);
  Pi Coding Agent integration is the registered harness
  (auto-loads from this repo).

## Rejected parallel approaches (with reasons)

- **R1.** Add a `tests/` tier marker file by editing every existing
  test in math / pi_monitor / kaplansky. **REJECTED**: would conflate
  this entry with entry 01 / 02 / 03 (rationalization); the
  rationalization belongs in those entries' scope. Entry 00 only
  **seeds** the static check and confirms the §1 closed set is not
  violated today.
- **R2.** Author a `verify-constitution` as a separate package
  (`research_institution.verify_constitution`) imported into
  `gates/aggregate.py`. **REJECTED**: keep the constitution as
  *prose with a machine-checkable parser*; do not introduce a
  Python module that pre-judges the policy. The static check
  verifies the file structure, not the interpretation; downstream
  gates interpret.
- **R3.** Co-locate the canonical script at `math/scripts/` and
  make research-institution symlink it. **REJECTED**: research-
  institution is the canonical owner per architecture. Symlinks
  point OUTWARD from siblings TO the canonical repo, not inward.
- **R4.** Defer the three new durable records (`@ADR-0095-…`,
  `@INV-0095-…`, `@CTR-0095-…`) until entry 09 ships the
  attestation machinery. **REJECTED**: the canonical durable
  record is the right place to anchor the policy; the attestation
  machinery in 09 is downstream and CONSUMES the records, not
  produces them.
- **R5.** Edit the existing TypeScript pi extension to add
  `.specify/specs/` to `SANCTIONED_PATH_PATTERNS` in entry 00.
  **REJECTED**: that extension rewrite belongs in entry 09 (the
  prime-directive-mechanical-enforcement entry) where the
  exemption registry lives. Entry 00 writes only the canonical
  exemption registry (TOML), which entry 09 wires into the
  extension.
- **R6.** Author a per-constitution ADR enumerating §0–§12
  individually (twelve tiny ADRs). **REJECTED**: one ADR per
  constitutional ratification (here: `@ADR-0095-…`) plus one INV
  (ownership) plus one CTR (script contract) is the canonical
  triple. Inside the body of those three durable records, every
  §N sub-rule is documented; this matches the existing math
  `@ADR-0014` precedent (one ADR per durable decision cluster).

## Unresolved questions resolved before implementation

| Question | Resolution |
|---|---|
| Does Spec Kit provide a top-level `constitution` CLI command? | No. Top-level commands are `init / check / version / self / extension / integration / event / preset / bundle / workflow`. Constitution is delivered via the integration's slash command. This entry writes the file directly. |
| Does every repo need its own `.specify/` mount? | No. All eleven entries live under `research-institution/.specify/specs/`. Sibling repos do not need Spec Kit init because no spec dir lifts to them. |
| Is the strengthened regex changing? | No. Same pattern `(\b[Pp][Ll][Aa][Nn]|\b[Ss][Pp][Ee][Cc])[-_ ]?[0-9]{2,}`; this entry pins it via `@CTR-0095-prime-directive-check-script-contract`. |
| Does the entry write `transient-exemptions.toml` as TOML arrays of tables? | Yes (per `research-institution/.specify/memory/type-escapes.toml` precedent — same format, different registry). |
| Does entry 00 author every durable record cited in the constitution? | It authors three: `@ADR-0095-…`, `@INV-0095-…`, `@CTR-0095-…`. It does **not** author the existing durable records (those already exist). The cross-ref amendment to SEMANTIC_REGISTRY.md adds only the three new rows. |
| Will this entry be visible to the Spec Kit auto-loop without slash commands? | Yes — the integration provides slash commands that wrap the canonical file write this entry performs. Future tool calls (write/edit) targeting `constitution-verify.md` and other paths in the entry will go through the prime-directive extension as normal; this entry's body avoids forbidden literals by idiom. |

## Open risks

- **R-A.** The current pi extension
  (`~/.pi/agent/extensions/prime-directive-guard.ts`) does **not**
  yet consult `transient-exemptions.toml`. Until entry 09 lands,
  the registry written by entry 00 is **enforceable only via the
  canonical script**, not via the runtime extension. Entry 00
  META.md records this with a "consumer entry" annotation pointing
  at entry 09.
- **R-B.** Sibling `AGENTS.md` amendments in T3.2/T3.4/T3.6 must
  avoid adding new prose that contains forbidden literals; the
  amendments are limited to the cross-reference list. Verified
  per-task.
- **R-C.** The script `transient-exemptions.toml` is read by
  entry 09's extension update; entry 00 ships a v0.0.0 file with
  three rows that match the four `AGENTS.md` sanctioned-glob list
  and the math §22 grandfather. Drift between this file and the
  `AGENTS.md` text is acceptable only when entry 09 reconciles.

## Cross-references

- `research-institution/.specify/memory/constitution.md` (typing
  constitution, unchanged, sibling file).
- `research-institution/.specify/memory/type-escapes.toml` (empty
  ledger, format precedent for the new `transient-exemptions.toml`).
- `research-institution/docs/concepts/architecture.md` (kernel /
  OS / driver / program model; cross-repo wiring authority is
  research-institution).
- `research-institution/docs/semantic/SEMANTIC_REGISTRY.md`
  (existing registry; amended by FR-7).
- `research-institution/.agents/transient/test_and_simulation_suite.md`
  (eleven-entry program; this is entry 00 of it).
- `research-institution/scripts/check-prime-directive.sh` (canonical
  script; extended by FR-3).
- `~/.pi/agent/extensions/prime-directive-guard.ts` (runtime
  enforcement; entry 09 will wire to the new registry).
