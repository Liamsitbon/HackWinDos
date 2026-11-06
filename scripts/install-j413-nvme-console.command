#!/bin/bash
# Install only the EXP064 console-diagnostic firmware; preserve Windows media.
set -euo pipefail
PROJECT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec sudo /usr/bin/python3 "$PROJECT/scripts/install-j413-direct-setup.py" \
    --firmware-only --native-mount \
    --image-sha256 d2c2f46520e2b33059b738370a344eedd5130536de499829af249230fe571123
