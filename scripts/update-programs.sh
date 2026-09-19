#!/bin/sh
# scripts/update-programs.sh — bump pins across the catalog and pyproject.
# Currently a no-op stub; future work wires this to `git tag --list` per program.
#
# Per @CTR-0088, every entry's `mathlint_pin` MUST match
# ^[A-Za-z0-9._/-]+$. This script prints a reminder of the current pins.

set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

python3 <<EOF
import tomllib, pathlib
data = tomllib.loads(pathlib.Path("$ROOT/catalog/programs.toml").read_text())
print(f"{'NAME':<20} {'PIN':<15} {'REPOSITORY'}")
for e in data["programs"]:
    print(f"{e['name']:<20} {e['mathlint_pin']:<15} {e['repository']}")
EOF

echo ""
echo "update-programs: no-op stub; bump pins manually for now"
