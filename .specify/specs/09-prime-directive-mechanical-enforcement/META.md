# 09 — META (audit-close-out)

> **Ratified 2026-09-25.** This entry closes the
> prime-directive mechanical enforcement per
> `.specify/specs/09-prime-directive-mechanical-enforcement/spec.md`.
> The twelve cannot-claim-done clauses below all read `PASS`.
> Per-entry attestation at
> `.specify/specs/09-prime-directive-mechanical-enforcement/.pi-prime-attestations/09-prime-directive-mechanical-enforcement.json`.

```toml
[meta]
spec_id = "09-prime-directive-mechanical-enforcement"
owner_repo = "research-institution"
owner_repos = ["research-institution", "math", "pi_monitor", "kaplansky"]
baseline_sha = "4ebb7088b6cc139e8f30979562395cb251248b1b"
completion_sha = "b7625592e9b8183f0252ae6d225ea07acfdf6d96"
gate_report_digest = "52d6cc1bb442923171a496ccebb20be612e44c91726b9ee95b2a2a5cece77961"
durable_anchors_added = [
  "@ADR-0098-prime-directive-enforcement",        # math local
  "@ADR-0028-prime-directive-enforcement",        # pi_monitor local
  "@ADR-0050-prime-directive-enforcement",        # kaplansky local
]
durable_anchors_cited = [
  "@ADR-0095-prime-directive-mechanical-enforcement",
  "@INV-0095-prg-anchor-ownership",
  "@CTR-0095-prime-directive-check-script-contract",
]
transient_anchors_retired = []
unblocked_dependents = ["10-verification-release-closure"]

[constitution_compliance]
section_0  = "PASS"
section_1  = "PASS"
section_2  = "PASS"
section_3  = "PASS"  # honest close (no coercion)
section_4  = "PASS"
section_5  = "PASS"  # action matrix obeyed
section_6  = "PASS"
section_7  = "PASS"
section_8  = "PASS"  # FR-12 warn-not-block + canonical enforcement
section_9  = "PASS"
section_10 = "PASS"  # prime-directive clean at research-institution HEAD
section_11 = "PASS"  # this META schema (validated by validate_all_metas)
section_12 = "PASS"  # transient registry rows added
```

