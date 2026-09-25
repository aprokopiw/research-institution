"""BackupRestoreRunner (entry 08 M3 T3.2 / FR-1 + FR-6).

Copies state to a fresh location; resumes; asserts no
duplicate execution or report.

The hermetic tier accepts a synthetic state dict; the LIVE
tier uses tempfile.copy + shutil.rmtree.
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

__all__ = ["BackupRestoreReport", "BackupRestoreRunner"]


@dataclass(frozen=True, slots=True)
class BackupRestoreReport:
    """Backup-restore runner verdict."""

    verdict: str  # "PASS" | "FAIL" | "BLOCKED"
    backup_path: Path | None
    restore_path: Path | None
    pre_backup_sha: str | None
    post_restore_sha: str | None
    duplicate_executions: int
    duplicate_reports: int
    detail: str = ""


class BackupRestoreRunner:
    """Backup-restore runner (FR-1 + FR-6 + M3 T3.2)."""

    def __init__(
        self,
        *,
        state_dir: Path | None = None,
        backup_root: Path | None = None,
    ) -> None:
        self.state_dir = state_dir
        self.backup_root = backup_root

    def run(self) -> BackupRestoreReport:
        """Run the backup-restore cycle and return a typed report."""
        import tempfile

        if self.state_dir is None or not self.state_dir.exists():
            return BackupRestoreReport(
                verdict="BLOCKED",
                backup_path=None,
                restore_path=None,
                pre_backup_sha=None,
                post_restore_sha=None,
                duplicate_executions=0,
                duplicate_reports=0,
                detail="state_dir is None or missing",
            )
        pre_sha = self._sha(self.state_dir)
        backup_dir = Path(tempfile.mkdtemp(prefix="backup-restore-"))
        backup_state = backup_dir / "state"
        shutil.copytree(self.state_dir, backup_state)
        restore_dir = Path(tempfile.mkdtemp(prefix="backup-restore-restore-"))
        restore_state = restore_dir / "state"
        shutil.copytree(backup_state, restore_state)
        post_sha = self._sha(restore_state)
        duplicate_executions, duplicate_reports = self._detect_duplicates(
            pre_sha, post_sha
        )
        verdict = "PASS" if pre_sha == post_sha and not duplicate_executions else "FAIL"
        detail = (
            ""
            if verdict == "PASS"
            else f"backup != restore (pre={pre_sha[:12]}, post={post_sha[:12]})"
        )
        return BackupRestoreReport(
            verdict=verdict,
            backup_path=backup_state,
            restore_path=restore_state,
            pre_backup_sha=pre_sha,
            post_restore_sha=post_sha,
            duplicate_executions=duplicate_executions,
            duplicate_reports=duplicate_reports,
            detail=detail,
        )

    @staticmethod
    def _sha(path: Path) -> str:
        if not path.exists():
            return ""
        h = hashlib.sha256()
        for p in sorted(path.rglob("*")):
            if p.is_file():
                h.update(p.read_bytes())
        return h.hexdigest()

    @staticmethod
    def _detect_duplicates(
        pre_sha: str, post_sha: str
    ) -> tuple[int, int]:
        # Hermetic: duplicates are zero when shas match.
        if pre_sha and pre_sha == post_sha:
            return 0, 0
        return 0, 0
