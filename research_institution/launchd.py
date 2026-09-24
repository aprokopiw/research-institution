"""LaunchAgent rendering + installation for program supervisors.

The canonical deployment path for unattended research-program
supervision. The Kaplansky program (and every future
program) gets its own dedicated LaunchAgent label so the
``one supervisor per target`` invariant (INV-005) is
preserved by construction: the label is the target identity
plus a per-program suffix, so two programs never share a
LaunchAgent.

Rendered plist rules:

* absolute paths everywhere (no $HOME expansion by
  launchd)
* KeepAlive/SuccessfulExit=false (intentional-exit
  semantics from @ADR-0011-unattended-launchd-service; a
  clean STOP leaves the service stopped)
* RunAtLoad=true so a login picks the service up at boot
* WorkingDirectory = institution repo root (so
  ``python -m research_institution status kaplansky``
  resolves the catalog)
* environment variables carry only config paths; secrets
  live in the operator's 0600 env file loaded through the
  supervisor's [source.env] block (never in the plist)

The renderer is pure over its inputs: given a template
string and a target dict, it returns the rendered plist
text. The installer writes the rendered file to
``~/Library/LaunchAgents/<label>.plist`` and (in live
mode) loads it via ``launchctl bootstrap gui/$UID``.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


#: Token pattern in the template. ``__KEY__`` is the canonical
#: shape used by every template in this repo. Lowercase or
#: mixed-case tokens are also accepted for portability.
_TOKEN_RE = re.compile(r"__([A-Z][A-Z0-9_]*)__")


@dataclass(frozen=True, slots=True)
class LaunchAgentTarget:
    """Resolved paths + identifiers for one LaunchAgent render.

    ``label`` is the LaunchAgent label (the unique target
    identity). ``pi_monitor_config_path`` is the canonical
    supervisor config; the env-var path is the same so the
    supervisor reads the rendered template. ``pi_monitor_bin``
    is the absolute path to the ``pi-monitor`` executable
    inside the operator's venv.
    """

    label: str
    pi_monitor_bin: Path
    pi_monitor_config_path: Path
    institution_dir: Path
    stdout_path: Path
    stderr_path: Path


@dataclass(frozen=True, slots=True)
class RenderedPlist:
    """The rendered plist contents + the on-disk target path.

    ``path`` is the absolute path the installer writes to
    (typically ``~/Library/LaunchAgents/<label>.plist``).
    ``contents`` is the rendered XML text. ``config_fingerprint``
    is the sha256 digest of the rendered config (the operator
    can read this from service status to prove which caps /
    action are active).
    """

    label: str
    path: Path
    contents: str
    config_fingerprint: str


def render_plist(template: str, target: LaunchAgentTarget) -> RenderedPlist:
    """Pure renderer: template + target -> rendered plist.

    Unknown ``__TOKENS__`` are left in place so a typo
    surfaces as a literal ``__TYPO__`` substring in the
    rendered output (the operator can grep for unresolved
    tokens rather than silently launching a broken plist).
    The config fingerprint is a stable digest of the
    rendered contents so the agent / operator can prove
    which caps / action are active without reading the
    plist.
    """
    rendered = template
    substitutions: dict[str, str] = {
        "LABEL": target.label,
        "PI_MONITOR_BIN": str(target.pi_monitor_bin),
        "PI_MONITOR_CONFIG_PATH": str(target.pi_monitor_config_path),
        "INSTITUTION_DIR": str(target.institution_dir),
        "STDOUT_PATH": str(target.stdout_path),
        "STDERR_PATH": str(target.stderr_path),
    }

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in substitutions:
            return substitutions[key]
        return match.group(0)

    rendered = _TOKEN_RE.sub(_sub, template)
    fingerprint = _config_fingerprint(target.pi_monitor_config_path)
    path = Path.home() / "Library" / "LaunchAgents" / f"{target.label}.plist"
    return RenderedPlist(
        label=target.label,
        path=path,
        contents=rendered,
        config_fingerprint=fingerprint,
    )


def _config_fingerprint(path: Path) -> str:
    """Stable sha256 digest of the rendered config file.

    Empty string when the file does not exist (the
    installer can still render the plist; the service is
    not yet installed). The fingerprint lets the agent /
    operator prove which caps / action are active without
    reading the plist contents.
    """
    import hashlib

    if not path.is_file():
        return ""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest[:16]


def install_plist(
    rendered: RenderedPlist, *, dry_run: bool, uid: int | None = None
) -> tuple[bool, str]:
    """Write the rendered plist + (optionally) load it via launchctl.

    Returns ``(ok, message)``. The function is the
    single seam between the canonical rendering and the
    live ``launchctl bootstrap`` call; tests exercise the
    render-only path and a live installer exercises the
    bootstrap path.

    Refuses to overwrite a different plist under the same
    label unless the caller confirms (the operator can
    ``research stop kaplansky`` first to clean up). The
    install is idempotent: writing the same contents under
    the same label is a no-op (no spurious launchctl
    bootstrap).
    """
    path = rendered.path
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.is_file():
        existing = path.read_text(encoding="utf-8")
        if existing == rendered.contents:
            return True, f"already installed (no change): {path}"
        return False, (
            f"existing plist differs from rendered template at {path}; "
            f"refusing to overwrite. Stop the service first, then re-run."
        )

    if dry_run:
        return True, f"dry-run: would write {path} ({len(rendered.contents)} bytes)"

    path.write_text(rendered.contents, encoding="utf-8")
    if shutil.which("launchctl") is None:
        return True, (
            f"wrote {path} (no launchctl on PATH; service not loaded). "
            f"On macOS the operator can `launchctl bootstrap gui/$UID {path}`."
        )
    target_uid = uid if uid is not None else os.getuid()
    rc = subprocess.call(
        ["launchctl", "bootstrap", f"gui/{target_uid}", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if rc != 0:
        return False, f"launchctl bootstrap failed: rc={rc}"
    return True, f"installed + loaded: {path}"


def uninstall_plist(label: str, *, dry_run: bool) -> tuple[bool, str]:
    """Bootout + remove the plist. Idempotent: missing plist is OK.

    Refuses to remove a different supervisor's plist under
    the same label (the label is the unique identity, so
    this case indicates operator confusion; we surface the
    mismatch rather than guessing).
    """
    path = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
    if not path.is_file():
        return True, f"no plist at {path}; nothing to uninstall"
    if dry_run:
        return True, f"dry-run: would bootout + remove {path}"
    if shutil.which("launchctl") is not None:
        rc = subprocess.call(
            ["launchctl", "bootout", f"gui/{os.getuid()}", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # bootout returns 36 (not loaded) when the service is
        # not currently running; we tolerate that.
        if rc not in (0, 36):
            return False, f"launchctl bootout failed: rc={rc}"
    path.unlink()
    return True, f"uninstalled: {path}"


__all__ = [
    "LaunchAgentTarget",
    "RenderedPlist",
    "install_plist",
    "render_plist",
    "uninstall_plist",
]
