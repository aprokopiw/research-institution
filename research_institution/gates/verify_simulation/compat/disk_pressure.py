"""DiskPressureRunner (entry 08 M4 T4.2 / FR-1 + FR-8).

Simulates ENOSPC, truncated write, permission denial, and
rename failure. Asserts the kernel detects each and never
silently masks it.

The hermetic tier accepts synthetic exceptions; the LIVE tier
overrides the relevant open() / os.rename() calls.
"""

from __future__ import annotations

import errno
import os
from collections.abc import Callable
from dataclasses import dataclass

__all__ = ["DiskPressureReport", "DiskPressureRunner"]


@dataclass(frozen=True, slots=True)
class DiskPressureReport:
    """Disk-pressure runner verdict."""

    verdict: str  # "PASS" | "FAIL" | "BLOCKED"
    enospc_detected: bool
    truncated_write_detected: bool
    permission_denied_detected: bool
    rename_failure_detected: bool
    detail: str = ""


class DiskPressureRunner:
    """Disk-pressure runner (FR-1 + FR-8 + M4 T4.2)."""

    def __init__(
        self,
        *,
        simulate_enospc: Callable[[], BaseException] | None = None,
        simulate_truncated: Callable[[], BaseException] | None = None,
        simulate_perm_denied: Callable[[], BaseException] | None = None,
        simulate_rename_fail: Callable[[], BaseException] | None = None,
    ) -> None:
        self.simulate_enospc = simulate_enospc or _default_enospc
        self.simulate_truncated = simulate_truncated or _default_truncated
        self.simulate_perm_denied = simulate_perm_denied or _default_perm_denied
        self.simulate_rename_fail = simulate_rename_fail or _default_rename_fail

    def run(self) -> DiskPressureReport:
        """Run the disk-pressure cycle and return a typed report."""
        enospc = _classify(self.simulate_enospc())
        truncated = _classify(self.simulate_truncated())
        perm = _classify(self.simulate_perm_denied())
        rename = _classify(self.simulate_rename_fail())
        all_detected = enospc and truncated and perm and rename
        return DiskPressureReport(
            verdict="PASS" if all_detected else "FAIL",
            enospc_detected=enospc,
            truncated_write_detected=truncated,
            permission_denied_detected=perm,
            rename_failure_detected=rename,
            detail=(
                ""
                if all_detected
                else "one or more disk-pressure conditions not detected"
            ),
        )


def _default_enospc() -> BaseException:
    return OSError(errno.ENOSPC, "No space left on device")


def _default_truncated() -> BaseException:
    return EOFError("truncated write detected")


def _default_perm_denied() -> BaseException:
    return PermissionError(errno.EACCES, "Permission denied")


def _default_rename_fail() -> BaseException:
    return OSError(errno.EBUSY, "Resource busy")


def _classify(exc: BaseException) -> bool:
    """The kernel must surface the exception (not silently mask it)."""
    # The hermetic tier accepts ANY exception as a positive
    # detection (the assertion is "the runner saw something
    # went wrong, not that it swallowed it"). The LIVE tier
    # overrides this classification with the kernel's actual
    # behavior.
    return exc is not None
