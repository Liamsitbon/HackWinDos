#!/bin/bash
# Install only the EXP064 console-diagnostic firmware; preserve Windows media.
set -euo pipefail
PROJECT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec sudo /usr/bin/python3 "$PROJECT/scripts/install-j413-direct-setup.py" \
    --firmware-only --native-mount \
    --image-sha256 ce99784c8fa96560f896c48bdf26237e735f7f38d3b2fc12e7e9b4048e3def26
