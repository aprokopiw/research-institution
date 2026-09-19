# Research-Institution Quickstart

The research-institution repo orchestrates math-engine +
pi_monitor + N research programs. This runbook walks an
operator through bootstrapping a fresh checkout, verifying
the institution is wired, and running the canonical green
gate.

## One-liner

```sh
# Bootstrap (clone + pip-install every catalog entry):
bash research-institution/scripts/bootstrap-institution.sh

# Verify (the canonical green gate):
bash research-institution/green-gate/check-institution.sh --hermetic
```

When the green gate prints `GREEN INSTITUTION READY`, the
institution is fully wired at the slot + entry-point +
config level.

## What it proves

The green gate runs three sub-checks in order:

1. **Engine** (math-engine via
   `scripts/check-local-system-readiness.sh
   --skip-external --use-program=self_test-sample` in
   hermetic mode; the operator's real provider in live
   mode). Proves the mathlint slot is wired.
2. **Supervisor** (pi_monitor's `doctor`, if on PATH).
   Proves the supervisor is configured.
3. **Programs** (each entry in `catalog/programs.toml`
   whose `local_path` resolves). For kaplansky today,
   `scripts/check-program-institution.sh --hermetic`
   asserts the entry point is registered + the kaplansky
   invariants parse.

Together these prove: math-engine is wired, the supervisor
is reachable, and every catalog entry is integrated.

## What it does NOT prove

* The gate does NOT prove the institution can do live work
  (paired-smoke receipt, live kaplansky run). For live
  evidence, run `--live` mode (operator-only; requires
  LLM credentials).
* The gate does NOT prove model credentials are valid;
  operators with credentials run `--live` separately.
* The gate does NOT prove every catalog entry's
  `mathlint_pin` is current; use
  `scripts/update-programs.sh` to check pins.

## Cross-references

* `@INV-0091` — mathlint does not ship program launchers.
* `@INV-0092` — pi_monitor does not name mathlint.
* `@INV-0093` — institution green gate is the canonical
  wiring evidence.
* `@CTR-0088` — institution catalog schema.
* `@CTR-0089` — kaplansky's `check-program-institution.sh`
  contract.
* `@CTR-0090` — mathlint has no program console scripts.
* `@CTR-0091` — pi_monitor work-source identity is
  config-driven.
* `@CTR-0092` — pi_monitor long-running command allowlist
  is config-driven.
* `@ADR-0091` — mathlint does not ship program launchers.
* `@ADR-0092` — pi_monitor does not name mathlint.
* `plan-010 VERIFY-EVERYTHING.md` — the math-engine
  one-line answer (mathlint's hermetic gate).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `engine: FAILED` (LOCAL000 / math-engine not green) | mathlint not installed | `pip install -e ~/Documents/andrei/math` |
| `engine: FAILED` (system-readiness stub fails) | sample-program path missing | `uv sync` in math-engine; rerun |
| `supervisor: not on PATH` | pi_monitor not installed | Install pi_monitor (`pip install -e ~/Documents/andrei/pi_monitor`) |
| `program=kaplansky: WARN: local_path missing` | kaplansky not cloned | `git clone https://github.com/aprokopiw/math-kaplansky $HOME/Documents/andrei/kaplansky` |
| `program=kaplansky: FAILED` (entry-point not registered) | kaplansky not pip-installed | `(cd $HOME/Documents/andrei/kaplansky && pip install -e .)` |
| `multiple MathLint program providers installed` | sample-program entry-point leaked | Reinstall mathlint from source (`pip install -e ~/Documents/andrei/math`) |
| `mathlint-kaplansky: command not found` | launcher not on PATH | `(cd $HOME/Documents/andrei/kaplansky && pip install -e .)` (adds the console script) |
