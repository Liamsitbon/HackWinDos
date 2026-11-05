"""Verify completion of a partial FAT WinPE volume without replacing prior files."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('usb_media_completion', ROOT/'scripts/complete-j413-usb-media.py')
media = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(media)


class UsbMediaCompletionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source, self.target = self.root/'source', self.root/'target'
        pe = bytearray(256)
        pe[:2] = b'MZ'; pe[60] = 64; pe[64:68] = b'PE\0\0'
        pe[68:70] = b'\x64\xaa'; pe[88:90] = b'\x0b\x02'; pe[156] = 10
        wim = bytearray(208); wim[:8] = b'MSWIM\0\0\0'; wim[8] = 208
        files = [bytes(pe), b'regf'+bytes(4092), bytes(wim), b'$SDI0001'+bytes(504)]
        hashes = {}
        for rel, data in zip(media.HASHES, files):
            path = self.source/rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
            hashes[rel] = hashlib.sha256(data).hexdigest()
            if rel not in media.PAYLOADS:
                path = self.target/rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        self.ledger = self.root/'EXPERIMENTS.md'
        self.ledger.write_text('prior evidence\n')
        for name, value in [('ROOT', self.root), ('HASHES', hashes), ('LEDGER', self.ledger), ('RECORDS', self.root/'records')]:
            p = patch.object(media, name, value); p.start(); self.addCleanup(p.stop)
        p = patch.object(media.subprocess, 'check_output', side_effect=lambda *a, **k: 'a'*40 if k.get('text') else b'a'*40)
        p.start(); self.addCleanup(p.stop)

    def perform(self):
        missing = media.plan(self.source, self.target)
        with contextlib.redirect_stdout(io.StringIO()):
            media.complete(self.source, self.target, missing)

    def test_missing_ramdisk_payloads_are_detected_copied_verified_and_idempotent(self):
        self.assertEqual(len(media.inspect(self.target)['errors']), 2)
        prior = {p: p.read_bytes() for p in self.target.rglob('*') if p.is_file()}
        self.assertEqual(media.plan(self.source, self.target), list(media.PAYLOADS))
        self.perform()
        self.assertFalse(media.inspect(self.target)['errors'])
        self.assertEqual(media.plan(self.source, self.target), [])
        for path, data in prior.items():
            self.assertEqual(path.read_bytes(), data)
        for rel in media.PAYLOADS:
            self.assertEqual((self.target/rel).read_bytes(), (self.source/rel).read_bytes())
        manifest = json.loads(next(media.RECORDS.glob('*/MANIFEST.json')).read_text())
        self.assertEqual(manifest['originally_absent'], list(media.PAYLOADS))
        self.assertIn('Before ', self.ledger.read_text())
        self.assertIn('physical boot inconclusive', self.ledger.read_text())

    def test_existing_different_file_and_changed_source_are_never_overwritten(self):
        path = self.target/media.PAYLOADS[0]
        path.parent.mkdir(); path.write_bytes(b'authored data')
        with self.assertRaisesRegex(ValueError, 'refusing to overwrite'):
            media.plan(self.source, self.target)
        self.assertEqual(path.read_bytes(), b'authored data')
        path.unlink()
        (self.source/'boot/boot.sdi').write_bytes(b'changed source')
        with self.assertRaisesRegex(ValueError, 'four ARM64 WinPE'):
            media.plan(self.source, self.target)
        self.assertFalse(media.RECORDS.exists())

    def test_copy_failure_removes_partial_new_file_and_preserves_original_loader(self):
        loader = self.target/'efi/boot/bootaa64.efi'
        before = loader.read_bytes()
        def fail_copy(src, dst, size):
            dst.write(b'partial')
            raise OSError('simulated USB disconnect')
        with patch.object(media.shutil, 'copyfileobj', side_effect=fail_copy):
            with self.assertRaisesRegex(OSError, 'disconnect'):
                self.perform()
        self.assertEqual(loader.read_bytes(), before)
        self.assertFalse((self.target/media.PAYLOADS[0]).exists())
        self.assertIn('prior files untouched', self.ledger.read_text())

    def test_partition_resolution_rejects_internal_media_and_mismatched_physical_disk(self):
        parts = [{'DiskUUID': media.SOURCE_UUID, 'DeviceIdentifier': 'disk8s3'},
                 {'DiskUUID': media.TARGET_UUID, 'DeviceIdentifier': 'disk8s2'}]
        infos = {'disk8s3': {'DiskUUID': media.SOURCE_UUID, 'Internal': False, 'FilesystemType': 'exfat', 'MountPoint': str(self.source), 'ParentWholeDisk': 'disk8'},
                 'disk8s2': {'DiskUUID': media.TARGET_UUID, 'Internal': False, 'FilesystemType': 'msdos', 'MountPoint': str(self.target), 'ParentWholeDisk': 'disk8'}}
        def query(*args):
            if args == ('list', '-plist'):
                return {'AllDisksAndPartitions': [{'Partitions': parts}]}
            self.assertEqual(args[:2], ('info', '-plist'))
            return infos[args[2]]
        with patch.object(media, 'query', side_effect=query):
            self.assertEqual(media.media(), (self.source, self.target))
            infos['disk8s2']['ParentWholeDisk'] = 'disk9'
            with self.assertRaisesRegex(ValueError, 'same SanDisk'):
                media.media()
            infos['disk8s2']['Internal'] = True
            with self.assertRaisesRegex(ValueError, 'identity/filesystem/mount'):
                media.media()
