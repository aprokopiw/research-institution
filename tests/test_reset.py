"""Tests for the `reset` cleanup verb.

The reset verb composes the existing typed surface (catalog,
paths, supervisor probe) rather than re-implementing it. The
tests here therefore exercise:

  - Discovery invariants (stale vs alive classification).
  - Mutator refusals (never touch a live supervisor).
  - Dry-run vs --apply parity.
  - CLI argv shape (the verb's public surface).
  - End-to-end happy paths against an isolated filesystem.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from research_institution.reset import (
    AliveLock,
    DEFAULT_STALE_HEARTBEAT_SECONDS,
    ResetReport,
    StaleLock,
    StaleProcess,
    _pid_alive,
    discover_stale_locks,
    discover_stale_state_dirs,
    purge_state_dirs,
    remove_stale_locks,
    reset,
    terminate_stale_processes,
)


# ---------------------------------------------------------------------------
# Helpers: build an isolated state tree so tests don't depend on the
# operator's actual ~/.local/state. Each test gets a tmp_path with
# a fake PI_MONITOR_STATE_DIR and HOME; the reset module reads HOME
# for ``_expand_known_roots`` so we monkeypatch it explicitly.
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect HOME so ``_KNOWN_STATE_ROOTS`` resolves under tmp_path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def _make_state_dir(parent: Path, name: str) -> Path:
    d = parent / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_lock(state_dir: Path, pid: int) -> Path:
    lock = state_dir / "supervisor.lock"
    lock.write_text(str(pid), encoding="utf-8")
    return lock


def _write_state_json(state_dir: Path, *, heartbeat_unix: float, wedge_class: str) -> Path:
    state = state_dir / "state.json"
    state.write_text(
        json.dumps(
            {
                "supervisor_pid": 12345,
                "heartbeat_unix": heartbeat_unix,
                "last_wedge_class": wedge_class,
            }
        ),
        encoding="utf-8",
    )
    return state


# ---------------------------------------------------------------------------
# Unit tests for the mutators and discovery functions.
# ---------------------------------------------------------------------------


def test_pid_alive_returns_false_for_zero_and_negative() -> None:
    assert _pid_alive(0) is False
    assert _pid_alive(-1) is False


def test_remove_stale_locks_dry_run_returns_paths_without_unlinking(
    tmp_path: Path,
) -> None:
    lock = _write_lock(_make_state_dir(tmp_path, "kaplansky"), 99999)
    removed = remove_stale_locks([StaleLock(path=lock, stale_pid=99999)], dry_run=True)
    assert removed == (lock,)
    assert lock.exists()  # not touched


def test_remove_stale_locks_apply_unlinks(tmp_path: Path) -> None:
    lock = _write_lock(_make_state_dir(tmp_path, "kaplansky"), 99999)
    removed = remove_stale_locks([StaleLock(path=lock, stale_pid=99999)], dry_run=False)
    assert removed == (lock,)
    assert not lock.exists()


def test_purge_state_dirs_refuses_when_lock_pid_is_alive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A live supervisor's state dir must not be deleted.

    ``_pid_alive`` returns False for synthetic high PIDs (they
    don't exist), so we use the actual current process PID and
    bind to it via a state dir we own.
    """
    live_pid = os.getpid()
    sd = _make_state_dir(tmp_path, "live")
    _write_lock(sd, live_pid)
    _write_state_json(sd, heartbeat_unix=0.0, wedge_class="healthy")
    purged = purge_state_dirs([sd], dry_run=False)
    assert purged == ()
    assert sd.exists()


def test_purge_state_dirs_handles_missing_lock(tmp_path: Path) -> None:
    """A state dir without a supervisor.lock, when explicitly named,
    IS purged.

    The mutator trusts the caller; ``discover_stale_state_dirs``
    is the gatekeeper that decides which dirs are eligible.
    Passing a dir without a lock is an explicit operator
    decision and the mutator respects it.

    The lock-alive refusal is a defense-in-depth race check,
    NOT a general "skip dirs without locks" rule.
    """
    sd = _make_state_dir(tmp_path, "no_lock")
    (sd / "state.json").write_text("{}", encoding="utf-8")
    purged = purge_state_dirs([sd], dry_run=False)
    assert purged == (sd,)
    assert not sd.exists()


def test_terminate_stale_processes_dry_run_returns_wedged_only(tmp_path: Path) -> None:
    cfg = tmp_path / "cfg"
    healthy = StaleProcess(
        config_path=cfg,
        pid=1,
        heartbeat_unix=__import__("time").time(),
        last_wedge_class="healthy",
    )
    wedged = StaleProcess(
        config_path=cfg,
        pid=2,
        heartbeat_unix=__import__("time").time() - 9999,
        last_wedge_class="stuck_loop",
    )
    targets = terminate_stale_processes([healthy, wedged], dry_run=True)
    assert targets == (wedged,)


def test_stale_process_is_wedged_classification(tmp_path: Path) -> None:
    """``is_wedged`` is True iff (class != healthy) OR (heartbeat too old)."""
    cfg = tmp_path / "cfg"
    now = __import__("time").time()
    old_heartbeat = now - DEFAULT_STALE_HEARTBEAT_SECONDS - 1
    # healthy + recent = NOT wedged
    healthy_recent = StaleProcess(
        config_path=cfg, pid=1, heartbeat_unix=now, last_wedge_class="healthy"
    )
    assert healthy_recent.is_wedged is False
    # healthy + stale heartbeat = wedged
    healthy_stale = StaleProcess(
        config_path=cfg,
        pid=2,
        heartbeat_unix=old_heartbeat,
        last_wedge_class="healthy",
    )
    assert healthy_stale.is_wedged is True
    # wedged class + recent heartbeat = wedged (class wins)
    wedged_class = StaleProcess(
        config_path=cfg,
        pid=3,
        heartbeat_unix=now,
        last_wedge_class="stuck_loop",
    )
    assert wedged_class.is_wedged is True


