#!/usr/bin/env python3
"""Audit/package complete ARM64 binaries; INF source metadata is not a driver."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = {
    'AppleDockChannel': ('apple-dockchannel', 'APPL0008', 'MTP firmware, DART, IRQ and HID report adapter need qualification'),
    'AppleAgx': ('apple-agx', 'APPL0002', 'J413 runtime resource/firmware/broker contract differs from the J313 implementation'),
}
GAPS = {
    'internal_audio': 'No Windows audio driver implementation in this checkout',
    'wifi': 'No Windows Wi-Fi driver implementation in this checkout',
    'bluetooth': 'No Windows Bluetooth transport driver implementation in this checkout',
    'battery_and_power': 'No completed J413 Windows ACPI/PEP runtime implementation',
    'camera': 'No Windows ISP/camera driver implementation in this checkout',
    'external_display': 'No completed Windows DCP/external-display runtime driver',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def arm64_native_driver(path):
    data = path.read_bytes()
    if len(data) < 64 or data[:2] != b'MZ':
        return False
    offset = struct.unpack_from('<I', data, 60)[0]
    if offset < 64 or offset > len(data) - 94:
        return False
    pe = data[offset:offset+94]
    return (pe[:4] == b'PE\0\0' and struct.unpack_from('<H', pe, 4)[0] == 0xaa64 and
            struct.unpack_from('<H', pe, 24)[0] == 0x20b and struct.unpack_from('<H', pe, 92)[0] == 1)


def audit(packages_root):
    packages = {}
    for name, (source, hardware_id, limitation) in PACKAGES.items():
        files = [packages_root/name/(name+suffix) for suffix in ('.inf', '.sys', '.cat')]
        missing = [p.name for p in files if not p.is_file()]
        problems = []
        if not missing:
            inf = files[0].read_text(errors='replace').upper()
            if 'NTARM64' not in inf or 'ACPI\\'+hardware_id not in inf:
                problems.append('INF does not target the expected ARM64 hardware ID')
            if not arm64_native_driver(files[1]):
                problems.append('SYS is not an ARM64 PE32+ native driver')
            if files[2].stat().st_size == 0:
                problems.append('Catalog is empty')
        packages[name] = {
            'source': 'drivers/'+source+'/windows', 'hardware_id': 'ACPI\\'+hardware_id,
            'missing_files': missing, 'problems': problems,
            'complete_binary_package': not missing and not problems,
            'runtime_qualified': False, 'limitation': limitation,
            # Binary completeness is not a functioning platform/driver contract.
            # Revisit only with the source contract and a recorded experiment.
            'automatic_injection_eligible': False,
            'automatic_injection_blocker': limitation,
            'sha256': {p.name: sha(p) for p in files if p.is_file()},
        }
    return {
        'platform': 'j413', 'architecture': 'ARM64', 'runtime_qualified': False,
        'packages': packages, 'missing_native_implementations': GAPS,
        'inbox_owners': {'usb': 'USBXHCI/USBHUB3/USBSTOR/HIDUSB after valid platform handoff',
                         'storage': 'STORNVME/DISK over the emulated NVMe contract',
                         'basic_display': 'Firmware GOP/basic display; no acceleration proof'},
        'excluded': {'AppleInput': 'J313 SPI input is not the J413 DockChannel transport'},
        'all_requested_drivers_complete': False,
        'qualification': 'Binary/header audit only; catalog trust and hardware operation are not verified',
    }


def package(packages_root, output):
    report = audit(packages_root)
    selected = [n for n, item in report['packages'].items() if item['complete_binary_package']]
    if not selected:
        raise ValueError('No complete ARM64 INF/SYS/CAT package exists; INF-only files are not ready')
    if output.exists():
        raise ValueError('Output already exists; choose a new directory to preserve the previous package')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.j413-driver-package-') as directory:
        staging = Path(directory)/'payload'
        staging.mkdir()
        for name in selected:
            destination = staging/name
            destination.mkdir()
            for file in report['packages'][name]['sha256']:
                shutil.copyfile(packages_root/name/file, destination/file)
                if sha(destination/file) != report['packages'][name]['sha256'][file]:
                    raise ValueError('Package changed during copy: '+name+'/'+file)
        (staging/'MANIFEST.json').write_text(json.dumps(report, indent=2)+'\n')
        shutil.copyfile(ROOT/'scripts/install-j413-drivers.ps1', staging/'install-drivers.ps1')
        shutil.copyfile(ROOT/'scripts/inject-j413-drivers.ps1', staging/'inject-drivers.ps1')
        staging.rename(output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packages-root', type=Path, default=ROOT/'dist/j413-driver-build')
    parser.add_argument('--output', type=Path, default=ROOT/'dist/m2-windows-drivers')
    parser.add_argument('--audit', action='store_true', help='report gaps; do not stage drivers')
    args = parser.parse_args()
    try:
        report = audit(args.packages_root) if args.audit else package(args.packages_root, args.output)
        print(json.dumps(report, indent=2))
    except (OSError, ValueError) as error:
        print('Driver packaging stopped: '+str(error), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
