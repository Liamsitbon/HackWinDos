#!/usr/bin/env python3
"""Add only missing WinPE payloads to the recorded SanDisk FAT boot partition."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.check_j413_setup import inspect

SOURCE_UUID = '6EF78F22-8A6D-454C-880E-1DDD706CADE4'
TARGET_UUID = 'D0E51975-0AE3-45C5-8EE0-85C51B0FCC78'
HASHES = {
    'efi/boot/bootaa64.efi': 'fae47d78487e781aa06466775cb461adeb7ff7f887fe2c15295bb2eb4f4954e1',
    'efi/microsoft/boot/bcd': 'b90ef16b94c3dda7d76cc39840befaa9786887517445c3b6f47ebc806d0ab105',
    'sources/boot.wim': 'dcf58a3d6be5d8747ba8b475f6bbc3782a53bc5dc14c7b11e73ff140deeab534',
    'boot/boot.sdi': 'cd2c00ce027687ce4a8bdc967f26a8ab82f651c9becd703658ba282ec49702bd',
}
PAYLOADS = ('sources/boot.wim', 'boot/boot.sdi')
LEDGER = ROOT/'investigation/EXPERIMENTS.md'
RECORDS = ROOT/'.local/usb-media'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def query(*args):
    return plistlib.loads(subprocess.check_output(['diskutil', *args]))


def media():
    parts = [p for d in query('list', '-plist').get('AllDisksAndPartitions', [])
             for p in d.get('Partitions', [])]
    infos = []
    for identity, fs in [(SOURCE_UUID, 'exfat'), (TARGET_UUID, 'msdos')]:
        matches = [p for p in parts if p.get('DiskUUID', '').upper() == identity]
        if len(matches) != 1:
            raise ValueError('Recorded SanDisk partition is not uniquely connected')
        info = query('info', '-plist', matches[0]['DeviceIdentifier'])
        mount = info.get('MountPoint')
        if (info.get('DiskUUID', '').upper() != identity or info.get('Internal') is not False or
                info.get('FilesystemType') != fs or not mount or not Path(mount).is_dir()):
            raise ValueError('Recorded external partition identity/filesystem/mount mismatch')
        infos.append(info)
    if not infos[0].get('ParentWholeDisk') or infos[0]['ParentWholeDisk'] != infos[1].get('ParentWholeDisk'):
        raise ValueError('Source and destination must be partitions of the same SanDisk')
    return tuple(Path(i['MountPoint']) for i in infos)


def plan(source, target):
    if inspect(source)['errors']:
        raise ValueError('Source does not contain all four ARM64 WinPE boot payloads')
    missing = []
    for rel, expected in HASHES.items():
        if digest(source/rel) != expected:
            raise ValueError('Source changed from verified media: '+rel)
        destination = target/rel
        if destination.exists():
            if digest(destination) != expected:
                raise ValueError('Existing destination differs; refusing to overwrite: '+rel)
        elif rel in PAYLOADS:
            missing.append(rel)
        else:
            raise ValueError('Destination fallback loader or BCD is missing')
    needed = sum((source/rel).stat().st_size for rel in missing)
    if missing and shutil.disk_usage(target).free < needed + 16 * 1024 * 1024:
        raise ValueError('Insufficient FAT boot partition free space')
    return missing


def record(text):
    with LEDGER.open('a') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())


def complete(source, target, missing):
    exp = 'EXP-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-USB-MEDIA-'+uuid.uuid4().hex[:8]
    directory = RECORDS/exp
    directory.mkdir(parents=True)
    state = {}
    for name, repository in [('root', ROOT), ('m1n1', ROOT/'m1n1_windows'), ('Mu', ROOT/'mu')]:
        state[name] = {
            'commit': subprocess.check_output(['git', '-C', str(repository), 'rev-parse', 'HEAD'], text=True).strip(),
            'branch': subprocess.check_output(['git', '-C', str(repository), 'branch', '--show-current'], text=True).strip(),
            'diff_sha256': hashlib.sha256(subprocess.check_output(['git', '-C', str(repository), 'diff', 'HEAD', '--binary'])).hexdigest(),
        }
    manifest = {'experiment': exp, 'profile': 'FAT32-WinPE-payload-completion', 'source_uuid': SOURCE_UUID, 'target_uuid': TARGET_UUID,
                'source': str(source), 'target': str(target), 'sha256': HASHES,
                'originally_absent': missing, 'source_state': state,
                'recovery': 'Existing files are untouched. Remove only these newly added files after verifying recorded hashes.'}
    (directory/'MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n')
    record(f'\n\n## {exp} — complete FAT WinPE payloads\n\nBefore {datetime.now(timezone.utc).isoformat()}: '
           f'command {shlex.join(sys.argv)}; source {source} UUID {SOURCE_UUID}; target {target} UUID {TARGET_UUID}; '
           f'root branch master; source state {json.dumps(state, sort_keys=True)}; '
           f'manifest/recovery record {directory}/MANIFEST.json; SHA256 {digest(directory/"MANIFEST.json")}; '
           f'payload hashes {json.dumps(HASHES, sort_keys=True)}. Hypothesis: adding only missing {missing} '
           'completes the FAT partition WinPE relative paths. Existing loader/BCD and all firmware/partitions unchanged. '
           'Expected checkpoint: matching destination hashes and four valid headers; no firmware launch.\n')
    created = []
    try:
        for rel in missing:
            if rel not in PAYLOADS:
                raise ValueError('Unexpected copy path')
            destination = target/rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation: never truncate or replace an existing file.
            with destination.open('xb') as output:
                created.append(destination)
                with (source/rel).open('rb') as input_stream:
                    shutil.copyfileobj(input_stream, output, 4 * 1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
            if digest(destination) != HASHES[rel]:
                raise ValueError('Destination verification failed: '+rel)
        result = inspect(target)
        if result['errors']:
            raise ValueError('Destination preflight failed: '+str(result['errors']))
        record(f'\nAfter {datetime.now(timezone.utc).isoformat()}, {exp}: verified {missing}; '
               'four boot headers valid; verdict implemented, physical boot inconclusive. '
               'No boot phases, stop code, CPU/IRQ/timer, USB input/SSH/RDP/storage liveness measured; no reboot.\n')
        print('FAT WinPE payloads verified. Record: '+str(directory/'MANIFEST.json'))
    except BaseException as error:
        for destination in created:
            destination.unlink(missing_ok=True)
        record(f'\nAfter {datetime.now(timezone.utc).isoformat()}, {exp}: failed {error!r}; '
               'new files from this attempt removed, prior files untouched; verdict inconclusive. No launch.\n')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    source, target = media()
    missing = plan(source, target)
    if args.dry_run:
        print('Verified SanDisk; missing payloads: '+str(missing))
    elif missing:
        # Re-resolve the UUIDs immediately before writing to the mounted disk.
        if media() != (source, target):
            raise ValueError('Media identity changed during preflight')
        complete(source, target, missing)
    else:
        print('Both SanDisk boot payloads already match verified source bytes.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print('Media completion stopped: '+str(error), file=sys.stderr)
        sys.exit(1)
