#!/bin/bash
set -euo pipefail
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$TASK_ROOT"
phase=${1:?supply-log-phase}
: "${M1N1DEVICE:?set the current console serial device}"
: "${M1N1VUART:?set the current virtual UART serial device}"
if [ "${AIR_SERIAL_LOCK_ACTIVE:-}" != 1 ]; then exec python3 "$TASK_ROOT/scripts/air-serial-guard.py" --port "$M1N1DEVICE" --port "$M1N1VUART" -- "$0" "$@"; fi
export LLDDIR=/tmp/agx-lld-dir/ M1N1DEVICE="$M1N1DEVICE" PYTHONUNBUFFERED=1
: "${AGX_DURABLE_PREFLIGHT_JSON:?run guest durable preflight after ordered reboot}"
python3 "$TASK_ROOT/scripts/g3-launchers/soc-reset.py" --preflight-command-json "$AGX_DURABLE_PREFLIGHT_JSON" --port "$M1N1DEVICE" --port "$M1N1VUART" -- proxyenv/bin/python m1n1_windows/proxyclient/tools/reboot.py 2>&1 | tee ".local/experiments/EXP784-g3-parent-size/${phase}-soc-reset.log"
proxyenv/bin/python m1n1_windows/proxyclient/tools/chainload.py .local/experiments/EXP784-g3-parent-size/recovery/m1n1-exp377.macho 2>&1 | tee ".local/experiments/EXP784-g3-parent-size/${phase}-chainload.log"
env -u WOM1_AGX_G2_POWER_BROKER WOM1_ALLOW_LEGACY_LAUNCH_CONTRACT=1 proxyenv/bin/python -u run_uefi.py .local/experiments/EXP784-g3-parent-size/recovery/J313_EFI-exp392.fd --device "$M1N1DEVICE" --display-mode physical --debug-mode off --low-mem --contract-output ".local/experiments/EXP784-g3-parent-size/${phase}-contract.bin" 2>&1 | tee ".local/experiments/EXP784-g3-parent-size/${phase}-full.log"
