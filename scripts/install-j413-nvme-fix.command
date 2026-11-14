#!/bin/bash
# Compatibility entry point for the candidate containing the NVMe correction.
set -euo pipefail
PROJECT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec /bin/bash "$PROJECT/scripts/install-j413-usb-first.command" "$@"
