#!/bin/sh
# Turnkey build script for Windows ARM64 on the MacBook Air M2 (Mac14,2 / T8112 / J413).
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

echo "================================================================="
echo "   Windows ARM64 on MacBook Air M2 (J413) - Automated Builder    "
echo "================================================================="

# Check architecture
ARCH=$(uname -m)
OS=$(uname -s)
if [ "$OS" = Darwin ]; then
    MODEL=$(sysctl -n hw.model 2>/dev/null || echo "Unknown")
    echo "Host: $MODEL ($ARCH, $OS)"
else
    echo "Host: Linux ($ARCH)"
fi

# Step 1: Stage J413 platform files into Mu and m1n1
echo "\n[*] Step 1/4: Staging J413 platform files and overlays..."
python3 "$ROOT/tools/j413_platform.py" --stage
python3 "$ROOT/tools/j413_platform.py" --stage-m1n1
python3 "$ROOT/tools/prepare_j413_exfat.py"

# Step 2: Check prerequisites
echo "\n[*] Step 2/4: Checking toolchains and dependencies..."
python3 -c "
import sys
if not ((3, 10) <= sys.version_info[:2] < (3, 13)):
    print(f'Warning: Python {sys.version.split()[0]} detected. Mu build scripts recommend Python 3.10-3.12.')
else:
    print(f'Python version {sys.version.split()[0]} OK.')
"

# Step 3: Run the J413 boot experiment build
echo "\n[*] Step 3/4: Compiling J413 firmware, m1n1 stages, and packaging boot.bin..."
if [ "${1:-}" = "--dry-run" ]; then
    "$ROOT/scripts/build-j413-boot-experiment.sh" --dry-run
    exit 0
fi

# If inside Darwin without container flag, build-j413-boot-experiment will use container or native
"$ROOT/scripts/build-j413-boot-experiment.sh"

# Step 4: Verification and Summary
echo "\n[*] Step 4/4: Validating output artifacts..."
python3 "$ROOT/tools/artifact_manifest.py" verify "$ROOT/dist/j413/boot-experiment/MANIFEST.json" \
    --platform j413 --require-role boot.bin=standalone-bootstrap --require-role J413_EFI.fd=guest-firmware

echo "\n================================================================="
echo "   BUILD SUCCESSFUL!                                             "
echo "   Target: MacBook Air M2 (Mac14,2 / T8112 / J413)               "
echo "   Output: dist/j413/boot-experiment/boot.bin                    "
echo "================================================================="
echo "To install to your EFI System Partition (ESP):"
echo "  sudo ./scripts/install-esp.sh --disk /dev/diskXsY dist/j413/boot-experiment/boot.bin"
echo ""
echo "To package Windows drivers (GPU, Input, Touchpad, Audio):"
echo "  ./scripts/package-m2-drivers.sh"
echo "================================================================="
