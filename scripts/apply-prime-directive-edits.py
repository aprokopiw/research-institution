#!/usr/bin/env python3
"""
apply-prime-directive-edits.py — APPLY phase.

Reads the JSONL produced by collect-prime-directive-edits.py (after
human review) and applies the rewrites back to the original files.

Apply rules:
  - Records with keep=True are skipped (grandfathered; no rewrite).
  - Records with applied=True are skipped (already done; idempotent).
  - new_text must differ from match (else skip with a warning).
  - Edits within a single file are applied in DESCENDING line order
    so that line numbers of un-applied edits remain valid.
  - On any error (file not found, line doesn't match), abort and
    print a clear diagnostic. Don't half-apply.

USAGE:
  bash scripts/apply-prime-directive-edits.py <in.jsonl> [--dry-run]

--dry-run: print what would be applied without writing any files.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # research-institution/scripts/.. -> institution root


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", type=Path)
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be applied without writing")
    args = ap.parse_args()

    # Read all records, group by file
    by_file: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for line_no, raw in enumerate(args.jsonl.read_text(encoding="utf-8").splitlines(), start=1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"FATAL: invalid JSON at line {line_no}: {e}", file=sys.stderr)
            print(f"  raw: {raw[:200]}", file=sys.stderr)
            sys.exit(2)
        # Validate shape
        for k in ("repo", "path", "line", "match", "new_text", "keep", "applied"):
            if k not in rec:
                print(f"FATAL: record missing key {k!r} at line {line_no}", file=sys.stderr)
                sys.exit(2)
        by_file[(rec["repo"], rec["path"])].append(rec)

    n_files = len(by_file)
    n_edits = sum(len(v) for v in by_file.values())
    n_skipped_keep = sum(1 for v in by_file.values() for r in v if r["keep"])
    n_skipped_applied = sum(1 for v in by_file.values() for r in v if r["applied"])
    n_to_apply = n_edits - n_skipped_keep - n_skipped_applied
    print(f"loaded {n_edits} edit(s) across {n_files} file(s); "
          f"applying {n_to_apply} (skipping {n_skipped_keep} keep, "
          f"{n_skipped_applied} applied)", file=sys.stderr)

    if args.dry_run:
        print("--dry-run: no files written", file=sys.stderr)

    for (repo, rel), recs in by_file.items():
        repo_root = REPO_ROOT / repo
        path = repo_root / rel
        if not path.exists():
            print(f"FATAL: {path} not found", file=sys.stderr)
            sys.exit(2)

        original_text = path.read_text(encoding="utf-8")
        lines = original_text.splitlines(keepends=True)

        # Filter to records we'll actually apply, sort DESCENDING by line
        to_apply = [r for r in recs if not r["keep"] and not r["applied"] and r["new_text"] != r["match"]]
        if not to_apply:
            continue
        to_apply.sort(key=lambda r: -r["line"])

        # Apply from the bottom up so earlier line numbers stay valid
        for r in to_apply:
            line_no = r["line"]
            expected = r["match"]
            if line_no < 1 or line_no > len(lines):
                print(f"FATAL: {path}:{line_no} out of range", file=sys.stderr)
                sys.exit(2)
            current = lines[line_no - 1]
            current_stripped = current.rstrip("\n").rstrip("\r")
            if current_stripped != expected:
                # Tolerate trailing whitespace differences
                if current_stripped.rstrip() != expected.rstrip():
                    print(f"FATAL: {path}:{line_no} content mismatch", file=sys.stderr)
                    print(f"  expected: {expected!r}", file=sys.stderr)
                    print(f"  actual:   {current_stripped!r}", file=sys.stderr)
                    sys.exit(2)
            # Preserve original line ending
            ending = current[len(current_stripped):]
            new_line = r["new_text"] + ending
            if args.dry_run:
                print(f"  WOULD edit {path}:{line_no}", file=sys.stderr)
                print(f"    - {expected!r}", file=sys.stderr)
                print(f"    + {r['new_text']!r}", file=sys.stderr)
            else:
                lines[line_no - 1] = new_line

        if not args.dry_run:
            new_text = "".join(lines)
            # Guard: ensure the rewrite actually changed something
            if new_text == original_text:
                print(f"WARN: {path} unchanged after apply (lines matched but text identical?)", file=sys.stderr)
                continue
            path.write_text(new_text, encoding="utf-8")
            print(f"  wrote {path} ({len(to_apply)} edit(s))", file=sys.stderr)

    print("\ndone.", file=sys.stderr)


if __name__ == "__main__":
    main()
