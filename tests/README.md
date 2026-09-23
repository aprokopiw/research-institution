# research-institution tests — verification-locality decision tree

> **The verification-locality decision tree.** A fresh
> agent who knows *what they want to test* but not *which
> test file to open* should read this doc. The decision
> tree maps question to file in one hop.

## The decision tree

```text
"Am I testing..."
│
├── "the catalog" (catalog schema, program registry, marker files)
│   └── test_catalog.py, test_catalog_consistent.py,
│       test_catalog_fresh_checkout.py, test_catalog_types.py
│
├── "the dispatcher" (CLI verbs, gate check, status, stop, watch)
│   └── test_cli.py, test_dispatcher.py, test_gate_check.py,
│       test_gates_module.py
│
├── "the source-decision wire format" (Dispatch / Wait / OperatorRequired / Stop)
│   ├── for the wire codec (parse_source_decision)
│   │   └── test_source_decision_contract.py, test_source_decision_wire_typed.py
│   ├── for the typed source-decision envelope (research-institution mirror)
│   │   └── test_source_decision_wire_typed.py, test_typed_work_envelopes.py
│   ├── for stagnation handling (plan-013)
│   │   └── test_source_decision_stagnation.py  ← NEW in plan-013 PR-C
│   └── for the wire schema being byte-identical to pre-PR-C
│       └── test_wire_schema_unchanged.py  ← NEW in plan-013 PR-C
│
├── "the green gate" (the canonical wiring evidence)
│   ├── for the hermetic gate (no LLM calls)
│   │   └── test_green_gate_hermetic.py, test_green_gate_cli_shape.py
│   ├── for the live gate (with credentials)
│   │   └── test_cold_start_hermetic.py
│   └── for the green gate aggregator
│       └── test_gates_module.py
│
├── "the bootstrap" (clone + install from fresh checkout)
│   └── test_bootstrap_dry_run.py
│
├── "cross-repo type identity" (the math + pi_monitor wire is mirrored here)
│   ├── for the four-repository type audit
│   │   └── test_cross_repo_type_identity.py
│   ├── for the composition root (research-institution fills the OS-side slot)
│   │   └── test_compose_work_selection.py, test_os_provider_compose_proof.py
│   └── for the source-decision wire fuzz (randomized payloads)
│       └── test_fuzz_wire_codec.py
│
├── "state-machine dispatch" (the supervisor cycle)
│   ├── for the dispatch state machine
│   │   └── test_state_machine_dispatch.py
│   ├── for composed dispatch property tests
│   │   └── test_composed_dispatch_property.py
│   └── for supervisor probes / status queries
│       └── test_supervisor_probe.py, test_supervisor_status_typed.py
│
├── "status / health" (the supervisor's runtime state)
│   ├── for the status enum shape
│   │   └── test_status.py, test_status_types.py
│   └── for the typed health model
│       └── test_health.py, test_health_typed.py
│
├── "skill installation" (the per-program `pi` skills)
│   └── test_skill_template.py
│
├── "contract enforcement" (the package-level invariants)
│   ├── for the cross-package boundary
│   │   └── test_package_boundary.py
│   ├── for the contracts module's public surface
│   │   └── test_contracts.py
│   └── for the entry-point contract (mathlint.providers / mathlint.program_work_selection)
│       └── test_entry_point_contract.py
│
├── "durable semantic records" (the @ADR / @INV / @CTR integrity)
│   └── test_invariants.py
│
├── "mutation survival" (the green gate after dependency bumps)
│   └── test_mutation_survival.py
│
└── "the research_institution_provider plugin" (the @ADR-0007 slot filler)
    └── test_research_institution_provider.py
```

## The canonical validation commands

From the repo root:

```bash
# The full green gate (canonical wiring evidence).
RESEARCH_INSTITUTION_VWIRE_DIRECT=1 bash scripts/verify-institution.sh

# The full unit + integration test suite.
.venv/bin/python -m pytest -q

# Just the source-decision tests (plan-013 PR-C target).
.venv/bin/python -m pytest -q tests/test_source_decision_stagnation.py \
    tests/test_source_decision_contract.py \
    tests/test_wire_schema_unchanged.py

# Just the cross-repo type identity tests.
.venv/bin/python -m pytest -q tests/test_cross_repo_type_identity.py \
    tests/test_compose_work_selection.py \
    tests/test_os_provider_compose_proof.py
```

## Where new tests should land (semantic-repo doctrine)

When you add a new test, ask:

1. **Is it testing the catalog?** Add to `test_catalog.py`
   (or one of its siblings). Don't create a new test file
   for catalog content.
2. **Is it testing the dispatcher?** Add to `test_cli.py`
   or `test_dispatcher.py`. Don't create a new test file
   unless the test is genuinely a new surface (e.g. plan-013
   PR-C adds `test_source_decision_stagnation.py` for
   plan-013-specific behavior).
3. **Is it testing the wire format?** Add to
   `test_source_decision_contract.py` or one of its
   siblings. Don't fork.
4. **Is it testing a cross-repo contract?** Add to
   `test_cross_repo_type_identity.py`. The math + pi_monitor
   wire contracts live in math + pi_monitor; the
   research-institution-side mirror lives here.

If your test doesn't fit any of the existing files,
**ask first**. A new test file should be justified by a
genuine new surface, not by a casual choice of placement.

## See also

- `docs/README.md` — the 5-minute cold-start navigation index.
- `docs/operations/verification-gates.md` — the canonical
  validation command catalog.
- `docs/operations/plan-013-live-supervisor-authority.md` —
  the unified plan that adds the new test files.
