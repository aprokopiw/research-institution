# 09 — Quickstart

## Local verification commands

```sh
# 1. Emit an attestation.
cd ~/Documents/andrei/research-institution
python -m research_institution prime_directive attest \
    09-prime-directive-mechanical-enforcement
echo "exit=$?"   # 0
cat .pi-prime-attestations/09-prime-directive-mechanical-enforcement.json
# expected: spec_id, completion_sha, config_fingerprint, digest

# 2. Validate the attestation at current SHA.
python -m research_institution prime_directive validate \
    .pi-prime-attestations/09-prime-directive-mechanical-enforcement.json
echo "exit=$?"   # 0 (PASS)

# 3. Validate the entry 00 META template.
python -m research_institution spec_audit_close META_validate \
    .specify/specs/00-verify-constitution-ratification/META.md
echo "exit=$?"   # 0

# 4. Run --enforce against the canonical script.
bash scripts/check-prime-directive.sh --enforce
echo "exit=$?"   # 0

# 5. Per-repo `check-prime-directive-enforced`.
cd ../math            && make check-prime-directive-enforced && cd -
cd ../pi_monitor      && make check-prime-directive-enforced && cd -
cd ../kaplansky       && make check-prime-directive-enforced && cd -
echo "exit=$?"   # 0

# 6. Strict-grep clean.
make check-prime-directive
echo "exit=$?"   # 0
```

## Expected gate statuses

| Gate | Status |
|---|---|
| VG-0…VG-3 | `PASS` (via prior entries; entry 09 supplements) |
| VG-4…VG-8 | `NOT_APPLICABLE` |

## Artifact locations

```
research-institution/
  research_institution/prime_directive/
    __init__.py
    attest.py
    validate.py
    meta_validator.py
    extension_bridge.py
  scripts/META_validator.py
  scripts/check-prime-directive.sh        # +--enforce mode

~/.pi/agent/extensions/prime-directive-guard.ts  # upgraded

math/
  Makefile                                   # +check-prime-directive-enforced
  docs/semantic/adr/adr-NNNN-prime-directive-enforcement.md
pi_monitor/
  Makefile                                   # +check-prime-directive-enforced
  docs/adr/adr-NNNN-prime-directive-enforcement.md
kaplansky/
  Makefile                                   # +check-prime-directive-enforced
  docs/.../adr-NNNN-prime-directive-enforcement.md
```

## Cross-references

- `spec.md` cannot-claim-done list.
- Entry 10's release closure consumes entry 09's artifacts.
