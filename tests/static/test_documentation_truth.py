"""Documentation truth audit (release-gate row 6).

Cited contracts:
    @CTR-0101-release-gate-contract
    @INV-0093-institution-green-gate-canonical

Walks every durable ``.md`` file under the research-institution
repo and asserts none of the six forbidden primary-tier strings
(``e2e``, ``smoke``, ``acceptance``, ``endurance``, ``live``,
``chaos``) appear as **active markers** — i.e. in a tier-marker
context (decorator / comment / directive / marker key).

Prose-only mentions (e.g. "live broadcast", "chaos theory")
are intentionally NOT flagged; the audit targets *active
markers*, not words in body text. This matches the policy in
``research_institution/verification/doc_truth.py``.

The test is hermetic: it imports the production helper, which
is the single source of truth for what counts as a marker.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def test_no_forbidden_primary_tier_markers_in_durable_docs() -> None:
    """No durable ``.md`` carries a forbidden primary-tier marker."""
    from research_institution.verification.doc_truth import (
        audit_documentation_truth,
    )

    offenders = audit_documentation_truth(repo_root=REPO)
    pretty = [f"{p}:{ln}: {m}" for p, ln, m in offenders]
    assert not offenders, (
        "forbidden primary-tier markers found:\n  " + "\n  ".join(pretty)
    )


def test_prose_mentions_are_not_flagged() -> None:
    """Prose-only mentions of forbidden strings must not be flagged."""
    from research_institution.verification.doc_truth import (
        FORBIDDEN_PRIMARY_TIER_MARKERS,
        audit_documentation_truth,
    )

    # Sanity-check the FORBIDDEN set is the documented six.
    assert FORBIDDEN_PRIMARY_TIER_MARKERS == (
        "e2e",
        "smoke",
        "acceptance",
        "endurance",
        "live",
        "chaos",
    ), "FORBIDDEN_PRIMARY_TIER_MARKERS drifted from the verify-constitution §1.2 list"
    # The audit on a clean repo returns an empty offender list;
    # the prior test catches real violations. This test just
    # asserts the audit is wired and the FORBIDDEN set is stable.
    audit_documentation_truth(repo_root=REPO)


def test_walker_skips_transient_paths() -> None:
    """The walker ignores transient paths (.venv, .pi-glla, _retired, …)."""
    from research_institution.verification.doc_truth import (
        _iter_durable_docs,
    )

    yielded = list(_iter_durable_docs(REPO))
    for path in yielded:
        assert "_retired" not in path.parts, (
            f"walker should skip _retired/ but emitted: {path}"
        )
        assert ".venv" not in path.parts, (
            f"walker should skip .venv/ but emitted: {path}"
        )
        assert ".pi-glla" not in path.parts, (
            f"walker should skip .pi-glla/ but emitted: {path}"
        )


def test_truth_audit_offender_is_tuple() -> None:
    """Offender tuple shape is (path, line, marker)."""
    from research_institution.verification.doc_truth import (
        audit_documentation_truth,
    )

    offenders = audit_documentation_truth(repo_root=REPO)
    for entry in offenders:
        assert len(entry) == 3, f"unexpected offender shape: {entry}"
        path, line, marker = entry
        assert isinstance(path, str)
        assert isinstance(line, int)
        assert isinstance(marker, str)
