"""Unit tests for extension_bridge (entry 09 M2)."""

from __future__ import annotations

from pathlib import Path

from research_institution.prime_directive.extension_bridge import (
    render_sanctioned_globs,
)


def _registry(tmp_path: Path) -> Path:
    body = """\
schema_version = "1"

[[exemption]]
glob = "/foo/bar/"
reason = "test row"
owner = "09-prime-directive-mechanical-enforcement"
added_at = "2026-09-25"
expiry_spec_id = "09-prime-directive-mechanical-enforcement"

[[exemption]]
glob = "/baz/"
reason = "another test row"
owner = "09-prime-directive-mechanical-enforcement"
added_at = "2026-09-25"
expiry_spec_id = "09-prime-directive-mechanical-enforcement"
"""
    p = tmp_path / "transient-exemptions.toml"
    p.write_text(body, encoding="utf-8")
    return p


def test_render_sanctioned_globs_includes_registry_rows(tmp_path: Path) -> None:
    globs = render_sanctioned_globs(registry_path=_registry(tmp_path))
    assert "/foo/bar/" in globs
    assert "/baz/" in globs


def test_render_sanctioned_globs_always_includes_extras(tmp_path: Path) -> None:
    globs = render_sanctioned_globs(registry_path=_registry(tmp_path))
    # Spec dirs and caches are always in the sanctioned-globs shape.
    assert "/.specify/specs/" in globs
    assert "/.pi-prime-attestations/" in globs
    assert "/.venv/" in globs


def test_render_sanctioned_globs_deduplicates(tmp_path: Path) -> None:
    globs = render_sanctioned_globs(registry_path=_registry(tmp_path))
    # Stable: deduplicated while preserving order.
    assert len(globs) == len(dict.fromkeys(globs))


def test_render_sanctioned_globs_empty_registry_uses_only_extras(tmp_path: Path) -> None:
    # Empty registry file.
    p = tmp_path / "transient-exemptions.toml"
    p.write_text("", encoding="utf-8")
    globs = render_sanctioned_globs(registry_path=p)
    assert "/.specify/specs/" in globs
    assert "/foo/bar/" not in globs


def test_render_sanctioned_globs_missing_registry_uses_only_extras(tmp_path: Path) -> None:
    globs = render_sanctioned_globs(registry_path=tmp_path / "not-here.toml")
    assert "/.specify/specs/" in globs
