"""LaunchAgent rendering + installation tests.

The brief (Section E) requires:
* Distinct LaunchAgent label per program (one supervisor
  per target, INV-005).
* Absolute paths everywhere.
* KeepAlive/SuccessfulExit=false (intentional-exit
  semantics from @ADR-0011-unattended-launchd-service).
* No credentials in the plist (only env-var paths).
* Idempotent install: re-rendering the same template +
  target is a no-op.

Tests use the canonical template from
``launchd-templates/kaplansky-pi-monitor.plist.xml``
(read-only) so a future template edit propagates here.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from research_institution.launchd import (
    LaunchAgentTarget,
    RenderedPlist,
    install_plist,
    render_plist,
    uninstall_plist,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _template_path() -> Path:
    return REPO_ROOT / "launchd-templates" / "kaplansky-pi-monitor.plist.xml"


def _sample_target(
    *,
    label: str = "com.local.research-institution.kaplansky",
    tmp_path: Path,
) -> LaunchAgentTarget:
    pi_monitor_bin = tmp_path / "venv" / "bin" / "pi-monitor"
    pi_monitor_bin.parent.mkdir(parents=True, exist_ok=True)
    pi_monitor_bin.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    cfg = tmp_path / "config.toml"
    cfg.write_text("[project]\nname='kaplansky'\n", encoding="utf-8")
    institution = tmp_path / "research-institution"
    institution.mkdir(exist_ok=True)
    logs = tmp_path / "logs"
    logs.mkdir(exist_ok=True)
    return LaunchAgentTarget(
        label=label,
        pi_monitor_bin=pi_monitor_bin,
        pi_monitor_config_path=cfg,
        institution_dir=institution,
        stdout_path=logs / "out.log",
        stderr_path=logs / "err.log",
    )


class TestPlistTemplate:
    """The canonical template satisfies the deployment rules."""

    def test_template_file_exists(self) -> None:
        assert _template_path().is_file()

    def test_template_has_no_credentials(self) -> None:
        text = _template_path().read_text(encoding="utf-8")
        # No API key / OAuth / secret literal leaks. The
        # template only references config paths.
        for forbidden in ("API_KEY", "OPENAI_API_KEY", "MINIMAX_KEY", "sk-"):
            assert forbidden not in text, (
                f"template must not contain credentials; found {forbidden!r}"
            )

    def test_template_keeps_intentional_exit_semantics(self) -> None:
        text = _template_path().read_text(encoding="utf-8")
        # ``SuccessfulExit`` = ``false`` keeps a clean STOP
        # stopped (the operator restarts via ``research
        # start``).
        assert re.search(
            r"<key>SuccessfulExit</key>\s*<false/>",
            text,
            re.MULTILINE,
        ), "template must declare KeepAlive/SuccessfulExit=false"

    def test_template_keeps_run_at_load(self) -> None:
        text = _template_path().read_text(encoding="utf-8")
        assert re.search(
            r"<key>RunAtLoad</key>\s*<true/>",
            text,
            re.MULTILINE,
        ), "template must declare RunAtLoad=true"


class TestPlistRender:
    """Pure renderer substitutes every documented token."""

    def test_renders_every_target_field(self, tmp_path: Path) -> None:
        target = _sample_target(tmp_path=tmp_path)
        rendered = render_plist(_template_path().read_text(encoding="utf-8"), target)
        assert isinstance(rendered, RenderedPlist)
        assert rendered.label == target.label
        assert str(target.pi_monitor_bin) in rendered.contents
        assert str(target.pi_monitor_config_path) in rendered.contents
        assert str(target.institution_dir) in rendered.contents
        assert str(target.stdout_path) in rendered.contents
        assert str(target.stderr_path) in rendered.contents
        # Path on disk = ~/Library/LaunchAgents/<label>.plist
        assert rendered.path == (
            Path.home() / "Library" / "LaunchAgents" / f"{target.label}.plist"
        )

    def test_leaves_unknown_tokens_alone(self, tmp_path: Path) -> None:
        template = "<plist><dict><key>X</key><string>__TYPO__</string></dict></plist>"
        target = _sample_target(tmp_path=tmp_path)
        rendered = render_plist(template, target)
        assert "__TYPO__" in rendered.contents, (
            "an unknown token must surface as a literal so the operator "
            "can grep for unresolved tokens"
        )

    def test_config_fingerprint_matches_rendered_config(
        self, tmp_path: Path
    ) -> None:
        target = _sample_target(tmp_path=tmp_path)
        rendered = render_plist(_template_path().read_text(encoding="utf-8"), target)
        # The config file content drives the fingerprint.
        import hashlib

        expected = hashlib.sha256(
            target.pi_monitor_config_path.read_bytes()
        ).hexdigest()[:16]
        assert rendered.config_fingerprint == expected

    def test_config_fingerprint_empty_when_config_missing(
        self, tmp_path: Path
    ) -> None:
        target = LaunchAgentTarget(
            label="com.local.test",
            pi_monitor_bin=tmp_path / "bin" / "pi-monitor",
            pi_monitor_config_path=tmp_path / "no-such.toml",
            institution_dir=tmp_path / "inst",
            stdout_path=tmp_path / "out.log",
            stderr_path=tmp_path / "err.log",
        )
        rendered = render_plist(_template_path().read_text(encoding="utf-8"), target)
        assert rendered.config_fingerprint == ""


class TestPlistInstall:
    """The installer is idempotent and refuses unsafe overwrites."""

    def test_dry_run_does_not_write(self, tmp_path: Path) -> None:
        # Force HOME to a tmp_path so the installer cannot pollute
        # the operator's LaunchAgents.
        import os

        monkeypatch_home = tmp_path / "home"
        monkeypatch_home.mkdir()
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(monkeypatch_home)
        try:
            target = _sample_target(tmp_path=tmp_path)
            rendered = render_plist(
                _template_path().read_text(encoding="utf-8"), target
            )
            ok, msg = install_plist(rendered, dry_run=True)
            assert ok
            assert "dry-run" in msg
            assert not rendered.path.exists()
        finally:
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home

    def test_install_writes_idempotently(self, tmp_path: Path) -> None:
        import os

        monkeypatch_home = tmp_path / "home"
        monkeypatch_home.mkdir()
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(monkeypatch_home)
        try:
            target = _sample_target(tmp_path=tmp_path)
            rendered = render_plist(
                _template_path().read_text(encoding="utf-8"), target
            )
            ok1, msg1 = install_plist(rendered, dry_run=True)
            assert ok1
            # Force-write the file (dry-run path doesn't actually
            # write, so emulate the first install).
            rendered.path.write_text(rendered.contents, encoding="utf-8")
            # Second call sees identical contents -> no-op.
            ok2, msg2 = install_plist(rendered, dry_run=True)
            assert ok2
            assert "already installed" in msg2
        finally:
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home

    def test_install_refuses_to_overwrite_different_plist(
        self, tmp_path: Path
    ) -> None:
        import os

        monkeypatch_home = tmp_path / "home"
        monkeypatch_home.mkdir()
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(monkeypatch_home)
        try:
            target = _sample_target(tmp_path=tmp_path)
            rendered = render_plist(
                _template_path().read_text(encoding="utf-8"), target
            )
            rendered.path.parent.mkdir(parents=True, exist_ok=True)
            rendered.path.write_text(
                "<plist><dict><key>Label</key><string>different</string></dict></plist>",
                encoding="utf-8",
            )
            ok, msg = install_plist(rendered, dry_run=True)
            assert not ok
            assert "differs" in msg
        finally:
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home


class TestPlistUninstall:
    """Uninstall is idempotent and refuses missing plist cleanly."""

    def test_uninstall_missing_is_noop(self, tmp_path: Path) -> None:
        import os

        monkeypatch_home = tmp_path / "home"
        monkeypatch_home.mkdir()
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(monkeypatch_home)
        try:
            ok, msg = uninstall_plist("com.local.test.missing", dry_run=True)
            assert ok
            assert "nothing to uninstall" in msg
        finally:
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home

    def test_uninstall_dry_run_does_not_delete(self, tmp_path: Path) -> None:
        import os

        monkeypatch_home = tmp_path / "home"
        monkeypatch_home.mkdir()
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(monkeypatch_home)
        try:
            target = _sample_target(tmp_path=tmp_path)
            rendered = render_plist(
                _template_path().read_text(encoding="utf-8"), target
            )
            rendered.path.parent.mkdir(parents=True, exist_ok=True)
            rendered.path.write_text(rendered.contents, encoding="utf-8")
            ok, msg = uninstall_plist(target.label, dry_run=True)
            assert ok
            assert "dry-run" in msg
            assert rendered.path.exists()
        finally:
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
