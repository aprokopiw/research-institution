#!/usr/bin/env python3
"""
collect-prime-directive-edits.py — COLLECT phase (snippet format).

Scans all 4 institution repos for prime-directive violations using
the strengthened pattern, and emits ONE big text file containing
every hit as a 3-line snippet (line-before, matched-line,
line-after) with file:line markers.

The user edits the snippet file in place — reword the matched line
to use a durable @ADR/@INV/@CTR anchor instead of the transient
literal. Then apply-prime-directive-edits.py reads the edited file
and substitutes each rewording back into the original source file.

USAGE:
  python3 scripts/collect-prime-directive-edits.py <out.txt>

OUTPUT FORMAT (text, designed for editing in any editor):

  >>> BEGIN SNIPPET repo=research-institution path=research_institution/cli.py line=42
  41 | # previous line for context
  42 | # plan-013 OS-side extension (rewritten line goes here)
  43 | # next line for context
  <<< END SNIPPET (match fingerprint: <sha256-hex-of-line-42>)

The apply step uses the fingerprint (sha256 of the original
matched line) to locate the right position in the source file even
if other edits have shifted line numbers. If the same fingerprint
appears at multiple positions in a file, the apply step aborts
with a clear diagnostic.

Sanctioned paths are exempt (see SANCTIONED_GLOBS).
"""

import hashlib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/.. -> institution root
REPOS = ["research-institution", "math", "pi_monitor", "kaplansky"]

# Strengthened prime-directive pattern (mirrors check-prime-directive.sh)
PRIME_DIRECTIVE_PATTERN = re.compile(
    r"(\b[Pp][Ll][Aa][Nn]|\b[Ss][Pp][Ee][Cc])[-_ ]?[0-9]{2,}"
)

# Sanctioned paths — exempt from collection. Mirrors check-prime-directive.sh
# plus math AGENTS.md classes #7, #15, #16, #17.
SANCTIONED_GLOBS = [
    "AGENTS.md",
    "/.pi-glla/",
    "/.agents/",
    "/.venv/",
    "/build/",
    "/__pycache__/",
    "/.git/",
    "/docs/operations/plan-",
    "-closure-audit.md",
    "-live-supervisor-authority.md",
    # Math spec-kit source-of-truth (AGENTS.md class #15)
    "/artifacts/temp/specs/",
    "/specs/002-canonical-research-state/",
    # Math plan-009 durable records + Phase U verification (class #16/17)
    "/docs/operations/plan-009-durable-records",
    "/docs/operations/plan-009-phase-u-stop-the-line",
    # Math prime-directive enforcement script itself (class #7)
    "/scripts/coherence/_metrics/d9_prime_directive_clean.py",
    # Math decoupling-history archives (historical extraction trace)
    "/docs/decoupling-history/",
    # Kaplansky RESUME.md names the active Spec Kit feature
    "/docs/RESUME.md",
    # Kaplansky spec-kit source-of-truth
    "/specs/",
    "/.specify/",
]


def is_sanctioned(path: str) -> bool:
    return any(s in path for s in SANCTIONED_GLOBS)


def is_inside_markdown_link(pos: int, line: str) -> bool:
    """Return True if pos is inside a markdown link's [text] or (target)."""
    for m in re.finditer(r"\[([^\]]*)\]\(([^)]*)\)", line):
        if m.start(1) <= pos < m.end(1):
            return True
        if m.start(2) <= pos < m.end(2):
            return True
    return False


def fingerprint(line: str) -> str:
    """Stable hash of the matched line content (used as snippet key)."""
    return hashlib.sha256(line.strip().encode("utf-8")).hexdigest()[:16]


