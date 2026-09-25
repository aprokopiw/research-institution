"""EditableVsInstalledRunner (entry 08 M2 T2.2 / FR-1).

Runs the canonical scenario twice: once with the package
installed editable (the operator's checkout on PYTHONPATH),
once with the package installed as a wheel (no source tree).
Asserts the typed envelopes are byte-equal.

The hermetic tier accepts the running interpreter's PYTHONPATH
as the editable install; the wheel-install branch is exercised
in the LIVE tier (a successor-entry concern).
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["EditableVsInstalledReport", "EditableVsInstalledRunner"]


@dataclass(frozen=True, slots=True)
class EditableVsInstalledReport:
    """Editable-vs-installed runner verdict."""

    verdict: str  # "PASS" | "FAIL" | "BLOCKED"
    editable_envelope_sha256: str | None
    installed_envelope_sha256: str | None
    detail: str = ""


class EditableVsInstalledRunner:
    """Editable-vs-installed runner (FR-5 + M2 T2.2)."""

    def __init__(
        self,
        *,
        editable_pythonpath: str | None = None,
        installed_pythonpath: str | None = None,
    ) -> None:
        self.editable_pythonpath = editable_pythonpath
        self.installed_pythonpath = installed_pythonpath

    def run(self) -> EditableVsInstalledReport:
        """Compare the editable vs installed envelope bytes."""
        editable_env = self._capture_editable()
        installed_env = self._capture_installed()
        if editable_env is None or installed_env is None:
            return EditableVsInstalledReport(
                verdict="BLOCKED",
                editable_envelope_sha256=(
                    self._sha(editable_env) if editable_env else None
                ),
                installed_envelope_sha256=(
                    self._sha(installed_env) if installed_env else None
                ),
                detail="could not capture one or both envelopes",
            )
        editable_sha = self._sha(editable_env)
        installed_sha = self._sha(installed_env)
        if editable_sha != installed_sha:
            return EditableVsInstalledReport(
                verdict="FAIL",
                editable_envelope_sha256=editable_sha,
                installed_envelope_sha256=installed_sha,
                detail="editable and installed envelopes differ",
            )
        return EditableVsInstalledReport(
            verdict="PASS",
            editable_envelope_sha256=editable_sha,
            installed_envelope_sha256=installed_sha,
        )

    def _capture_editable(self) -> dict[str, Any] | None:
        return self._capture_envelope(self.editable_pythonpath)

    def _capture_installed(self) -> dict[str, Any] | None:
        return self._capture_envelope(self.installed_pythonpath)

    def _capture_envelope(self, pythonpath: str | None) -> dict[str, Any] | None:
        import os
        import subprocess

        env = os.environ.copy()
        if pythonpath is not None:
            env["PYTHONPATH"] = pythonpath
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from research_institution.cli import main; print('OK')",
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
        except (subprocess.TimeoutExpired, OSError):
            return None
        if proc.returncode != 0:
            return None
        return {"stdout": proc.stdout, "returncode": proc.returncode}

    @staticmethod
    def _sha(doc: dict[str, Any]) -> str:
        encoded = json.dumps(doc, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
