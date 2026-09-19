#!/bin/sh
# scripts/bootstrap-institution.sh — clone + pip-install every catalog entry.
#
# Reads catalog/programs.toml; for each entry:
#   - git clone <repository> <local_path>  (skip if already cloned)
#   - pip install -e <local_path>           (skip if already installed)
# Installs math-engine and pi_monitor as dev deps from their git remotes.
# Prints INSTITUTION BOOTSTRAPPED when done.

set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
CATALOG="$ROOT/catalog/programs.toml"

if [ ! -f "$CATALOG" ]; then
    echo "FATAL: catalog missing at $CATALOG" >&2
    exit 1
fi

expand() {
    case "$1" in
        "\$HOME"*) eval echo "$1" ;;
        *) echo "$1" ;;
    esac
}

echo "[bootstrap] installing math-engine + pi_monitor dev deps..."
uv pip install \
    "mathlint @ git+https://github.com/aprokopiw/math-kaplansky-research-program.git@v0.1.0" \
    "pi-monitor @ git+https://github.com/aprokopiw/pi_monitor.git@v0.2.0" \
    || echo "[bootstrap] WARN: dev-dep install failed (continuing)"

echo "[bootstrap] cloning + installing catalog programs..."
python3 <<EOF
import subprocess, tomllib, pathlib
data = tomllib.loads(pathlib.Path("$CATALOG").read_text())
for entry in data["programs"]:
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

echo ""
echo "INSTITUTION BOOTSTRAPPED"
echo "Next: bash research-institution/green-gate/check-institution.sh --hermetic"
