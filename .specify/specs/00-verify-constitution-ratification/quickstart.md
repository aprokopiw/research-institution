# 00 — Quickstart

## Local verification commands (this entry's success criteria)

Every command below should exit `0` at the entry's completion SHA.

```sh
# 1. Canonical script passes against the research-institution tree.
cd ~/Documents/andrei/research-institution
make check-prime-directive
echo "exit=$?"   # 0

# 2. Self-test mode of the canonical script runs.
bash scripts/check-prime-directive.sh --selftest
echo "exit=$?"   # 0
# emits one line beginning: "self-test ok: canonical grep present, sanctioned-globs recognised:"

# 3. Cross-repo identity: same exit code / output across all four repos.
bash scripts/check-prime-directive.sh --selftest > /tmp/ri.txt 2>&1
(
  cd ~/Documents/andrei/math            && bash scripts/check-prime-directive.sh --selftest > /tmp/math.txt 2>&1
  cd ~/Documents/andrei/pi_monitor      && bash scripts/check-prime-directive.sh --selftest > /tmp/pimon.txt 2>&1
  cd ~/Documents/andrei/kaplansky       && bash scripts/check-prime-directive.sh --selftest > /tmp/kap.txt 2>&1
)
diff /tmp/ri.txt /tmp/math.txt && diff /tmp/ri.txt /tmp/pimon.txt && diff /tmp/ri.txt /tmp/kap.txt
echo "exit=$?"   # 0

# 4. Static checks (constitution + canonical-script identity).
uv run --project research-institution pytest -q \
  tests/static/test_constitution_consistency.py \
  tests/static/test_canonical_script_identity.py
echo "exit=$?"   # 0

# 5. Emission of the META attestation (scaffolded by 09; entry 00
#    uses a minimal local emitter until 09 lands).
python -m research_institution prime_directive attest 00-verify-constitution-ratification
echo "exit=$?"   # 0
cat .pi-prime-attestations/00-verify-constitution-ratification.json
# JSON must contain:
#   "spec_id": "00-verify-constitution-ratification"
#   "digest":   "<sha256 over (completion_sha || config_fingerprint)>"
```

## The "expected GREEN / expected BLOCKED / expected NOT_RUN" status per gate

At entry 00's completion SHA:

| Gate | Expected status | Why |
|---|---|---|
| VG-0 | `PASS` | static checks + canonical script self-test pass |
| VG-1 | `PASS` | initial no-op `test_closed_tier_vocabulary.py` shows zero violations in current trees |
| VG-2 | `NOT_RUN` | no skips added; absence recorded in META |
| VG-3 | `PASS` (focused) | static + self-test = the deterministic subset |
| VG-4 | `NOT_APPLICABLE` | entry 00 ships no S2 scenario |
| VG-5 | `NOT_APPLICABLE` | entry 00 ships no S3 deployment |
| VG-6 | `NOT_APPLICABLE` | entry 00 ships no S1 mutation |
| VG-7 | `NOT_APPLICABLE` | entry 00 ships no S4 canary |
| VG-8 | `NOT_APPLICABLE` | entry 00 ships no S5 soak |

Any deviation from this table is gate `FAIL` per constitution §3.

## Artifact locations

```
research-institution/
  .specify/
    memory/
      constitution.md                  # typing constitution (unchanged)
      constitution-verify.md           # THIS ENTRY'S PRODUCT
      transient-exemptions.toml        # THIS ENTRY'S PRODUCT
      type-escapes.toml                # precedent format reference
    specs/
      00-verify-constitution-ratification/
        spec.md
        plan.md
        tasks.md
        research.md
        data-model.md
        quickstart.md
        META.md
        contracts/
          (none for entry 00)
  scripts/
    check-prime-directive.sh            # canonical + extended with --selftest
    check-prime-directive-enforced.sh   # scaffolded; entry 09 finishes
  tests/static/
    test_constitution_consistency.py
    test_canonical_script_identity.py
    test_closed_tier_vocabulary.py      # initial scaffold (no-op)
  docs/semantic/
    adr/adr-0095-prime-directive-mechanical-enforcement.md
    invariants/inv-0095-prg-anchor-ownership.md
    contracts/ctr-0095-prime-directive-check-script-contract.md
    SEMANTIC_REGISTRY.md                # amended

math/scripts/check-prime-directive.sh         # symlink OR byte-diff copy
pi_monitor/scripts/check-prime-directive.sh   # symlink OR byte-diff copy
kaplansky/scripts/check-prime-directive.sh    # symlink OR byte-diff copy

.pi-prime-attestations/
  00-verify-constitution-ratification.json    # META attestation
```

## Cleanup on failure (per constitution §3, no rollback of policy without a follow-on entry)

If M5 attestation emission fails:

1. Do NOT mark the task `[x]`. The task remains `[~]`.
2. The dependent entry's first task reads META.md / attestation.
   Missing → the dependent entry starts in `BLOCKED` and emits a
   `HOLD:` line in its own META.
3. Resolution: either amend the failing task's body and re-run its
   `verify:` command, or open a follow-on entry to retest the
   failing task at a new SHA. **Never** hand-patch the attestation
   JSON; that is gate `FAIL` per S3.5.

## Cross-references

- `quickstart.md` of entry 01 (`01-test-suite-rationalization`,
  not yet authored) will be the first spec to consume the static
  check seeded by entry 00.
- The cross-repo `AGENTS.md` institution-wide prevention section
  was already wired by the spec-kit init that produced
  `research-institution/.specify/`; this entry does not change
  those sections (FR-8 only narrows the cross-reference list).
