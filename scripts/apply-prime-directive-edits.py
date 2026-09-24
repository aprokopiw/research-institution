#!/usr/bin/env python3
"""
apply-prime-directive-edits.py — APPLY phase (snippet format).

Reads the snippet file produced by collect-prime-directive-edits.py
(after human editing) and substitutes each rewording back into the
original source file.

For each snippet block:

  >>> BEGIN SNIPPET repo=<r> path=<p> line=<n>
   <n-1> | <line-1>
   <n>   | <line-N>           <-- the matched line, edited by the human
   <n+1> | <line+1>
  <<< END SNIPPET (fingerprint: <sha>)

The apply step:
  1. Locates line <n> in <r>/<p>. Reads its content; computes its
     fingerprint. If the computed fingerprint != snippet fingerprint,
     abort (the file has drifted; human must reconcile).
  2. Computes the "old content" (the line as it stands in the file
     right now, with original line ending) and the "new content"
     (line <n> from the snippet, with the same ending).
  3. Writes the change.

SPECIAL MARKERS:
  - 'KEEP: ' prefix on the middle line: skip that snippet (grandfather).
  - Empty middle line (whitespace only): delete the original line.

  - '[context omitted: line N is itself a hit — see its snippet]':
    A read-only context marker; the apply step ignores these.

USAGE:
  python3 scripts/apply-prime-directive-edits.py <snippets.txt> [--dry-run]

--dry-run: print what would change, but don't write files.

EXIT CODES:
  0  all changes applied successfully
  1  at least one snippet could not be applied (drift, ambiguous
     fingerprint, missing file) — aborts on first error to keep
     the tree recoverable via `git reset`
"""

import argparse
import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/.. -> institution root

SNIPPET_BEGIN = re.compile(r">>> BEGIN SNIPPET repo=(\S+) path=(\S+) line=(\d+)")
SNIPPET_END = re.compile(r"<<< END SNIPPET \(fingerprint: ([0-9a-f]+)\)")
LINE_FMT = re.compile(r"^\s*(\d+)\s*\|\s?(.*)$")


def fingerprint(line: str) -> str:
    return hashlib.sha256(line.strip().encode("utf-8")).hexdigest()[:16]


