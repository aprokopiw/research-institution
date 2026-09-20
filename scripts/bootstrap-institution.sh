#!/bin/sh
# scripts/bootstrap-institution.sh — clone + pip-install every catalog entry.
#
# Reads catalog/programs.toml; for each entry:
#   - git clone <repository> <local_path>  (skip if already cloned)
#   - pip install -e <local_path>           (skip if already installed)
# Installs math-engine and pi_monitor as dev deps from their git remotes.
# Prints INSTITUTION BOOTSTRAPPED when done.
#
# Idempotent: safe to re-run after partial success.
# Tolerates: missing uv (skips dev-dep install with WARN), missing
#            catalog (FATAL), empty catalog (succeeds with no programs).

set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
CATALOG="$ROOT/catalog/programs.toml"

if [ ! -f "$CATALOG" ]; then
    echo "FATAL: catalog missing at $CATALOG" >&2
    exit 1
fi

# Dev-deps install: tolerate missing `uv` and missing venv gracefully.
# Operators without uv already have mathlint + pi_monitor available
# via their existing venv; this step is a convenience, not a hard dep.
if command -v uv >/dev/null 2>&1; then
    echo "[bootstrap] installing math-engine + pi_monitor dev deps via uv..."
    if uv pip install \
        "mathlint @ git+https://github.com/aprokopiw/math-kaplansky-research-program.git@v0.1.0" \
        "pi-monitor @ git+https://github.com/aprokopiw/pi_monitor.git@v0.2.0" \
        2>/dev/null; then
        echo "[bootstrap] dev deps installed"
    else
        echo "[bootstrap] WARN: dev-dep install failed (continuing; mathlint/pi-monitor must already be installed)"
    fi
else
    echo "[bootstrap] WARN: uv not on PATH; skipping dev-dep install (mathlint/pi-monitor must already be installed)"
fi

echo "[bootstrap] cloning + installing catalog programs..."
python3 <<EOF
import subprocess, sys, tomllib, pathlib

catalog = pathlib.Path("$CATALOG")
data = tomllib.loads(catalog.read_text())
programs = data.get("programs") or []

if not programs:
    print("[bootstrap] catalog is empty; nothing to clone")
    sys.exit(0)

for entry in programs:
    name = entry["name"]
    repo = entry["repository"]
    raw_path = entry["local_path"]
    local_path = raw_path.replace("\$HOME", str(pathlib.Path.home()))
    print(f"[{name}] local_path={local_path}")
    if not pathlib.Path(local_path).exists():
        print(f"[{name}] cloning {repo} -> {local_path}")
        subprocess.run(["git", "clone", repo, local_path], check=False)
    else:
        print(f"[{name}] already cloned at {local_path}")
EOF

# Transient-state purge for each catalog program's local checkout.
# Scope is intentionally narrow: only the directories that the
# GLLA loop writes to during a run (`.pi-glla/`) and the build
# cache directories. The 187-attempt dispatch loop (postmortem
# anchor @INV-0093) identified stale run state as a contributor;
# clearing these paths on bootstrap gives the next run a clean
# slate without touching the operator's untracked work.
#
# Why not `git clean -fdX` on the whole repo: that would also
# remove any in-progress editor scratch files the operator may
# have. Scoping to `.pi-glla/` + `build/` + `dist/` + `.pytest_cache/`
# is the smallest set that's both safe and effective.
echo ""
echo "[bootstrap] purging transient state from each program's local checkout..."
python3 <<EOF
import shutil, pathlib, sys, tomllib

catalog = pathlib.Path("$CATALOG")
data = tomllib.loads(catalog.read_text())
TRANSIENT_DIRS = (".pi-glla", "build", "dist", ".pytest_cache")

for entry in data.get("programs") or []:
    local_path = pathlib.Path(entry["local_path"].replace("\$HOME", str(pathlib.Path.home())))
    if not local_path.exists():
        continue
    for sub in TRANSIENT_DIRS:
        target = local_path / sub
        if target.is_dir():
            print(f"[{entry['name']}] purging {target}")
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            print(f"[{entry['name']}] removing {target}")
            target.unlink()
EOF

echo ""
echo "INSTITUTION BOOTSTRAPPED"
echo "Next: bash green-gate/check-institution.sh --hermetic"
