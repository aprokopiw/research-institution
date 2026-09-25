# 03 — Plan

## Technical context

Third sister entry in the rationalization family. The kaplansky side
adds unique domain-specific evidence (the `programs/*.toml` schema
and work-selection reducer) atop the standard vocabulary work.

## Existing implementation to extend

- `kaplansky/pyproject.toml` — pytest configuration; thin.
- `kaplansky/Makefile` — has test target.
- `kaplansky/tests/` — flat, ~84 modules.
- `kaplansky/AGENTS.md` — Spec-Kit mode + cross-repo prevention
  layer; cross-ref amendments only.
- `kaplansky/programs/{…}` — schema source; untouched, but
  referenced by the new tests.
- `kaplansky/scripts/check-program-institution.sh` — wired to the
  canonical prime-directive script via symlink (per entry 00).
- `research-institution/.specify/memory/transient-exemptions.toml`
  — appends kaplansky rows.
- `research-institution/scripts/check-prime-directive.sh` —
  canonical, used at kaplansky HEAD.

## Components changed

| Path | Change |
|---|---|
| `kaplansky/pyproject.toml` | pytest config; tier markers. |
| `kaplansky/Makefile` | tier-routed + cleanup targets. |
| `kaplansky/tests/README.md` | rewrite by subsystem + tier. |
| `kaplansky/tests/static/{test_closed_tier_vocabulary.py,test_dependency_vocabulary.py,test_skip_xfail_baseline.py,skip_xfail_baseline.toml}` | new. |
| `kaplansky/tests/domain/{test_roadmap_schema_roundtrip,test_frozen_claims,test_palomar_provenance,test_modules,test_compute_registry}.py` | new (FR-5). |
| `kaplansky/tests/work_selection/{test_dependency_valid_operation,test_blocked_completion,test_stale_outcomes}.py` | new. |
| `kaplansky/tests/artifacts/test_artifact_integrity.py` | new. |
| `kaplansky/tests/plugin/{test_mathlint_provider,test_entry_point_collision}.py` | new. |
| `kaplansky/tests/launcher/test_institution_check.py` | new. |
| `kaplansky/tests/security/test_no_kaplansky_literal_in_siblings.py` | new. |
| `kaplansky/scripts/check-prime-directive.sh` | symlink (or byte-diff copy). |
| `kaplansky/AGENTS.md` | cross-ref amendment only. |
| `research-institution/.specify/memory/transient-exemptions.toml` | append kaplansky rows. |

## Components explicitly NOT changed

- `kaplansky/programs/*` (research content is frozen for this
  entry; entry 04 + 10 are the consumers).
- `kaplansky/src/kaplansky/*` (production code unchanged; entry
  04 + 06 may extend later).
- `kaplansky/paper/`, `kaplansky/mathematics/`, etc., are research
  artifacts — not touched.

## Repository ownership boundary

```
kaplansky            (test topology; static checks; domain /
                       work-selection / artifacts / plugin /
                       launcher / security tests; launcher wiring)
research-institution (transient-exemptions.toml kaplansky rows)
```

## Constitution Check (entry-03-specific)

- **§1, §2, §3, §5** — same as 01 / 02.
- **§7** — sample-program contract (referenced; entry 04 implements
  stateful sample; entry 03 just enforces the static contract
  including "frozen-claims are immutable").
- **§10** — canonical prime-directive script at kaplansky HEAD.
- **§11** — META emitted.

## Data and state migration

- `tests/static/skip_xfail_baseline.toml` — schema same as 01/02,
  kaplansky paths.
- Folder migration preserves `git log --follow`.

## Failure atomicity and rollback

- Folder migrations one commit per subdir; each commit green.
- Domain test modules are independent (each can be reverted
  alone).

## Security / credential impact

- `test_no_kaplansky_literal_in_siblings.py` is a structural check
  (no real-credential handling).
- `test_mathlint_provider.py` runs at install time only (entry
  04 / 06 own the install-time simulation; entry 03 only does a
  static-shape check).

## Performance / runtime budgets

- `pytest --collect-only --no-cov -q` ≤ 30 s.
- `make test-tier-fast` ≤ 5 min.
- The ten domain / work-selection modules combined ≤ 30 s.

## Test / evidence tier map (entry 03)

| Artifact | Tier |
|---|---|
| `test_closed_tier_vocabulary.py` | contract |
| `test_dependency_vocabulary.py` | contract |
| `test_skip_xfail_baseline.py` | contract |
| `test_roadmap_schema_roundtrip.py` | contract |
| `test_frozen_claims.py` | contract |
| `test_palomar_provenance.py` | contract |
| `test_modules.py` | contract |
| `test_compute_registry.py` | contract |
| `test_dependency_valid_operation.py` | unit (reducer pure function) |
| `test_blocked_completion.py` | unit |
| `test_stale_outcomes.py` | unit |
| `test_artifact_integrity.py` | unit + integration (filesystem; temp dir) |
| `test_mathlint_provider.py` | unit + property |
| `test_entry_point_collision.py` | integration |
| `test_institution_check.py` | integration |
| `test_no_kaplansky_literal_in_siblings.py` | contract |

`NOT_APPLICABLE` for `process` / `deployment` / `provider_live`
here — those land in entries 05 / 06 / 07 / 10.

## Gate integration

- VG-0 / VG-1 / VG-2: same as 01 / 02.
- VG-3: `make test-tier-fast` green.
- VG-4…VG-8: `NOT_APPLICABLE`.

## Documentation and durable-record changes

- New: ten test modules, three static checks, baseline TOML,
  launcher symlink, security static check.
- Amended: `pyproject.toml`, `Makefile`, `tests/README.md`,
  `AGENTS.md` cross-ref.
- New durable records: none. (Domain test coverage proves
  existing durable records; no new cross-repo anchors by 03.)

## Cross-repository compatibility

- The `test_no_kaplansky_literal_in_siblings.py` runs against
  `research-institution/src`, `math/src`, `pi_monitor/src` —
  read-only inspection.
- The `test_mathlint_provider.py` exercises a static install-time
  assertion only; no live install.

## Retirement / cleanup

- `make test-tier-cleanup` empties any orphan ambiguous-tier
  directory at completion SHA.
- `transient-exemptions.toml` rows seeded by 03 expire on this
  entry's id.
