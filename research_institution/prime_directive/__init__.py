"""Prime-directive CLI surface for the Spec-Kit cycle (entry 09 M1 + M2).

The Spec-Kit cycle adapter (``pi_monitor.work.sources.spec_kit_cycle``)
gates each entry's audit-close-out tickable on the presence of a
matching ``.specify/specs/<slug>/.pi-prime-attestations/<slug>.json``.
The supervised Pi worker emits that attestation via the
subcommands exposed here; the canonical digest formula is
``sha256(completion_sha || config_fingerprint)`` (v2 form per
the e2178ab fix) so the cycle adapter can reject stale or
tampered attestations on every observation.

The package is split into four submodules per FR-1:

  * :mod:`research_institution.prime_directive.attest` —
    ``attest(spec_id, *, completion_sha)`` + the v2 digest
    helpers.
  * :mod:`research_institution.prime_directive.validate` —
    ``validate_attestation(...)`` + chain verifier.
  * :mod:`research_institution.prime_directive.meta_validator` —
    META.md §11.2 schema validator.
  * :mod:`research_institution.prime_directive.extension_bridge` —
    canonical registry renderer for the runtime extension.

This ``__init__`` re-exports the public API + owns the Typer
subcommand group (``app``).
"""

from __future__ import annotations

from pathlib import Path

import typer

from research_institution.prime_directive.attest import (
    attest as _attest_module_attest,
    compute_digest,
    config_fingerprint,
)
from research_institution.prime_directive.extension_bridge import (
    render_sanctioned_globs,
)
from research_institution.prime_directive.meta_validator import (
    validate_meta,
    validate_all_metas,
)
from research_institution.prime_directive.validate import (
    validate_attestation,
    verify_attestation_chain,
)

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
    payload = _attest_module_attest(
        spec_id=slug,
        completion_sha=completion_sha or "HEAD",
        root=root or _institution_root(),
        write=write,
    )
    import json

    typer.echo(json.dumps(payload, indent=2))


@app.command("validate")
def validate(
    slug: str = typer.Option(..., "--slug", help="Entry slug."),
    root: Path | None = typer.Option(
        None,
        "--root",
        help="Workspace root (default: institution repo root).",
    ),
) -> None:
    """Validate the per-entry attestation JSON for ``--slug``."""
    workspace = (root or _institution_root()).resolve()
    attestations_dir = workspace / ".specify" / "specs" / slug / ".pi-prime-attestations"
    target = attestations_dir / f"{slug}.json"
    if not target.exists():
        typer.echo(f"attestation missing: {target}", err=True)
        raise typer.Exit(code=78)
    result = validate_attestation(target, root=workspace)
    typer.echo(
        f"{result.verdict}: slug={result.slug} "
        f"completion_sha={result.completion_sha[:12]}..."
    )
    if result.verdict == "PASS":
        raise typer.Exit(code=0)
    if result.verdict == "BLOCKED":
        raise typer.Exit(code=78)
    raise typer.Exit(code=1)


@app.command("render-globs")
def render_globs_cmd() -> None:
    """Render the canonical ``SANCTIONED_PATH_PATTERNS`` shape."""
    for glob in render_sanctioned_globs():
        typer.echo(glob)


@app.command("validate-meta")
def validate_meta_cmd(
    path: Path = typer.Argument(..., help="Path to META.md."),
    strict: bool = typer.Option(False, "--strict", help="Reject PENDING placeholders."),
) -> None:
    """Validate one META.md against the §11.2 schema."""
    result = validate_meta(path, strict_placeholders=strict)
    typer.echo(f"{result.verdict}: {result.spec_id} ({result.detail})")
    if result.verdict == "PASS":
        raise typer.Exit(code=0)
    if result.verdict == "NOT_APPLICABLE":
        raise typer.Exit(code=78)
    raise typer.Exit(code=1)


__all__ = [
    "app",
    "attest",
    "compute_digest",
    "config_fingerprint",
    "render_sanctioned_globs",
    "validate_all_metas",
    "validate_attestation",
    "validate_meta",
    "verify_attestation_chain",
]
