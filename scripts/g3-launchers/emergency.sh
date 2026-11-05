#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$TASK_ROOT"
: "${M1N1DEVICE:?set the current console serial device}"
: "${M1N1VUART:?set the current virtual UART serial device}"
if [ "${AIR_SERIAL_LOCK_ACTIVE:-}" != 1 ]; then exec python3 "$TASK_ROOT/scripts/air-serial-guard.py" --port "$M1N1DEVICE" --port "$M1N1VUART" -- "$0" "$@"; fi
export LLDDIR=/tmp/agx-lld-dir/ M1N1DEVICE="$M1N1DEVICE" PYTHONUNBUFFERED=1
unset WOM1_AGX_G2_POWER_BROKER
python3 "$TASK_ROOT/scripts/g3-launchers/soc-reset.py" --emergency-recovery --port "$M1N1DEVICE" --port "$M1N1VUART" -- ./proxyenv/bin/python m1n1_windows/proxyclient/tools/reboot.py
./proxyenv/bin/python m1n1_windows/proxyclient/tools/chainload.py .local/experiments/EXP-20260903-377-secondary-cpu-receipt/assisted-boot/m1n1.macho
exec ./proxyenv/bin/python -u run_uefi.py .local/experiments/EXP-20260903-385-hvc-single-page/recovery/J313_EFI-no-agx-autoboot.fd --device "$M1N1DEVICE" --display-mode physical --debug-mode off --low-mem --contract-output .local/experiments/EXP784-g3-parent-size/emergency-contract.bin
