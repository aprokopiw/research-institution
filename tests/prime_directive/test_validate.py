"""Unit tests for validate (entry 09 M2)."""

from __future__ import annotations

import json
from pathlib import Path

from research_institution.prime_directive.attest import attest
from research_institution.prime_directive.validate import (
    AttestationResult,
    validate_attestation,
)


def _sha(n: int) -> str:
    return f"{n:040d}"


def test_validate_attestation_pass(tmp_path: Path) -> None:
    payload = attest(
        spec_id="09-prime-directive-mechanical-enforcement",
        completion_sha=_sha(1),
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
    # Caller passes completion_sha as already-reachable (validated
    # against the local reflog); supply reachable_shas to skip the
    # git rev-list call.
    res = validate_attestation(
        out,
        root=tmp_path,
        reachable_shas=(_sha(1),),
    )
    assert isinstance(res, AttestationResult)
    assert res.verdict == "PASS"
    assert res.completion_sha == _sha(1)


def test_validate_attestation_blocked_when_completion_sha_unreachable(tmp_path: Path) -> None:
    payload = attest(
        spec_id="09-prime-directive-mechanical-enforcement",
        completion_sha=_sha(2),
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
    res = validate_attestation(
        out,
        root=tmp_path,
        reachable_shas=(),  # nothing reachable in this hermetic setting
    )
    assert res.verdict == "BLOCKED"


def test_validate_attestation_fail_when_digest_tampered(tmp_path: Path) -> None:
    payload = attest(
        spec_id="09-prime-directive-mechanical-enforcement",
        completion_sha=_sha(3),
        root=tmp_path,
    )
    bad = dict(payload)
    bad["digest"] = "0" * 64
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    res = validate_attestation(
        bad_path,
        root=tmp_path,
        reachable_shas=(_sha(3),),
    )
    assert res.verdict == "FAIL"
    assert res.detail == "digest mismatch"
