# 00 — Data Model

This entry introduces three machine-checkable artifacts. The other
specs and the static checks below operate on these schemas.

## 1. `constitution-verify.md` (Markdown + parseable section structure)

A Markdown file with:

- Top-level metadata (YAML in frontmatter or Markdown bullet block):
  - `Version: <SemVer>`
  - `Ratified: <ISO 8601 date | "pending">`
  - `Last amended: <ISO 8601 date | "pending">`
  - `Owner repository: research-institution`
- Twelve top-level `## §N` sections (each carrying a Statement, a
  numbered list of Sub-Rules (S§N.M), and a "Linked durable anchors"
  bullet list).
- A `## Governance` section.

Self-test (`tests/static/test_constitution_consistency.py`) verifies:

- file exists at
  `research-institution/.specify/memory/constitution-verify.md`;
- file contains all twelve `## §0`…`## §12` headers plus `## Governance`;
- top metadata is present and parseable;
- for every `@ADR-NNNN`, `@INV-NNNN`, `@CTR-NNNN`, `@CON-NNNN`
  reference in §N sub-rules, the same ID appears in the cross-repo
  registry (`research-institution/docs/semantic/SEMANTIC_REGISTRY.md`)
  or in a per-repo `docs/semantic/{adr,invariants,contracts}/<id>-…md`
  file;
- `**Version:**` line equals the version stored in the registry
  ratchet.

## 2. `transient-exemptions.toml` (TOML registry of every sanctioned-transient form institution-wide)

Schema:

```toml
version = "0.0.0"            # SemVer of the registry; bump on edit
generated_by = "00-verify-constitution-ratification"

[[exemption]]
id = "ag-agents-md-institution-prevention"
repos = ["research-institution", "math", "pi_monitor", "kaplansky"]
path_pattern = "/AGENTS.md"
why = "Rule-naming document; defines the rule itself."
delete_when = "never (rule-naming document retains the rule forever)"
expiry_spec_id = null

[[exemption]]
id = "math-ag-22-kaplansky-grandfather-list"
repos = ["math"]
path_pattern = "src/mathlint/cli/apps.py"
# (and the other six files enumerated in math AGENTS §22)
delete_when = "all seven files removed in same commit"
expiry_spec_id = "04-stateful-sample-research"  # entry that retires the
                                                  # grandfather per
                                                  # @ADR-0091 cleanup

# … additional rows per repo …
```

Fields:

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Stable id for the row (kebab-case). |
| `repos` | yes | Set of repos where this exemption applies. |
| `path_pattern` | yes | Glob-like substring matched against file absolute path. |
| `why` | yes | One-sentence rationale. |
| `delete_when` | yes | Sentence describing the deletion-coupling trigger. |
| `expiry_spec_id` | yes | The entry ID (slugs like `04-stateful-sample-research`) that retires this row. `null` for rule-naming docs. |
| `added_by_commit` | yes | SHA of the commit that added this row. |
| `retired_by_commit` | optional | Set when the row retires; required to retire. |

Self-test verifies:

- TOML parses (`tomllib.loads(...)`);
- `version` is a SemVer string;
- every row has all required fields;
- for each row, the `path_pattern` matches at least one real file
  in each named repo (cross-checked with `Path.rglob` /
  `pathlib.Path.exists()` — symlinks resolved);
- the `retired_by_commit`, if set, is a real git commit reachable
  from `HEAD`.

Future entry 09 consumes this registry: the runtime extension loads
it on every workspace open; the canonical CI script emits the
diff-vs-registry on each run.

## 3. `META.md` (per-entry audit-close artifact)

Top-of-file TOML frontmatter; body in Markdown.

Frontmatter keys:

| Key | Type | Required | Meaning |
|---|---|---|---|
| `spec_id` | string | yes | Zero-padded `NN-slug` (e.g. `00-verify-constitution-ratification`); matches dir name. |
| `owner_repo` | string | yes | Single owner repo (most-common case). |
| `owner_repos` | array | yes (set) | Always present (single-element set when `owner_repo == owner_repos`). |
| `baseline_sha` | string | yes | The HEAD SHA at the moment the spec's tasks begin. |
| `completion_sha` | string | yes | The HEAD SHA at META emission. |
| `gate_report_digest` | string | yes | `sha256:` prefix + 64-hex digest of the gate-report blob. |
| `durable_anchors_added` | array | yes | List of `@…` records introduced by this entry. |
| `durable_anchors_cited` | array | yes | List of `@…` records cited from this entry's artifacts. |
| `transient_anchors_retired` | array | yes | List of `{id, retired_by_commit}` pairs. |
| `unblocked_dependents` | array | yes | List of `NN-slug` strings (or `HOLD:` annotations). |
| `constitution_compliance` | object | yes | Map: `constitution_0…12: "PASS" | "FAIL" | "NOT_APPLICABLE"` keyed by §-number. |

`constitution.md` §11.2 carries the canonical schema; entry 09 adds
the validator.

### Cross-repo attestation artifact

Each entry is also reflected in a per-repo
`.pi-prime-attestations/<spec-id>.json`. The format is initially
declared here (entry 09 finishes its machinery):

```json
{
  "schema_version": "0.0.0",
  "spec_id": "00-verify-constitution-ratification",
  "owner_repo": "research-institution",
  "completion_sha": "<sha>",
  "config_fingerprint": "<sha256 over research-institution/research_institution/config.py>",
  "digest": "<sha256 over (completion_sha || config_fingerprint)>",
  "gate_report_blob": "<path>",
  "signed_off_by": "<operator or ci-bot name>"
}
```

The attestation **is the canonical machine-checked evidence** that
the entry met its `Cannot claim done when…` clauses. Tasks in M5
emit it; tasks in dependent entries read it.

---

## Cross-references

- `constitution-verify.md` §11 (audit-close-out schema).
- `constitution-verify.md` §3 (gate-status algebra).
- `transient-exemptions.toml` precedent:
  `research-institution/.specify/memory/type-escapes.toml` (TOML
  format).
- Future consumer: entry 09
  (`prime-directive-mechanical-enforcement`) wires the registry
  into the runtime extension.
