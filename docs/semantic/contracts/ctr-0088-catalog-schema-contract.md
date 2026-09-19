---
id: CTR-0088
kind: contract
status: active
title: Institution catalog schema contract
introduced: 2026-09-19
related: [ADR-0091]
parties: institution catalog, mathlint, research programs
---
# CTR-0088: Institution catalog schema contract

## Boundary

Every entry in `catalog/programs.toml` MUST satisfy the
schema in `catalog/schema.toml`.

## Guarantees

Each `[[programs]]` entry has exactly nine required keys:

* `name` — unique, matches `^[a-z][a-z0-9_-]*$`.
* `display_name` — free-form human label.
* `repository` — git URL (https form).
* `entry_point` — `module:callable` under
  `mathlint.providers`.
* `local_path` — operator-local clone path; starts with
  `/` or `$HOME`.
* `mathlint_pin` — git ref-like (`^[A-Za-z0-9._/-]+$`).
* `live_credentials_required` — bool.
* `live_credential_env_vars` — list of env var names.
* `check_program_script` — path relative to program repo
  root, ends in `.sh`.

Cross-entry invariants:

* `name` is unique across all entries.
* `entry_point` module segments are unique across entries.
* `local_path` is absolute or `$HOME`-relative.
* `check_program_script` ends in `.sh`.

## Preconditions / assumptions

The catalog is a TOML document. Schema validation is
enforced by `tests/test_catalog_consistent.py`.

## Non-guarantees

The schema does not enforce runtime resolution of
`local_path` or `repository`; those are resolved at
green-gate time.

## Cross-references

* `@ADR-0091` — the program-agnostic mathlint contract
  (every program ships its own launcher).
* `catalog/schema.toml` — the schema source of truth.
* `tests/test_catalog_consistent.py` — the contract test.
