---
id: CTR-0095
kind: contract
status: active
title: Prime-directive check-script contract — regex, sanctioned-globs, exit codes, selftest
introduced: 2026-09-25
related:
  - @ADR-0095-prime-directive-mechanical-enforcement
  - @INV-0095-prg-anchor-ownership
  - @CTR-0020-three-repo-wire-contract (math)
  - @ADR-0006-research-institution-scope
parties: research_institution (canonical owner), math + pi_monitor + kaplansky (consumers via symlink)
---

# CTR-0095: Prime-directive check-script contract

## Boundary

`research-institution/scripts/check-prime-directive.sh` is the
single canonical implementation of the institution-wide
prime-directive grep. Sibling repos invoke it through a
symlink at `<sibling>/scripts/check-prime-directive.sh` (or a
byte-diff-equivalent copy); the canonical text is not
duplicated. The script is the **only** entry point that both
the CI merge gate (`make check-prime-directive-enforced`) and
the runtime pi extension consult; both layers MUST agree on
the regex, the sanctioned-globs list, and the exit-code
semantics.

## Producer

`research-institution/scripts/check-prime-directive.sh`
(updated 2026-09-25 by spec `00-verify-constitution-ratification`).

## Required behaviour

### Strengthened regex

```
(\b[Pp][Ll][Aa][Nn]|\b[Ss][Pp][Ee][Cc])[-_ ]?[0-9]{2,}
```

Catches every variant agents write — `plan-013`,
`Plan-013`, `PLAN_013`, `plan013`, `Plan 002`,
`spec-011`, `Spec-009`, `spec 011`. Does **not** match
common English words (`planner`, `specify`, `planetary`,
`spec_kit`) because the `[Pp][Ll][Aa][Nn]` /
`[Ss][Pp][Ee][Cc]` letter classes anchor the pattern to
the precise plan/spec spelling and the `[-_ ]?[0-9]{2,}`
suffix requires two or more trailing digits with at most
one optional separator.

### Sanctioned-globs list

Substring matches against the absolute file path. A hit
inside any of the following directories is silently allowed:

```
/AGENTS.md
/docs/operations/
-closure-audit.md
-live-supervisor-authority.md
/.pi-glla/
/.agents/transient/
/.venv/
/build/
/__pycache__/
/.git/
/.specify/specs/
```

Sibling repos MAY add their own local sanctioned-globs in a
**separate** registry (`math/scripts/prime-directive-local.toml`
or similar) provided the canonical list above is a subset of
the local list; this entry does not extend the canonical list
beyond the AGENTS.md mandated paths.

### Exit codes

| Code | Mode | Meaning |
|---|---|---|
| `0` | default | clean or hits-printed-but-tolerated |
| `0` | `--enforce` | clean (no hits) |
| `1` | `--enforce` | one or more unsanctioned hits |
| `78` | `--help` / bad args | usage error (gate `BLOCKED`) |
| `0` | `--selftest` | canonical pattern present + sanctioned-globs recognised |

The `--selftest` mode emits one line beginning:

```
self-test ok: canonical grep present, sanctioned-globs recognised: <list>
```

followed by `pass` on success; failure modes are documented
inline in the script.

### Invocation contract

```
bash scripts/check-prime-directive.sh                # scan repo
bash scripts/check-prime-directive.sh <path>...      # scan paths
bash scripts/check-prime-directive.sh --enforce      # exit 1 on hit
bash scripts/check-prime-directive.sh --selftest     # cross-repo identity
bash scripts/check-prime-directive.sh --help         # usage
```

## Consumer

- **CI merge gate** — `make check-prime-directive-enforced`
  in each of the four repos runs the script under `--enforce`;
  exit 1 blocks merge.
- **Operator workflow** — `make check-prime-directive`
  (default mode) prints any hits for human review.
- **Cross-repo identity test** —
  `tests/static/test_canonical_script_identity.py`
  invokes `--selftest` in each of the four repos and asserts
  byte-equal output.

## Failure modes

| Mode | Symptom | Action |
|---|---|---|
| Regex drift | script accepts a transient literal that the extension rejects (or vice versa) | bump `@CTR-0095` schema version, update both layers atomically, add a regression test |
| Sanctioned-glob drift | one repo allows a path the others forbid | bump the canonical registry; sibling symlinks inherit |
| Sibling symlink drift | `<sibling>/scripts/check-prime-directive.sh` diverges from canonical | `make check-prime-directive-enforced` fails in the sibling; identity test fails |

## Cross-references

- `@ADR-0095-prime-directive-mechanical-enforcement` —
  the decision to centralise enforcement.
- `@INV-0095-prg-anchor-ownership` — durable anchor
  ownership rule.
- `.specify/memory/transient-exemptions.toml` — canonical
  exemption registry (pi extension mirror).
- `~/.pi/agent/extensions/prime-directive-guard.ts` —
  runtime enforcement; entry 09 finishes the bridge.
