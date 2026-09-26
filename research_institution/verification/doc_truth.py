"""Documentation truth audit.

Cited contracts:
    @CTR-0095-prime-directive-check-script-contract

The verify-constitution §1.2 forbids six strings as primary
tier markers: ``e2e``, ``smoke``, ``acceptance``, ``endurance``,
``live``, ``chaos``. This audit walks every durable path and
asserts none of those strings appear as active markers.

The walker inspects ``docs/**/*.md``, ``README.md``, and
``AGENTS.md`` files; it does NOT inspect ``tests/``, ``.venv/``,
or other transient surfaces. The walker is pure-Python; it
returns a list of offending (path, line) tuples, and the
release gate / static test consume the result.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

__all__ = [
    "audit_documentation_truth",
    "FORBIDDEN_PRIMARY_TIER_MARKERS",
    "TruthAuditOffender",
]


FORBIDDEN_PRIMARY_TIER_MARKERS: tuple[str, ...] = (
    "e2e",
    "smoke",
    "acceptance",
    "endurance",
    "live",
    "chaos",
)

# Match one of the six forbidden strings when it appears as a
# bare primary-tier marker. We require a tier-marker context
# (decorator / comment / directive / marker key) to suppress
# prose-only hits like "live broadcast" or "chaos theory".
_TIER_MARKER_CONTEXTS: tuple[re.Pattern[str], ...] = (
    # @pytest.mark.<forbidden>
    re.compile(
        r"@pytest\.mark\.(?:"
        + "|".join(FORBIDDEN_PRIMARY_TIER_MARKERS)
        + r")\b"
    ),
    # tier: <forbidden> / tier = <forbidden>
    re.compile(
        r"#\s*tier\s*[:=]\s*(?:"
        + "|".join(FORBIDDEN_PRIMARY_TIER_MARKERS)
        + r")\b",
        re.IGNORECASE,
    ),
    # tier = "<forbidden>"
    re.compile(
        r"^\s*tier\s*=\s*\"(?:"
        + "|".join(FORBIDDEN_PRIMARY_TIER_MARKERS)
        + r")\"",
        re.IGNORECASE,
    ),
    # marker:<forbidden>:  (legacy spec-kit form)
    re.compile(
        r"marker:(?:"
        + "|".join(FORBIDDEN_PRIMARY_TIER_MARKERS)
        + r"):",
        re.IGNORECASE,
    ),
)

_DOC_SUFFIXES: tuple[str, ...] = (".md", ".rst", ".txt")


def _is_durable_doc(path: Path) -> bool:
    """Return True iff ``path`` is a durable doc (not transient)."""
    parts = set(path.parts)
    transient_markers = {
        ".venv",
        "__pycache__",
        "node_modules",
        ".git",
        "_retired",
        ".pi-glla",
        ".agents/transient",
        ".specify/specs",
    }
    return not (parts & transient_markers)


def _iter_durable_docs(repo_root: Path) -> Iterable[Path]:
    """Yield durable ``*.md`` files under ``repo_root``."""
    for path in sorted(repo_root.rglob("*.md")):
        if not path.is_file():
            continue
        if not _is_durable_doc(path):
            continue
        yield path


def audit_documentation_truth(repo_root: Path | None = None) -> list[tuple[str, int, str]]:
    """Return a list of offending ``(path, line, marker)`` tuples.

    An offender is a line in a durable doc that uses one of
    the six forbidden primary-tier strings in a tier-marker
    context (decorator / comment / directive / marker key).
    Prose-only mentions are intentionally NOT flagged; the
    audit targets *active markers*, not words in body text.
    """
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    offenders: list[tuple[str, int, str]] = []
    for path in _iter_durable_docs(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for regex in _TIER_MARKER_CONTEXTS:
                m = regex.search(line)
                if m:
                    offenders.append((str(path), lineno, m.group(0)))
                    break
    return offenders


# Public re-export of the offender tuple shape (path, line, marker).
class TruthAuditOffender:
    """Type-style alias for the ``(path, line, marker)`` tuple shape."""

    __slots__ = ("path", "line", "marker")

    def __init__(self, path: str, line: int, marker: str) -> None:
        self.path = path
        self.line = line
        self.marker = marker

    def __iter__(self):  # pragma: no cover - convenience only
        yield self.path
        yield self.line
        yield self.marker
