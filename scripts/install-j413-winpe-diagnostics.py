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
NATIVE_MOUNT = False


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


def collect_without_mount(disk, info, directory):
    from tools.fat32_readonly import Fat32Reader
    # The exact internal FAT ESP is independently re-resolved immediately before
    # opening the block device. No raw-device writer or repair routine is used.
    if base.find_esp() != disk or info.get('MountPoint'):
        raise ValueError('Raw collection target changed or is mounted')
    size, block = info.get('TotalSize'), info.get('DeviceBlockSize')
    if not isinstance(size,int) or not isinstance(block,int):
        raise ValueError('Measured partition size/block size unavailable')
    device = Path('/dev')/disk
    with device.open('rb', buffering=0) as stream:
        reader = Fat32Reader(stream,size,block)
        (directory/'FAT32.json').write_bytes(json_bytes(reader.geometry()))
        bootstrap = reader.read_file('m1n1/boot.bin',8*1024*1024)
        observed = base.digest(bootstrap)
        if observed != profile.BOOTSTRAP_SHA256:
            raise ValueError('Raw bootstrap differs from Setup-reaching firmware: '+observed)
        raw = reader.read_file('m1n1/j413uefi.log',65536)
    (directory/'j413uefi.log').write_bytes(raw)
    print('Read-only FAT32 extraction; bootstrap SHA256: '+observed)
    print(raw.split(b'\0',1)[0].decode('ascii','replace'))


def native_mount(disk, directory):
    if base.find_esp() != disk:
        raise ValueError('Native mount target identity changed')
    target = directory/'esp'
    target.mkdir(mode=0o700)
    result = subprocess.run(['/sbin/mount_msdos','-o','rw,nobrowse,noexec',
                             '/dev/'+disk,str(target)],capture_output=True)
    output = result.stdout+result.stderr
    (directory/'native-mount.txt').write_bytes(output)
    if result.returncode != 0 or not target.is_mount():
        print(output.decode(errors='replace'))
        raise ValueError('Native FAT mount failed; no repair or media replacement attempted')
    return target


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
    mounted_native = False
    try:
        was_mounted = bool(base.disk_info(disk).get('MountPoint'))
        mount_command = ['diskutil','mount'] + (['readOnly'] if collect_only else []) + [disk]
        result = subprocess.run(mount_command,capture_output=True)
        (directory/'mount.txt').write_bytes(result.stdout+result.stderr)
        info = base.disk_info(disk)
        if info.get('DiskUUID','').upper() != profile.ESP_UUID:
            raise ValueError('ESP changed after mount')
        mountpoint = info.get('MountPoint')
        if not mountpoint and not collect_only and NATIVE_MOUNT:
            mountpoint = str(native_mount(disk,directory))
            mounted_native = True
        if not mountpoint:
            if collect_only:
                collect_without_mount(disk,info,directory)
                base.record('\nAfter '+datetime.now(timezone.utc).isoformat()+', '+exp+
                            ': existing UEFI log collected through bounded read-only FAT32 extraction; '
                            'no mount, repair, media replacement or guest launch. Evidence '+str(directory)+'.\n')
                print('Evidence: '+str(directory))
                return
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
                installed_sha = profile.sha(mount/'sources/boot.wim')
                if installed_sha == profile.PREVIOUS_DIAGNOSTIC_SHA256:
                    # The photographed first diagnostic is a permitted upgrade
                    # source, only with its matching on-volume manifest.
                    previous = json.loads((mount/'J413Setup/WINPE-DIAGNOSTICS.json').read_text())
                    media = json.loads((mount/'J413Setup/MEDIA.json').read_text())
                    if (previous.get('profile') != 'winpe-diagnostic' or
                            previous.get('esp_uuid') != profile.ESP_UUID or
                            previous.get('firmware_sha256') != profile.BOOTSTRAP_SHA256 or
                            previous.get('source_boot_wim_sha256') != profile.SOURCE_SHA256 or
                            previous.get('artifacts', {}).get('boot.wim', {}).get('sha256') != installed_sha or
                            media.get('winpe_diagnostics') != previous):
                        raise ValueError('Previous diagnostic identity/metadata mismatch')
                elif installed_sha != profile.SOURCE_SHA256:
                    raise ValueError('Expected original or explicitly pinned previous diagnostic WIM')
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
                  (' --native-mount' if NATIVE_MOUNT else '')+
                  ' --restore '+shlex.quote(str(recovery_path)))
            if not restore:
                print('Diagnostic WIM installed and verified. Firmware remains unchanged.')
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
        if mounted_read_only or mounted_native:
            result = subprocess.run(['diskutil','unmount',disk],capture_output=True)
            (directory/'unmount.txt').write_bytes(result.stdout+result.stderr)
            if result.returncode != 0:
                base.record('\nCleanup '+exp+': unmount failed; see unmount.txt.\n')
                raise ValueError('Unmount did not complete; see '+str(directory/'unmount.txt'))


def main():
    global NATIVE_MOUNT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--collect-only',action='store_true',help='read the existing UEFI log without changing Setup media')
    parser.add_argument('--restore',type=Path)
    parser.add_argument('--native-mount',action='store_true',help='allow the macOS FAT mount helper if Disk Arbitration fails; never repair')
    args=parser.parse_args()
    if args.restore and args.collect_only:
        raise ValueError('Choose collect-only or restore')
    NATIVE_MOUNT = args.native_mount
    if NATIVE_MOUNT and args.collect_only:
        raise ValueError('Native write mount is not used for collection')
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