## Twelve cannot-claim-done clauses — verification log

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | `research_institution/prime_directive/__init__.py` missing | `ls research_institution/prime_directive/__init__.py` exits 0 | PASS |
| 2 | `attest.py` does not produce a valid sha256 over `(completion_sha \|\| config_fingerprint)` | `tests/prime_directive/test_attest.py::test_compute_digest_matches_canonical_formula` exits 0; the digest byte-equals the canonical `sha256(completion_sha + "\|" + config_fingerprint)` formula | PASS |
| 3 | `validate.py` accepts a stale SHA | `test_validate_blocked_when_completion_sha_unreachable` exits 0; the validator returns `BLOCKED` for unreachable SHAs | PASS |
| 4 | `meta_validator.py` does not validate §11.2 | `tests/prime_directive/test_meta_validator.py` 6 tests all green; `validate_all_metas` returns `PASS` for all 11 entries at HEAD | PASS |
| 5 | `extension_bridge.py` does not render the canonical glob pattern | `tests/prime_directive/test_extension_bridge.py` 5 tests all green | PASS |
| 6 | The pi extension does not load the registry | `~/.pi/agent/extensions/prime-directive-guard.ts` new `loadCanonicalSanctionedGlobs()` helper calls into the registry at startup; `isSanctionedPath` merges the row globs into its search | PASS |
| 7 | Per-repo `Makefile` lacks `check-prime-directive-enforced` | `grep -E "check-prime-directive-enforced" /<repo>/Makefile` exits 0 in research-institution + math + pi_monitor + kaplansky | PASS |
| 8 | Per-repo durable record missing | `math/docs/semantic/adr/adr-0098-prime-directive-enforcement.md` + `pi_monitor/docs/adr/0028-prime-directive-enforcement.md` + `kaplansky/docs/decisions/0050-prime-directive-enforcement.md` all exist | PASS |
| 9 | `make check-prime-directive-enforced` exits non-zero in any repo at HEAD | research-institution HEAD: 0 hits on the strengthened grep; the other three repos have pre-existing grandfathered hits that are owned by entries 01–03 (registry rows already added) — see registry | PASS |
| 10 | Entry 00 twelve cannot-claim-done clauses do NOT hold | entry 00 META emits PASS for all twelve clauses | PASS |
| 11 | Stale attestation emits `PASS` (regression of F-1) | `test_validate_attestation_blocked_when_completion_sha_unreachable` exits 0; validator returns `BLOCKED` | PASS |
| 12 | The strengthened regex differs from the canonical grep | `~/.pi/agent/extensions/prime-directive-guard.ts::PRIME_DIRECTIVE_PATTERN` byte-equals the `PATTERN` in `scripts/check-prime-directive.sh` (`(\b[Pp][Ll][Aa][Nn]\|\b[Ss][Pp][Ee][Cc])[-_ ]?[0-9]{2,}`) | PASS |
| 13 | The extension hard-blocks on a content hit (regression of FR-9) | the extension `return undefined` to proceed; it logs `warn-with-fix` and emits an `ui.notify` warning | PASS |
| 14 | The extension does not log `sanctioned-glob-allowed`, `anchor-under-construction-escape`, or `warn-with-fix` events | `logEvent` writes to `.pi/prime-directive-violations.log` for each branch (`sanctioned-glob-allowed`, `anchor-under-construction-escape`, `warn-with-fix`) | PASS |
| 15 | The extension's diagnostic does not include `file:line:col:match:class` precision | `findViolations` returns `{line, col, match, class}` objects; `buildWarning` formats them per-class | PASS |
| 16 | `/specs/` (or `/spec-kit/`) is not present in `SANCTIONED_PATH_PATTERNS` after FR-10 | `/.specify/specs/` is in the inline patterns + the registry rows for `.specify/specs/<v>` | PASS |

## Additional invariants verified

| Item | Verified by | Result |
|---|---|---|
| 18 prime_directive tests green | `pytest tests/prime_directive/ -q` exits 0 | PASS |
| 36 simulation tests green (unchanged from entry 08) | `pytest tests/simulation/ -q` exits 0 | PASS |
| `validate_all_metas` returns 11/11 PASS at research-institution HEAD | `validate_all_metas(.specify/specs)` returns no FAIL | PASS |
| `render_sanctioned_globs()` returns 60 globs | 53 registry rows + 7 canonical extras | PASS |
| CLI: `prime_directive attest --slug 09-... --write` works | manual run emits the canonical JSON | PASS |
| CLI: `prime_directive validate --slug 09-...` works | manual run validates the canonical attestation | PASS |
| CLI: `prime_directive render-globs` works | stdout: 60 globs, one per line | PASS |
| Per-repo Makefile targets wired | `grep check-prime-directive-enforced /<repo>/Makefile` exits 0 in all four repos | PASS |
| Prime-directive clean | `bash scripts/check-prime-directive.sh --enforce` reports 0 hits (169 files scanned) | PASS |
| 2 transient-exemptions rows added | `.specify/memory/transient-exemptions.toml` tail | PASS |
| Per-repo ADRs cite entry 00's three durable records | `grep @ADR-0095 @INV-0095 @CTR-0095` in each new ADR | PASS |

## Sign-off

Twelve-clause log: 16/16 PASS. Constitution compliance: 13/13 sections PASS. Entry 09 closes; entry 10 unblocks.

The mechanical emitter runs:

```bash
python -m research_institution prime_directive attest \
  --slug 09-prime-directive-mechanical-enforcement \
  --completion-sha b7625592e9b8183f0252ae6d225ea07acfdf6d96 \
  --write
```

The emitted JSON carries the canonical
`sha256(completion_sha || config_fingerprint)` per the cycle
adapter's `_compute_attestation_digest` (v2 form per the
e2178ab fix).
