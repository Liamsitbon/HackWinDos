#!/usr/bin/env python3
"""Install the exact same-volume ARM64 Windows Setup candidate on this Mac's existing Asahi ESP."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.verify_install_image import verify

ESP_UUID = '6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB'
IMAGE = ROOT / 'dist/j413/boot-experiment/boot.bin'
IMAGE_SHA256 = '639d558d3e1abe42024df8edc298f12e283cc87906920851858a76e66db59cc9'
LEDGER = ROOT / 'investigation/EXPERIMENTS.md'
BACKUPS = ROOT / '.local/direct-setup-installs'
SETUP_SOURCE = None
FIRMWARE_ONLY = False
COMPANION_FILES = ('m1n1/J413_EFI.fd', 'J413Setup/FIRMWARE-MANIFEST.json', 'J413Setup/MEDIA.json')


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


def verify_same_volume(mount, expected_image_sha256=None):
    from tools.check_j413_setup import inspect
    result = inspect(mount)
    if result['errors']:
        raise ValueError('Same-volume Setup is incomplete: '+str(result['errors']))
    metadata = json.loads((mount/'J413Setup/MEDIA.json').read_text())
    if metadata.get('partition_uuid') != ESP_UUID or metadata.get('mode') != 'same-volume-windows-setup':
        raise ValueError('Setup manifest belongs to another volume')
    expected = IMAGE_SHA256 if expected_image_sha256 is None else expected_image_sha256
    if metadata.get('firmware_manifest', {}).get('artifacts', {}).get('boot.bin', {}).get('sha256') != expected:
        raise ValueError('Setup manifest names a different boot image')
    required = {'efi/boot/bootaa64.efi','efi/microsoft/boot/bcd','sources/boot.wim','boot/boot.sdi','setup.exe'}
    files = metadata.get('files', {})
    if not required.issubset({name.lower() for name in files}):
        raise ValueError('Setup manifest omits required payloads')
    parts = metadata.get('split_install_images', {})
    if 'install.swm' not in parts:
        raise ValueError('Same-volume install.swm is missing')
    for relative, record in files.items():
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts or '\\' in relative:
            raise ValueError('Invalid Setup manifest path')
        if relative.lower() == 'm1n1/boot.bin':
            continue  # The old bootstrap is replaced only after this preflight.
        target = mount/path
        if target.stat().st_size != record['size'] or file_digest(target) != record['sha256']:
            raise ValueError('Setup payload changed: '+relative)
    for name, record in parts.items():
        if not re.fullmatch(r'install(?:[0-9]+)?\.swm', name):
            raise ValueError('Invalid split image filename')
        target = mount/'sources'/name
        if target.stat().st_size != record['size'] or file_digest(target) != record['sha256']:
            raise ValueError('Split Setup image changed: '+name)


def file_digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b''):
            result.update(block)
    return result.hexdigest()


def atomic_file(path, data):
    temporary = path.with_name('.j413-update.'+uuid.uuid4().hex)
    try:
        with temporary.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o644)
        if temporary.read_bytes() != data:
            raise ValueError('Temporary companion verification failed')
        os.replace(temporary, path)
        if path.read_bytes() != data:
            raise ValueError('Installed companion verification failed')
    finally:
        temporary.unlink(missing_ok=True)


def load_companions(directory, record):
    entries = record.get('companion_files', {})
    if set(entries) != set(COMPANION_FILES):
        raise ValueError('Incomplete firmware companion recovery record')
    result = {}
    for relative, entry in entries.items():
        name = entry['backup_file']
        if not re.fullmatch(r'companion-[0-2]\.before', name):
            raise ValueError('Invalid companion backup path')
        path = directory/name
        if not path.is_file() or path.is_symlink():
            raise ValueError('Missing companion backup')
        data = path.read_bytes()
        if digest(data) != entry['sha256']:
            raise ValueError('Companion recovery hash mismatch')
        result[relative] = data
    return result


def backup_companions(mount, directory):
    entries = {}
    for index, relative in enumerate(COMPANION_FILES):
        path = mount/relative
        if not path.is_file() or path.is_symlink() or path.parent.is_symlink():
            raise ValueError('Expected a regular firmware companion: '+relative)
        data = path.read_bytes()
        name = f'companion-{index}.before'
        with (directory/name).open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        entries[relative] = {'backup_file': name, 'sha256': digest(data)}
    record = {'companion_files': entries}
    load_companions(directory, record)  # Verify every backup before any ESP mutation.
    return entries


def firmware_companions(mount, provenance, bootstrap):
    metadata = json.loads((mount/'J413Setup/MEDIA.json').read_text())
    fd = (IMAGE.parent/'J413_EFI.fd').read_bytes()
    if digest(fd) != provenance['artifacts']['J413_EFI.fd']['sha256']:
        raise ValueError('FD differs from candidate manifest')
    if digest(bootstrap) != provenance['artifacts']['boot.bin']['sha256']:
        raise ValueError('Bootstrap differs from candidate manifest')
    metadata['firmware_manifest'] = provenance
    metadata['includes_bootstrap'] = True
    metadata['firmware_updated_utc'] = datetime.now(timezone.utc).isoformat()
    for relative, data in [('m1n1/J413_EFI.fd', fd), ('m1n1/boot.bin', bootstrap)]:
        metadata['files'][relative] = {'size': len(data), 'sha256': digest(data)}
    return {'m1n1/J413_EFI.fd': fd,
            'J413Setup/FIRMWARE-MANIFEST.json': (json.dumps(provenance, indent=2)+'\n').encode(),
            'J413Setup/MEDIA.json': (json.dumps(metadata, indent=2)+'\n').encode()}


def candidate():
    manifest = verify(IMAGE)
    if (manifest.get('platform') != 'j413' or manifest.get('display') != 'physical' or
            manifest.get('debug') != 'off'):
        raise ValueError('Expected the J413 physical/debug-off image')
    data = IMAGE.read_bytes()
    if digest(data) != IMAGE_SHA256:
        raise ValueError('Build changed; this installer is pinned to the same-volume Setup candidate')
    from tools.j413_platform import require_current_firmware, m1n1_sources_sha256
    require_current_firmware(manifest)
    if (manifest.get('direct_setup', {}).get('partition_uuid') != ESP_UUID or
            manifest.get('platform_m1n1_sources_sha256') != m1n1_sources_sha256()):
        raise ValueError('Direct target or source contract mismatch; configure and rebuild for the exact ESP UUID')
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
    companion_rollback = None
    bootstrap_replaced = False
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
        if FIRMWARE_ONLY or (restoring and provenance.get('companion_files')):
            if restoring:
                changes = load_companions(source.parent, provenance)
            else:
                print('Verifying existing Setup bytes; updating firmware without recopying Windows...', flush=True)
                verify_same_volume(Path(mount), expected_image_sha256=digest(old))
                changes = firmware_companions(Path(mount), provenance, data)
            entries = backup_companions(Path(mount), directory)
            recovery_metadata = json.loads(metadata.read_text())
            recovery_metadata['companion_files'] = entries
            atomic_file(metadata, (json.dumps(recovery_metadata, indent=2)+'\n').encode())
            companion_rollback = load_companions(directory, recovery_metadata)
            record(f'\nBefore companion replacement {exp_id}: verified recovery hashes '
                   f'{json.dumps(entries, sort_keys=True)}. Windows installer bytes are retained.\n')
            for relative, content in changes.items():
                atomic_file(Path(mount)/relative, content)
        elif not restoring:
            if SETUP_SOURCE is not None:
                from tools.j413_setup_bundle import stage
                print('Staging and verifying complete same-volume Setup before replacing the bootstrap...', flush=True)
                stage(SETUP_SOURCE, Path(mount), IMAGE.parent, provenance, ESP_UUID, include_bootstrap=False)
            verify_same_volume(Path(mount))
        temporary = target.with_name('.boot.bin.new.'+uuid.uuid4().hex)
        with temporary.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o644)
        if digest(temporary.read_bytes()) != digest(data):
            raise ValueError('Temporary payload verification failed')
        os.replace(temporary, target)
        bootstrap_replaced = True
        temporary = None
        run('sync')
        if digest(target.read_bytes()) != digest(data):
            raise ValueError('Installed payload verification failed')
        record(f'\nAfter {datetime.now(timezone.utc).isoformat()}, {exp_id}: installed '
               f'{target}, SHA256 {digest(data)}; byte verification passed. Verdict: installed; '
               'boot/USB/Windows result inconclusive. No boot phases, Windows stop/parameters, '
               'CPU/IRQ/timer or display/input/storage/SSH/RDP liveness measured; no reboot or launch. '
               'Next checkpoint: operator records fixed-volume NVMe/ARM64 loader entry and the actual resulting Windows phase.\n')
        print(f'Installed: {target}\nSHA256: {digest(data)}\nBackup: {backup}')
        print('Rollback: sudo python3 '+shlex.quote(str(Path(__file__).resolve()))+
              ' --esp-uuid '+shlex.quote(ESP_UUID)+' --restore '+shlex.quote(str(metadata)))
        print('No reboot performed. This remains an experimental image.')
    except Exception as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if companion_rollback is not None:
            try:
                if bootstrap_replaced:
                    atomic_file(target, old)
                for relative, content in companion_rollback.items():
                    atomic_file(Path(mount)/relative, content)
                run('sync')
                record(f'\nRollback {exp_id}: prior bootstrap/companions restored and byte-verified after update failure.\n')
            except Exception as rollback_error:
                record(f'\nRollback {exp_id} FAILED: {json.dumps(str(rollback_error))}; use recorded recovery before boot.\n')
        record(f'\nAfter {datetime.now(timezone.utc).isoformat()}, {exp_id}: FAILED '
               f'{json.dumps(str(exc))}; verdict inconclusive. Backup directory {directory}; '
               'no automatic repair or reboot. Check the installed hash before any launch.\n')
        raise


def main():
    global ESP_UUID, IMAGE_SHA256, SETUP_SOURCE, FIRMWARE_ONLY
    parser = argparse.ArgumentParser(description=__doc__, epilog=
        'Recreating the UEFI environment is a separate procedure: '
        'https://asahilinux.org/docs/platform/open-os-interop/ . '
        'This experimental image has not passed a physical Windows boot.')
    parser.add_argument('--dry-run', action='store_true', help='verify artifact and target; write nothing')
    parser.add_argument('--verify-only', action='store_true', help='verify image without requiring an installed ESP')
    parser.add_argument('--esp-uuid', help='explicit PARTUUID of a newly installed internal Asahi ESP')
    parser.add_argument('--restore', type=Path, metavar='RECOVERY.json')
    parser.add_argument('--image-sha256', help='explicit SHA256 of a rebuilt and recorded direct candidate')
    parser.add_argument('--setup-source', type=Path, help='complete ARM64 Setup media to stage after the bootstrap backup')
    parser.add_argument('--firmware-only', action='store_true', help='verify existing Setup and update firmware/provenance with a complete companion backup; no Windows recopy')
    args = parser.parse_args()
    if args.image_sha256:
        if not re.fullmatch('[0-9a-fA-F]{64}', args.image_sha256):
            raise ValueError('Invalid image SHA256')
        IMAGE_SHA256 = args.image_sha256.lower()
    SETUP_SOURCE = args.setup_source
    FIRMWARE_ONLY = args.firmware_only
    if FIRMWARE_ONLY and (SETUP_SOURCE is not None or args.restore is not None):
        raise ValueError('--firmware-only cannot be combined with --setup-source or --restore')
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
