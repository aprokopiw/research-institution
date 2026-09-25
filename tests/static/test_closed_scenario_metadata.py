"""Closed-scenario metadata test (entry 06 T3.2).

Every registered scenario in ``verify_simulation.scenarios`` MUST
carry the canonical metadata keys per FR-6 of the spec. A scenario
missing any of the keys surfaces here. The static check is also
responsible for the private-import / manual-finalize grep
verifications per FR-4 (the harness does NOT call private
supervisor methods or manual finalize helpers).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def test_every_registered_scenario_has_canonical_keys() -> None:
    """Every registered scenario carries the FR-6 metadata keys."""
    from research_institution.gates.verify_simulation.scenarios import (
        all_scenarios,
        metadata_dict,
    )

    canonical_keys = {
        "name",
        "owner",
        "minimum_tier",
        "maximum_runtime_seconds",
        "fault_injection_point",
        "expected_final_state",
        "required_event_subsequence",
        "forbidden_events",
        "cleanup_expectations",
        "source_path",
        "notes",
    }
    for scenario in all_scenarios():
        meta = metadata_dict(scenario)
        missing = canonical_keys - set(meta.keys())
        assert not missing, (
            f"scenario {scenario.name!r} missing metadata keys: {sorted(missing)}"
        )


def test_every_registered_scenario_has_valid_owner() -> None:
    from research_institution.gates.verify_simulation.scenarios import (
        all_scenarios,
    )

    valid_owners = {"math", "pi_monitor"}
    for scenario in all_scenarios():
        assert scenario.owner in valid_owners, (
            f"scenario {scenario.name!r} has invalid owner: {scenario.owner}"
        )


def test_every_registered_scenario_has_positive_runtime() -> None:
    from research_institution.gates.verify_simulation.scenarios import (
        all_scenarios,
    )

    for scenario in all_scenarios():
        assert scenario.maximum_runtime_seconds > 0, (
            f"scenario {scenario.name!r} has non-positive runtime"
        )


def test_every_registered_scenario_has_valid_minimum_tier() -> None:
    from research_institution.gates.verify_simulation.scenarios import (
        all_scenarios,
    )

    valid_tiers = {
        "unit",
        "property",
        "contract",
        "integration",
        "process",
        "deployment",
        "provider_live",
        "soak",
    }
    for scenario in all_scenarios():
        assert scenario.minimum_tier in valid_tiers, (
            f"scenario {scenario.name!r} has invalid tier: {scenario.minimum_tier}"
        )


def test_verify_simulation_package_has_no_private_imports() -> None:
    """Per FR-4, the verify-simulation package MUST NOT import
    private pi_monitor supervisor methods. AST inspection finds
    any ``from pi_monitor.supervision._dispatch_loop import``
    statement.
    """
    pkg = REPO / "research_institution" / "gates" / "verify_simulation"
    offenders: list[str] = []
    for py_file in sorted(pkg.rglob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "_dispatch_loop" in module or "_supervisor" in module:
                    offenders.append(
                        f"{py_file}:{node.lineno}: private import {module}"
                    )
    assert not offenders, (
        "private imports found in verify-simulation package:\n  "
        + "\n  ".join(offenders)
    )


def test_verify_simulation_package_has_no_manual_finalize_calls() -> None:
    """Per FR-4, the harness MUST NOT call ``finalize_attempt`` /
    ``complete_active`` / ``record_publication``. AST inspection
    finds any name reference to these strings.
    """
    pkg = REPO / "research_institution" / "gates" / "verify_simulation"
    forbidden = {"finalize_attempt", "complete_active", "record_publication"}
    offenders: list[str] = []
    for py_file in sorted(pkg.rglob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden:
                offenders.append(f"{py_file}:{node.lineno}: {node.id}")
            elif (
                isinstance(node, ast.Attribute)
                and node.attr in forbidden
            ):
                offenders.append(f"{py_file}:{node.lineno}: {node.attr}")
    assert not offenders, (
        "manual finalize hooks referenced in verify-simulation:\n  "
        + "\n  ".join(offenders)
    )
