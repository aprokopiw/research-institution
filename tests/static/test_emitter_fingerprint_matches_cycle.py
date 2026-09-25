"""test_emitter_fingerprint_matches_cycle.py

Regression test for the v2 attestation-digest drift bug surfaced when
three audited entries (00 / 01 / 02) carried attestation JSONs emitted
by an older formula of ``scripts/emit-attestation.py`` that no longer
matched the cycle adapter's current fingerprint. The cycle adapter
correctly reported them not-closed, blocking the worker at entry 00.

This test pins the byte-for-byte equivalence between:

* ``pi_monitor.work.sources.spec_kit_cycle._config_fingerprint``
  (and ``_compute_attestation_digest``)

* ``research_institution.scripts.emit_attestation._config_fingerprint``
  (and ``_compute_digest``)

A drift in either side flips this test red, so the next person who
touches either formula will see the failure up front instead of
discovering it the next time the worker tries to advance.

Run with ``pytest tests/static/test_emitter_fingerprint_matches_cycle.py``.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def _import_cycle_helpers():
    """Lazy import so the test reports a clear error if pi_monitor is absent."""
    mod = importlib.import_module("pi_monitor.work.sources.spec_kit_cycle")
    return mod._config_fingerprint, mod._compute_attestation_digest


def _import_emitter_helpers():
    """Import the emitter (path-bound script) without depending on PYTHONPATH."""
    import sys

    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    # The script's filename has hyphens; load via importlib under a safe name.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "research_inst_emit_attestation", scripts_dir / "emit-attestation.py"
    )
    assert spec and spec.loader, "emit-attestation.py failed to load"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._config_fingerprint, module._compute_digest


def _shared_globs():
    from pi_monitor.work.sources.spec_kit_cycle import SPEC_KIT_CYCLE_DEFAULT_GLOBS
    return list(SPEC_KIT_CYCLE_DEFAULT_GLOBS)


def test_config_fingerprint_matches_cycle(tmp_path: Path) -> None:
    """Adapter and emitter must produce the same fingerprint for the
    same ``(root, task_globs)``.
    """
    cfg_cycle, _ = _import_cycle_helpers()
    cfg_emit, _ = _import_emitter_helpers()

    globs = _shared_globs()
    root = tmp_path.resolve()

    fp_cycle = cfg_cycle(root, globs)
    fp_emit = cfg_emit(root, globs)
    assert fp_cycle == fp_emit, (
        "config_fingerprint diverged between adapter and emitter; "
        f"adapter={fp_cycle[:16]}... emitter={fp_emit[:16]}..."
    )


def test_digest_matches_cycle(tmp_path: Path) -> None:
    """``sha256(completion_sha | config_fingerprint)`` must agree across
    both helpers for the same input triple.
    """
    _, dg_cycle = _import_cycle_helpers()
    _, dg_emit = _import_emitter_helpers()

    globs = _shared_globs()
    root = tmp_path.resolve()
    # Deterministic 40-hex-byte completion_sha (any sha-looking hex is fine).
    completion_sha = "5ea145be18d509f9e4ade55f2843591421e1b09f"

    cfg_cycle, cfg_emit = _import_cycle_helpers()[0], _import_emitter_helpers()[0]
    fp_cycle = cfg_cycle(root, globs)
    fp_emit = cfg_emit(root, globs)
    assert fp_cycle == fp_emit

    dg_cycle_val = dg_cycle(completion_sha, fp_cycle)
    dg_emit_val = dg_emit(completion_sha, fp_emit)
    assert dg_cycle_val == dg_emit_val, (
        "digest diverged between adapter and emitter; "
        f"adapter={dg_cycle_val[:16]}... emitter={dg_emit_val[:16]}..."
    )


def test_glob_sort_invariant(tmp_path: Path) -> None:
    """Re-ordering the globs arg must not change the fingerprint.

    The adapter explicitly sorts before hashing; the emitter must too,
    or an operator who lists ``task_globs`` in a different order will
    see attested entries flip to not-closed.
    """
    cfg_cycle, _ = _import_cycle_helpers()
    cfg_emit, _ = _import_emitter_helpers()

    globs_a = [".specify/specs/*/tasks.md", ".specify/specs/*/META.md"]
    globs_b = [".specify/specs/*/META.md", ".specify/specs/*/tasks.md"]
    root = tmp_path.resolve()

    assert cfg_cycle(root, globs_a) == cfg_cycle(root, globs_b)
    assert cfg_emit(root, globs_a) == cfg_emit(root, globs_b)


def test_real_repo_attestations_validate(tmp_path: Path) -> None:
    """Every emitted attestation already on disk for entries 00/01/02
    must round-trip through the current cycle adapter's
    ``_audit_close_out_state`` and report closed=True.

    If this fails, the operator must re-run
    ``scripts/emit-attestation.py --write`` for the affected entry,
    OR audit why the prior META claim should not be honored.
    """
    sys_mod = importlib.import_module("pi_monitor.work.sources.spec_kit_cycle")
    spec_dirs = sys_mod._discover_spec_dirs
    audit = sys_mod._audit_close_out_state

    repo_root = Path(__file__).resolve().parents[2]
    task_globs = _shared_globs()
    found = False
    for entry_dir in spec_dirs(repo_root):
        meta = (entry_dir / "META.md").read_text()
        if "[meta]" not in meta:
            continue
        # Only assert against entries that *claim* audit-close-out
        # (have a non-PENDING completion_sha). Draft entries
        # legitimately return closed=False here.
        import re as _re
        m = _re.search(r'completion_sha\s*=\s*"([a-f0-9]+)"', meta)
        if not m:
            continue
        completion_sha = m.group(1)
        closed, reasons = audit(
            entry_dir,
            entry_dir.name,
            completion_sha,
            project_root=repo_root,
            task_globs=task_globs,
        )
        if not closed:
            pytest.fail(
                f"{entry_dir.name} closes via META + attestation on disk "
                f"(completion_sha={completion_sha[:12]}...) but the cycle "
                f"adapter says not closed: {reasons}. "
                f"Re-emit with `python scripts/emit-attestation.py --slug "
                f"{entry_dir.name} --write`."
            )
        found = True
    if not found:
        pytest.skip("no entry claims audit-close-out in this checkout")
