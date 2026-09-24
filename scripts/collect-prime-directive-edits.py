#!/usr/bin/env python3
"""
collect-prime-directive-edits.py — COLLECT phase.

Scans all 4 institution repos for prime-directive violations
(strengthened pattern) and emits a JSONL file where each record
identifies the hit and proposes a new_text based on the canonical
durable-anchor mapping.

The human-edited JSONL is consumed by apply-prime-directive-edits.py.

USAGE:
  bash scripts/collect-prime-directive-edits.py <out.jsonl>

The canonical mapping lives in this file. Each entry is:
  (regex_pattern, replacement_template, anchor_id, rationale)

The regex is applied to the matched line. If the result differs from
the original, that's the proposed new_text. If the regex doesn't
match, the record is emitted with new_text == match (caller must
hand-edit). Records with keep=True in the JSONL are grandfathered
during apply (no rewrite).

OUTPUT JSONL SHAPE (one record per line):
  {
    "repo": str,
    "path": str,
    "line": int,                  # 1-indexed editor line number
    "match": str,                 # the original line (stripped)
    "new_text": str,              # the proposed replacement
    "anchor": str | null,         # the durable anchor that justifies the rewrite
    "rationale": str | null,
    "keep": bool,                 # True = grandfather (no rewrite); defaults False
    "applied": False              # set to True by apply script
  }

The apply script sorts records per-file by line descending and
rewrites lines in-place. Collision-safe.
"""

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # research-institution/scripts/.. -> institution root
REPOS = ["research-institution", "math", "pi_monitor", "kaplansky"]

# Strengthened prime-directive pattern (mirrors check-prime-directive.sh)
PRIME_DIRECTIVE_PATTERN = re.compile(
    r"(\b[Pp][Ll][Aa][Nn]|\b[Ss][Pp][Ee][Cc])[-_ ]?[0-9]{2,}"
)

# Sanctioned-path globs (mirrors check-prime-directive.sh)
SANCTIONED_GLOBS = [
    "AGENTS.md",
    "/.pi-glla/",
    "/.agents/",
    "/.venv/",
    "/build/",
    "/__pycache__/",
    "/.git/",
    # Closure audits and plan docs are themselves sanctioned
    "/docs/operations/plan-",
    "-closure-audit.md",
    "-live-supervisor-authority.md",
]


def is_sanctioned(path: str) -> bool:
    """Return True if the path is exempt from the prime-directive grep."""
    return any(s in path for s in SANCTIONED_GLOBS)


