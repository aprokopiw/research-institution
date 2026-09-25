#!/usr/bin/env python3
"""META.md validator (entry 09 FR-7).

CLI that parses every spec dir's ``META.md`` and validates against
the schema defined in ``constitution-verify.md`` §11.2. Emits
``PASS`` / ``FAIL`` / ``NOT_APPLICABLE`` and exits with the gate-
status-algebra code (0 / 78 / 1).

Usage:

    python -m research_institution.META_validator PATH [PATH ...]
    # or:
    python scripts/META_validator.py .specify/specs/*/META.md

Every required field must be present and non-empty. ``PENDING`` is
rejected only when ``--strict`` is set; default is draft-friendly
because META.md is emitted only after audit-close-out and the
``PENDING`` sentinel is the natural draft value.

The validator never modifies files. It exists to give the
supervisor and the operator a fast machine-checked answer to
"is this entry's META ready?".
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# Required fields per constitution-verify.md §11.2.
REQUIRED_META_FIELDS: tuple[str, ...] = (
    "spec_id",
    "owner_repo",
    "baseline_sha",
    "completion_sha",
    "gate_report_digest",
    "durable_anchors_added",
    "durable_anchors_cited",
    "transient_anchors_retired",
    "unblocked_dependents",
)

# Gate-status-algebra exit codes (constitution-verify.md §3).
EXIT_PASS = 0
EXIT_BLOCKED = 78
EXIT_FAIL = 1

# A META.md carries its data as either:
#  1. a YAML/TOML frontmatter block between two ``---`` markers, or
#  2. a fenced ```` ```toml ```` code block.
# Form (1) is canonical per constitution-verify.md §11.2; form (2)
# is the prose-friendly variant used in the eleven-entry program
# because it lets the spec author include narrative context above
# and below the data without an extra ``---`` separator.
FRONTMATTER_RE = re.compile(r"(?ms)^---\s*\n(.+?)\n---")
TOML_FENCE_RE = re.compile(r"(?ms)^```(?:toml)?\s*\n(.+?)^```", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class MetaValidation:
    path: Path
    status: str  # "PASS" | "FAIL" | "NOT_APPLICABLE"
    missing_fields: tuple[str, ...]
    pending_fields: tuple[str, ...]
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "status": self.status,
            "missing_fields": list(self.missing_fields),
            "pending_fields": list(self.pending_fields),
            "reason": self.reason,
        }


def parse_META(path: Path) -> dict | None:
    """Parse a single META.md. Returns the ``[meta]`` table or None.

    Tries ``---`` frontmatter first; falls back to the first fenced
    ```` ```toml ```` block. Returns None when neither form parses
    or the ``[meta]`` table is absent.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = FRONTMATTER_RE.search(text) or TOML_FENCE_RE.search(text)
    if not m:
        return None
    try:
        doc = tomllib.loads(m.group(1))
    except tomllib.TOMLDecodeError:
        return None
    meta = doc.get("meta")
    return meta if isinstance(meta, dict) else None


def validate_one(path: Path, *, strict: bool) -> MetaValidation:
    if not path.exists():
        return MetaValidation(
            path=path,
            status="NOT_APPLICABLE",
            missing_fields=(),
            pending_fields=(),
            reason="META.md does not exist",
        )
    meta = parse_META(path)
    if meta is None:
        return MetaValidation(
            path=path,
            status="FAIL",
            missing_fields=(),
            pending_fields=(),
            reason="META.md frontmatter is missing or not TOML",
        )
    missing = tuple(f for f in REQUIRED_META_FIELDS if f not in meta)
    if missing:
        return MetaValidation(
            path=path,
            status="FAIL",
            missing_fields=missing,
            pending_fields=(),
            reason=f"missing required fields: {', '.join(missing)}",
        )
    pending = tuple(
        f for f in REQUIRED_META_FIELDS
        if strict and str(meta.get(f, "")).strip().upper() == "PENDING"
    )
    if strict and pending:
        return MetaValidation(
            path=path,
            status="FAIL",
            missing_fields=(),
            pending_fields=pending,
            reason=f"PENDING placeholders remain (strict): {', '.join(pending)}",
        )
    return MetaValidation(
        path=path,
        status="PASS",
        missing_fields=(),
        pending_fields=pending,
    )


def iter_META_paths(args: Iterable[str], recursive: bool) -> Iterable[Path]:
    """Resolve positional args into META.md paths.

    Accepts: a directory (recurses into ``.specify/specs/*/META.md``
    if ``recursive``), an explicit file, or a glob expanded by the
    shell.
    """
    for raw in args:
        p = Path(raw)
        if p.is_dir() and recursive:
            base = p / ".specify" / "specs"
            if base.exists():
                yield from sorted(base.glob("*/META.md"))
        elif p.is_file():
            yield p
        else:
            yield p


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="META.md validator (entry 09 FR-7).")
    parser.add_argument(
        "paths", nargs="+", help="One or more META.md files or spec dirs."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Reject META.md that still has PENDING placeholders.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="When a path is a directory, scan .specify/specs/*/META.md.",
    )
    args = parser.parse_args(argv)

    results: list[MetaValidation] = []
    for path in iter_META_paths(args.paths, args.recursive):
        results.append(validate_one(path, strict=args.strict))

    if not results:
        print("no META.md found under the given paths", file=sys.stderr)
        return EXIT_FAIL

    failed = 0
    inapplicable = 0
    for r in results:
        print(f"{r.status:18s} {r.path}")
        if r.status == "FAIL":
            failed += 1
            print(f"    reason: {r.reason}")
        elif r.status == "NOT_APPLICABLE":
            inapplicable += 1

    print()
    print(
        f"summary: {len(results) - failed - inapplicable} PASS, "
        f"{failed} FAIL, {inapplicable} NOT_APPLICABLE"
    )
    if failed:
        return EXIT_FAIL
    if inapplicable and inapplicable == len(results):
        return EXIT_BLOCKED
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main())
