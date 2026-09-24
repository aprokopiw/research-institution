#!/usr/bin/env python3
"""
rewrite-snippets.py — bulk-rewrite the snippet file with safe token
substitutions.

Reads the snippet file and rewrites each middle line in place, BUT
preserves the contents of any markdown-link [text](target)
construct. Considers lines with 'pre-', 'post-', or 'historical' as
KEEP rather than rewriting.

Conservative rewrite rules:
  - "plan-NNN" -> "@ADR-XXXX"  (mapped per ANCHOR_MAP)
  - "spec-NNN" -> "@CTR-XXXX" or "@INV-XXXX"
  - Handles Plan-013, plan_013, plan013, Spec 014, etc.

KEEP cases (require human judgment):
  - Long historical-context paragraphs (>200 chars)
  - Pre-/post- comparisons (likely historical framing)
  - String literals (surrounded by quotes)

USAGE:
  python3 rewrite-snippets.py <snippets.txt> [--apply]

EXIT CODES: 0 ok, 1 error
"""

import argparse
import re
import sys
from pathlib import Path

ANCHOR_MAP = {
    "plan-005": "@ADR-0006", "plan-006": "@ADR-0011", "plan-007": "@ADR-0065",
    "plan-008": "@ADR-0088", "plan-009": "@ADR-0088", "plan-010": "@ADR-0088",
    "plan-011": "@ADR-0007", "plan-012": "@ADR-0088", "plan-013": "@ADR-0011",
    "spec-001": "@CTR-0001", "spec-002": "@CTR-0002", "spec-003": "@CTR-0003",
    "spec-004": "@INV-0007", "spec-005": "@CTR-0005", "spec-006": "@CTR-0005",
    "spec-007": "@ADR-0017", "spec-008": "@CTR-0075", "spec-009": "@CTR-0070",
    "spec-010": "@CTR-0012", "spec-011": "@CTR-0081", "spec-012": "@CTR-0081",
    "spec-013": "@CTR-0081", "spec-014": "@CTR-0081", "spec-015": "@CTR-0081",
}

# Build a regex that matches any variant of each token:
# plan-013 / Plan-013 / PLAN_013 / plan013 / Plan 013 / Spec 014, etc.
# The pattern allows zero-or-one of [-_ ] between word and digits.
TOKEN_PARTS = []
for token in sorted(ANCHOR_MAP.keys(), key=len, reverse=True):
    word, digits = token.split("-", 1)
    TOKEN_PARTS.append(rf"\b{word}[-_ ]?{digits}\b")
TOKEN_RE = re.compile("|".join(TOKEN_PARTS), re.IGNORECASE)


def token_to_anchor(match: re.Match) -> str:
    """Map a matched variant (e.g. 'Spec 014') to its canonical anchor."""
    text = match.group(0).lower()
    # Normalize: 'plan 013' -> 'plan-013', 'plan013' -> 'plan-013', 'Plan-013' -> 'plan-013'
    m = re.match(r"(\w+)[-_ ]?(\d+)", text)
    if not m:
        return match.group(0)
    canonical = f"{m.group(1)}-{m.group(2)}"
    return ANCHOR_MAP.get(canonical, match.group(0))


def is_safe_to_rewrite(line_text: str) -> bool:
    """Conservative: skip if any of these conditions hold."""
    if len(line_text) > 200:
        return False
    if re.search(r"\bpre-plan\b|\bpost-plan\b|\bpre-spec\b|\bpost-spec\b", line_text, re.IGNORECASE):
        return False
    if line_text.lstrip().startswith("#") and re.search(r"historical|rationale|context", line_text, re.IGNORECASE):
        return False
    # String-literal heuristic: lots of quote marks -> likely a fixture
    if line_text.count('"') >= 4 or line_text.count("'") >= 4:
        return False
    return True


def rewrite_preserving_links(line_text: str) -> str:
    """Apply TOKEN_RE.sub only OUTSIDE markdown-link [text](target) constructs."""
    # Find every markdown-link span
    segments = []
    last = 0
    for m in re.finditer(r"\[[^\]]*\]\([^)]*\)", line_text):
        # Apply rewrite to the gap before this link
        segments.append(TOKEN_RE.sub(token_to_anchor, line_text[last:m.start()]))
        # Keep the link untouched
        segments.append(m.group(0))
        last = m.end()
    # Trailing segment
    segments.append(TOKEN_RE.sub(token_to_anchor, line_text[last:]))
    return "".join(segments)


SNIPPET_BEGIN = re.compile(r">>> BEGIN SNIPPET repo=(\S+) path=(\S+) line=(\d+)")
LINE_FMT = re.compile(r"^\s*(\d+)\s*\|\s?(.*)$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("snippets", type=Path)
    ap.add_argument("--apply", action="store_true",
                    help="actually write the file (default: dry-run)")
    args = ap.parse_args()

    text = args.snippets.read_text(encoding="utf-8")
    lines = text.splitlines()

    n_rewritten = 0
    n_kept = 0
    n_unchanged = 0

    out: list[str] = []
    i = 0
    while i < len(lines):
        m = SNIPPET_BEGIN.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue

        out.append(lines[i])
        i += 1
        if i + 2 >= len(lines):
            out.append(lines[i])
            break

        before_line = lines[i]
        middle_line = lines[i + 1]
        after_line = lines[i + 2]

        m_mid = LINE_FMT.match(middle_line)
        if not m_mid:
            out.extend([before_line, middle_line, after_line])
            i += 3
            continue

        line_no = int(m_mid.group(1))
        mid_text = m_mid.group(2)

        if not is_safe_to_rewrite(mid_text):
            new_middle = f"{line_no:5d} | KEEP: {mid_text}"
            out.extend([before_line, new_middle, after_line])
            n_kept += 1
        else:
            # Rewrite, but protect markdown-link constructs
            new_mid_text = rewrite_preserving_links(mid_text)
            if new_mid_text == mid_text:
                out.extend([before_line, middle_line, after_line])
                n_unchanged += 1
            else:
                new_middle = f"{line_no:5d} | {new_mid_text}"
                out.extend([before_line, new_middle, after_line])
                n_rewritten += 1

        i += 3
        if i < len(lines):
            out.append(lines[i])  # END marker
            i += 1
        if i < len(lines):
            out.append(lines[i])  # blank
            i += 1

    print(f"rewrite summary:")
    print(f"  rewritten:  {n_rewritten}")
    print(f"  kept (KEEP): {n_kept}")
    print(f"  unchanged:  {n_unchanged}")

    if args.apply:
        args.snippets.write_text("\n".join(out) + "\n", encoding="utf-8")
        print(f"\nwrote {args.snippets}")
    else:
        print(f"\n--dry-run (use --apply to write)")


if __name__ == "__main__":
    main()
