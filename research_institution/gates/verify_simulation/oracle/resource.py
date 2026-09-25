"""Resource oracle (entry 06 T2.5).

Verifies the subprocess count returns to the baseline after a
scenario run. On macOS, ``ps`` enumeration captures the
supervisor + fake-Pi + fixture subprocesses; a successful run
reaps them all via the supervisor's ``stop()`` (per entry 05's
``process_tree_cleanup.reap_subprocess_tree``).

The oracle accepts a callable ``baseline_subprocess_count`` and
``current_subprocess_count`` so the harness can inject both
snapshots. When the run is hermetic, the snapshots are
identical; when the run preserves temp_root on failure, the
oracle returns ``OVER_BUDGET`` instead of FAIL (so the operator
sees a clear "look at the preserved root" signal).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

__all__ = ["ResourceReport", "resource_oracle"]


@dataclass(frozen=True, slots=True)
class ResourceReport:
    """Resource oracle verdict."""

    verdict: str  # "PASS" | "FAIL" | "OVER_BUDGET"
    baseline_subprocess_count: int
    current_subprocess_count: int
    detail: str = ""


def resource_oracle(
    *,
    baseline_subprocess_count: int,
    current_subprocess_count: int,
    preserved: bool = False,
) -> ResourceReport:
    """Compare baseline vs current subprocess counts."""
    if preserved:
        return ResourceReport(
            verdict="OVER_BUDGET",
            baseline_subprocess_count=baseline_subprocess_count,
            current_subprocess_count=current_subprocess_count,
            detail="temp_root preserved on failure; baseline comparison skipped",
        )
    if current_subprocess_count > baseline_subprocess_count:
        return ResourceReport(
            verdict="FAIL",
            baseline_subprocess_count=baseline_subprocess_count,
            current_subprocess_count=current_subprocess_count,
            detail=(
                f"subprocess count grew: baseline={baseline_subprocess_count}, "
                f"current={current_subprocess_count}"
            ),
        )
    return ResourceReport(
        verdict="PASS",
        baseline_subprocess_count=baseline_subprocess_count,
        current_subprocess_count=current_subprocess_count,
    )


def _psutil_subprocess_count() -> int:
    """Return the live process count via psutil (default snapshot)."""
    import psutil

    return sum(1 for _ in psutil.process_iter())
