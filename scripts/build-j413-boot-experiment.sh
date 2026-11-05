#!/bin/sh
# Build an unqualified J413 UEFI experiment. Never installs or changes disks.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
case "${1:-}" in
    --dry-run)
        echo "Build J413 DEBUG Mu and two J413 m1n1 stages with proxy disabled; verify nested boot.bin and manifest."
        echo "Output: dist/j413/boot-experiment; requires a separately recorded hardware experiment."
        exit 0 ;;
    "") ;;
    *) echo "usage: $0 [--dry-run]" >&2; exit 2 ;;
esac
if [ "$(uname -s)" = Darwin ] && [ "${J413_IN_CONTAINER:-0}" != 1 ]; then
    docker build -t windows-on-m2-build:local -f "$ROOT/Dockerfile.build" "$ROOT"
    exec docker run --rm -e J413_IN_CONTAINER=1 -e J413_SKIP_MU="${J413_SKIP_MU:-0}" \
        -v "$ROOT:/work" -w /work windows-on-m2-build:local scripts/build-j413-boot-experiment.sh
fi
cd "$ROOT"
python3 tools/j413_direct_setup.py --check
python3 tools/j413_platform.py --stage-m1n1
if [ "${J413_SKIP_MU:-0}" != 1 ]; then scripts/build-j413-firmware.sh; fi
python3 tools/artifact_manifest.py verify dist/j413/firmware-debug/MANIFEST.json \
    --platform j413 --require-role J413_EFI.fd=guest-firmware
python3 - <<'PY'
from pathlib import Path
from tools.artifact_manifest import verify_manifest
from tools.j413_platform import require_current_firmware
require_current_firmware(verify_manifest(Path('dist/j413/firmware-debug/MANIFEST.json'), expected_platform='j413'))
PY
OUT="$ROOT/dist/j413/boot-experiment"
mkdir -p "$OUT"
STAGING=$(mktemp -d "$ROOT/dist/j413/.boot-experiment.XXXXXX")
BACKUP=
cleanup() {
    [ -z "$STAGING" ] || rm -rf "$STAGING"
    if [ -n "$BACKUP" ] && [ -d "$BACKUP" ] && [ ! -e "$OUT" ]; then mv "$BACKUP" "$OUT"; fi
}
trap cleanup EXIT HUP INT TERM
for role in 0 1; do
    make -C m1n1_windows clean
    make -C m1n1_windows -j"${JOBS:-4}" J413=1 EXTRA_CFLAGS="-DM1N1_STAGE$role -DM1N1_J413 -DM1N1_NO_PROXY"
    cp m1n1_windows/build/m1n1.bin "$STAGING/m1n1-stage$role.bin"
done
cp dist/j413/firmware-debug/J413_EFI.fd "$STAGING/J413_EFI.fd"
python3 tools/pack_boot.py --stage0-m1n1 "$STAGING/m1n1-stage0.bin" \
    --stage1-m1n1 "$STAGING/m1n1-stage1.bin" --firmware "$STAGING/J413_EFI.fd" \
    --layout config/j413-guest-layout.json --output "$STAGING/boot.bin" \
    --display physical --debug off --source-commit "$(git -C m1n1_windows rev-parse HEAD)" \
    --compiler "$(gcc --version | head -1)"
python3 - "$STAGING/TOOLCHAINS.json" <<'PY'
import json, subprocess, sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({
    "gcc": subprocess.check_output(["gcc", "--version"], text=True).splitlines()[0],
    "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(),
    "rust_target": "aarch64-unknown-none-softfloat",
}, indent=2) + "\n")
PY
python3 tools/artifact_manifest.py create --allow-dirty --platform j413 --root "$ROOT" \
    --directory "$STAGING" --profile debug --display physical --debug off \
    --compiler "$(gcc --version | head -1)" boot.bin m1n1-stage0.bin m1n1-stage1.bin J413_EFI.fd TOOLCHAINS.json
python3 tools/artifact_manifest.py verify "$STAGING/MANIFEST.json" --platform j413 \
    --require-role boot.bin=standalone-bootstrap --require-role J413_EFI.fd=guest-firmware
BACKUP=$(mktemp -d "$ROOT/dist/j413/.boot-experiment-previous.XXXXXX")
rmdir "$BACKUP"
if [ -e "$OUT" ]; then mv "$OUT" "$BACKUP"; fi
mv "$STAGING" "$OUT"
STAGING=
[ ! -d "$BACKUP" ] || rm -rf "$BACKUP"
BACKUP=
echo "J413 experimental image: $OUT/boot.bin (no hardware launch, install or Windows qualification)."
