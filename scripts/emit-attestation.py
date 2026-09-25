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

The ``_config_fingerprint`` and ``_compute_digest`` helpers here
MUST be byte-for-byte equivalent to the v2 form used in
``pi_monitor.work.sources.spec_kit_cycle``:

* config_fingerprint payload = US (0x1F) join of
    ["spec-kit-cycle.config_fingerprint.v2",
     "root=<root>",
     "task_globs=<csv of sorted globs>"]
* digest payload = ``"<completion_sha>|<config_fingerprint>"``

``tests/static/test_emitter_fingerprint_matches_cycle.py`` enforces
this equivalence at test time so the two cannot drift.

Exit codes follow the gate-status algebra:
    0   PASS    attestation written
    1   FAIL    META.md missing or invalid
    78  BLOCKED could not determine completion_sha
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path

# v2 constants — keep in lockstep with
# pi_monitor.work.sources.spec_kit_cycle.
CONFIG_FINGERPRINT_VERSION = "spec-kit-cycle.config_fingerprint.v2"
US = "\x1f"  # unit separator; same byte the adapter uses.
DEFAULT_CYCLE_GLOBS: tuple[str, ...] = (".specify/specs/*/tasks.md",)
SCHEMA_VERSION = 1


def _config_fingerprint(
    root: Path,
    task_globs: tuple[str, ...] | list[str] = DEFAULT_CYCLE_GLOBS,
) -> str:
    """v2 config fingerprint — byte-for-byte mirror of the cycle adapter.

    Captures the cycle's lookup scope (``root``) and the wrapped
    scanner's ``task_globs`` (sorted before hashing so caller order
    does not affect determinism). No wall-clock or filesystem
    metadata enters the hash; repeated scans of unchanged state
    produce the same fingerprint and an attestation re-verifies
    across supervisor restarts.
    """
    payload = US.join(
        [
            CONFIG_FINGERPRINT_VERSION,
            f"root={root}",
            f"task_globs={','.join(sorted(task_globs))}",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _compute_digest(completion_sha: str, config_fingerprint: str) -> str:
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


def emit(
    slug: str,
    root: Path,
    completion_sha: str | None = None,
    *,
    task_globs: tuple[str, ...] = DEFAULT_CYCLE_GLOBS,
) -> tuple[dict, str]:
    """Pure emit: returns ``(payload, digest)`` for the given slug.

    Does no I/O. ``completion_sha`` falls back to the slug's
    ``META.md`` when omitted. The ``task_globs`` arg is exposed so
    tests can pin the formula against a specific glob set without
    touching the default.
    """
    spec_dir = root / ".specify" / "specs" / slug
    if not spec_dir.is_dir():
        raise FileNotFoundError(f"spec dir does not exist: {spec_dir}")
    if completion_sha is None:
        completion_sha = _read_META_completion_sha(spec_dir / "META.md")
    if not completion_sha or completion_sha.strip().upper() == "PENDING":
        raise ValueError(
            f"could not determine completion_sha for {slug}; "
            "set it on META.md or pass --completion-sha"
        )
    cfg_fp = _config_fingerprint(root, task_globs)
    digest = _compute_digest(completion_sha, cfg_fp)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "slug": slug,
        "completion_sha": completion_sha,
        "config_fingerprint": cfg_fp,
        "digest": digest,
    }
    return payload, digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit per-entry attestation JSON for the cycle adapter."
    )
    parser.add_argument(
        "--slug", required=True,
        help="Entry slug, e.g. 00-verify-constitution-ratification",
    )
    parser.add_argument("--root", default=".", help="Workspace root (default: cwd)")
    parser.add_argument(
        "--completion-sha", default=None,
        help="Override completion_sha (default: read from META.md)",
    )
    parser.add_argument(
        "--write", action="store_true",
        help="Actually write the file (default: dry-run, print to stdout)",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    try:
        payload, _digest = emit(
            args.slug,
            root,
            completion_sha=args.completion_sha,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 78

    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"

    if not args.write:
        print(text)
        return 0

    spec_dir = root / ".specify" / "specs" / args.slug
    attest_dir = spec_dir / ".pi-prime-attestations"
    attest_dir.mkdir(exist_ok=True)
    out = attest_dir / f"{args.slug}.json"
    out.write_text(text)
    print(f"wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
