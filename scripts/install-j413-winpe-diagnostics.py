#!/usr/bin/env python3
"""Collect existing USB evidence and optionally install the exact WinPE diagnostic WIM."""
import argparse
from datetime import datetime, timezone
import importlib.util
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
from tools import j413_winpe_diagnostics as profile

spec = importlib.util.spec_from_file_location('direct_setup_installer', ROOT/'scripts/install-j413-direct-setup.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
BACKUPS = ROOT/'.local/winpe-diagnostic-installs'
MARKER = 'J413Setup/DIAGNOSTIC-TARGET-'+profile.ESP_UUID+'.txt'
FILES = ('sources/boot.wim', 'J413Setup/MEDIA.json', 'J413Setup/WINPE-DIAGNOSTICS.json', MARKER)


def json_bytes(data):
    return (json.dumps(data, indent=2)+'\n').encode()


def copy_atomic(source, destination, expected):
    temporary = destination.with_name('.j413-wim-'+uuid.uuid4().hex)
    try:
        with source.open('rb') as inp, temporary.open('xb') as out:
            shutil.copyfileobj(inp, out, 4*1024*1024)
            out.flush()
            os.fsync(out.fileno())
        temporary.chmod(0o644)
        if profile.sha(temporary) != expected:
            raise ValueError('Temporary WIM/backup hash mismatch')
        os.replace(temporary, destination)
        if profile.sha(destination) != expected:
            raise ValueError('Installed WIM/backup hash mismatch')
    finally:
        temporary.unlink(missing_ok=True)


def snapshot(mount, directory):
    entries = {}
    for index, relative in enumerate(FILES):
        source = mount/relative
        if source.is_symlink() or source.parent.is_symlink():
            raise ValueError('Symlink in diagnostic target')
        if not source.exists():
            if index < 2:
                raise ValueError('Original Setup payload/metadata absent')
            entries[relative] = {'absent': True}
            continue
        if not source.is_file():
            raise ValueError('Expected a regular diagnostic target file')
        expected = profile.sha(source)
        name = f'payload-{index}.before'
        copy_atomic(source, directory/name, expected)
        entries[relative] = {'backup_file':name, 'sha256':expected}
    return entries


def recovery_files(record_path):
    record_path = record_path.resolve()
    if not record_path.is_relative_to(BACKUPS.resolve()):
        raise ValueError('Recovery record must belong to this installer')
    record = json.loads(record_path.read_text())
    if record.get('esp_uuid') != profile.ESP_UUID or set(record.get('files', {})) != set(FILES):
        raise ValueError('Recovery target/file identities differ')
    for index, relative in enumerate(FILES):
        entry = record['files'][relative]
        if entry.get('absent') is True:
            if index < 2:
                raise ValueError('Required recovery file absent')
            continue
        if entry.get('backup_file') != f'payload-{index}.before':
            raise ValueError('Invalid backup filename')
        path = record_path.parent/entry['backup_file']
        if not path.is_file() or path.is_symlink() or profile.sha(path) != entry.get('sha256'):
            raise ValueError('Recovery file hash mismatch')
    return record


def restore_files(mount, record_path):
    record_path = record_path.resolve()
    record = recovery_files(record_path)  # Validate all bytes before mutating any file.
    for relative, entry in record['files'].items():
        target = mount/relative
        if target.is_symlink() or target.parent.is_symlink():
            raise ValueError('Symlink in recovery target')
        if entry.get('absent') is True:
            target.unlink(missing_ok=True)
        else:
            copy_atomic(record_path.parent/entry['backup_file'], target, entry['sha256'])


def collect(mount, directory):
    for relative in ('m1n1/j413uefi.log', 'J413Setup/MEDIA.json'):
        path = mount/relative
        if path.is_file() and not path.is_symlink():
            shutil.copyfile(path, directory/Path(relative).name)
    log = directory/'j413uefi.log'
    if log.exists():
        print(log.read_bytes().split(b'\0', 1)[0].decode('ascii', 'replace'))


def operate(disk, diagnostic, restore=None, collect_only=False):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    exp = 'EXP-'+stamp+'-J413-WINPE-'+uuid.uuid4().hex[:8]
    directory = BACKUPS/exp
    directory.mkdir(parents=True, mode=0o700)
    base.record('\n\n## '+exp+' — '+('collect' if collect_only else 'restore' if restore else 'install')+
                ' WinPE diagnostic media\n\nBefore '+datetime.now(timezone.utc).isoformat()+
                ': target '+disk+' PARTUUID '+profile.ESP_UUID+'; source state '+json.dumps(base.source_state(),sort_keys=True)+
                '; command '+shlex.join(sys.argv)+'; unchanged firmware SHA256 '+profile.BOOTSTRAP_SHA256+
                '; WIM/profile '+json.dumps(diagnostic,sort_keys=True)+'. Expected checkpoint existing log capture'+
                (' only' if collect_only else ' and verified WIM/media transaction')+
                '; failure identity/mount/hash/copy error. Recovery destination '+str(directory)+
                '. No firmware replacement, driver load, partition/format/repair, security change or reboot.\n')
    recovery_path = None
    mounted_read_only = False
    try:
        was_mounted = bool(base.disk_info(disk).get('MountPoint'))
        mount_command = ['diskutil','mount'] + (['readOnly'] if collect_only else []) + [disk]
        result = subprocess.run(mount_command,capture_output=True)
        (directory/'mount.txt').write_bytes(result.stdout+result.stderr)
        info = base.disk_info(disk)
        if info.get('DiskUUID','').upper() != profile.ESP_UUID:
            raise ValueError('ESP changed after mount')
        mountpoint = info.get('MountPoint')
        if not mountpoint:
            raise ValueError('ESP did not mount. No repair or media replacement attempted; see '+str(directory/'mount.txt'))
        mount = Path(mountpoint)
        mounted_read_only = collect_only and not was_mounted
        if profile.sha(mount/'m1n1/boot.bin') != profile.BOOTSTRAP_SHA256:
            raise ValueError('Keep the photographed Setup-reaching firmware unchanged')
        collect(mount, directory)
        if not collect_only:
            if os.statvfs(mount).f_flag & os.ST_RDONLY:
                raise ValueError('ESP is mounted read-only; unmount it before installing diagnostics')
            if restore:
                recovery_files(restore)
            else:
                base.verify_same_volume(mount)
                if profile.sha(mount/'sources/boot.wim') != profile.SOURCE_SHA256:
                    raise ValueError('Expected original Setup WIM; restore an earlier diagnostic update first')
                if os.statvfs(mount).f_bavail*os.statvfs(mount).f_frsize < diagnostic['artifacts']['boot.wim']['size']+16*1024*1024:
                    raise ValueError('Not enough ESP space for an atomic WIM replacement')
            entries = snapshot(mount, directory)
            recovery_path = directory/'RECOVERY.json'
            base.atomic_file(recovery_path, json_bytes({'esp_uuid':profile.ESP_UUID,'files':entries,'experiment':exp}))
            recovery_files(recovery_path)
            base.record('\nBefore replacement '+exp+': verified recovery hashes '+json.dumps(entries,sort_keys=True)+'.\n')
            if restore:
                restore_files(mount, restore)
            else:
                metadata = json.loads((mount/'J413Setup/MEDIA.json').read_text())
                metadata['files']['sources/boot.wim'] = diagnostic['artifacts']['boot.wim']
                metadata['winpe_diagnostics'] = diagnostic
                copy_atomic(profile.OUT/'boot.wim',mount/'sources/boot.wim',diagnostic['artifacts']['boot.wim']['sha256'])
                base.atomic_file(mount/'J413Setup/MEDIA.json',json_bytes(metadata))
                base.atomic_file(mount/'J413Setup/WINPE-DIAGNOSTICS.json',json_bytes(diagnostic))
                base.atomic_file(mount/MARKER,(profile.ESP_UUID+'\r\n').encode('ascii'))
            base.run('sync')
        base.record('\nAfter '+datetime.now(timezone.utc).isoformat()+', '+exp+
                    ': host transaction completed; firmware unchanged. Existing evidence '+str(directory)+
                    '. Native diagnostic execution, input/USB, disk/PnP state and Windows installation remain unqualified; no launch or reboot.\n')
        print('Evidence: '+str(directory))
        if recovery_path:
            print('Rollback: sudo /usr/bin/python3 '+shlex.quote(str(Path(__file__).resolve()))+
                  ' --restore '+shlex.quote(str(recovery_path)))
        print('No reboot performed.')
    except Exception as error:
        if recovery_path is not None:
            try:
                restore_files(mount,recovery_path)
                base.run('sync')
                base.record('\nRollback '+exp+': previous WIM and metadata byte-verified.\n')
            except Exception as rollback_error:
                base.record('\nRollback '+exp+' FAILED: '+json.dumps(str(rollback_error))+'. Use recorded recovery before boot.\n')
        base.record('\nAfter '+datetime.now(timezone.utc).isoformat()+', '+exp+': FAILED '+json.dumps(str(error))+
                    '; no physical diagnostic result or reboot. Evidence '+str(directory)+'.\n')
        raise
    finally:
        if mounted_read_only:
            result = subprocess.run(['diskutil','unmount',disk],capture_output=True)
            (directory/'unmount.txt').write_bytes(result.stdout+result.stderr)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--collect-only',action='store_true',help='read the existing UEFI log without changing Setup media')
    parser.add_argument('--restore',type=Path)
    args=parser.parse_args()
    if args.restore and args.collect_only:
        raise ValueError('Choose collect-only or restore')
    diagnostic = {} if args.restore or args.collect_only else profile.verify()
    if args.restore:
        recovery_files(args.restore)
    disk = base.find_esp()
    if args.dry_run:
        print('Verified target '+disk+' ('+profile.ESP_UUID+'); no mount or write.')
        return
    if os.geteuid() != 0:
        raise ValueError('Run with sudo for ESP access, or --dry-run for a read-only plan')
    operate(disk,diagnostic,restore=args.restore,collect_only=args.collect_only)


if __name__ == '__main__':
    try:
        main()
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as error:
        print('Stopped: '+str(error),file=sys.stderr)
        sys.exit(1)
