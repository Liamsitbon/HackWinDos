#!/bin/sh
# Experimental UEFI component build. Does not create/install a boot.bin.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
case "${1:-}" in
    --check) exec python3 "$ROOT/tools/j413_platform.py" ;;
    --dry-run)
        echo "Stage pinned J413 overlay; create .build/j413-venv; stuart_setup/update/build (CLANGPDB, DEBUG, AIC_BUILD=FALSE)."
        echo "Output: dist/j413/firmware-debug/J413_EFI.fd; no installable standalone boot image."
        exit 0 ;;
    "") ;;
    *) echo "usage: $0 [--check|--dry-run]" >&2; exit 2 ;;
esac
if [ "$(uname -s)" = Darwin ] && [ "${J413_IN_CONTAINER:-0}" != 1 ]; then
    docker build -t windows-on-m2-build:local -f "$ROOT/Dockerfile.build" "$ROOT"
    exec docker run --rm -e J413_IN_CONTAINER=1 -v "$ROOT:/work" -w /work \
        windows-on-m2-build:local scripts/build-j413-firmware.sh
fi
python3 "$ROOT/tools/j413_direct_setup.py" --check
python3 "$ROOT/tools/j413_platform.py" --stage
python3 "$ROOT/tools/prepare_j413_exfat.py"
VENV="$ROOT/.build/j413-venv"
[ "${J413_IN_CONTAINER:-0}" != 1 ] || VENV="$ROOT/.build/j413-venv-linux"
MU_PYTHON_SELECTED=
for candidate in "${MU_PYTHON:-python3.12}" python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
        "$candidate" -c 'import sys; raise SystemExit(not ((3,10) <= sys.version_info[:2] < (3,13)))' >/dev/null 2>&1; then
        MU_PYTHON_SELECTED=$candidate
        break
    fi
done
[ -n "$MU_PYTHON_SELECTED" ] || { echo "Mu requires Python 3.10 through 3.12" >&2; exit 2; }
# A venv is bound to its creating interpreter. Replace only this script's own
# incompatible venv, keeping all other development environments untouched.
if [ -f "$VENV/pyvenv.cfg" ] && ! "$VENV/bin/python" -c 'import sys; raise SystemExit(not ((3,10) <= sys.version_info[:2] < (3,13)))'; then
    rm -rf "$VENV"
fi
"$MU_PYTHON_SELECTED" -m venv "$VENV"
"$VENV/bin/pip" install -q -r "$ROOT/mu/pip-requirements.txt"
"$VENV/bin/pip" install -q 'setuptools<81' wheel
PLATFORM=Platform/MacBookAirM2Pkg/PlatformBuild.py
(
    cd "$ROOT/mu"
    "$VENV/bin/stuart_setup" -c "$PLATFORM" TOOL_CHAIN_TAG=CLANGPDB
    # Use native tools from Dockerfile.build instead of the x86-only NuGet
    # dependencies. Restore the exact YAML files even on a failed build.
    BACKUP=$(mktemp -d "$ROOT/.build/j413-extdeps.XXXXXX")
    restore_deps() {
        for relative in MU_BASECORE/BaseTools/Bin/nasm_ext_dep.yaml \
            MU_BASECORE/BaseTools/Bin/iasl_ext_dep.yaml \
            MU_BASECORE/.pytool/Plugin/UncrustifyCheck/uncrustify_ext_dep.yaml; do
            if [ -f "$BACKUP/$relative" ]; then cp "$BACKUP/$relative" "$relative"; fi
        done
        rm -rf "$BACKUP"
    }
    trap restore_deps EXIT HUP INT TERM
    for relative in MU_BASECORE/BaseTools/Bin/nasm_ext_dep.yaml \
        MU_BASECORE/BaseTools/Bin/iasl_ext_dep.yaml \
        MU_BASECORE/.pytool/Plugin/UncrustifyCheck/uncrustify_ext_dep.yaml; do
        if [ -f "$relative" ]; then
            mkdir -p "$BACKUP/$(dirname "$relative")"
            cp "$relative" "$BACKUP/$relative"
            rm "$relative"
        fi
    done
    "$VENV/bin/stuart_update" -c "$PLATFORM" TOOL_CHAIN_TAG=CLANGPDB
    "$VENV/bin/stuart_build" -c "$PLATFORM" TOOL_CHAIN_TAG=CLANGPDB TARGET=DEBUG 'BLD_*_AIC_BUILD=FALSE'
)
python3 "$ROOT/tools/check_j413_prepi.py" \
    "$ROOT/mu/Build/MacBookAirM2-AARCH64/DEBUG_CLANGPDB/AARCH64/AppleSiliconPkg/PrePi/PrePi"
OUTPUT="$ROOT/dist/j413/firmware-debug"
mkdir -p "$OUTPUT"
cp "$ROOT/mu/Build/MacBookAirM2-AARCH64/DEBUG_CLANGPDB/FV/J413MACBOOKAIRM2_EFI.fd" "$OUTPUT/J413_EFI.fd"
COMPILER=$(clang --version | head -1)
python3 "$ROOT/tools/artifact_manifest.py" create --allow-dirty --platform j413 \
    --root "$ROOT" --directory "$OUTPUT" --profile debug --display physical \
    --debug uart --compiler "$COMPILER" J413_EFI.fd
python3 "$ROOT/tools/artifact_manifest.py" verify "$OUTPUT/MANIFEST.json" --platform j413 \
    --require-role J413_EFI.fd=guest-firmware