def parse_snippets(text: str):
    """Yield (repo, path, line_no, before, middle, after, expected_fp) for each snippet block."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m_begin = SNIPPET_BEGIN.match(lines[i])
        if not m_begin:
            i += 1
            continue
        repo = m_begin.group(1)
        path = m_begin.group(2)
        line_no = int(m_begin.group(3))

        # Next 3 lines: before, middle, after
        if i + 4 >= len(lines):
            print(f"FATAL: truncated snippet starting at line {i + 1}", file=sys.stderr)
            sys.exit(2)
        before_line = lines[i + 1]
        middle_line = lines[i + 2]
        after_line = lines[i + 3]

        m_before = LINE_FMT.match(before_line)
        m_middle = LINE_FMT.match(middle_line)
        m_after = LINE_FMT.match(after_line)
        if not (m_before and m_middle and m_after):
            print(f"FATAL: malformed snippet at line {i + 1}", file=sys.stderr)
            sys.exit(2)
        before = m_before.group(2)
        middle = m_middle.group(2)
        after = m_after.group(2)

        # 5th line: end marker with fingerprint
        m_end = SNIPPET_END.match(lines[i + 4])
        if not m_end:
            print(f"FATAL: missing END marker at snippet starting line {i + 1}", file=sys.stderr)
            sys.exit(2)
        expected_fp = m_end.group(1)

        yield repo, path, line_no, before, middle, after, expected_fp
        i += 6  # 1 BEGIN + 3 content + 1 END + 1 blank


def apply_to_file(path: Path, edits: list, dry_run: bool) -> tuple[int, int]:
    """Apply edits to a single file. Returns (applied_count, skipped_count).

    edits: list of dicts with keys: line_no, before (unused), middle (new text),
           after (unused), expected_fp, keep, delete.
    """
    raw = path.read_text(encoding="utf-8")
    raw_lines = raw.splitlines(keepends=True)

    # Compute fingerprint of every line for the ambiguity check
    line_fps = {i + 1: fingerprint(l.rstrip("\n").rstrip("\r"))
                for i, l in enumerate(raw_lines)}

    applied = 0
    skipped = 0

    # Sort DESCENDING so earlier line numbers stay valid during the apply
    sorted_edits = sorted(edits, key=lambda e: -e["line_no"])

    for edit in sorted_edits:
        line_no = edit["line_no"]
        expected_fp = edit["expected_fp"]
        middle = edit["middle"]
        keep = edit["keep"]
        delete = edit["delete"]

        if line_no < 1 or line_no > len(raw_lines):
            print(f"FATAL: {path}:{line_no} out of range", file=sys.stderr)
            sys.exit(2)

        current = raw_lines[line_no - 1]
        current_stripped = current.rstrip("\n").rstrip("\r")
        current_fp = line_fps[line_no]

        if current_fp != expected_fp:
            print(f"FATAL: {path}:{line_no} fingerprint mismatch", file=sys.stderr)
            print(f"  expected: {expected_fp}", file=sys.stderr)
            print(f"  actual:   {current_fp}  ({current_stripped[:80]!r})", file=sys.stderr)
            print(f"  -> file has drifted; resolve by hand", file=sys.stderr)
            sys.exit(2)

        if keep:
            skipped += 1
            if dry_run:
                print(f"  KEEP    {path}:{line_no}", file=sys.stderr)
            continue

        if delete:
            # Replace with empty line preserving ending
            ending = current[len(current_stripped):]
            new_line = ending
            action = "DELETE"
        else:
            # Preserve the original line ending on the new content
            ending = current[len(current_stripped):]
            new_line = middle + ending
            action = "REWRITE"

        if dry_run:
            print(f"  {action}  {path}:{line_no}", file=sys.stderr)
            print(f"    - {current_stripped[:120]!r}", file=sys.stderr)
            print(f"    + {middle[:120]!r}", file=sys.stderr)
        else:
            raw_lines[line_no - 1] = new_line
        applied += 1

    if not dry_run and applied > 0:
        path.write_text("".join(raw_lines), encoding="utf-8")

    return applied, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("snippets", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    text = args.snippets.read_text(encoding="utf-8")

    # Group edits by (repo, path)
    by_file: dict[tuple[str, str], list] = defaultdict(list)
    n_total = 0
    for repo, path, line_no, before, middle, after, expected_fp in parse_snippets(text):
        # Parse middle-line directives
        stripped_middle = middle.strip()
        if stripped_middle == "":
            # Empty middle line: delete the original
            keep, delete = False, True
            new_middle = ""
        elif stripped_middle.startswith("KEEP"):
            keep, delete = True, False
            new_middle = middle
        else:
            keep, delete = False, False
            new_middle = middle

        by_file[(repo, path)].append({
            "line_no": line_no,
            "before": before,
            "middle": new_middle,
            "after": after,
            "expected_fp": expected_fp,
            "keep": keep,
            "delete": delete,
        })
        n_total += 1

    n_files = len(by_file)
    n_keep = sum(1 for v in by_file.values() for e in v if e["keep"])
    n_delete = sum(1 for v in by_file.values() for e in v if e["delete"])
    n_rewrite = n_total - n_keep - n_delete

    print(f"loaded {n_total} snippet(s) across {n_files} file(s); "
          f"applying {n_rewrite} rewrite(s) + {n_delete} delete(s), "
          f"skipping {n_keep} KEEP", file=sys.stderr)
    if args.dry_run:
        print("--dry-run: no files will be written\n", file=sys.stderr)

    total_applied = 0
    total_skipped = 0
    for (repo, rel), edits in by_file.items():
        repo_root = REPO_ROOT / repo
        path = repo_root / rel
        if not path.exists():
            print(f"FATAL: {path} not found", file=sys.stderr)
            sys.exit(2)
        applied, skipped = apply_to_file(path, edits, args.dry_run)
        total_applied += applied
        total_skipped += skipped
        if applied > 0:
            print(f"  wrote {path} ({applied} change(s){', ' + str(skipped) + ' KEEP' if skipped else ''})", file=sys.stderr)

    print(f"\ntotal: {total_applied} applied, {total_skipped} KEEP", file=sys.stderr)


if __name__ == "__main__":
    main()
