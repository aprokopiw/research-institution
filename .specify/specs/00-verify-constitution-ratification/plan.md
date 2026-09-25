# 00 — Plan

## Technical context

This entry ratifies the institutional verify-constitution and seeds the
mechanical enforcement machinery. It touches only the research-
institution repo (canonical text + canonical script + canonical
registry). Sibling repos receive **only** the symlink copy of
`scripts/check-prime-directive.sh`, one commit each, sequenced
alongside the canonical commit. They do **not** receive a
verify-constitution amendment (per existing governance: typing and
verify constitutions live canonically in research-institution; sibling
`AGENTS.md` already points at `research-institution/scripts/`).

## Existing implementation to extend

- `research-institution/scripts/check-prime-directive.sh` — already
  exists per the four-repo `AGENTS.md` institution-wide prevention
  layer section. This entry ratifies it canonically (already is) and
  adds `--selftest` mode for cross-repo identity validation.
- `~/.pi/agent/extensions/prime-directive-guard.ts` — exists; blocks
  `write` / `edit` with a hard-coded `SANCTIONED_PATH_PATTERNS` list.
  This entry does **not** edit the extension; entry 09 does.
- `research-institution/.specify/memory/constitution.md` — exists,
  eight typing principles. Untouched by this entry.
- `research-institution/docs/semantic/SEMANTIC_REGISTRY.md` —
  exists; amended by FR-7.

## Components changed (research-institution only, except where noted)

| Path | Change |
|---|---|
| `.specify/memory/constitution-verify.md` | new (FR-1). |
| `.specify/memory/transient-exemptions.toml` | new (FR-2). |
| `scripts/check-prime-directive.sh` | add `--selftest` mode (FR-3, FR-5). |
| `scripts/check-prime-directive-enforced.sh` | new (initial scaffold returning `NOT_RUN`; entry 09 finishes it). |
| `tests/static/test_constitution_consistency.py` | new (FR-4). |
| `tests/static/test_canonical_script_identity.py` | new (FR-5). |
| `docs/semantic/adr/adr-0095-prime-directive-mechanical-enforcement.md` | new (FR-6). |
| `docs/semantic/invariants/inv-0095-prg-anchor-ownership.md` | new (FR-6). |
| `docs/semantic/contracts/ctr-0095-prime-directive-check-script-contract.md` | new (FR-6). |
| `docs/semantic/SEMANTIC_REGISTRY.md` | amend (FR-7). |
| `AGENTS.md` (research-institution) | amend cross-reference portion only (FR-8). |
| `math/AGENTS.md`, `pi_monitor/AGENTS.md`, `kaplansky/AGENTS.md` | amend cross-reference portion only (FR-8). |
| `math/scripts/check-prime-directive.sh`, `pi_monitor/scripts/check-prime-directive.sh`, `kaplansky/scripts/check-prime-directive.sh` | symlink-or-copy creation (FR-3, FR-8). |
| `.pi-prime-attestations/00-verify-constitution-ratification.json` | new (META emission). |
| `META.md` (this directory) | new. |

## Components explicitly NOT changed

- `research-institution/.specify/memory/constitution.md` (typing
  constitution).
- `research-institution/AGENTS.md` text **outside** the cross-
  reference portion of the institution-wide prevention block.
- Any sibling repo's `src/` or production code.
- `~/.pi/agent/extensions/prime-directive-guard.ts` (entry 09).

## Repository ownership boundary

This entry's footprint:

```
research-institution  (durable code, durable records, canonical scripts, META)
math                 (symlink or byte-equivalent copy of check-prime-directive.sh, AGENTS.md cross-ref amendment)
pi_monitor           (symlink or byte-equivalent copy, AGENTS.md cross-ref amendment)
kaplansky            (symlink or byte-equivalent copy, AGENTS.md cross-ref amendment)
```

## Constitution Check (entry-00-specific)

This entry MUST satisfy, at completion SHA:

