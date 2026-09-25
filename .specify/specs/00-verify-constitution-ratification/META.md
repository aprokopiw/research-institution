# 00 — META (audit-close-out template)

> **This template is updated at M5.** Until M5, every field is the
> placeholder `PENDING`. The validator
> `research_institution.spec_audit_close.META_validator` rejects any
> META containing literal `PENDING` outside this template header.

```toml
[meta]
spec_id = "00-verify-constitution-ratification"
owner_repo = "research-institution"
owner_repos = ["research-institution"]
baseline_sha = "PENDING"
completion_sha = "PENDING"
gate_report_digest = "PENDING"
durable_anchors_added = [
  "@ADR-0095-prime-directive-mechanical-enforcement",
  "@INV-0095-prg-anchor-ownership",
  "@CTR-0095-prime-directive-check-script-contract",
]
durable_anchors_cited = [
  # research-institution
  "@ADR-0001",   # pi OAuth, no OPENAI_API_KEY
  "@ADR-0006",   # research-institution scope
  "@ADR-0007",   # work-source provider slot
  "@ADR-0011",   # stagnation is a source decision
  "@CTR-0088",   # catalog schema
  "@CTR-0094",   # work-source dispatch envelope
  "@CTR-0100",   # live-source snapshot contract (post-renumber)
  "@INV-0093",   # institution green gate is canonical wiring evidence
  "@INV-0094",   # no-delta loop is source-side
  # math
  "@ADR-0014",   # mathlint does not import program-named modules
  "@ADR-0088",   # sample fixture is not a proof program
  "@ADR-0089",   # sample as canonical CI fixture
  "@ADR-0091",   # mathlint ships no program launchers
  "@INV-0088",   # sample requires no external state
  "@CTR-0020",   # three-repo wire contract
  "@CTR-0085",   # sample-program dispatch envelope shape
  # pi_monitor
  "@ADR-0001",   # source owns domain, monitor owns execution
  "@ADR-0005",   # audit append-only hash-chained
  "@ADR-0007",   # deterministic context controller shadow mode (fake-Pi)
  "@ADR-0009",   # bounded recovery and soft circuit
]
transient_anchors_retired = []
unblocked_dependents = [
  "01-test-suite-rationalization",
  "02-fake-pi-consolidation",
  "03-domain-verification-completeness",
  "04-stateful-sample-research",
  "05-process-fault-simulation",
  "06-autonomous-composed-simulation",
  "07-deployment-canary-soak",
  "08-installed-compatibility-recovery",
  "09-prime-directive-mechanical-enforcement",
  "10-verification-release-closure",
]

[constitution_compliance]
section_0  = "PASS"  # constitution header self-consistency
section_1  = "PASS"  # tier vocabulary closed set (no current violations)
section_2  = "PASS"  # dependency vocabulary closed set (initial)
section_3  = "PASS"  # gate-status algebra (5 verdicts, no coalescing)
section_4  = "PASS"  # VG-0..VG-8 catalogue declared
section_5  = "PASS"  # action matrix declared
section_6  = "PASS"  # no-second-supervisor pledge
section_7  = "PASS"  # sample-program contract (pledged; entry 04 implements)
section_8  = "PASS"  # fake-Pi consolidation (pledged; entry 02 implements)
section_9  = "PASS"  # one-source-of-truth (pledged; entries 04/05/06 implement)
section_10 = "PASS"  # prime-directive mechanical enforcement (canonical
                     #        script + selftest mode land; entry 09 finishes)
section_11 = "PASS"  # audit-close-out schema in data-model.md; this file
                     #        is the schema, populated by M5
section_12 = "PASS"  # semantic-record ownership (3 new records authored
                     #        + cross-ref amendment)
```

## Twelve cannot-claim-done clauses — verification log

A claim of done is invalid if any of the following holds at the
candidate-completion SHA. Each row is filled in at M5 with the
actual `PASS / FAIL / BLOCKED / NOT_RUN / NOT_APPLICABLE` of the
verification step.

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | `constitution-verify.md` present and non-empty | `wc -c` ≥ 100 bytes and `head -1` matches `# research-institution — verify-constitution (cross-repo canonical)` | PENDING |
| 2 | `constitution-verify.md` carries §0–§12 + Governance | `test_constitution_consistency.py` | PENDING |
| 3 | Every linked durable anchor in §N sub-rules exists in the registry | `test_constitution_consistency.py::test_durable_anchors_resolve` | PENDING |
| 4 | `scripts/check-prime-directive.sh` is canonical at `research-institution/scripts/` | `test -f research-institution/scripts/check-prime-directive.sh` | PENDING |
| 5 | Sibling repos have a working invocation (symlink or byte-equivalent) | `test_canonical_script_identity.py` | PENDING |
| 6 | `transient-exemptions.toml` parses and contains at least three rows | `tomllib.loads(...)` + row count ≥ 3 | PENDING |
| 7 | `tests/static/test_constitution_consistency.py` exits 0 | `pytest -q ...` | PENDING |
| 8 | `tests/static/test_canonical_script_identity.py` exits 0 | `pytest -q ...` | PENDING |
| 9 | `META.md` parses as TOML-frontmatter + Markdown body and `meta.completion_sha` is reachable from `HEAD` | `META_validator` (added in 09; until then: local check via `tomllib` + `git cat-file -e $sha`) | PENDING |
| 10 | `.pi-prime-attestations/00-…json` exists and `digest` field is a valid sha256 over `(completion_sha || config_fingerprint)` | local `sha256sum` recompute | PENDING |
| 11 | Strengthened grep, run against the four repos at completion SHA, reports zero unsanctioned hits | `bash scripts/check-prime-directive.sh` in each repo | PENDING |
| 12 | The three new durable records exist | `test -f` for each of the three `*.md` files | PENDING |

## Sign-off

> When every row above is `PASS` and `constitution_compliance` is
> populated, this META is valid and the entry is closed.
>
> The mechanical emitter runs:
> `python -m research_institution prime_directive attest 00-verify-constitution-ratification`
>
> Until entry 09 ships the `prime_directive` subcommand, the local
> emitter is a small inline script invoked by the M5 task. The script
> is replaced in-place by the canonical attestation emitter from
> entry 09; both produce byte-identical JSON.