# ---------------------------------------------------------------------------
# Discovery integration: synthesize a state tree and assert discovery
# returns the right buckets.
# ---------------------------------------------------------------------------


def test_discover_stale_locks_separates_alive_from_dead(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end discovery against a fake state tree.

    Two stale dirs (dead PIDs) and one live dir (current
    process PID) must classify correctly.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    pi_monitor = tmp_path / ".local" / "state" / "mathlint" / "pi-monitor"
    pi_monitor.mkdir(parents=True)

    # Two stale (dead high PIDs).
    s1 = _make_state_dir(tmp_path / ".local" / "state" / "pi-monitor", "kaplansky")
    s2 = _make_state_dir(tmp_path / ".local" / "state" / "pi-monitor", "math")
    _write_lock(s1, 99999)
    _write_lock(s2, 99998)

    # One alive (us).
    live_dir = pi_monitor
    _write_lock(live_dir, os.getpid())

    stale, alive = discover_stale_locks()
    stale_paths = {s.path for s in stale}
    assert (s1 / "supervisor.lock") in stale_paths
    assert (s2 / "supervisor.lock") in stale_paths
    assert any(a.path == live_dir / "supervisor.lock" for a in alive)


def test_discover_stale_state_dirs_excludes_dirs_without_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    # No lock at all -> NOT stale (could be forensics).
    _make_state_dir(tmp_path / ".local" / "state" / "pi-monitor", "no_lock")
    out = discover_stale_state_dirs()
    assert all(d.name != "no_lock" for d in out)


# ---------------------------------------------------------------------------
# Top-level reset() entry point.
# ---------------------------------------------------------------------------


def test_reset_dry_run_refuses_to_mutate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    s = _make_state_dir(tmp_path / ".local" / "state" / "pi-monitor", "kaplansky")
    lock = _write_lock(s, 99999)
    report = reset(dry_run=True)
    assert lock.exists(), "dry-run must not touch the filesystem"
    assert report.dry_run is True
    assert lock in report.locks_removed


def test_reset_apply_removes_stale_locks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    s = _make_state_dir(tmp_path / ".local" / "state" / "pi-monitor", "kaplansky")
    lock = _write_lock(s, 99999)
    report = reset(dry_run=False)
    assert report.dry_run is False
    assert not lock.exists()
    assert lock in report.locks_removed


def test_reset_ok_true_when_only_alive_locks_were_kept() -> None:
    """The only thing that fails ``report.ok`` is a refused purge.

    Alive-lock refusals are EXPECTED (we WANT to keep them).
    The verb should not exit non-zero just because there's a
    live supervisor in the way.
    """
    report = ResetReport(
        dry_run=True,
        locks_skipped_alive=(AliveLock(path=Path("/x"), alive_pid=123),),
    )
    assert report.ok is True


def test_reset_ok_false_when_purge_was_refused() -> None:
    report = ResetReport(
        dry_run=False,
        state_dirs_refused_alive=((Path("/x"), 123),),
    )
    assert report.ok is False


def test_reset_render_includes_kept_alive_lock(tmp_path: Path) -> None:
    """The render() output labels alive locks as KEEP (not REFUSED).

    Operator-facing distinction: KEEP is correct behavior; REFUSED
    is a real failure that needs operator action.
    """
    report = ResetReport(
        dry_run=True,
        locks_skipped_alive=(AliveLock(path=tmp_path / "lock", alive_pid=1),),
    )
    rendered = report.render()
    assert "KEEP alive lock" in rendered
    assert "REFUSED remove alive lock" not in rendered


# ---------------------------------------------------------------------------
# CLI surface tests.
# ---------------------------------------------------------------------------


def test_cli_reset_dry_run_prints_summary(
    cli_runner, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = cli_runner.invoke(["reset"])
    assert result.exit_code == 0
    assert "WOULD clean up institution state" in result.stdout


def test_cli_reset_requires_yes_for_purge(cli_runner, tmp_path: Path) -> None:
    result = cli_runner.invoke(
        ["reset", "--apply", "--purge-state", str(tmp_path / "x")]
    )
    assert result.exit_code == 2
    assert "requires --yes" in result.stdout or "requires --yes" in result.stderr


def test_cli_reset_requires_apply_for_purge(cli_runner, tmp_path: Path) -> None:
    result = cli_runner.invoke(
        ["reset", "--purge-state", str(tmp_path / "x"), "--yes"]
    )
    assert result.exit_code == 2
    assert "--apply" in (result.stdout + result.stderr)


def test_cli_reset_apply_runs_with_no_stale_locks(
    cli_runner, monkeypatch: pytest.MonkeyPatch
) -> None:
    # With a fresh HOME there are no stale locks; apply should
    # just print "no actions needed" and exit 0.
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("HOME", td)
        result = cli_runner.invoke(["reset", "--apply"])
    assert result.exit_code == 0
    assert "no actions needed" in result.stdout
