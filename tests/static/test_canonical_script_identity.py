"""Cross-repo identity check for the canonical prime-directive script.

Per `.specify/specs/00-verify-constitution-ratification/spec.md` FR-5
and the plan's T4.2, this module verifies:

  1. Every repo (research-institution, math, pi_monitor, kaplansky)
     carries ``scripts/check-prime-directive.sh`` reachable either as
     a symlink or as a byte-diff-equivalent copy of the canonical
     research-institution script.
  2. Every invocation of the script in ``--selftest`` mode produces
     identical canonical phrases (canonical-grep-present,
     sanctioned-globs-recognised) and identical exit codes.
  3. The script is reachable from this repo's working directory
     (`make check-prime-directive` exits 0 at HEAD).

Failure is gate `FAIL` per constitution §3.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path("/Users/erinprokopiw/Documents/andrei/research-institution")
CANONICAL = REPO / "scripts" / "check-prime-directive.sh"
SIBLING_SCRIPTS: dict[str, Path] = {
    "research-institution": CANONICAL,
    "math": REPO.parent / "math" / "scripts" / "check-prime-directive.sh",
    "pi_monitor": REPO.parent / "pi_monitor" / "scripts" / "check-prime-directive.sh",
    "kaplansky": REPO.parent / "kaplansky" / "scripts" / "check-prime-directive.sh",
}


def _run_selftest(script: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), "--selftest"],
        check=False,
        capture_output=True,
        text=True,
    )


def _run_canonical_grep(script: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script)],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )


@pytest.fixture(scope="module")
def canonical_bytes() -> bytes:
    assert CANONICAL.exists(), f"canonical script missing: {CANONICAL}"
    return CANONICAL.read_bytes()


@pytest.mark.parametrize("repo_name", sorted(SIBLING_SCRIPTS))
def test_sibling_script_resolves(repo_name: str) -> None:
    """Every sibling repo has a reachable script (symlink or copy)."""
    script = SIBLING_SCRIPTS[repo_name]
    assert script.exists() or script.is_symlink(), (
        f"{repo_name} has no scripts/check-prime-directive.sh"
    )


@pytest.mark.parametrize("repo_name", sorted(SIBLING_SCRIPTS))
def test_sibling_script_byte_equals_canonical(
    repo_name: str, canonical_bytes: bytes
) -> None:
    """Sibling script is a symlink or byte-diff-equivalent of canonical.

    Per @CTR-0095-prime-directive-check-script-contract and FR-5, the
    regex, sanctioned-globs list, and exit-code behaviour must be
    byte-equal across the four repos. Symlinks to the canonical
    script satisfy this trivially; explicit copies must match byte-
    for-byte.
    """
    script = SIBLING_SCRIPTS[repo_name]
    if script.is_symlink():
        # Resolve the symlink and compare bytes against the canonical.
        resolved = script.resolve()
        assert resolved == CANONICAL.resolve(), (
            f"{repo_name}'s script symlinks to {resolved}, "
            f"expected {CANONICAL}"
        )
        return
    assert script.exists(), f"{repo_name} script missing: {script}"
    actual = script.read_bytes()
    assert actual == canonical_bytes, (
        f"{repo_name}'s script drifted from canonical; "
        f"diff: {script} vs {CANONICAL}"
    )


@pytest.mark.parametrize("repo_name", sorted(SIBLING_SCRIPTS))
def test_sibling_selftest_exit_code(repo_name: str) -> None:
    """``--selftest`` exits 0 in every sibling repo."""
    script = SIBLING_SCRIPTS[repo_name]
    result = _run_selftest(script)
    assert result.returncode == 0, (
        f"{repo_name} --selftest exited {result.returncode}; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


@pytest.mark.parametrize("repo_name", sorted(SIBLING_SCRIPTS))
def test_sibling_selftest_emits_canonical_phrase(repo_name: str) -> None:
    """``--selftest`` reports the canonical identity phrase."""
    script = SIBLING_SCRIPTS[repo_name]
    result = _run_selftest(script)
    assert "self-test ok" in result.stdout, (
        f"{repo_name} --selftest stdout missing canonical phrase; "
        f"got: {result.stdout!r}"
    )
    assert "canonical grep present" in result.stdout, (
        f"{repo_name} --selftest stdout missing canonical-grep phrase; "
        f"got: {result.stdout!r}"
    )
    assert "sanctioned-globs recognised" in result.stdout, (
        f"{repo_name} --selftest stdout missing sanctioned-globs phrase; "
        f"got: {result.stdout!r}"
    )


def test_canonical_repo_grep_is_clean() -> None:
    """`make check-prime-directive` exits 0 in the canonical repo."""
    result = _run_canonical_grep(CANONICAL)
    assert result.returncode == 0, (
        f"canonical grep exited {result.returncode}; "
        f"stdout={result.stdout!r}"
    )


def test_canonical_script_is_executable() -> None:
    """The canonical script has the executable bit set."""
    mode = CANONICAL.stat().st_mode
    assert mode & 0o111, f"{CANONICAL} is not executable (mode={oct(mode)})"


def test_canonical_script_has_selftest_mode() -> None:
    """``bash scripts/check-prime-directive.sh --selftest`` is reachable
    and emits the deterministic identity report."""
    if shutil.which("bash") is None:
        pytest.skip("bash not on PATH")
    result = _run_selftest(CANONICAL)
    assert result.returncode == 0, result.stdout + result.stderr
    # Determinism: the report line starts with the canonical phrase
    # AND ends with the `pass` / `registry: …` footer.
    assert "pass" in result.stdout, result.stdout
    assert "registry:" in result.stdout, result.stdout
