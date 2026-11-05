"""Same-volume file transaction tests; WIM subprocesses are simulated here."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import j413_setup_bundle as bundle


class SetupBundleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source, self.target, self.firmware = (self.root/name for name in ('source','target','firmware'))
        for directory in (self.source,self.target,self.firmware): directory.mkdir()
        pe = bytearray(256);pe[:2]=b'MZ';pe[60]=64;pe[64:68]=b'PE\0\0'
        struct.pack_into('<H',pe,68,0xaa64);struct.pack_into('<H',pe,88,0x20b);struct.pack_into('<H',pe,156,10)
        wim=bytearray(208);wim[:8]=b'MSWIM\0\0\0';wim[8]=208
        data={'efi/boot/bootaa64.efi':bytes(pe),'efi/microsoft/boot/bcd':b'regf'+bytes(4092),
              'sources/boot.wim':bytes(wim),'sources/install.wim':bytes(wim),
              'boot/boot.sdi':b'$SDI0001'+bytes(504),'setup.exe':bytes(pe),
              'autounattend.xml':b'private settings','Drivers/unsafe.inf':b'not qualified',
              'sources/unattend.xml':b'private settings'}
        for rel,value in data.items():
            path=self.source/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)
        (self.firmware/'boot.bin').write_bytes(b'candidate')
        (self.firmware/'J413_EFI.fd').write_bytes(b'firmware')
        self.identity='12345678-9ABC-4DEF-8123-456789ABCDEF'
        self.manifest={'direct_setup':{'mode':'single-gpt-volume','partition_uuid':self.identity}}
        (self.firmware/'MANIFEST.json').write_text(json.dumps(self.manifest))
        self.commands=[];self.arch='12'

    def wim(self, arguments):
        self.commands.append(arguments)
        if arguments[0]=='info':
            return ('<WIM><IMAGE INDEX="1"><NAME>test</NAME><WINDOWS><ARCH>'+self.arch+'</ARCH></WINDOWS></IMAGE></WIM>').encode()
        if arguments[0]=='split':
            Path(arguments[2]).write_bytes(b'split fixture')
            return b'ok'
        self.assertEqual(arguments[0],'verify')
        return b'ok'

    def perform(self):
        return bundle.stage(self.source,self.target,self.firmware,self.manifest,self.identity,runner=self.wim)

    def test_complete_sources_bootstrap_and_verified_split_share_one_destination(self):
        result=self.perform()
        self.assertEqual((self.target/'m1n1/boot.bin').read_bytes(),b'candidate')
        self.assertTrue((self.target/'sources/install.swm').is_file())
        self.assertFalse((self.target/'sources/install.wim').exists())
        self.assertFalse((self.target/'autounattend.xml').exists())
        self.assertFalse((self.target/'sources/unattend.xml').exists())
        self.assertFalse((self.target/'Drivers').exists())
        self.assertEqual(result['partition_uuid'],self.identity)
        self.assertFalse(result['native_boot_qualified'])
        self.assertFalse(result['driver_status']['all_requested_drivers_complete'])
        self.assertEqual(len([c for c in self.commands if c[0]=='verify']),2)

    def test_wrong_target_or_architecture_is_rejected_before_any_copy(self):
        self.manifest['direct_setup']['partition_uuid']='other'
        with self.assertRaisesRegex(ValueError,'another Setup partition'):self.perform()
        self.assertEqual(list(self.target.iterdir()),[])
        self.manifest['direct_setup']['partition_uuid']=self.identity;self.arch='9'
        with self.assertRaisesRegex(ValueError,'ARM64'):self.perform()
        self.assertEqual(list(self.target.iterdir()),[])

    def test_existing_different_bootstrap_is_preserved_before_copy(self):
        (self.target/'m1n1').mkdir();path=self.target/'m1n1/boot.bin';path.write_bytes(b'old bootstrap')
        with self.assertRaisesRegex(ValueError,'Existing target differs'):self.perform()
        self.assertEqual(path.read_bytes(),b'old bootstrap')
        self.assertFalse((self.target/'efi').exists())

    def test_copy_does_not_remove_another_creators_file_or_leave_an_empty_file_on_source_error(self):
        source=self.root/'data';source.write_bytes(b'source');destination=self.root/'copied'
        original_open=Path.open
        def race(path, mode='r', *args, **kwargs):
            if path==destination and mode=='xb':
                with original_open(path,'wb') as stream:stream.write(b'another creator')
                raise FileExistsError('race')
            return original_open(path,mode,*args,**kwargs)
        with patch.object(Path,'open',race):
            with self.assertRaises(FileExistsError):bundle.copy_checked(source,destination)
        self.assertEqual(destination.read_bytes(),b'another creator')
        destination.unlink();source.unlink()
        with self.assertRaises(FileNotFoundError):bundle.copy_checked(source,destination)
        self.assertFalse(destination.exists())

    def test_source_symlink_and_overlapping_destination_are_rejected(self):
        (self.source/'support').symlink_to(self.firmware,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlinks'):self.perform()
        with self.assertRaisesRegex(ValueError,'must differ'):
            bundle.stage(self.source,self.source,self.firmware,self.manifest,self.identity,runner=self.wim)
