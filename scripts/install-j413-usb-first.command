#!/bin/bash
# Install the recorded EXP068 USB-first firmware candidate transactionally.
set -euo pipefail
PROJECT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
INSTALLER=(/usr/bin/python3 "$PROJECT/scripts/install-j413-direct-setup.py"
    --firmware-only --native-mount
    --image-sha256 3ed26369b22873d94fa663a83d1d643cc318ad4ac178fe052c22cb9592fbb12d)
case "${1:-}" in
    '') exec sudo "${INSTALLER[@]}" ;;
    --dry-run) exec "${INSTALLER[@]}" --dry-run ;;
    *) printf 'Usage: %s [--dry-run]\n' "$0" >&2; exit 2 ;;
esac
