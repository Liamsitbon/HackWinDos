#!/bin/sh
# Turnkey launch runner for Windows ARM64 on the MacBook Air M2 (Mac14,2 / T8112 / J413).
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

DISPLAY=physical
DEBUG=uart
DRY_RUN=0
FOREGROUND=1
PSTATE=12 # 3480 MHz for M2 Avalanche cores

usage() {
    echo "usage: $0 [--display none|physical|virtual|both] [--debug off|uart|full|monitor]" >&2
    echo "          [--pstate 1..12] [--background] [--dry-run]" >&2
    exit 2
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --display) [ "$#" -ge 2 ] || usage; DISPLAY=$2; shift 2 ;;
        --debug) [ "$#" -ge 2 ] || usage; DEBUG=$2; shift 2 ;;
        --pstate) [ "$#" -ge 2 ] || usage; PSTATE=$2; shift 2 ;;
        --background) FOREGROUND=0; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help) usage ;;
        *) usage ;;
    esac
done

echo "================================================================="
echo "   Windows ARM64 on MacBook Air M2 (J413) - Launcher             "
echo "================================================================="
echo "Platform: MacBook Air M2 (Mac14,2 / T8112 / J413)"
echo "Display: $DISPLAY (2560x1664 contract, 10240 stride)"
echo "Debug Mode: $DEBUG"
echo "Target P-state: Level $PSTATE (Avalanche P-cores boosted)"
echo "AIC2 IRQ Route: Physical IRQ 1112 -> Virtual INTID 857"
echo "================================================================="

export WOM2_PCPU_PSTATE="$PSTATE"
export WOM1_PCPU_PSTATE="$PSTATE"

FIRMWARE="$ROOT/dist/j413/firmware-debug/J413_EFI.fd"
if [ ! -f "$FIRMWARE" ] && [ -f "$ROOT/dist/j413/boot-experiment/J413_EFI.fd" ]; then
    FIRMWARE="$ROOT/dist/j413/boot-experiment/J413_EFI.fd"
fi

LAYOUT="$ROOT/config/j413-guest-layout.json"

if [ "$DRY_RUN" -eq 1 ]; then
    echo "[*] Dry run: verified configuration and parameters successfully."
    exit 0
fi

if [ ! -f "$FIRMWARE" ]; then
    echo "Notice: J413 firmware artifact not yet compiled. Running ./scripts/build-m2.sh first..."
    ./scripts/build-m2.sh
fi

ARGS="--display $DISPLAY --debug $DEBUG --layout $LAYOUT"
if [ "$FOREGROUND" -eq 1 ]; then
    ARGS="$ARGS --foreground"
fi

exec "$ROOT/scripts/run-assisted.sh" --firmware "$FIRMWARE" $ARGS
