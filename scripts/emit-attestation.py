#!/usr/bin/env python3
"""emit-attestation.py — emit a per-entry attestation JSON.

The Spec-Kit cycle adapter (pi_monitor.work.sources.spec_kit_cycle)
gates each entry's audit-close-out tickable on the presence of a
matching ``.pi-prime-attestations/<slug>.json``. This script is the
operator's (and the supervised worker's) one-shot emitter for that
file.

Usage:
    python scripts/emit-attestation.py --slug 00-verify-constitution-ratification
    python scripts/emit-attestation.py --slug NN-slug --completion-sha <sha>

If ``--completion-sha`` is omitted, the script reads
``META.md``'s ``[meta].completion_sha`` and uses that. The
attestation's ``digest`` field is the canonical sha256 over
``completion_sha || config_fingerprint``; the cycle adapter
recomputes the same digest and compares on every observation, so
a stale or tampered attestation is detected on the next scan.

Exit codes follow the gate-status algebra:
    0   PASS    attestation written
    1   FAIL    META.md missing or invalid
    78  BLOCKED could not determine completion_sha
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

# Same shape as the cycle adapter's helpers. Keep them in sync;
# if you change the digest formula here, change it in the adapter
# too and bump the schema version. The adapter uses
# ``str(SPEC_KIT_CYCLE_DEFAULT_GLOBS)`` (a list repr); we mirror
# that byte-for-byte so the digests match.
DEFAULT_CYCLE_GLOBS = (".specify/specs/*/tasks.md",)
SCHEMA_VERSION = 1


def _config_fingerprint(root: Path) -> str:
    import hashlib
    # Mirror the adapter: ``str(list_of_globs) | str(root)`` is the
    # canonical config-fingerprint payload. The list-repr form
    # includes the brackets and the comma-separated glob strings.
    payload = f"{list(DEFAULT_CYCLE_GLOBS)}|{root}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _compute_digest(completion_sha: str, config_fingerprint: str) -> str:
    import hashlib
    payload = f"{completion_sha}|{config_fingerprint}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_META_completion_sha(meta_path: Path) -> str:
    if not meta_path.exists():
        return ""
    raw = meta_path.read_text(encoding="utf-8", errors="replace")
    fm = re.search(r"(?ms)^---\s*\n(.+?)\n---", raw) or re.search(
        r"(?ms)^```(?:toml)?\s*\n(.+?)^```", raw, re.MULTILINE
    )
    if not fm:
        return ""
    try:
        doc = tomllib.loads(fm.group(1))
    except tomllib.TOMLDecodeError:
        return ""
    return str(doc.get("meta", {}).get("completion_sha", ""))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit per-entry attestation JSON for the cycle adapter."
    )
    parser.add_argument("--slug", required=True, help="Entry slug, e.g. 00-verify-constitution-ratification")
    parser.add_argument("--root", default=".", help="Workspace root (default: cwd)")
    parser.add_argument(
        "--completion-sha",
        default=None,
        help="Override completion_sha (default: read from META.md)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually write the file (default: dry-run, print to stdout)",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    spec_dir = root / ".specify" / "specs" / args.slug
    if not spec_dir.is_dir():
        print(f"spec dir does not exist: {spec_dir}", file=sys.stderr)
        return 1

    completion_sha = args.completion_sha or _read_META_completion_sha(
        spec_dir / "META.md"
    )
    if not completion_sha or completion_sha.strip().upper() == "PENDING":
        print(
            f"could not determine completion_sha for {args.slug}; "
            "set it on META.md or pass --completion-sha",
            file=sys.stderr,
        )
        return 78

    config_fingerprint = _config_fingerprint(root)
    digest = _compute_digest(completion_sha, config_fingerprint)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "slug": args.slug,
        "completion_sha": completion_sha,
        "config_fingerprint": config_fingerprint,
        "digest": digest,
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"

    if not args.write:
        print(text)
        return 0

    attest_dir = spec_dir / ".pi-prime-attestations"
    attest_dir.mkdir(exist_ok=True)
    out = attest_dir / f"{args.slug}.json"
    out.write_text(text)
    print(f"wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
