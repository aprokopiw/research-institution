"""Compat package for entry 08 installed-compatibility-recovery.

Submodules:

  * ``matrix`` — ``CompatMatrixRunner`` (M2 T2.1).
  * ``editable`` — ``EditableVsInstalledRunner`` (M2 T2.2).
  * ``rollback`` — ``RollbackRunner`` (M3 T3.1).
  * ``backup`` — ``BackupRestoreRunner`` (M3 T3.2).
  * ``corruption`` — ``CorruptionRunner`` (M4 T4.1).
  * ``disk_pressure`` — ``DiskPressureRunner`` (M4 T4.2).
  * ``python_versions`` — the supported Python-version matrix
    (FR-4).

The runners are pure functions of their inputs. The hermetic
tier uses synthetic inputs (a tmp HOME, a tmp state dir, a
synthetic scenario stream); the LIVE tier builds clean venvs
per cell. This package exists to keep the LIVE-tier heavy
lifting out of the canonical test surface.
"""

from research_institution.gates.verify_simulation.compat.matrix import (
    CompatCell,
    CompatMatrixReport,
    CompatMatrixRunner,
)
from research_institution.gates.verify_simulation.compat.editable import (
    EditableVsInstalledReport,
    EditableVsInstalledRunner,
)
from research_institution.gates.verify_simulation.compat.rollback import (
    RollbackReport,
    RollbackRunner,
)
from research_institution.gates.verify_simulation.compat.backup import (
    BackupRestoreReport,
    BackupRestoreRunner,
)
from research_institution.gates.verify_simulation.compat.corruption import (
    CorruptionReport,
    CorruptionRunner,
)
from research_institution.gates.verify_simulation.compat.disk_pressure import (
    DiskPressureReport,
    DiskPressureRunner,
)

__all__ = [
    "BackupRestoreReport",
    "BackupRestoreRunner",
    "CompatCell",
    "CompatMatrixReport",
    "CompatMatrixRunner",
    "CorruptionReport",
    "CorruptionRunner",
    "DiskPressureReport",
    "DiskPressureRunner",
    "EditableVsInstalledReport",
    "EditableVsInstalledRunner",
    "RollbackReport",
    "RollbackRunner",
]
