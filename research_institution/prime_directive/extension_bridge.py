"""extension_bridge — registry consumer for the prime-directive guard.

Per .specify/specs/09-prime-directive-mechanical-enforcement/
spec.md FR-6, the runtime extension at
``~/.pi/agent/extensions/prime-directive-guard.ts`` loads the
canonical registry (``transient-exemptions.toml``) and renders
the ``SANCTIONED_PATH_PATTERNS`` shape the extension expects.

This module is the typed Python wire that surfaces the registry
rows so the extension's TypeScript can mirror the rendering. The
TypeScript side can either:

  (a) call ``python -m research_institution prime_directive
      extension_bridge --render-globs`` and parse stdout, OR
  (b) read the registry directly (the TOML is canonical).

The renderer is the audit path: when the Python renderer +
the TypeScript renderer disagree, the operator catches it
during the gate-status-algebra reconcile.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

__all__ = ["render_sanctioned_globs", "load_registry", "RegistryRow"]


def load_registry(path: Path | None = None) -> list[dict[str, object]]:
    """Load the transient-exemptions registry from TOML."""
    if path is None:
        path = _default_registry_path()
    if not path.exists():
        return []
    doc = tomllib.loads(path.read_text(encoding="utf-8"))
    rows = doc.get("exemption", [])
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def render_sanctioned_globs(
    *,
    registry_path: Path | None = None,
    extras: tuple[str, ...] = (
        "/.specify/specs/",
        "/AGENTS.md",
        "/.pi-glla/",
        "/.agents/transient/",
        "/.venv/",
        "/build/",
        "/node_modules/",
        "/__pycache__/",
        "/.pytest_cache/",
        "/.ruff_cache/",
        "/.hypothesis/",
        "/.mypy_cache/",
        "/.coverage",
        "/.pi-prime-attestations/",
    ),
) -> tuple[str, ...]:
    """Return the canonical ``SANCTIONED_PATH_PATTERNS`` shape.

    The renderer reads the registry's ``glob`` field for every
    row (which already encodes the sanctioned path patterns)
    and adds the canonical extras (spec dirs, AGENTS.md, transient
    plan dirs, generated caches). The TypeScript extension's
    ``SANCTIONED_PATH_PATTERNS`` array is the same shape.
    """
    rows = load_registry(registry_path)
    globs: list[str] = []
    for row in rows:
        g = row.get("glob")
        if isinstance(g, str):
            globs.append(g)
    for e in extras:
        globs.append(e)
    # Dedup while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for g in globs:
        if g in seen:
            continue
        seen.add(g)
        out.append(g)
    return tuple(out)


def _default_registry_path() -> Path:
    """Locate ``transient-exemptions.toml`` from this file."""
    here = Path(__file__).resolve()
    for ancestor in [here, *here.parents]:
        candidate = ancestor / ".specify" / "memory" / "transient-exemptions.toml"
        if candidate.exists():
            return candidate
    return Path.cwd() / ".specify" / "memory" / "transient-exemptions.toml"


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m research_institution.prime_directive.extension_bridge --render-globs``.

    Emits one glob per line on stdout. Exit 0 on success.
    """
    argv = argv if argv is not None else sys.argv[1:]
    if "--render-globs" in argv:
        for glob in render_sanctioned_globs():
            print(glob)
        return 0
    print("usage: python -m research_institution.prime_directive.extension_bridge --render-globs", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