# Canonical rewriting rules. Order matters: most-specific first.
# Each tuple: (regex, replacement, anchor, rationale)
#
# NOTE: replacements use the durable-anchor form. The apply step writes
# the proposed new_text verbatim, so if the regex captures surrounding
# prose it will be preserved.
SUBSTITUTIONS = [
    # spec-NNN -> @CTR-NNNN or @INV-NNNN (math contract/invariant anchors)
    (re.compile(r"\bspec-011 T005\b"), "spec-011 T005 gate (per @CTR-0081)", "@CTR-0081", "spec-011 hardening gate -> @CTR-0081"),
    (re.compile(r"\bspec-011\b(?!\s*T0)"), "spec-011 (per @CTR-0081-state-machine-hardening-pytest-marker)", "@CTR-0081", "spec-011 wire contract -> @CTR-0081"),
    (re.compile(r"\bspec-010\b"), "spec-010 (per @CTR-0012-observability-views)", "@CTR-0012", "spec-010 observability -> @CTR-0012"),
    (re.compile(r"\bspec-009 FR-023\b"), "spec-009 FR-023 (per @CTR-0070-restartable-supervisor-contract)", "@CTR-0070", "spec-009 FR-023 idempotency -> @CTR-0070"),
    (re.compile(r"\bspec-009\b"), "spec-009 (per @CTR-0070-restartable-supervisor-contract)", "@CTR-0070", "spec-009 supervisor cycle -> @CTR-0070"),
    (re.compile(r"\bspec-008\b"), "spec-008 (per @CTR-0075-worker-launcher-port-implementation-contract)", "@CTR-0075", "spec-008 typed authority -> @CTR-0075"),
    (re.compile(r"\bspec-007\b"), "spec-007 (per @ADR-0017-budgets-and-accounting)", "@ADR-0017", "spec-007 budgets -> @ADR-0017"),
    (re.compile(r"\bspec-005 T005\b"), "spec-005 T005 (per @CTR-0005-transition-plans-and-effects)", "@CTR-0005", "spec-005 T005 -> @CTR-0005"),
    (re.compile(r"\bspec-005\b"), "spec-005 (per @CTR-0005-transition-plans-and-effects)", "@CTR-0005", "spec-005 transition plans -> @CTR-0005"),
    (re.compile(r"\bspec-004 FR-024\b"), "spec-004 FR-024 (per @INV-0007-atomic-revision-bound-commit)", "@INV-0007", "spec-004 FR-024 launch intent -> @INV-0007"),
    (re.compile(r"\bspec-004\b"), "spec-004 (per @INV-0007-atomic-revision-bound-commit)", "@INV-0007", "spec-004 atomic revision -> @INV-0007"),
    (re.compile(r"\bspec-003\b"), "spec-003 (per @CTR-0003-semantic-event-envelope)", "@CTR-0003", "spec-003 ask step -> @CTR-0003"),
    (re.compile(r"\bspec-002\b"), "spec-002 (per @CTR-0002-canonical-snapshot-and-schema)", "@CTR-0002", "spec-002 canonical snapshot -> @CTR-0002"),
    (re.compile(r"\bspec-001\b"), "spec-001 (per @CTR-0001-finish-and-mediated-intake)", "@CTR-0001", "spec-001 finish submission -> @CTR-0001"),
    # plan-NNN -> durable anchors
    (re.compile(r"\bplan-013 PR-([A-D])\b"), r"plan-013 PR-\1 (no-delta loop fix per @ADR-0011)", "@ADR-0011", "plan-013 PR-X -> @ADR-0011"),
    (re.compile(r"\bplan-013\b"), "plan-013 (no-delta loop fix per @ADR-0011 + @INV-0094)", "@ADR-0011", "plan-013 provenance -> @ADR-0011"),
    (re.compile(r"\bplan-011\b"), "plan-011 (research-institution portability per @ADR-0007 + @INV-0093)", "@ADR-0007", "plan-011 portability -> @ADR-0007"),
    (re.compile(r"\bplan-009\b"), "plan-009 (spec wiring; see @ADR-0088 + @CTR-0075)", "@CTR-0075", "plan-009 spec wiring -> @CTR-0075"),
    (re.compile(r"\bplan-008\b"), "plan-008 (pyramid inversion; see @ADR-0088)", "@ADR-0088", "plan-008 pyramid inversion -> @ADR-0088"),
    (re.compile(r"\bplan-007\b"), "plan-007 (truth-bearing callsite; see @ADR-0065)", "@ADR-0065", "plan-007 truth-bearing callsite -> @ADR-0065"),
    (re.compile(r"\bplan-005\b"), "plan-005 (research-institution foundation; see @ADR-0006)", "@ADR-0006", "plan-005 -> @ADR-0006"),
    (re.compile(r"\bplan-006\b"), "plan-006 (postgres coordination; see @ADR-0011)", "@ADR-0011", "plan-006 -> @ADR-0011"),
    # Capitalized variants
    (re.compile(r"\bPlan-013\b"), "Plan-013 (no-delta loop fix per @ADR-0011 + @INV-0094)", "@ADR-0011", "Plan-013 capitalized -> @ADR-0011"),
    (re.compile(r"\bPLAN-013\b"), "PLAN-013 (no-delta loop fix per @ADR-0011 + @INV-0094)", "@ADR-0011", "PLAN-013 upper -> @ADR-0011"),
    (re.compile(r"\bPlan 013\b"), "Plan 013 (no-delta loop fix per @ADR-0011 + @INV-0094)", "@ADR-0011", "Plan 013 space -> @ADR-0011"),
    (re.compile(r"\bPlan 002\b"), "Plan 002 (no-delta loop fix per @ADR-0011 + @INV-0094)", "@ADR-0011", "Plan 002 space -> @ADR-0011"),
]


def propose_new_text(original_line: str) -> tuple[str, str | None, str | None]:
    """Run the substitution rules in order; return (new_text, anchor, rationale).

    If no rule fires, return (original_line, None, None) — caller must
    hand-edit the new_text.
    """
    for rx, repl, anchor, rationale in SUBSTITUTIONS:
        new = rx.sub(repl, original_line)
        if new != original_line:
            return new, anchor, rationale
    return original_line, None, None


def collect_hits(repo_root: Path, repo_name: str):
    """Walk one repo, yielding (path, line_no, line_text) for every hit."""
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in (".py", ".md", ".toml", ".yaml", ".yml"):
            continue
        rel = str(path.relative_to(repo_root))
        if is_sanctioned(f"/{rel}"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, line in enumerate(text.splitlines(keepends=False), start=1):
            if PRIME_DIRECTIVE_PATTERN.search(line):
                yield rel, line_no, line


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <out.jsonl>", file=sys.stderr)
        sys.exit(1)
    out_path = Path(sys.argv[1])

    records = []
    for repo in REPOS:
        repo_root = REPO_ROOT / repo
        if not repo_root.is_dir():
            print(f"  skipping {repo}: not found", file=sys.stderr)
            continue
        print(f"  collecting {repo} ...", file=sys.stderr)
        count = 0
        for rel, line_no, line in collect_hits(repo_root, repo):
            new_text, anchor, rationale = propose_new_text(line)
            records.append({
                "repo": repo,
                "path": rel,
                "line": line_no,
                "match": line,
                "new_text": new_text,
                "anchor": anchor,
                "rationale": rationale,
                "keep": False,
                "applied": False,
            })
            count += 1
        print(f"    {count} hit(s)", file=sys.stderr)

    with out_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"\nwrote {len(records)} record(s) to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
