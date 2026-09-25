"""meta_validator — META.md schema validator (entry 09 M2 + FR-1).

The validator parses each spec dir's ``META.md`` and asserts
the §11.2 schema (constitution-verify.md §11.2). The required
fields are:

    spec_id, owner_repo, owner_repos,
    baseline_sha, completion_sha, gate_report_digest,
    durable_anchors_added, durable_anchors_cited,
    transient_anchors_retired, unblocked_dependents,
    constitution_compliance.section_0..section_12

The validator emits PASS / FAIL / NOT_APPLICABLE per
constitution-verify.md §3 (gate-status algebra).
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

__all__ = ["MetaValidationResult", "validate_meta"]


_REQUIRED_FIELDS: tuple[str, ...] = (
    "spec_id",
    "owner_repo",
    "owner_repos",
    "baseline_sha",
    "completion_sha",
    "gate_report_digest",
    "durable_anchors_added",
    "durable_anchors_cited",
    "transient_anchors_retired",
    "unblocked_dependents",
    "constitution_compliance",
)


@dataclass(frozen=True, slots=True)
class MetaValidationResult:
    """The validator's verdict on a single META.md."""

    verdict: str  # "PASS" | "FAIL" | "NOT_APPLICABLE"
    spec_id: str | None
    missing_fields: tuple[str, ...] = ()
    placeholders: tuple[str, ...] = ()
    detail: str = ""


_PLACEHOLDER_RE = re.compile(r"\bPENDING\b", re.IGNORECASE)


def _extract_toml_block(text: str) -> str | None:
    """Pull the triple-backtick toml block out of META.md."""
    fence = "```"
    start = text.find(f"{fence}toml")
    if start < 0:
        return None
    body_start = start + len(fence) + len("toml")
    end = text.find(fence, body_start)
    if end < 0:
        return None
    return text[body_start:end]


def validate_meta(
    path: Path,
    *,
    strict_placeholders: bool = False,
) -> MetaValidationResult:
    """Validate one ``META.md`` against the §11.2 schema."""
    if not path.exists():
        return MetaValidationResult(
            verdict="NOT_APPLICABLE",
            spec_id=None,
            detail=f"META.md not found: {path}",
        )
    text = path.read_text(encoding="utf-8")
    toml_block = _extract_toml_block(text)
    if toml_block is None:
        return MetaValidationResult(
            verdict="FAIL",
            spec_id=None,
            detail="META.md has no ```toml``` block",
        )
    try:
        doc = tomllib.loads(toml_block)
    except tomllib.TOMLDecodeError as exc:
        return MetaValidationResult(
            verdict="FAIL",
            spec_id=None,
            detail=f"TOML decode error: {exc}",
        )
    if "meta" not in doc:
        return MetaValidationResult(
            verdict="FAIL",
            spec_id=None,
            detail="META.md missing [meta] table",
        )
    meta = doc["meta"]
    # Resolve fields from the meta table or the top-level doc.
    resolved_meta = {**doc, **meta}
    missing = tuple(k for k in _REQUIRED_FIELDS if k not in resolved_meta)
    if missing:
        return MetaValidationResult(
            verdict="FAIL",
            spec_id=str(meta.get("spec_id", "")) or None,
            missing_fields=missing,
            detail=f"missing fields: {missing}",
        )
    # Check placeholders.
    placeholders = _find_placeholders(doc) if strict_placeholders else ()
    if placeholders:
        return MetaValidationResult(
            verdict="FAIL",
            spec_id=str(meta.get("spec_id", "")),
            placeholders=placeholders,
            detail=f"placeholder values remain: {placeholders}",
        )
    # constitution_compliance: section_0..section_12. The table
    # may live at the top level (entry 00..03 era) or inside
    # ``[meta]`` (entry 04+). Both forms are accepted.
    cc_root: dict[str, object] = doc.get("constitution_compliance") or {}
    if not cc_root and isinstance(meta.get("constitution_compliance"), dict):
        cc_root = meta["constitution_compliance"]  # type: ignore[assignment]
    if cc_root:
        missing_sections = tuple(
            f"section_{i}" for i in range(13) if f"section_{i}" not in cc_root
        )
        if missing_sections:
            return MetaValidationResult(
                verdict="FAIL",
                spec_id=str(meta.get("spec_id", "")),
                detail=f"missing constitution_compliance sections: {missing_sections}",
            )
    return MetaValidationResult(
        verdict="PASS",
        spec_id=str(meta.get("spec_id", "")),
    )


def _find_placeholders(doc: object) -> tuple[str, ...]:
    out: list[str] = []
    if isinstance(doc, dict):
        for k, v in doc.items():
            if isinstance(v, str) and _PLACEHOLDER_RE.search(v):
                out.append(k)
            elif isinstance(v, (dict, list)):
                out.extend(_find_placeholders(v))
    elif isinstance(doc, list):
        for item in doc:
            out.extend(_find_placeholders(item))
    return tuple(out)


def validate_all_metas(
    specs_root: Path,
    *,
    strict_placeholders: bool = False,
) -> list[MetaValidationResult]:
    """Validate every spec dir's ``META.md`` under ``specs_root``."""
    if not specs_root.exists():
        return []
    results: list[MetaValidationResult] = []
    for meta in sorted(specs_root.glob("*/META.md")):
        results.append(validate_meta(meta, strict_placeholders=strict_placeholders))
    return results
