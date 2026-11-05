#!/bin/sh
# Package complete J413 ARM64 binaries; --audit reports missing implementations.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec python3 "$ROOT/tools/package_j413_drivers.py" "$@"
