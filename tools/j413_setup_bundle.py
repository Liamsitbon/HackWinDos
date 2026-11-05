#!/usr/bin/env python3
"""Stage a complete same-volume FAT32 Windows ARM64 Setup bundle, without formatting."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.check_j413_setup import inspect
from tools.verify_install_image import verify
from tools.package_j413_drivers import audit as driver_audit


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b''):
            result.update(block)
    return result.hexdigest()


def source_files(source):
    files = []
    for directory in ('efi', 'boot', 'sources', 'support'):
        parent = source/directory
        if parent.is_symlink():
            raise ValueError('Source directory symlinks are not accepted: '+directory)
        if not parent.is_dir():
            continue
        for path in sorted(parent.rglob('*')):
            relative = path.relative_to(source)
            if path.is_symlink():
                raise ValueError('Source symlinks are not accepted: '+str(relative))
            if not path.is_file() or any(part.startswith('.') for part in relative.parts):
                continue
            if re.fullmatch(r'sources/install(?:\d*\.swm|\.wim)', str(relative), re.I):
                continue
            if path.name.lower() in ('autounattend.xml', 'unattend.xml'):
                continue
            files.append(relative)
    for name in ('setup.exe', 'bootmgr.efi', 'bootmgfw.efi'):
        if (source/name).is_file():
            files.append(Path(name))
    return files


def copy_checked(source, destination):
    if destination.exists():
        if sha(destination) != sha(source):
            raise ValueError('Existing file differs; refusing to replace: '+str(destination))
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with source.open('rb') as input_stream:
            with destination.open('xb') as output:
                created = True
                shutil.copyfileobj(input_stream, output, 4*1024*1024)
                output.flush()
                os.fsync(output.fileno())
        if sha(destination) != sha(source):
            raise ValueError('Copy verification failed: '+str(destination))
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise


def wim(command):
    return subprocess.check_output(['wimlib-imagex', *map(str, command)], stderr=subprocess.STDOUT)


def arm64_images(path, runner=wim):
    xml = ET.fromstring(runner(['info', path, '--xml']))
    images = xml.findall('IMAGE')
    if not images or any(item.findtext('WINDOWS/ARCH') != '12' for item in images):
        raise ValueError('Every WIM image must be ARM64: '+str(path))
    return [{'index': item.get('INDEX'), 'name': item.findtext('NAME'), 'architecture': 'ARM64'} for item in images]


def stage(source, target, firmware, manifest, identity, runner=wim, include_bootstrap=True):
    identity = str(uuid.UUID(identity)).upper()
    contract = manifest.get('direct_setup', {})
    if identity != contract.get('partition_uuid') or contract.get('mode') != 'single-gpt-volume':
        raise ValueError('Firmware is bound to another Setup partition; configure and rebuild for this exact UUID')
    if (source.resolve().is_relative_to(target.resolve()) or
            target.resolve().is_relative_to(source.resolve())):
        raise ValueError('Source and destination must differ')
    if inspect(source)['errors'] or not (source/'sources/install.wim').is_file() or not (source/'setup.exe').is_file():
        raise ValueError('Source must be complete ARM64 Setup media with install.wim')
    if list((target/'sources').glob('install*.swm')):
        raise ValueError('Split WIM output already exists; preserve it and use a fresh destination')
    images = {'boot.wim': arm64_images(source/'sources/boot.wim', runner),
              'install.wim': arm64_images(source/'sources/install.wim', runner)}
    files = [(source/relative, target/relative) for relative in source_files(source)]
    if include_bootstrap:
        files += [(firmware/'boot.bin', target/'m1n1/boot.bin'),
                  (firmware/'J413_EFI.fd', target/'m1n1/J413_EFI.fd')]
    needed = (source/'sources/install.wim').stat().st_size + 64*1024*1024
    for src, dst in files:
        if not src.is_file():
            raise ValueError('Missing source: '+str(src))
        if src.stat().st_size > 0xffffffff:
            raise ValueError('Unsplit file exceeds the FAT32 limit: '+str(src))
        if dst.exists():
            if sha(src) != sha(dst):
                raise ValueError('Existing target differs: '+str(dst))
        else:
            needed += src.stat().st_size
    if shutil.disk_usage(target).free < needed:
        raise ValueError('Insufficient space for the complete single-volume installer')
    for src, dst in files:
        copy_checked(src, dst)
    (target/'sources').mkdir(exist_ok=True)
    runner(['split', source/'sources/install.wim', target/'sources/install.swm', '3800'])
    parts = sorted((target/'sources').glob('install*.swm'))
    if not parts or any(part.stat().st_size > 0xffffffff for part in parts):
        raise ValueError('Split WIM output is absent or exceeds FAT32 limits')
    runner(['verify', target/'sources/install.swm', '--ref='+str(target/'sources/install*.swm')])
    runner(['verify', target/'sources/boot.wim'])
    result = inspect(target)
    if result['errors']:
        raise ValueError('Destination boot preflight failed: '+str(result['errors']))
    report = {
        'format_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'platform': 'j413', 'mode': 'same-volume-windows-setup', 'partition_uuid': identity,
        'native_boot_qualified': False, 'images': images, 'firmware_manifest': manifest,
        'includes_bootstrap': include_bootstrap,
        'files': {str(dst.relative_to(target)): {'size': dst.stat().st_size, 'sha256': sha(dst)} for _, dst in files},
        'split_install_images': {part.name: {'size': part.stat().st_size, 'sha256': sha(part)} for part in parts},
        'source_install_wim_sha256': sha(source/'sources/install.wim'),
        'driver_status': driver_audit(ROOT/'dist/j413-driver-build'),
        'qualification': 'Files, ARM64 WIM metadata, WIM integrity and fixed target verified; native boot and custom drivers unqualified',
    }
    records = target/'J413Setup'; records.mkdir(exist_ok=True)
    (records/'MEDIA.json').write_text(json.dumps(report, indent=2)+'\n')
    shutil.copyfile(firmware/'MANIFEST.json', records/'FIRMWARE-MANIFEST.json')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--volume', type=Path, required=True)
    parser.add_argument('--partition-uuid', required=True)
    parser.add_argument('--firmware', type=Path, default=ROOT/'dist/j413/boot-experiment')
    parser.add_argument('--without-bootstrap', action='store_true', help='preserve an existing bootstrap for a later separate pinned install')
    parser.add_argument('--apply', action='store_true', help='copy files to the explicitly identified FAT volume; never format')
    args = parser.parse_args()
    identity = str(uuid.UUID(args.partition_uuid)).upper()
    manifest = verify(args.firmware/'boot.bin')
    info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', str(args.volume)]))
    if (info.get('DiskUUID', '').upper() != identity or info.get('FilesystemType') != 'msdos' or
            Path(info.get('MountPoint', '')).resolve() != args.volume.resolve()):
        raise ValueError('Target UUID, FAT filesystem or mount point mismatch')
    if manifest.get('direct_setup', {}).get('partition_uuid') != identity:
        raise ValueError('The candidate is bound to another volume UUID')
    if not args.apply:
        print('Target and firmware binding verified. Use --apply to stage files; no files changed.')
        return
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    exp = 'EXP-'+stamp+'-DIRECT-SETUP-'+uuid.uuid4().hex[:8]
    ledger = ROOT/'investigation/EXPERIMENTS.md'
    record = ('\n\n## '+exp+' — same-volume Setup staging\n\nBefore '+datetime.now(timezone.utc).isoformat()+
        ': target '+str(args.volume)+' PARTUUID '+identity+'; firmware SHA256 '+sha(args.firmware/'boot.bin')+
        '; manifest '+str(args.firmware/'MANIFEST.json')+'; command '+repr(sys.argv)+
        '. Existing different files are rejected before copy; original source and internal partition layout are preserved. '
        'Expected checkpoint complete hashed ARM64 FAT32 Setup plus firmware on one volume; no launch.\n')
    with ledger.open('a') as stream: stream.write(record)
    try:
        report = stage(args.source,args.volume,args.firmware,manifest,identity,include_bootstrap=not args.without_bootstrap)
        with ledger.open('a') as stream:
            stream.write('\nAfter '+datetime.now(timezone.utc).isoformat()+', '+exp+': staged and hash/WIM verified; MEDIA.json '+str(args.volume/'J413Setup/MEDIA.json')+
                         '; verdict implemented; no native boot phases, stop code, CPU/IRQ/timer/input/storage/network liveness or reboot.\n')
        print('Same-volume Setup prepared: '+str(args.volume/'J413Setup/MEDIA.json'))
        print('Copied files: '+str(len(report['files']))+'; split install parts: '+str(len(report['split_install_images'])))
    except BaseException as error:
        with ledger.open('a') as stream: stream.write('\nAfter '+datetime.now(timezone.utc).isoformat()+', '+exp+': staging failed '+repr(error)+'; verdict inconclusive; no launch.\n')
        raise


if __name__ == '__main__':
    try:
        main()
    except (ValueError,OSError,subprocess.CalledProcessError) as error:
        print('Setup staging stopped: '+str(error),file=sys.stderr)
        raise SystemExit(1)
