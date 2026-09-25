"""validate — per-entry attestation validator (entry 09 M2 + FR-1).

The cycle adapter recomputes the digest from the attestation's
``completion_sha`` + the local ``config_fingerprint`` and
rejects stale or tampered attestations. This module is the
typed wire for that validator.

The ``validate_attestation`` function reads a JSON file (or
parses a dict) and returns a typed ``AttestationResult``. Stale
SHAs (i.e. completion_sha not reachable from HEAD) raise the
gate-status algebra to ``BLOCKED`` (exit 78).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from research_institution.prime_directive.attest import (
    compute_digest,
    config_fingerprint,
)

__all__ = ["AttestationResult", "validate_attestation", "verify_attestation_chain"]


@dataclass(frozen=True, slots=True)
class AttestationResult:
    """The validator's verdict on a single attestation."""

    verdict: str  # "PASS" | "FAIL" | "BLOCKED"
    slug: str | None
    completion_sha: str | None
    digest: str | None
    expected_digest: str | None
    detail: str = ""


def validate_attestation(
    attestation: dict[str, object] | Path,
    *,
    root: Path | None = None,
    task_globs: tuple[str, ...] | list[str] = (".specify/specs/*/tasks.md",),
    reachable_shas: tuple[str, ...] | None = None,
) -> AttestationResult:
    """Validate an attestation dict (or load it from a Path).

    The validator returns ``BLOCKED`` when ``completion_sha``
    is not in ``reachable_shas`` (the local reflog). When
    ``reachable_shas`` is ``None``, the validator calls
    ``git rev-list --all`` to populate it.
    """
    if isinstance(attestation, Path):
        attestation = json.loads(attestation.read_text(encoding="utf-8"))
    slug = attestation.get("slug") if isinstance(attestation, dict) else None
    completion_sha = (
        attestation.get("completion_sha")
        if isinstance(attestation, dict)
        else None
    )
    digest = attestation.get("digest") if isinstance(attestation, dict) else None
    if not (slug and completion_sha and digest):
        return AttestationResult(
            verdict="FAIL",
            slug=str(slug) if slug else None,
            completion_sha=str(completion_sha) if completion_sha else None,
            digest=str(digest) if digest else None,
            expected_digest=None,
            detail="attestation missing slug/completion_sha/digest",
        )
    workspace = (root or Path.cwd()).resolve()
    config_fp = config_fingerprint(workspace, task_globs)
    expected = compute_digest(
        completion_sha=str(completion_sha), config_fingerprint_value=config_fp
    )
    if digest != expected:
        return AttestationResult(
            verdict="FAIL",
            slug=str(slug),
            completion_sha=str(completion_sha),
            digest=str(digest),
            expected_digest=expected,
            detail="digest mismatch",
        )
    # Reachable-SHA check.
    if reachable_shas is None:
        reachable_shas = _git_reachable_shas(workspace)
    if str(completion_sha) not in reachable_shas:
        return AttestationResult(
            verdict="BLOCKED",
            slug=str(slug),
            completion_sha=str(completion_sha),
            digest=str(digest),
            expected_digest=expected,
            detail=f"completion_sha not reachable from HEAD: {completion_sha}",
        )
    return AttestationResult(
        verdict="PASS",
        slug=str(slug),
        completion_sha=str(completion_sha),
        digest=str(digest),
        expected_digest=expected,
    )


def verify_attestation_chain(
    dirpath: Path,
    *,
    root: Path | None = None,
) -> tuple[AttestationResult, ...]:
    """Verify every attestation under ``dirpath`` (e.g.
    ``.specify/specs/*/.pi-prime-attestations/``).
    """
    if not dirpath.exists():
        return ()
    files = sorted(dirpath.glob("*.json"))
    return tuple(
        validate_attestation(f, root=root or dirpath.parent.parent.parent)
        for f in files
    )


def _git_reachable_shas(repo: Path) -> tuple[str, ...]:
    try:
        proc = subprocess.run(
            ["git", "rev-list", "--all"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ()
    if proc.returncode != 0:
        return ()
    return tuple(s for s in proc.stdout.splitlines() if s)
