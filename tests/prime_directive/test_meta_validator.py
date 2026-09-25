"""Unit tests for meta_validator (entry 09 M2)."""

from __future__ import annotations

from pathlib import Path

from research_institution.prime_directive.meta_validator import (
    validate_all_metas,
    validate_meta,
)


GOOD_META = """\
# 99 — sample META

```toml
[meta]
spec_id = "99-sample-entry"
owner_repo = "research-institution"
owner_repos = ["research-institution"]
baseline_sha = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
completion_sha = "cafebabecafebabecafebabecafebabecafebabe"
gate_report_digest = "{digest}"
durable_anchors_added = []
durable_anchors_cited = ["@ADR-9999"]
transient_anchors_retired = []
unblocked_dependents = ["10-verification-release-closure"]

[constitution_compliance]
section_0  = "PASS"
section_1  = "PASS"
section_2  = "PASS"
section_3  = "PASS"
section_4  = "PASS"
section_5  = "PASS"
section_6  = "PASS"
section_7  = "PASS"
section_8  = "PASS"
section_9  = "PASS"
section_10 = "PASS"
section_11 = "PASS"
section_12 = "PASS"
```
"""


def test_validate_meta_pass(tmp_path: Path) -> None:
    p = tmp_path / "META.md"
    p.write_text(GOOD_META, encoding="utf-8")
    res = validate_meta(p)
    assert res.verdict == "PASS"
    assert res.spec_id == "99-sample-entry"


def test_validate_meta_strict_rejects_pending(tmp_path: Path) -> None:
    body = GOOD_META.replace(
        'baseline_sha = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"',
        'baseline_sha = "PENDING"',
    )
    p = tmp_path / "META.md"
    p.write_text(body, encoding="utf-8")
    res = validate_meta(p, strict_placeholders=True)
    assert res.verdict == "FAIL"


def test_validate_meta_missing_section(tmp_path: Path) -> None:
    body = GOOD_META.replace(
        'section_12 = "PASS"\n', ""
    )
    p = tmp_path / "META.md"
    p.write_text(body, encoding="utf-8")
    res = validate_meta(p)
    assert res.verdict == "FAIL"


def test_validate_meta_no_toml_block(tmp_path: Path) -> None:
    p = tmp_path / "META.md"
    p.write_text("# 99 — no TOML body", encoding="utf-8")
    res = validate_meta(p)
    assert res.verdict == "FAIL"


def test_validate_meta_not_applicable(tmp_path: Path) -> None:
    p = tmp_path / "does-not-exist.md"
    res = validate_meta(p)
    assert res.verdict == "NOT_APPLICABLE"


def test_validate_all_metas_discovers_repo_directory(tmp_path: Path) -> None:
    specs = tmp_path / ".specify" / "specs"
    (specs / "99-sample-entry").mkdir(parents=True)
    (specs / "99-sample-entry" / "META.md").write_text(GOOD_META, encoding="utf-8")
    (specs / "00-no-meta").mkdir(parents=True)
    # Place an empty META.md that fails (or NA). The package reads
    # every */META.md under the dir.
    results = validate_all_metas(specs)
    assert len(results) == 1  # only 99-sample-entry has META.md
    verdicts = {r.verdict for r in results}
    assert verdicts == {"PASS"}
