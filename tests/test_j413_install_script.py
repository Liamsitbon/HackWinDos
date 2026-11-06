"""Verify install/rollback transactions against a simulated mounted ESP."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('j413_installer', ROOT/'scripts/install-j413-usb1-phy.py')
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallScriptTests(unittest.TestCase):
    installer = installer
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.mount = self.root/'mounted ESP'
        self.target = self.mount/'m1n1/boot.bin'
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(b'previous payload')
        self.ledger = self.root/'EXPERIMENTS.md'
        self.ledger.write_text('existing ledger\n')
        self.backups = self.root/'backups'
        for key, value in [('ROOT', self.root), ('LEDGER', self.ledger), ('BACKUPS', self.backups)]:
            p = patch.object(self.installer, key, value)
            p.start(); self.addCleanup(p.stop)
        p = patch.object(self.installer, 'source_state', return_value={'root': {'commit': 'a'*40}})
        p.start(); self.addCleanup(p.stop)
        self.commands = []
        p = patch.object(self.installer, 'run', side_effect=self.fake_run)
        p.start(); self.addCleanup(p.stop)

        self.assertEqual(self.installer.ROOT, self.root)
        self.assertEqual(self.installer.BACKUPS, self.backups)

    def fake_run(self, *args):
        self.commands.append(args)
        if args == ('diskutil', 'mount', 'disk9s7'):
            return b'mounted'
        if args == ('diskutil', 'info', '-plist', 'disk9s7'):
            return plistlib.dumps({'DiskUUID': self.installer.ESP_UUID, 'MountPoint': str(self.mount),
                                  'Internal': True, 'Content': 'EFI', 'FilesystemType': 'msdos'})
        if args == ('sync',):
            return b''
        raise AssertionError(f'Unexpected hardware command {args!r}')

    def perform(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.installer.install(b'new payload', 'disk9s7', self.root/'candidate.bin', {'test': True})

    def recovery_record(self):
        return next(self.backups.glob('*/RECOVERY.json'))

    def test_verified_backup_precedes_atomic_replace_and_rollback_recovers_exact_bytes(self):
        real_replace = self.installer.os.replace
        def checked_replace(source, target):
            record = self.recovery_record()
            self.assertEqual((record.parent/'boot.bin.before').read_bytes(), b'previous payload')
            self.assertIn('Before replacement', self.ledger.read_text())
            self.assertEqual(Path(source).parent, self.target.parent)
            return real_replace(source, target)
        with patch.object(self.installer.os, 'replace', side_effect=checked_replace):
            self.perform()
        self.assertEqual(self.target.read_bytes(), b'new payload')
        record = self.recovery_record()
        data, source, provenance = self.installer.recovery(record)
        self.assertEqual(data, b'previous payload')
        with contextlib.redirect_stdout(io.StringIO()):
            self.installer.install(data, 'disk9s7', source, provenance, restoring=True)
        self.assertEqual(self.target.read_bytes(), b'previous payload')
        self.assertEqual(len(list(self.backups.glob('*/RECOVERY.json'))), 2)
        self.assertTrue(self.ledger.read_text().startswith('existing ledger\n'))
        self.assertIn('no reboot or launch', self.ledger.read_text())
        self.assertFalse(list(self.target.parent.glob('.boot.bin.new.*')))

    def test_failed_backup_never_replaces_installed_file(self):
        original_open = Path.open
        def fail_backup(path, mode='r', *args, **kwargs):
            if path.name == 'boot.bin.before' and mode == 'xb':
                raise OSError('simulated full backup volume')
            return original_open(path, mode, *args, **kwargs)
        with patch.object(Path, 'open', fail_backup), patch.object(self.installer.os, 'replace') as replace:
            with self.assertRaisesRegex(OSError, 'full backup'):
                self.perform()
            replace.assert_not_called()
        self.assertEqual(self.target.read_bytes(), b'previous payload')
        self.assertIn('FAILED', self.ledger.read_text())

    def test_failed_replace_keeps_old_bytes_and_cleans_temporary_file(self):
        with patch.object(self.installer.os, 'replace', side_effect=OSError('simulated rename failure')):
            with self.assertRaisesRegex(OSError, 'rename failure'):
                self.perform()
        self.assertEqual(self.target.read_bytes(), b'previous payload')
        self.assertFalse(list(self.target.parent.glob('.boot.bin.new.*')))
        self.assertTrue(self.recovery_record().is_file())
        self.assertIn('FAILED', self.ledger.read_text())

    def test_restore_rejects_tampering_and_records_outside_backup_root(self):
        self.perform()
        record = self.recovery_record()
        (record.parent/'boot.bin.before').write_bytes(b'changed recovery')
        with self.assertRaisesRegex(ValueError, 'recorded hash'):
            self.installer.recovery(record)
        with self.assertRaisesRegex(ValueError, 'backup directory'):
            self.installer.recovery(self.root/'unrelated.json')
        self.assertEqual(self.target.read_bytes(), b'new payload')

    def test_dry_run_has_no_mount_or_ledger_or_backup_writes(self):
        before = self.ledger.read_bytes()
        with patch.object(self.installer, 'candidate', return_value=(b'new', self.root/'candidate', {})), \
             patch.object(self.installer, 'find_esp', return_value='disk9s7'), \
             patch.object(self.installer.sys, 'argv', ['installer', '--dry-run']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.installer.main()
        self.assertEqual(self.ledger.read_bytes(), before)
        self.assertFalse(self.backups.exists())
        self.assertFalse(self.commands)

    def test_partition_uuid_resolution_and_wrong_identity_fail_closed(self):
        tree = {'AllDisksAndPartitions': [{'Partitions': [
            {'DiskUUID': 'other', 'DeviceIdentifier': 'disk0s4'},
            {'DiskUUID': self.installer.ESP_UUID.lower(), 'DeviceIdentifier': 'disk9s7'}]}]}
        real_run = self.fake_run
        def query(*args):
            if args == ('diskutil', 'list', '-plist'):
                return plistlib.dumps(tree)
            return real_run(*args)
        with patch.object(self.installer, 'run', side_effect=query):
            self.assertEqual(self.installer.find_esp(), 'disk9s7')
            tree['AllDisksAndPartitions'][0]['Partitions'].append(
                {'DiskUUID': self.installer.ESP_UUID, 'DeviceIdentifier': 'disk10s1'})
            with self.assertRaisesRegex(ValueError, 'exactly one'):
                self.installer.find_esp()
        with patch.object(self.installer, 'disk_info', return_value={'DiskUUID': 'changed'}):
            with self.assertRaisesRegex(ValueError, 'identity changed'):
                self.perform()
        self.assertEqual(self.target.read_bytes(), b'previous payload')

    def test_changed_build_cannot_be_installed_with_stale_script(self):
        image = self.root/'boot.bin'
        image.write_bytes(b'other build')
        with patch.object(self.installer, 'IMAGE', image), patch.object(self.installer, 'verify', return_value={
                'platform': 'j413', 'display': 'physical', 'debug': 'off'}):
            with self.assertRaisesRegex(ValueError, 'pinned'):
                self.installer.candidate()
        self.assertEqual(self.target.read_bytes(), b'previous payload')


DISCOVERY_SPEC = importlib.util.spec_from_file_location('j413_discovery_installer', ROOT/'scripts/install-j413-usb-discovery.py')
discovery_installer = importlib.util.module_from_spec(DISCOVERY_SPEC)
DISCOVERY_SPEC.loader.exec_module(discovery_installer)


class UsbDiscoveryInstallScriptTests(InstallScriptTests):
    installer = discovery_installer

    def test_verify_only_needs_no_disk_and_new_target_requires_an_explicit_uuid(self):
        new_uuid = '12345678-9ABC-4DEF-8123-456789ABCDEF'
        with patch.object(self.installer, 'ESP_UUID', self.installer.ESP_UUID), \
             patch.object(self.installer, 'candidate', return_value=(b'new', self.root/'candidate', {})), \
             patch.object(self.installer, 'find_esp') as find_esp, \
             patch.object(self.installer.sys, 'argv', ['installer', '--verify-only', '--esp-uuid', new_uuid.lower()]), \
             contextlib.redirect_stdout(io.StringIO()):
            self.installer.main()
            self.assertEqual(self.installer.ESP_UUID, new_uuid)
            find_esp.assert_not_called()
        self.assertFalse(self.commands)
        self.assertFalse(self.backups.exists())


DIRECT_SPEC = importlib.util.spec_from_file_location('j413_direct_installer', ROOT/'scripts/install-j413-direct-setup.py')
direct_installer = importlib.util.module_from_spec(DIRECT_SPEC)
DIRECT_SPEC.loader.exec_module(direct_installer)


class DirectSetupInstallScriptTests(UsbDiscoveryInstallScriptTests):
    installer = direct_installer

    def setUp(self):
        super().setUp()
        self.real_same_volume_check = self.installer.verify_same_volume
        patched = patch.object(self.installer, 'verify_same_volume')
        patched.start(); self.addCleanup(patched.stop)

    def test_explicit_native_mount_rechecks_device_and_uses_only_fat_mount(self):
        with patch.object(self.installer, 'find_esp', return_value='disk9s7'), \
             patch.object(self.installer, 'disk_info', return_value={'DiskUUID':self.installer.ESP_UUID}), \
             patch.object(Path, 'is_mount', return_value=True), \
             patch.object(self.installer, 'run', return_value=b'') as run:
            self.assertEqual(self.installer.native_mount('disk9s7',self.root), self.root/'esp')
            run.assert_called_once_with('/sbin/mount_msdos','-o','rw,nobrowse,noexec','/dev/disk9s7',str(self.root/'esp'))
        with patch.object(self.installer, 'find_esp', return_value='disk9s8'):
            with self.assertRaisesRegex(ValueError,'identity changed'):
                self.installer.native_mount('disk9s7',self.root)

    def test_failed_normal_mount_allows_explicit_fallback_and_unmounts(self):
        def run(*args):
            if args == ('diskutil','mount','disk9s7'):
                raise subprocess.CalledProcessError(1,args,b'mount failure')
            if args == ('diskutil','unmount','disk9s7'):
                self.commands.append(args); return b'unmounted'
            return self.fake_run(*args)
        with patch.object(self.installer,'NATIVE_MOUNT',True), \
             patch.object(self.installer,'run',side_effect=run), \
             patch.object(self.installer,'disk_info',return_value={'DiskUUID':self.installer.ESP_UUID}), \
             patch.object(self.installer,'native_mount',return_value=self.mount) as native:
            self.perform()
        native.assert_called_once()
        self.assertEqual(self.target.read_bytes(),b'new payload')
        self.assertIn(('diskutil','unmount','disk9s7'),self.commands)
        self.assertTrue(self.recovery_record().is_file())

    def test_native_unmount_failure_cannot_report_success(self):
        def run(*args):
            if args in [('diskutil','mount','disk9s7'),('diskutil','unmount','disk9s7')]:
                raise subprocess.CalledProcessError(1,args,b'mount/unmount failure')
            return self.fake_run(*args)
        with patch.object(self.installer,'NATIVE_MOUNT',True), \
             patch.object(self.installer,'run',side_effect=run), \
             patch.object(self.installer,'disk_info',return_value={'DiskUUID':self.installer.ESP_UUID}), \
             patch.object(self.installer,'native_mount',return_value=self.mount):
            with self.assertRaises(subprocess.CalledProcessError): self.perform()
        self.assertIn('unmount FAILED',self.ledger.read_text())

    def test_same_volume_manifest_must_bind_target_and_image(self):
        with patch('tools.check_j413_setup.inspect', return_value={'errors': []}):
            folder = self.mount/'J413Setup';folder.mkdir()
            path = folder/'MEDIA.json'
            path.write_text(json.dumps({'partition_uuid': 'different'}))
            with self.assertRaisesRegex(ValueError, 'another volume'):
                self.real_same_volume_check(self.mount)
            data = {'partition_uuid': self.installer.ESP_UUID, 'mode': 'same-volume-windows-setup',
                    'firmware_manifest': {'artifacts': {'boot.bin': {'sha256': 'wrong'}}}}
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'different boot image'):
                self.real_same_volume_check(self.mount)

    def test_same_volume_checker_rejects_modified_split_image(self):
        from tools.j413_setup_bundle import sha
        files = {}
        for relative in ['efi/boot/bootaa64.efi','efi/microsoft/boot/bcd','sources/boot.wim','boot/boot.sdi','setup.exe']:
            path = self.mount/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
            files[relative] = {'size': path.stat().st_size, 'sha256': sha(path)}
        split = self.mount/'sources/install.swm';split.write_bytes(b'split fixture')
        metadata = {'partition_uuid': self.installer.ESP_UUID, 'mode': 'same-volume-windows-setup',
                    'firmware_manifest': {'artifacts': {'boot.bin': {'sha256': self.installer.IMAGE_SHA256}}},
                    'files': files, 'split_install_images': {'install.swm': {'size': split.stat().st_size,'sha256': sha(split)}}}
        folder=self.mount/'J413Setup';folder.mkdir();(folder/'MEDIA.json').write_text(json.dumps(metadata))
        with patch('tools.check_j413_setup.inspect', return_value={'errors': []}):
            self.real_same_volume_check(self.mount)
            split.write_bytes(b'modified')
            with self.assertRaisesRegex(ValueError, 'Split Setup image changed'):
                self.real_same_volume_check(self.mount)

    def firmware_fixture(self):
        digest = self.installer.digest
        files = {}
        for relative in ['efi/boot/bootaa64.efi', 'efi/microsoft/boot/bcd',
                         'sources/boot.wim', 'boot/boot.sdi', 'setup.exe', 'm1n1/J413_EFI.fd']:
            path = self.mount/relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('fixture '+relative).encode())
            files[relative] = {'size': path.stat().st_size, 'sha256': digest(path.read_bytes())}
        split = self.mount/'sources/install.swm'
        split.write_bytes(b'split fixture')
        folder = self.mount/'J413Setup'
        folder.mkdir()
        previous = {'artifacts': {'boot.bin': {'sha256': digest(self.target.read_bytes())}}}
        (folder/'FIRMWARE-MANIFEST.json').write_text(json.dumps(previous))
        (folder/'MEDIA.json').write_text(json.dumps({
            'partition_uuid': self.installer.ESP_UUID, 'mode': 'same-volume-windows-setup',
            'firmware_manifest': previous, 'files': files,
            'split_install_images': {'install.swm': {'size': split.stat().st_size,
                                                    'sha256': digest(split.read_bytes())}}}))
        image = self.root/'candidate/boot.bin'
        image.parent.mkdir()
        image.write_bytes(b'new payload')
        fd = image.parent/'J413_EFI.fd'
        fd.write_bytes(b'new firmware descriptor')
        p = patch.object(self.installer, 'IMAGE', image)
        p.start(); self.addCleanup(p.stop)
        p = patch.object(self.installer, 'FIRMWARE_ONLY', True)
        p.start(); self.addCleanup(p.stop)
        p = patch('tools.check_j413_setup.inspect', return_value={'errors': []})
        p.start(); self.addCleanup(p.stop)
        self.installer.verify_same_volume.side_effect = self.real_same_volume_check
        self.new_provenance = {'artifacts': {
            'boot.bin': {'sha256': digest(image.read_bytes())},
            'J413_EFI.fd': {'sha256': digest(fd.read_bytes())}}}
        self.previous_companions = {r: (self.mount/r).read_bytes() for r in self.installer.COMPANION_FILES}
        return image, split

    def update_firmware(self, image):
        with contextlib.redirect_stdout(io.StringIO()):
            self.installer.install(image.read_bytes(), 'disk9s7', image, self.new_provenance)

    def test_firmware_only_preserves_setup_and_restores_all_firmware_companions(self):
        image, split = self.firmware_fixture()
        original_stat = split.stat()
        with patch('tools.j413_setup_bundle.stage', side_effect=AssertionError('Windows must not be recopied')):
            self.update_firmware(image)
        self.assertEqual(self.target.read_bytes(), b'new payload')
        self.assertEqual((self.mount/'m1n1/J413_EFI.fd').read_bytes(), b'new firmware descriptor')
        self.assertEqual(split.read_bytes(), b'split fixture')
        self.assertEqual(split.stat().st_mtime_ns, original_stat.st_mtime_ns)
        self.installer.verify_same_volume.assert_called_once_with(
            self.mount, expected_image_sha256=self.installer.digest(b'previous payload'))
        metadata = json.loads((self.mount/'J413Setup/MEDIA.json').read_text())
        self.assertEqual(metadata['firmware_manifest'], self.new_provenance)
        record = self.recovery_record()
        data, source, provenance = self.installer.recovery(record)
        with patch.object(self.installer, 'FIRMWARE_ONLY', False), contextlib.redirect_stdout(io.StringIO()):
            self.installer.install(data, 'disk9s7', source, provenance, restoring=True)
        self.assertEqual(self.target.read_bytes(), b'previous payload')
        for relative, content in self.previous_companions.items():
            self.assertEqual((self.mount/relative).read_bytes(), content)

    def test_partial_companion_failure_rolls_back_before_bootstrap_replacement(self):
        image, _ = self.firmware_fixture()
        real_replace = self.installer.os.replace
        failed = False
        def fail_media_once(source, target):
            nonlocal failed
            if Path(target) == self.mount/'J413Setup/MEDIA.json' and not failed:
                failed = True
                raise OSError('simulated companion write failure')
            return real_replace(source, target)
        with patch.object(self.installer.os, 'replace', side_effect=fail_media_once):
            with self.assertRaisesRegex(OSError, 'simulated companion'):
                self.update_firmware(image)
        self.assertEqual(self.target.read_bytes(), b'previous payload')
        for relative, content in self.previous_companions.items():
            self.assertEqual((self.mount/relative).read_bytes(), content)
        self.assertIn('prior bootstrap/companions restored', self.ledger.read_text())
        self.assertFalse(list(self.mount.rglob('.j413-update.*')))

    def test_changed_setup_refuses_firmware_update_and_corrupt_backup_refuses_restore(self):
        image, split = self.firmware_fixture()
        split.write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'Split Setup image changed'):
            self.update_firmware(image)
        self.assertEqual(self.target.read_bytes(), b'previous payload')
        for relative, content in self.previous_companions.items():
            self.assertEqual((self.mount/relative).read_bytes(), content)
        entries = self.installer.backup_companions(self.mount, self.root)
        record = {'companion_files': entries}
        self.installer.load_companions(self.root, record)
        (self.root/'companion-0.before').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.installer.load_companions(self.root, record)
