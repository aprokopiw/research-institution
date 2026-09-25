"""attest — per-entry attestation emitter (entry 09 M2 + FR-1).

The canonical emitter that produces the JSON the cycle adapter
gates on. The digest formula is the canonical sha256 over
``completion_sha || config_fingerprint`` (v2 form per the
e2178ab fix).

The module exports ``attest(spec_id, *, completion_sha,
config_fingerprint, write)`` so the supervised Pi worker can
call it directly without shelling out to scripts/emit-attestation.py.
The script remains the operator-facing entry point; this module
is the typed wire.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

__all__ = ["attest", "compute_digest", "config_fingerprint"]


# v2 constants — keep in lockstep with the cycle adapter at
# pi_monitor.work.sources.spec_kit_cycle. The script-side
# emitter shares this module; any drift here breaks the cycle.
CONFIG_FINGERPRINT_VERSION: str = "spec-kit-cycle.config_fingerprint.v2"
US: str = "\x1f"  # unit separator; same byte the adapter uses.


def config_fingerprint(
    root: Path,
    task_globs: tuple[str, ...] | list[str] = (".specify/specs/*/tasks.md",),
) -> str:
    """Return the v2 config fingerprint for ``root`` + ``task_globs``."""
    payload = US.join(
        [
            CONFIG_FINGERPRINT_VERSION,
            f"root={root}",
            f"task_globs={','.join(sorted(task_globs))}",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_digest(
    *,
    completion_sha: str,
    config_fingerprint_value: str,
) -> str:
    """Return the canonical sha256 over ``completion_sha || config_fingerprint``."""
    payload = f"{completion_sha}|{config_fingerprint_value}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def attest(
    spec_id: str,
    *,
    completion_sha: str,
    root: Path | None = None,
    task_globs: tuple[str, ...] | list[str] = (".specify/specs/*/tasks.md",),
    write: bool = False,
) -> dict[str, object]:
    """Emit the per-entry attestation dict (and write if ``write=True``).

    The dict is the canonical attestation shape; the cycle
    adapter reads ``digest`` + ``completion_sha`` + ``slug`` to
    validate the entry.
    """
    workspace = (root or Path.cwd()).resolve()
    config_fp = config_fingerprint(workspace, task_globs)
    digest = compute_digest(
        completion_sha=completion_sha,
        config_fingerprint_value=config_fp,
    )
    payload: dict[str, object] = {
        "api_version": 1,
        "slug": spec_id,
        "completion_sha": completion_sha,
        "config_fingerprint": config_fp,
        "digest": digest,
    }
    if write:
        attestations_dir = workspace / ".specify" / "specs" / spec_id / ".pi-prime-attestations"
        attestations_dir.mkdir(parents=True, exist_ok=True)
        out = attestations_dir / f"{spec_id}.json"
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