- **§0**: §0–§12 + Governance all present in `constitution-verify.md`.
- **§1**: no current test in any of the four repos carries a tier
  marker outside the §1 closed set (validated by the pre-scaffold
  static check in `tests/static/test_closed_tier_vocabulary.py`
  initial commit — for entries that ship no test, the absence is
  recorded as `NOT_APPLICABLE` with rationale in META).
- **§3**: no gate-rollup-coalesced status is shipped by entry 00 (no
  gate implementation yet); absence is `NOT_APPLICABLE`.
- **§10**: scripts/check-prime-directive.sh is canonical at
  `research-institution/scripts/` and symlinks into the three
  siblings (FR-3). Test `test_canonical_script_identity.py`
  proves byte-equivalence (FR-5).
- **§11**: META.md exists, parses, and links the three new durable
  records (FR-6) + the strengthened-grep self-test (cannot-claim-
  done clause 11).

## Data and state migration

- None. No schema migrations. No durable state files.
- The new `transient-exemptions.toml` is the **first** entry of its
  kind; siblings may eventually add repo-local reads, but the
  canonical registry lives here.

## Failure atomicity and rollback

- This entry's commits are sequenced: (a) constitution file;
  (b) canonical registry amendment; (c) durable records; (d)
  canonical script + selftest mode; (e) sibling-repo symlinks +
  AGENTS.md cross-ref amendments (one commit per repo); (f) static
  checks; (g) META emission.
- Each commit produces a green `make check-prime-directive`. If any
  commit breaks the gate, the commit is reverted before continuing.
- Rollback is per-commit; the entry as a whole reverses cleanly
  because no production code or durable state was touched.

## Security / credential impact

- None. The new exemption registry contains no secrets and is
  consulted read-only by the existing extension.
- `test_canonical_script_identity.py` does not run real
  `check-prime-directive` against production paths; it uses
  self-test mode with synthetic input.

## Performance / runtime budgets

- `test_constitution_consistency.py`: < 1 s.
- `test_canonical_script_identity.py`: ≤ 5 s (four sibling
  self-tests, each sub-second).
- `bash scripts/check-prime-directive.sh` (cold): ≤ 10 s per repo
  (today: ≈ 2–3 s on warm cache).

## Test / evidence tier map (entry 00)

| Artifact | Tier | Evidence path |
|---|---|---|
| `constitution-verify.md` | contract | existence + parser + durable-anchor cross-check |
| `transient-exemptions.toml` | contract | TOML parse + key presence + cross-ref to each exempted path |
| `check-prime-directive.sh --selftest` | contract | exits 0 with deterministic stdout; byte-diff across four repos |
| `test_constitution_consistency.py` | unit | pure parser; no subprocess |
| `test_canonical_script_identity.py` | integration | subprocess to `bash` per repo; bounded per-call budget |
| `META.md` | contract | schema check against §11.2 |

This entry contributes **no** process / deployment / provider_live /
soak evidence. Those tiers land in entries 06 / 07 / 09 / 10.

## Gate integration

- VG-0: this entry's META references the SHA + inventory hash +
  manifest cross-checks.
- VG-1: initial commit of `test_closed_tier_vocabulary.py` seeds the
  static check; entry 01/02/03 extend per-repo.
- VG-2: no skips added by this entry; absence records as `NOT_RUN`.
- VG-3: owner-VG-3 demands a deterministic green; this entry ships
  the deterministic scripts.
- VG-4…VG-8: `NOT_APPLICABLE` for this entry; rationale in META.

## Documentation and durable-record changes

- New: constitution-verify.md (FR-1), transient-exemptions.toml
  (FR-2), three durable records (FR-6).
- Amended: SEMANTIC_REGISTRY.md (FR-7), four AGENTS.md cross-refs
  (FR-8), canonical script adds `--selftest` (FR-3, FR-5).

## Cross-repository compatibility

The canonical script is identical (modulo a possible shebang line
that resolves on the host OS). Sibling repos invoke it through a
symlink-or-copy with the same arg shape; byte-equivalence is
asserted by `test_canonical_script_identity.py`.

## Retirement / cleanup

This entry retires nothing (it is the entry point). It introduces the
retirement machinery (`transient-exemptions.toml` deletion-coupling,
governance log of exemption rows) that later entries will consume.
