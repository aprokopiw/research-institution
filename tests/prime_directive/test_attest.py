"""Unit tests for attest (entry 09 M2)."""

from __future__ import annotations

from pathlib import Path

from research_institution.prime_directive.attest import (
    attest,
    compute_digest,
    config_fingerprint,
)


def _sha(n: int) -> str:
    return f"{n:040d}"


def test_config_fingerprint_is_sha256_and_stable() -> None:
    fp = config_fingerprint(Path("/tmp/institution"))
    assert isinstance(fp, str)
    assert len(fp) == 64
    again = config_fingerprint(Path("/tmp/institution"))
    assert fp == again
    # Different globs => different fp.
    other = config_fingerprint(Path("/tmp/institution"), task_globs=("foo.md",))
    assert other != fp


def test_compute_digest_matches_canonical_formula() -> None:
    fp = config_fingerprint(Path("/tmp/institution"))
    d = compute_digest(completion_sha=_sha(1), config_fingerprint_value=fp)
    expected_input = f"{_sha(1)}|{fp}".encode("utf-8")
    import hashlib as _h

    expected = _h.sha256(expected_input).hexdigest()
    assert d == expected


def test_attest_dry_run_returns_payload_without_writing(tmp_path: Path) -> None:
    payload = attest(
        spec_id="09-prime-directive-mechanical-enforcement",
        completion_sha=_sha(42),
        root=tmp_path,
        write=False,
    )
    assert payload["api_version"] == 1
    assert payload["slug"] == "09-prime-directive-mechanical-enforcement"
    assert payload["completion_sha"] == _sha(42)
    assert isinstance(payload["digest"], str)
    assert isinstance(payload["config_fingerprint"], str)
    # File was not written.
    out = (
        tmp_path
        / ".specify"
        / "specs"
        / "09-prime-directive-mechanical-enforcement"
        / ".pi-prime-attestations"
        / "09-prime-directive-mechanical-enforcement.json"
    )
    assert not out.exists()


def test_attest_write_persists_canonical_json(tmp_path: Path) -> None:
    payload = attest(
        spec_id="09-prime-directive-mechanical-enforcement",
        completion_sha=_sha(7),
        root=tmp_path,
        write=True,
    )
    out = (
        tmp_path
        / ".specify"
        / "specs"
        / "09-prime-directive-mechanical-enforcement"
        / ".pi-prime-attestations"
        / "09-prime-directive-mechanical-enforcement.json"
    )
    assert out.exists()
    import json as _json

    on_disk = _json.loads(out.read_text(encoding="utf-8"))
    assert on_disk == payload
