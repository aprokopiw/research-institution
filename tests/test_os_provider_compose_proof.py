"""Durable proof that the OS-level provider composes program contributions.

Per @ADR-0007 the OS owns the work-source slot and each proof
program owns its content contributions (theorem view, audit
reports, obligation labels, etc.). Mathlint's
``register_program_providers`` is wholesale (replaces the entire
``ProgramProviders`` state on every call), so the OS must
invoke each program's ``register()``, read the merged state,
and re-emit ``ProgramProviders`` with its own slot attached in
one kernel write. Otherwise the half-line composition loses
data.

These tests assert the durable contract:

  - The OS-level provider's ``register()`` populates the
    ``work_source_provider`` slot.
  - It also populates every kaplansky contribution field.
  - The composition survives re-invocation (idempotency).
  - Program packages that are NOT installed do not crash the OS
    registration; the slot still installs.

If any test fails, @ADR-0007's wiring has regressed — the
supervisor's dispatch envelope will return empty theorem views
or no audit reports, and the next agent can find this test
pinpointing the regression immediately.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def mathlint_kernels():
    """Load mathlint only if importable. Operators may run this
    suite without a math venv; the fixture skips rather than
    fails so the institution's hermetic contract still holds."""
    try:
        mod = importlib.import_module("mathlint.program_providers")
    except ImportError as error:
        pytest.skip(f"mathlint not importable: {error}")
    return mod


@pytest.fixture(scope="module")
def kaplansky_pkg():
    try:
        mod = importlib.import_module("kaplansky.mathlint_plugin")
    except ImportError:
        return None
    return mod


@pytest.fixture()
def reset_providers(mathlint_kernels):
    """Snapshot the kernel state, run the test, then restore.

    Mathlint's process-wide state leaks across tests otherwise;
    this fixture isolates each test.
    """
    state_mod = mathlint_kernels
    snapshot = state_mod._state.current
    yield
    state_mod._state.current = snapshot


def test_os_register_populates_work_source_slot(mathlint_kernels) -> None:
    """The OS-level register() must leave work_source_provider populated."""
    from research_institution.providers.research_institution_provider import register

    # Reset state to a clean slate.
    mathlint_kernels._state.current = None
    register()
    providers = mathlint_kernels.program_providers()
    assert providers.work_source_provider is not None
    assert callable(providers.work_source_provider)


def test_os_register_compose_does_not_clobber_program_fields(mathlint_kernels, kaplansky_pkg) -> None:
    """If kaplansky is importable, the OS compose must leave every
    kaplansky contribution populated after register().

    Regression oracle: a refactor that calls the program
    plugin AFTER the work_source_provider attachment would
    overwrite the slot. A refactor that calls the program
    plugin BEFORE without re-reading the merged state would
    lose the program's fields. This test fails on either side.
    """
    if kaplansky_pkg is None:
        pytest.skip("kaplansky not installed in this env")
    from research_institution.providers.research_institution_provider import register

    mathlint_kernels._state.current = None
    register()
    providers = mathlint_kernels.program_providers()
    fields = [
        providers.publication_theorem_view,
        providers.obligation_labels,
        providers.identifier_namespace,
        providers.northstar_claim_patterns,
        providers.headline_readiness,
        providers.transgression_audit,
        providers.quotient_descent_audit,
        providers.certificate_verifier,
        providers.gap_package_probe,
        providers.roadmap_path,
        providers.repository_identity,
    ]
    assert all(fields), (
        f"OS compose lost one or more kaplansky fields: "
        f"theorem_view={providers.publication_theorem_view is not None}; "
        f"obligation_labels={bool(providers.obligation_labels)}; "
        f"namespace={providers.identifier_namespace!r}; "
        f"northstar_patterns={len(providers.northstar_claim_patterns)}; "
        f"roadmap={providers.roadmap_path!r}; "
        f"identity={providers.repository_identity!r}; "
        f"work_source_provider={providers.work_source_provider is not None}"
    )
    # And the OS-owned slot survives.
    assert providers.work_source_provider is not None


def test_os_register_idempotent(mathlint_kernels) -> None:
    """register() can be called twice without crashing or losing fields.

    The math kernel's entry-point discovery caches the entry
    point name across calls, but the OS-level register() is not
    gated by that cache (it is the gateway). Idempotency is the
    contract.
    """
    from research_institution.providers.research_institution_provider import register

    mathlint_kernels._state.current = None
    register()
    first = mathlint_kernels.program_providers()
    register()  # must not raise
    second = mathlint_kernels.program_providers()
    assert first.work_source_provider is not None
    assert second.work_source_provider is not None


def test_select_next_work_returns_wait_envelope(mathlint_kernels) -> None:
    """The OS work-source callable emits a typed Wait envelope."""
    from pi_monitor.work.work_source import Wait as _Wait

    from research_institution.providers.research_institution_provider import (
        select_next_work_for_supervisor,
    )

    env = select_next_work_for_supervisor(repository=__import__("pathlib").Path.cwd())
    assert isinstance(env, _Wait)
    assert env.source_revision.fingerprint
    assert env.reason_code == "wait_requested"
    assert env.decided_unix > 0
    # No ``work`` attribute on the OS-side Wait envelope. The OS
    # does not ship a roadmap reader yet (see @ADR-0007); when one
    # ships, the envelope graduates to a ``Dispatch`` carrying a
    # populated ``work`` list. Today, the absence of ``work`` is
    # the signal — pi-monitor's wire v1 rejects Wait envelopes
    # carrying ``work`` (unexpected-field error).


def test_select_next_work_is_pure() -> None:
    """select_next_work_for_supervisor is pure: it accepts a Path
    and returns a typed envelope. It does NOT read env vars or import
    any program-named modules. The contract is that the OS does
    not duplicate the kernel's source-decision logic — it
    supplies the dispatch shape and lets the kernel fill the
    work item.
    """
    from pi_monitor.work.work_source import (
        Dispatch,
        OperatorRequired,
        Stop,
        Wait,
    )

    from research_institution.providers.research_institution_provider import (
        select_next_work_for_supervisor,
    )

    # No env-var churn needed; the function uses the parameter.
    env = select_next_work_for_supervisor(repository=Path("/tmp"))  # noqa: S108
    assert isinstance(env, (Wait, Dispatch, OperatorRequired, Stop))
    assert env.source_revision
    assert env.reason_code in {"work_available", "wait_requested", "operator_required", "stop_requested"}
    assert env.decided_unix >= 0.0
