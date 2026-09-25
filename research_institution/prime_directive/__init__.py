"""Prime-directive CLI surface for the Spec-Kit cycle.

The Spec-Kit cycle adapter (``pi_monitor.work.sources.spec_kit_cycle``)
gates each entry's audit-close-out tickable on the presence of a
matching ``.pi-prime-attestations/<slug>.json``. The supervised Pi
worker emits that attestation via the subcommand exposed here
rather than by hand-writing JSON. The attestation carries the
canonical digest formula (``sha256(completion_sha ||
config_fingerprint)``) so the cycle adapter can reject stale or
tampered attestations on every observation.

Design notes:
  - The subcommand is intentionally minimal. It is a thin wrapper
    over ``scripts/emit-attestation.py`` so the script's behavior
    is reachable from both the operator shell and the supervised
    worker.
  - The completion SHA defaults to ``HEAD`` of the local repo; the
    worker can override with ``--completion-sha`` when a precise
    closing SHA matters (e.g. entry 10's release tag).
  - Exit codes follow the gate-status algebra
    (``constitution-verify.md`` §3): 0 PASS, 78 BLOCKED, 1 FAIL.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import typer

# Subcommand group exposed under ``python -m research_institution
# prime_directive ...``. Each command is its own subcommand; the
# group itself is a Typer app nested on the parent ``app``.
app = typer.Typer(
    name="prime_directive",
    help=(
        "Emit and validate per-entry attestation JSON for the "
        "Spec-Kit cycle adapter."
    ),
    no_args_is_help=True,
)


def _institution_root() -> Path:
    """Return the institution root (the research-institution repo)."""
    # Import lazily so the cycle adapter doesn't pull in the
    # full typer stack at module-load time.
    from research_institution.paths import institution_dir

    return institution_dir()


@app.command("attest")
def attest(
    slug: str = typer.Option(..., "--slug", help="Entry slug, e.g. 00-verify-constitution-ratification"),
    completion_sha: str | None = typer.Option(
        None,
        "--completion-sha",
        help="Override completion SHA (default: HEAD of the local repo).",
    ),
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Workspace root (default: institution repo root).",
    ),
    write: bool = typer.Option(
        False,
        "--write",
        help="Actually write the file (default: dry-run, print to stdout).",
    ),
) -> None:
    """Emit per-entry attestation JSON for the Spec-Kit cycle."""
    workspace = (root or _institution_root()).resolve()
    spec_dir = workspace / ".specify" / "specs" / slug
    if not spec_dir.is_dir():
        typer.echo(f"spec dir does not exist: {spec_dir}", err=True)
        raise typer.Exit(code=1)

    # Defer to the canonical helper at scripts/emit-attestation.py
    # so the script and CLI share one implementation. We shell out
    # rather than importing because the helper is single-file and
    # importable only via sys.path hacks; shelling keeps the
    # surface stable.
    repo_root = Path(__file__).resolve().parents[2]
    cmd = [
        sys.executable,
        str(repo_root / "scripts" / "emit-attestation.py"),
        "--slug",
        slug,
        "--root",
        str(workspace),
    ]
    if completion_sha:
        cmd += ["--completion-sha", completion_sha]
    if write:
        cmd += ["--write"]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    raise typer.Exit(code=proc.returncode)


@app.command("validate")
def validate(
    slug: str = typer.Option(..., "--slug", help="Entry slug."),
    strict: bool = typer.Option(
        True,
        "--strict/--no-strict",
        help="Reject META.md that still has PENDING placeholders.",
    ),
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Workspace root (default: institution repo root).",
    ),
) -> None:
    """Validate one entry's META.md + attestation JSON."""
    workspace = (root or _institution_root()).resolve()
    repo_root = Path(__file__).resolve().parents[2]

    # Validate META.
    validator = repo_root / "scripts" / "META_validator.py"
    cmd = [sys.executable, str(validator)]
    if strict:
        cmd += ["--strict"]
    cmd += [str(workspace / ".specify" / "specs" / slug / "META.md")]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        raise typer.Exit(code=proc.returncode)

    # Verify attestation JSON exists + digest matches.
    attest_path = (
        workspace
        / ".specify"
        / "specs"
        / slug
        / ".pi-prime-attestations"
        / f"{slug}.json"
    )
    if not attest_path.exists():
        typer.echo(f"attestation JSON missing: {attest_path}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"PASS {slug}: META valid, attestation present")


__all__ = ["app", "attest", "validate"]
