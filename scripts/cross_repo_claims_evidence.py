#!/usr/bin/env python3
"""Cross-repo claim-by-claim evidence harness.

Runs the cross-repo-consequential tests for the composed state of
the four repos (research-institution / math / pi_monitor / kaplansky).
Emits a JSON matrix describing which claims are backed by which
tests + their pass/fail.

The harness is the V2 evidence for the composed state. It does NOT
re-implement the green gate (that's `scripts/verify-institution.sh`);
it runs the seven foundational tests that exercise the cross-repo
seam between math + research-institution + pi_monitor.

Usage:

    python scripts/cross_repo_claims_evidence.py

Output:

    -- prints claim-by-claim summary to stdout
    -- writes /tmp/verify/claims-matrix.json with timestamp

Exit code 0 iff all 8 claims PASS.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, UTC

ROOT = "/Users/erinprokopiw/Documents/andrei"

REPOS = {
    "research-institution": f"{ROOT}/research-institution",
    "math": f"{ROOT}/math",
    "pi_monitor": f"{ROOT}/pi_monitor",
}
PYTHONS = {repo: os.path.join(REPOS[repo], ".venv/bin/python3") for repo in REPOS}
HAS_COV = {
    "math": True,
    "pi_monitor": True,
    "research-institution": False,
}

CLAIMS = [
    (
        "CLAIM-1",
        "@ADR-0011 wire schema byte-identical to pre-@ADR-0011 (DecisionKind / RoleName / reason-code set / envelope data-class shape)",
        ["research-institution/tests/test_wire_schema_unchanged.py"],
    ),
    (
        "CLAIM-2",
        "pi_monitor <-> mathlint cross-repo wire round-trip (ExecutionReportWireModel -> LiveSource.handle -> result_ack)",
        ["pi_monitor/tests/test_cross_repo_wire_round_trip.py"],
    ),
    (
        "CLAIM-3",
        "math consult() wrapper is pure (does not mutate artifacts / deltas ledger / audit / horizon files)",
        ["math/tests/integration/test_live_source_snapshot.py"],
    ),
    (
        "CLAIM-4",
        "compute_directive_content_hash() is byte-stable across compilations (researcher + architect paths, matches compiler output)",
        ["math/tests/integration/test_live_source_snapshot.py"],
    ),
    (
        "CLAIM-5",
        "Stagnation table translates verdict_kind correctly: 0 no-delta -> DISPATCH_RESEARCH; 2+ no-delta -> ARCHITECTURE_REVIEW_REQUIRED; 3+ with architect_synthesis -> DISPATCH_ARCHITECT; no roadmap -> NO_ELIGIBLE_WORK",
        ["math/tests/integration/test_live_source_snapshot.py"],
    ),
    (
        "CLAIM-6",
        "OS-side WorkRequest payload carries PAYLOAD_KEY_MATH_DIRECTIVE_CONTENT_HASH / TEMPLATE_HASH / STAGNATION_SESSION_COUNT / MATH_TARGET",
        [
            "research-institution/tests/test_source_decision_stagnation.py",
            "research-institution/tests/test_source_decision_contract.py",
        ],
    ),
    (
        "CLAIM-7",
        "CANONICAL_REASON_CODES is byte-equal across research-institution / pi_monitor (cross-repo identity)",
        ["research-institution/tests/test_cross_repo_type_identity.py"],
    ),
    (
        "CLAIM-8",
        "OS can sub-decide on real math projects: arbitrary (decision, revision) input -> deterministic correct envelope (property-test)",
        ["research-institution/tests/test_composed_dispatch_property.py"],
    ),
]


def run_claim(cid: str, name: str, files: list[str]) -> dict:
    repo = files[0].split("/")[0]
    cwd = REPOS[repo]
    py = PYTHONS[repo]
    test_args = [os.path.join(ROOT, f) for f in files]
    dedup_args = list(dict.fromkeys(test_args))
    env = os.environ.copy()
    if repo == "pi_monitor":
        env["PYTHONPATH"] = (
            f"{ROOT}/research-institution" + ":" + env.get("PYTHONPATH", "")
        )
    cov_args = ["--no-cov", "-p", "no:cacheprovider"] if HAS_COV[repo] else []
    try:
        result = subprocess.run(
            [py, "-m", "pytest", "-v", "--tb=short"] + cov_args + dedup_args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "id": cid,
            "name": name,
            "evidence": ", ".join(files),
            "rc": -1,
            "passed": 0,
            "failed": 0,
            "result": "FAIL (TIMEOUT)",
        }
    full = (result.stdout or "") + (result.stderr or "")
    n_pass = len(re.findall(r"\bPASSED\b", full))
    n_fail = len(re.findall(r"\bFAILED\b", full))
    pass_summary = re.search(r"(\d+)\s+passed", full)
    fail_summary = re.search(r"(\d+)\s+failed", full)
    if pass_summary:
        n_pass = max(n_pass, int(pass_summary.group(1)))
    if fail_summary:
        n_fail = max(n_fail, int(fail_summary.group(1)))
    rc = result.returncode
    return {
        "id": cid,
        "name": name,
        "evidence": ", ".join(files),
        "rc": rc,
        "passed": n_pass,
        "failed": n_fail,
        "result": "PASS" if (n_pass > 0 and n_fail == 0 and rc == 0) else f"FAIL (rc={rc})",
    }


def main() -> int:
    print(f"=== Cross-repo claim-by-claim evidence harness ===")
    print(f"=== generated at {datetime.now(UTC).isoformat()} ===")
    print(f"repos under test: {', '.join(REPOS)}")
    print()
    matrix = []
    n_pass_claims = 0
    for cid, name, files in CLAIMS:
        row = run_claim(cid, name, files)
        matrix.append(row)
        status = row["result"]
        if status == "PASS":
            n_pass_claims += 1
        print(f"{cid:<8} {status:<11} {row['passed']}/{row['failed']:<3} rc={row['rc']:<3}  {name}")
    print()
    print(f"Total: {n_pass_claims}/{len(CLAIMS)} claims PASS")
    os.makedirs("/tmp/verify", exist_ok=True)
    with open("/tmp/verify/claims-matrix.json", "w") as f:
        json.dump(
            {
                "claims": matrix,
                "generated_at": datetime.now(UTC).isoformat(),
                "status": (
                    "GREEN-V2"
                    if n_pass_claims == len(CLAIMS)
                    else "RED"
                ),
            },
            f,
            indent=2,
        )
    print(f"Matrix saved to /tmp/verify/claims-matrix.json")
    return 0 if n_pass_claims == len(CLAIMS) else 1


if __name__ == "__main__":
    sys.exit(main())
