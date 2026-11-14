#!/bin/bash
# Compatibility entry point: install the current reviewed NVMe correction.
set -euo pipefail
PROJECT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec /bin/bash "$PROJECT/scripts/install-j413-nvme-fix.command" "$@"
