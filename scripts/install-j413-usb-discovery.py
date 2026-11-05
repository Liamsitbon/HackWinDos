#!/usr/bin/env python3
"""Install the exact bounded ARM64 USB discovery candidate on this Mac's existing Asahi ESP."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shlex
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.verify_install_image import verify

ESP_UUID = '3953DFAE-A571-42D9-9FC7-F962BC4CE923'
IMAGE = ROOT / 'dist/j413/boot-experiment/boot.bin'
IMAGE_SHA256 = '817b006fb1f5c9c23140dba3410ca2a6caa01fa0b3c73bb590324682289cc4ed'
LEDGER = ROOT / 'investigation/EXPERIMENTS.md'
BACKUPS = ROOT / '.local/esp-installs'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def run(*args):
    return subprocess.check_output(args, stderr=subprocess.STDOUT)


def disk_info(disk):
    return plistlib.loads(run('diskutil', 'info', '-plist', disk))


def find_esp():
    tree = plistlib.loads(run('diskutil', 'list', '-plist'))
    matches = set()
    for drive in tree.get('AllDisksAndPartitions', []):
        for part in drive.get('Partitions', []):
            if part.get('DiskUUID', '').upper() == ESP_UUID:
                matches.add(part['DeviceIdentifier'])
    if len(matches) != 1:
        raise ValueError('Expected exactly one recorded Asahi ESP; it is absent or ambiguous. After a fresh UEFI installation, '
                         'supply its exact partition UUID with --esp-uuid. No partition is created by this script.')
    disk = matches.pop()
    info = disk_info(disk)
    if (info.get('DiskUUID', '').upper() != ESP_UUID or
            info.get('Content') != 'EFI' or info.get('Internal') is not True or
            info.get('FilesystemType') != 'msdos'):
        raise ValueError('Target is not the recorded internal FAT ESP')
    return disk


def candidate():
    manifest = verify(IMAGE)
    if (manifest.get('platform') != 'j413' or manifest.get('display') != 'physical' or
            manifest.get('debug') != 'off'):
        raise ValueError('Expected the J413 physical/debug-off image')
    data = IMAGE.read_bytes()
    if digest(data) != IMAGE_SHA256:
        raise ValueError('Build changed; this installer is pinned to the bounded USB discovery candidate')
    return data, IMAGE, manifest


def recovery(path):
    path = path.resolve()
    if not path.is_relative_to(BACKUPS.resolve()):
        raise ValueError('Recovery record must come from this installer backup directory')
    record = json.loads(path.read_text())
    if record.get('esp_uuid') != ESP_UUID:
        raise ValueError('Recovery record belongs to a different ESP')
    source = path.parent / 'boot.bin.before'
    data = source.read_bytes()
    if digest(data) != record['backup_sha256']:
        raise ValueError('Recovery bytes do not match their recorded hash')
    return data, source, record


def source_state():
    result = {}
    for name, directory in [('root', ROOT), ('m1n1', ROOT/'m1n1_windows'), ('Mu', ROOT/'mu')]:
        result[name] = {
            'commit': run('git', '-C', str(directory), 'rev-parse', 'HEAD').decode().strip(),
            'branch': run('git', '-C', str(directory), 'branch', '--show-current').decode().strip(),
            'diff_sha256': digest(run('git', '-C', str(directory), 'diff', 'HEAD', '--binary')),
        }
    return result


def record(text):
    with LEDGER.open('a', encoding='utf-8') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())


def install(data, disk, source, provenance, restoring=False):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    exp_id = 'EXP-' + stamp + '-J413-ESP-' + uuid.uuid4().hex[:8]
    directory = BACKUPS / exp_id
    directory.mkdir(parents=True, mode=0o700)
    state = source_state()
    (directory/'SOURCE.json').write_text(json.dumps(provenance, indent=2)+'\n')
    record(f'\n\n## {exp_id} — {"restore" if restoring else "install"} J413 payload\n\n'
           f'Before {datetime.now(timezone.utc).isoformat()}: target {disk}, PARTUUID {ESP_UUID}; '
           f'source {source}; SHA256 {digest(data)}; source state {json.dumps(state, sort_keys=True)}. '
           f'Command {shlex.join(sys.argv)}. Recovery destination {directory}/boot.bin.before. '
           'Expected checkpoint: verified atomic payload replacement only; no guest launch. '
           'Failure criterion: target, mount, backup, copy or hash verification fails. '
           'Evidence: this entry and backup directory; no format, repair, boot-policy change or reboot.\n')
    temporary = None
    try:
        run('diskutil', 'mount', disk)
        info = disk_info(disk)
        if info.get('DiskUUID', '').upper() != ESP_UUID:
            raise ValueError('Partition identity changed after mount')
        mount = info.get('MountPoint')
        if not mount or not Path(mount).is_dir():
            raise ValueError('ESP mount point unavailable')
        target = Path(mount)/'m1n1/boot.bin'
        if not target.is_file() or target.is_symlink():
            raise ValueError('Existing m1n1/boot.bin not found; refusing to create a new boot layout')
        old = target.read_bytes()
        backup = directory/'boot.bin.before'
        with backup.open('xb') as stream:
            stream.write(old)
            stream.flush()
            os.fsync(stream.fileno())
        backup.chmod(0o600)
        if digest(backup.read_bytes()) != digest(old):
            raise ValueError('Backup verification failed')
        metadata = directory/'RECOVERY.json'
        with metadata.open('x') as stream:
            json.dump({'esp_uuid': ESP_UUID, 'backup_sha256': digest(old),
                       'target': str(target), 'experiment': exp_id}, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        record(f'\nBefore replacement {exp_id}: recovery {backup}, SHA256 {digest(old)}; '
               'backup verified. Existing bootability is not newly qualified; macOS startup picker remains recovery.\n')
        temporary = target.with_name('.boot.bin.new.'+uuid.uuid4().hex)
        with temporary.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o644)
        if digest(temporary.read_bytes()) != digest(data):
            raise ValueError('Temporary payload verification failed')
        os.replace(temporary, target)
        temporary = None
        run('sync')
        if digest(target.read_bytes()) != digest(data):
            raise ValueError('Installed payload verification failed')
        record(f'\nAfter {datetime.now(timezone.utc).isoformat()}, {exp_id}: installed '
               f'{target}, SHA256 {digest(data)}; byte verification passed. Verdict: installed; '
               'boot/USB/Windows result inconclusive. No boot phases, Windows stop/parameters, '
               'CPU/IRQ/timer or display/input/storage/SSH/RDP liveness measured; no reboot or launch. '
               'Next checkpoint: operator records this exact image boot, USB child/filesystem discovery and ARM64 selection or late failure snapshot.\n')
        print(f'Installed: {target}\nSHA256: {digest(data)}\nBackup: {backup}')
        print('Rollback: sudo python3 '+shlex.quote(str(Path(__file__).resolve()))+
              ' --esp-uuid '+shlex.quote(ESP_UUID)+' --restore '+shlex.quote(str(metadata)))
        print('No reboot performed. This remains an experimental image.')
    except Exception as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        record(f'\nAfter {datetime.now(timezone.utc).isoformat()}, {exp_id}: FAILED '
               f'{json.dumps(str(exc))}; verdict inconclusive. Backup directory {directory}; '
               'no automatic repair or reboot. Check the installed hash before any launch.\n')
        raise


def main():
    global ESP_UUID
    parser = argparse.ArgumentParser(description=__doc__, epilog=
        'Recreating the UEFI environment is a separate procedure: '
        'https://asahilinux.org/docs/platform/open-os-interop/ . '
        'This experimental image has not passed a physical Windows boot.')
    parser.add_argument('--dry-run', action='store_true', help='verify artifact and target; write nothing')
    parser.add_argument('--verify-only', action='store_true', help='verify image without requiring an installed ESP')
    parser.add_argument('--esp-uuid', help='explicit PARTUUID of a newly installed internal Asahi ESP')
    parser.add_argument('--restore', type=Path, metavar='RECOVERY.json')
    args = parser.parse_args()
    if args.esp_uuid:
        ESP_UUID = str(uuid.UUID(args.esp_uuid)).upper()
    data, source, provenance = recovery(args.restore) if args.restore else candidate()
    if args.verify_only:
        print(f'Verified source: {source}\nSHA256: {digest(data)}')
        print('Image verification only: target and physical boot are not verified; no disk action.')
        return
    disk = find_esp()
    if args.dry_run:
        print(f'Verified source: {source}\nSHA256: {digest(data)}\nTarget: {disk} ({ESP_UUID})')
        print('Dry run: no mount, backup, write, repair or reboot.')
        return
    if os.geteuid() != 0:
        raise ValueError('Run with sudo to install, or use --dry-run for read-only verification')
    install(data, disk, source, provenance, restoring=bool(args.restore))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as exc:
        print(f'Installation stopped: {exc}', file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError) and exc.output:
            print(exc.output.decode(errors='replace'), file=sys.stderr)
        sys.exit(1)
