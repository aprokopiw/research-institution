"""Static checks for `.specify/memory/constitution-verify.md`.

Per `.specify/specs/00-verify-constitution-ratification/spec.md`
FR-4, this module verifies:

  1. The file exists, is non-empty, and parses as Markdown with a
     `**Version:**` header line.
  2. Every linked durable anchor in §N sub-rules (``@ADR-NNNN``,
     ``@INV-NNNN``, ``@CTR-NNNN``, ``@CON-NNNN``) exists in
     ``docs/semantic/SEMANTIC_REGISTRY.md`` AND a corresponding
     ``*.md`` file lives at the path the registry row names
     (research-institution-owned) or the equivalent path under
     a sibling repo (math / pi_monitor / kaplansky).
  3. Each §N section (§1…§12) carries Statement (or table-form
     introduction), Sub-rules, and Linked durable anchors; §0
     carries Statement + introductory guidance only.
  4. The file declares a `Governance` section after §12.

These checks pin the verify-constitution's structural integrity;
amendments that change §N sub-rules must surface here first
(constitution §0 amendment discipline).

The check is wired into `make test` via `pytest`; failure is gate
`FAIL` per constitution §3.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path("/Users/erinprokopiw/Documents/andrei/research-institution")
CONSTITUTION = REPO / ".specify" / "memory" / "constitution-verify.md"
REGISTRY = REPO / "docs" / "semantic" / "SEMANTIC_REGISTRY.md"

# Section markers per the canonical numbering (§0…§12 + Governance).
SECTION_RE = re.compile(r"^## §(\d+)\.\s", re.MULTILINE)
ANCHOR_RE = re.compile(r"@(ADR|INV|CTR|CON)-(\d{4})([\w-]*)")
# Match a sibling-repo qualifier that precedes an anchor citation,
# e.g. ``pi_monitor `@ADR-0005` …``. The same anchor ID can live
# in multiple repos (cross-repo namespace convention, see
# constitution §12.1); the qualifier disambiguates which repo's
# record is being cited. Anchors without a qualifier resolve via
# the research-institution registry row alone.
QUALIFIED_ANCHOR_RE = re.compile(
    r"\b(research-institution|math|pi_monitor|kaplansky)\s+`?@(ADR|INV|CTR|CON)-(\d{4})"
)
VERSION_RE = re.compile(r"\*\*Version:\*\*")
GOVERNANCE_RE = re.compile(r"^## Governance\b", re.MULTILINE)
SUBRULES_HEADER_RE = re.compile(r"^\*\*Sub-rules\.\*\*", re.MULTILINE)
LINKED_HEADER_RE = re.compile(r"^\*\*Linked durable anchors:\*\*", re.MULTILINE)
STATEMENT_HEADER_RE = re.compile(r"^\*\*Statement\.\*\*", re.MULTILINE)

# Sibling repos whose `docs/semantic/` trees host anchors that the
# research-institution registry references. Anchors anchored at
# math/pi_monitor/kaplansky paths are still cited by
# `constitution-verify.md` (e.g. `@ADR-0005` pi_monitor, `@ADR-0091`
# math); this list lets the resolver look beyond research-institution.
SIBLING_OWNERS = {
    "math": REPO.parent / "math",
    "pi_monitor": REPO.parent / "pi_monitor",
    "kaplansky": REPO.parent / "kaplansky",
}


@pytest.fixture(scope="module")
def constitution_text() -> str:
    assert CONSTITUTION.exists(), f"missing: {CONSTITUTION}"
    text = CONSTITUTION.read_text(encoding="utf-8")
    assert text.strip(), "constitution-verify.md is empty"
    return text


@pytest.fixture(scope="module")
def registry_rows() -> dict[str, str]:
    """Parse the cross-repo registry into {anchor_id: relative_path}.

    The registry is a markdown table; rows are ``| `@ADR-NNNN` | path | desc |``.
    Only the research-institution-owned index table is parsed; the
    sibling-repo subsections reuse the same row shape so the regex
    is applied to the whole file.

    Path normalisation: the registry stores paths as written in
    markdown. The redundant ``research-institution/`` prefix some
    rows carry (e.g. ``research-institution/docs/semantic/adr/``)
    is stripped because the registry lives inside this repo; sibling
    rows keep their literal ``math/`` / ``pi_monitor/`` /
    ``kaplansky/`` prefix and resolve against the sibling root.
    """
    assert REGISTRY.exists(), f"missing registry: {REGISTRY}"
    raw = REGISTRY.read_text(encoding="utf-8")
    rows: dict[str, str] = {}
    for line in raw.splitlines():
        m = re.match(r"^\|\s*`(@(?:ADR|INV|CTR|CON)-\d{4})`\s*\|\s*`?([^`|]+?)`?\s*\|", line)
        if m:
            path = m.group(2).strip().rstrip("/")
            if path.startswith("research-institution/"):
                path = path[len("research-institution/") :]
            rows[m.group(1)] = path
    assert rows, "registry parsed zero rows; table format may have changed"
    return rows


def test_constitution_has_version_line(constitution_text: str) -> None:
    """Constitution declares a `**Version:**` header line (FR-4.3)."""
    assert VERSION_RE.search(constitution_text), (
        "constitution-verify.md lacks a `**Version:**` header line"
    )


def test_constitution_has_governance_section(constitution_text: str) -> None:
    """Constitution closes with a `## Governance` section (FR-1)."""
    assert GOVERNANCE_RE.search(constitution_text), (
        "constitution-verify.md lacks a `## Governance` section"
    )


def test_constitution_sections_span_zero_to_twelve(constitution_text: str) -> None:
    """All thirteen sections §0…§12 are present, in order."""
    matches = SECTION_RE.findall(constitution_text)
    assert matches, "no `## §N.` section headers found"
    expected = [str(n) for n in range(13)]
    assert matches == expected, (
        f"section markers out of order or missing; got {matches}, want {expected}"
    )


def test_every_linked_anchor_resolves_in_registry(
    constitution_text: str, registry_rows: dict[str, str]
) -> None:
    """Every `@XXX-NNNN` in §N sub-rules resolves in the registry (FR-4.2).

    Resolution rules (per constitution §12.1):

      - **Qualified** form ``<repo> @ADR-NNNN`` resolves against the
        named sibling repo's ``docs/semantic/`` tree, NOT against the
        cross-repo registry row (the registry stores research-institution
        defaults; sibling anchors of the same ID live at the sibling).
      - **Unqualified** form ``@ADR-NNNN`` resolves via the registry.

    This avoids the trap where ``pi_monitor `@ADR-0005``` would otherwise
    mis-resolve to research-institution's ADR-0005 (reasoning tail).
    """
    cited_qualified: set[tuple[str, str]] = set()  # (repo, anchor_id)
    cited_unqualified: set[str] = set()
    for _n, body in _section_bodies(constitution_text):
        for m in QUALIFIED_ANCHOR_RE.finditer(body):
            cited_qualified.add((m.group(1), f"@{m.group(2)}-{m.group(3)}"))
        for m in ANCHOR_RE.finditer(body):
            anchor_id = f"@{m.group(1)}-{m.group(2)}"
            # Skip anchors that were already captured as qualified.
            start = m.start()
            window = body[max(0, start - 32): start]
            if QUALIFIED_ANCHOR_RE.search(window):
                continue
            cited_unqualified.add(anchor_id)
    assert cited_qualified or cited_unqualified, "no anchors cited"
    missing_unqualified = sorted(c for c in cited_unqualified if c not in registry_rows)
    assert not missing_unqualified, (
        f"unqualified anchors cited by constitution are missing from registry: "
        f"{missing_unqualified}"
    )
    # Qualified anchors: file must exist at the sibling repo.
    missing_qualified: list[str] = []
    for repo, anchor in cited_qualified:
        owner_root = SIBLING_OWNERS.get(repo)
        if owner_root is None or not owner_root.exists():
            missing_qualified.append(f"{repo} {anchor} (sibling owner absent)")
            continue
        kind = anchor[1:4].lower()  # "adr" / "inv" / "ctr" / "con"
        kind_dir_map = {
            "adr": ("adr", "adrs"),
            "inv": ("invariants",),
            "ctr": ("contracts",),
            "con": ("conventions", "constraints"),
        }
        nnnn = anchor.split("-")[1]
        # Filename varies by repo + kind:
        #   - math/kaplansky/research-institution: ``adr-NNNN-…md`` (kind-prefixed)
        #   - pi_monitor: ``NNNN-…md`` (no kind prefix, lives at docs/adr/)
        filename_globs: tuple[str, ...] = (f"{kind}-{nnnn}-*.md",)
        if repo == "pi_monitor" and kind == "adr":
            filename_globs = (f"{nnnn}-*.md", f"{kind}-{nnnn}-*.md")
        # pi_monitor's primary ADRs live at ``pi_monitor/docs/adr/``,
        # not under ``docs/semantic/adr/``. Prepend that special path
        # for ADR lookups.
        search_paths: list[Path] = []
        if repo == "pi_monitor" and kind == "adr":
            search_paths.append(owner_root / "docs" / "adr")
        for dname in kind_dir_map.get(kind, ()):
            search_paths.append(owner_root / "docs" / "semantic" / dname)
        found = False
        for d in search_paths:
            if not d.exists():
                continue
            for pattern in filename_globs:
                for f in d.glob(pattern):
                    if f.is_file():
                        found = True
                        break
                if found:
                    break
            if found:
                break
        if not found:
            missing_qualified.append(
                f"{repo} {anchor} (no file under {repo}/docs/)"
            )
    assert not missing_qualified, (
        f"qualified anchors missing on disk: {missing_qualified}"
    )


def test_every_registry_anchor_file_exists(registry_rows: dict[str, str]) -> None:
    """Every registry row points at an existing file on disk (FR-4.2).

    The registry stores *directory* paths (the canonical `*.md`
    filename within is the durable record). Resolution accepts either:
      - the path is itself a file (e.g. pi_monitor ADR rows name the
        full filename); or
      - the path is a directory and at least one ``*.md`` file lives
        under it (the durable record exists at some slug).
    """
    missing: list[str] = []
    for anchor, rel_path in registry_rows.items():
        if rel_path.startswith(("math/", "pi_monitor/", "kaplansky/")):
            owner_name = rel_path.split("/", 1)[0]
            suffix = rel_path[len(owner_name) + 1 :]
            owner_root = SIBLING_OWNERS.get(owner_name)
            if owner_root is None or not owner_root.exists():
                missing.append(f"{anchor} -> {rel_path} (sibling owner absent)")
                continue
            target = owner_root / suffix
        else:
            target = REPO / rel_path
        if target.is_file():
            continue
        if target.is_dir() and any(target.glob("*.md")):
            continue
        missing.append(f"{anchor} -> {target}")
    assert not missing, f"registry rows point at missing files: {missing}"


def _section_bodies(text: str) -> list[tuple[int, str]]:
    """Return ``[(section_number, body), ...]`` in document order."""
    starts = [m for m in SECTION_RE.finditer(text)]
    boundaries: list[tuple[int, int]] = []
    for i, m in enumerate(starts):
        nxt = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        boundaries.append((m.start(), nxt))
    out: list[tuple[int, str]] = []
    for s, e in boundaries:
        match = SECTION_RE.match(text[s : s + 8])
        if match is None:
            continue
        out.append((int(match.group(1)), text[s:e]))
    return out


def test_every_section_has_three_parts(constitution_text: str) -> None:
    """Each §N (except §0) carries Statement + Sub-rules + durable anchors.

    FR-4: "every §N section's body carries the three parts".
    The "Linked durable anchors" part is satisfied by EITHER the
    ``**Linked durable anchors:**`` header OR an ``@XXX-NNNN``
    citation anywhere in the section body (§4, §11, §12 enumerate
    their durable anchors inline rather than under that header).
    §5 substitutes a markdown table for the Statement prose; we
    accept either form. §0 is the how-to-read preamble and is
    exempt from the structural check.
    """
    offenders: list[str] = []
    for n, body in _section_bodies(constitution_text):
        if n == 0:
            # §0 is the preamble; its only structural obligation is to
            # exist (covered by test_constitution_sections_span_zero_to_twelve).
            continue
        has_statement = bool(STATEMENT_HEADER_RE.search(body)) or "|" in body[:600]
        has_subrules = bool(SUBRULES_HEADER_RE.search(body))
        has_linked = bool(LINKED_HEADER_RE.search(body)) or bool(ANCHOR_RE.search(body))
        missing_parts = [
            part
            for part, present in (
                ("Statement/intro", has_statement),
                ("Sub-rules", has_subrules),
                ("Linked durable anchors", has_linked),
            )
            if not present
        ]
        if missing_parts:
            offenders.append(f"§{n} missing: {', '.join(missing_parts)}")
    assert not offenders, "constitution sections incomplete:\n  " + "\n  ".join(offenders)
