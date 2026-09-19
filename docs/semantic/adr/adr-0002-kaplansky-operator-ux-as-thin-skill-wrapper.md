---
id: ADR-0002
kind: decision
status: accepted
title: Kaplansky operator UX is a thin pi-skill wrapper over launch/stop/watch scripts
date: 2026-09-13
related:
  - catalog/programs.toml
  - scripts/launch-program.sh
  - scripts/stop-program.sh
  - scripts/watch-program.sh
  - docs/operations/kaplansky-operator-ux.md
supersedes: []
---

# ADR-0002: Kaplansky operator UX is a thin pi-skill wrapper over launch/stop/watch scripts

## Context

The operator wants `@start_kaplansky`, `@end_kaplansky`, `@kaplansky_status` as one-keystroke invocations during a research run. Two paths exist:

1. **Reimplement the operator UX as a new Python/CLI tool.** Duplicates the catalog-driven launch logic that already lives in `scripts/launch-program.sh` (9-step PP-Y.1 launch UX per `@INV-0098`).
2. **Wrap the existing scripts as pi skills.** Skills are markdown files with a frontmatter `name` + `description`; pi discovers them under `~/.pi/agent/skills/` and exposes them as commands. The wrapper is documentation-only.

The launch/stop/watch scripts are already the canonical operator surface — the bootstrap README and `@INV-0093` point at them. A wrapper that bypasses them creates two competing paths.

## Decision

Each kaplansky operator command is a single markdown file under
`research-institution/skills/kaplansky/`. The file contains the
frontmatter pi needs plus a short pointer to the existing shell script:

- `start_kaplansky.md` → `scripts/launch-program.sh kaplansky`
- `end_kaplansky.md` → `scripts/stop-program.sh kaplansky`
- `kaplansky_status.md` → `scripts/watch-program.sh kaplansky --once`

`scripts/install-kaplansky-skills.sh` symlinks the three files into
`~/.pi/agent/skills/` (idempotent). The wrapper markdown carries no executable
logic — it documents the script invocation, the exit codes, and the
cross-references. The shell script remains the authoritative implementation.

## Rationale

- One operator surface, two access modes: skills for in-pi invocation, the
  script for direct shell use. No drift between them.
- The launch/stop/watch scripts already enforce catalog invariants
  (`@INV-0098`, `@CTR-0088`); duplicating that logic in skills would create a
  second source of truth.
- Skills-as-markdown costs zero maintenance: changing behavior means editing
  the existing shell script, not three skill files.
- Symlinks (not copies) keep the skill files inside the repo where they
  belong; `git status` shows the canonical version.

## Alternatives considered

- **Embed the operator commands as pi prompt-template entries.** Rejected:
  prompt templates are for prompting, not for invoking shell scripts.
- **Publish the skills as a separate npm/pip package.** Rejected: the
  research-institution repo is the natural owner; a package adds distribution
  friction for zero operator benefit.
- **Use one combined `kaplansky.md` skill with subcommands.** Rejected: pi's
  skill loader treats each `.md` file as a discrete skill; a single skill
  forces the operator to type `/skill:kaplansky start` and loses the
  one-keystroke UX.

## Consequences

- `scripts/install-kaplansky-skills.sh` must be run once after a fresh
  checkout; the bootstrap README calls this out.
- Removing a skill is `rm ~/.pi/agent/skills/<name>`; no repo cleanup needed
  beyond `git rm` of the markdown file.
- Future programs added to the catalog SHOULD follow the same pattern: a
  thin skill directory under `research-institution/skills/<program>/` whose
  files point at the matching `scripts/launch-program.sh <program>` etc.
- The wrapper markdown MUST NOT execute side effects on load (per pi's skill
  contract); it documents invocations only.

## Change triggers

Revisit if:

- pi's skill discovery rules change such that `~/.pi/agent/skills/<name>.md`
  no longer registers as a slash command.
- The launch/stop/watch scripts are replaced by a single binary that is
  called directly without subcommand dispatch (then skills can `exec` it).
- A new operator command emerges that does not map onto launch/stop/watch
  (e.g. "rotate kaplansky logs"); add a new skill file, do not overload
  these three.