def collect(repo_root: Path, repo_name: str, out):
    """Walk one repo; write each hit's 3-line snippet to out."""
    n_collected = 0
    n_skipped_sanctioned = 0
    n_skipped_link = 0
    n_skipped_overlap = 0

    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in (".py", ".md", ".toml", ".yaml", ".yml"):
            continue
        rel = str(path.relative_to(repo_root))
        if is_sanctioned(f"/{rel}"):
            n_skipped_sanctioned += 1
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        # Preserve line endings when emitting snippets so the apply step
        # can detect indent consistently. We use "\n" internally and
        # re-attach the original ending during apply.
        raw_lines = text.splitlines(keepends=True)
        line_texts = [r.rstrip("\n").rstrip("\r") for r in raw_lines]

        # First pass: collect all hit line numbers (for overlap detection).
        hit_lines: list[int] = []
        for line_no, line_text in enumerate(line_texts, start=1):
            if not PRIME_DIRECTIVE_PATTERN.search(line_text):
                continue
            matches = list(PRIME_DIRECTIVE_PATTERN.finditer(line_text))
            if all(is_inside_markdown_link(m.start(), line_text) for m in matches):
                continue
            hit_lines.append(line_no)

        hit_set = set(hit_lines)

        # Second pass: emit snippets. For each hit line, decide whether
        # its before-line and after-line are also hits; if so, replace
        # them with a placeholder so the human cannot accidentally edit
        # a context line that is itself somebody else's matched line.
        for line_no in hit_lines:
            line_text = line_texts[line_no - 1]
            fp = fingerprint(line_text)
            before_no = line_no - 1
            after_no = line_no + 1
            before_text = line_texts[before_no - 1] if before_no >= 1 else ""
            after_text = line_texts[after_no - 1] if after_no <= len(line_texts) else ""

            # If a context line is itself a hit, replace it with a
            # placeholder so the human doesn't accidentally edit it
            # (its own snippet block owns that line).
            if before_no in hit_set:
                before_display = "[context omitted: line %d is itself a hit — see its snippet]" % before_no
            else:
                before_display = before_text
            if after_no in hit_set:
                after_display = "[context omitted: line %d is itself a hit — see its snippet]" % after_no
            else:
                after_display = after_text

            print(f">>> BEGIN SNIPPET repo={repo_name} path={rel} line={line_no}", file=out)
            print(f"{before_no:5d} | {before_display}", file=out)
            print(f"{line_no:5d} | {line_text}", file=out)
            print(f"{after_no:5d} | {after_display}", file=out)
            print(f"<<< END SNIPPET (fingerprint: {fp})", file=out)
            print(file=out)
            n_collected += 1

    return n_collected, n_skipped_sanctioned, n_skipped_link, n_skipped_overlap


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <out.txt>", file=sys.stderr)
        sys.exit(1)
    out_path = Path(sys.argv[1])

    total_collected = 0
    total_sanctioned = 0
    total_link = 0
    total_overlap = 0

    with out_path.open("w", encoding="utf-8") as out:
        print("# Prime-directive snippet dump", file=out)
        print("#", file=out)
        print("# Each snippet is 3 lines (before | match | after) with file:line", file=out)
        print("# markers and a sha256 fingerprint for safe round-trip.", file=out)
        print("#", file=out)
        print("# To reword: edit ONLY the middle line (the matched one) in place.", file=out)
        print("# The before/after context lines are READ-ONLY. If a context", file=out)
        print("# line is itself a hit (overlap), it is replaced with a", file=out)
        print("# placeholder pointing at the snippet that owns it.", file=out)
        print("# To grandfather: prefix the middle line with 'KEEP: ' — the", file=out)
        print("#   apply step will leave that line untouched.", file=out)
        print("# To delete a snippet entirely: blank out the middle line.", file=out)
        print("#", file=out)
        print(file=out)

        for repo in REPOS:
            repo_root = REPO_ROOT / repo
            if not repo_root.is_dir():
                continue
            print(f"## repo: {repo}", file=out)
            print(file=out)
            n, ns, nl, no = collect(repo_root, repo, out)
            print(f"# {repo}: {n} snippet(s) collected, {ns} file(s) sanctioned, {nl} link-skipped, {no} overlap-suppressed", file=sys.stderr)
            total_collected += n
            total_sanctioned += ns
            total_link += nl
            total_overlap += no
            print(file=out)

    print(f"\ntotal: {total_collected} snippet(s) written to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
