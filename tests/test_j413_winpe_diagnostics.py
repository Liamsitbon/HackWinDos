"""Exercise diagnostic WIM replacement and rollback without hardware commands."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('winpe_installer', ROOT/'scripts/install-j413-winpe-diagnostics.py')
install = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(install)


class WinpeDiagnosticTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.mount=self.root/'ESP';self.output=self.root/'candidate'
        for name in ['sources','m1n1','J413Setup']:(self.mount/name).mkdir(parents=True)
        self.output.mkdir()
        self.old=b'original WIM';self.new=b'diagnostic WIM'
        (self.mount/'sources/boot.wim').write_bytes(self.old)
        (self.mount/'m1n1/boot.bin').write_bytes(b'unchanged bootstrap')
        self.metadata={'files':{'sources/boot.wim':{'size':len(self.old),'sha256':install.profile.sha(self.mount/'sources/boot.wim')}}}
        (self.mount/'J413Setup/MEDIA.json').write_text(json.dumps(self.metadata))
        (self.output/'boot.wim').write_bytes(self.new)
        self.manifest={'profile':'winpe-diagnostic','artifacts':{'boot.wim':{'size':len(self.new),'sha256':install.profile.sha(self.output/'boot.wim')}}}
        for obj,key,value in [(install,'BACKUPS',self.root/'backups'),
                              (install.profile,'OUT',self.output),
                              (install.profile,'SOURCE_SHA256',install.profile.sha(self.mount/'sources/boot.wim')),
                              (install.profile,'BOOTSTRAP_SHA256',install.profile.sha(self.mount/'m1n1/boot.bin'))]:
            p=patch.object(obj,key,value);p.start();self.addCleanup(p.stop)
        p=patch.object(install.base,'record');self.record=p.start();self.addCleanup(p.stop)
        for key,value in [('source_state',{'root':{'commit':'a'*40}}),
                          ('disk_info',{'DiskUUID':install.profile.ESP_UUID,'MountPoint':str(self.mount)}),
                          ('run',b''),('verify_same_volume',None)]:
            p=patch.object(install.base,key,return_value=value);p.start();self.addCleanup(p.stop)
        p=patch.object(install.subprocess,'run',return_value=subprocess.CompletedProcess([],0,b'mounted',b''))
        self.mount_command=p.start();self.addCleanup(p.stop)

    def perform(self):
        with contextlib.redirect_stdout(io.StringIO()):install.operate('disk9s4',self.manifest)

    def test_install_preserves_firmware_and_complete_restore_recovers_media(self):
        self.perform()
        self.assertEqual((self.mount/'sources/boot.wim').read_bytes(),self.new)
        self.assertEqual((self.mount/'m1n1/boot.bin').read_bytes(),b'unchanged bootstrap')
        self.assertTrue((self.mount/install.MARKER).exists())
        self.assertEqual(self.mount_command.call_args.args[0],['diskutil','mount','disk9s4'])
        record=next(install.BACKUPS.glob('*/RECOVERY.json'))
        install.restore_files(self.mount,record)
        self.assertEqual((self.mount/'sources/boot.wim').read_bytes(),self.old)
        self.assertEqual(json.loads((self.mount/'J413Setup/MEDIA.json').read_text()),self.metadata)
        self.assertFalse((self.mount/install.MARKER).exists())
        self.assertFalse((self.mount/'J413Setup/WINPE-DIAGNOSTICS.json').exists())

    def test_mid_update_failure_rolls_back_wim_and_metadata(self):
        atomic=install.base.atomic_file
        def fail_media(path,data):
            if path==self.mount/'J413Setup/MEDIA.json':raise OSError('simulated metadata write failure')
            return atomic(path,data)
        with patch.object(install.base,'atomic_file',side_effect=fail_media):
            with self.assertRaisesRegex(OSError,'simulated'):self.perform()
        self.assertEqual((self.mount/'sources/boot.wim').read_bytes(),self.old)
        self.assertEqual(json.loads((self.mount/'J413Setup/MEDIA.json').read_text()),self.metadata)
        self.assertFalse(list(self.mount.rglob('.j413-wim-*')))

    def test_corrupt_backup_refuses_restore_before_any_mutation(self):
        self.perform();record=next(install.BACKUPS.glob('*/RECOVERY.json'))
        (record.parent/'payload-0.before').write_bytes(b'corrupt backup')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):install.restore_files(self.mount,record)
        self.assertEqual((self.mount/'sources/boot.wim').read_bytes(),self.new)

    def test_collection_does_not_replace_media_and_requests_read_only_mount(self):
        with contextlib.redirect_stdout(io.StringIO()):install.operate('disk9s4',{},collect_only=True)
        self.assertEqual((self.mount/'sources/boot.wim').read_bytes(),self.old)
        self.assertEqual(self.mount_command.call_args.args[0],['diskutil','mount','readOnly','disk9s4'])
        self.assertFalse(list(install.BACKUPS.glob('*/RECOVERY.json')))
