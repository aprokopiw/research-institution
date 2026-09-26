"""Claim-manifest integrity check.

Cited contracts:
    @CTR-0101-release-gate-contract
    @CTR-0096-audit-close-out-runtime-evidence-contract
    @INV-0093-institution-green-gate-canonical

Asserts the durable CLAIM_MANIFEST.toml parses, every required
claim has ≥1 evidence node-id, and every claim's evidence
node-ids reference real pytest node-ids or registered
scenarios. The test is the static evidence surface for the
release-gate's row 2 (every_required_claim_has_evidence).

The test does NOT import production modules that require
running subprocesses; it is hermetic by construction.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO / "docs" / "semantic" / "CLAIM_MANIFEST.toml"

# Pytest node-id regex: ``<path>::<ClassName>::<test_name>`` or
# ``<path>::<test_name>``.
_PYTEST_NODE_ID_RE = re.compile(r"^[\w/.\-]+\.py::[\w]+(::[\w]+)?$")


def _load_manifest() -> dict[str, object]:
    if not MANIFEST_PATH.exists():
        pytest.skip(f"claim manifest missing: {MANIFEST_PATH}")
    return tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_claim_manifest_parses() -> None:
    """The manifest parses as TOML with the required schema_version."""
    doc = _load_manifest()
    assert doc.get("schema_version") == 1, (
        f"unexpected schema_version: {doc.get('schema_version')}"
    )
    assert isinstance(doc.get("claim"), list) and doc["claim"], (
        "manifest must declare a non-empty [[claim]] array"
    )


def test_every_required_claim_has_at_least_one_evidence() -> None:
    """Every required claim carries ≥1 evidence node-id."""
    doc = _load_manifest()
    claims = doc["claim"]
    zero_evidence = [
        c["id"] for c in claims
        if c.get("required") and not c.get("evidence_node_ids")
    ]
    assert not zero_evidence, (
        "required claims with zero evidence: "
        + ", ".join(str(x) for x in zero_evidence)
    )


def test_every_claim_has_canonical_name() -> None:
    """Every claim's name is one of the seven canonical release rows."""
    from research_institution.gates.verify_simulation.release import (
        CANONICAL_CHECK_NAMES,
    )

    canonical_names = set(CANONICAL_CHECK_NAMES)
    doc = _load_manifest()
    claims = doc["claim"]
    bad_names = [
        c["id"] for c in claims if c.get("name") not in canonical_names
    ]
    assert not bad_names, (
        f"claims with non-canonical names: {bad_names}; "
        f"canonical: {sorted(canonical_names)}"
    )


def test_evidence_node_ids_are_well_formed() -> None:
    """Every evidence node-id either matches a pytest node-id
    or is a registered verify-simulation scenario name.
    """
    from research_institution.gates.verify_simulation.scenarios import (
        all_scenarios,
    )

    scenario_names = {s.name for s in all_scenarios()}
    doc = _load_manifest()
    claims = doc["claim"]
    offenders: list[str] = []
    for claim in claims:
        for node_id in claim.get("evidence_node_ids", []):
            if node_id in scenario_names:
                continue
            if _PYTEST_NODE_ID_RE.match(node_id):
                continue
            offenders.append(f"{claim['id']}: {node_id}")
    assert not offenders, (
        "evidence node-ids must be pytest node-ids or scenario names:\n  "
        + "\n  ".join(offenders)
    )


def test_required_tier_is_in_closed_set() -> None:
    """Every claim's tier is in the §1 closed set."""
    canonical = {
        "unit",
        "property",
        "contract",
        "integration",
        "process",
        "deployment",
        "provider_live",
        "soak",
    }
    doc = _load_manifest()
    offenders = [
        c["id"] for c in doc["claim"]
        if c.get("tier") not in canonical
    ]
    assert not offenders, (
        f"claims with off-vocab tier: {offenders}; canonical: {sorted(canonical)}"
    )
