from __future__ import annotations

import subprocess
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "check-prime-directive.sh"
FORBIDDEN_REFERENCE = "Spec " + "002"


def _run_guard(repository: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), str(repository)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_guard_accepts_repository_with_only_sanctioned_hits(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text(FORBIDDEN_REFERENCE, encoding="utf-8")

    result = _run_guard(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "no unsanctioned hits" in result.stdout


def test_guard_rejects_unsanctioned_hit(tmp_path: Path) -> None:
    (tmp_path / "module.py").write_text(
        f'REFERENCE = "{FORBIDDEN_REFERENCE}"\n', encoding="utf-8"
    )

    result = _run_guard(tmp_path)

    assert result.returncode == 1
    assert "1 unsanctioned hit(s)" in result.stdout
