"""Verify explicit target generation, edit preservation and manifest binding."""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest

from tools.j413_direct_setup import RELATIVE, configure, render, target_uuid
from tools.artifact_manifest import create_manifest, verify_manifest, ManifestError

ROOT = Path(__file__).resolve().parents[1]


class DirectTargetTests(unittest.TestCase):
    def test_canonical_target_matches_generated_guid_and_preserves_local_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = '12345678-9abc-4def-8123-456789abcdef'
            self.assertEqual(configure(first, root), first.upper())
            source, destination = root/'platforms/j413/mu'/RELATIVE, root/'mu'/RELATIVE
            destination.parent.mkdir(parents=True)
            shutil.copyfile(source, destination)
            second = '87654321-9abc-4def-8123-456789abcdef'
            self.assertEqual(configure(second, root), second.upper())
            self.assertEqual(source.read_bytes(), destination.read_bytes())
            old = source.read_bytes(); destination.write_text('developer edits')
            with self.assertRaisesRegex(ValueError, 'local edits'):
                configure(first, root)
            self.assertEqual(source.read_bytes(), old)
            source.write_text(source.read_text().replace('0x87654321', '0x87654322'))
            with self.assertRaisesRegex(ValueError, 'inconsistent'):
                target_uuid(root)
        for value in ['00000000-0000-0000-0000-000000000000', 'not a UUID']:
            with self.assertRaises(ValueError):
                render(value)

    def test_manifest_carries_and_validates_the_same_partition_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git','init','-q',str(root)],check=True)
            (root/'config').mkdir()
            shutil.copyfile(ROOT/'config/j413-guest-layout.json',root/'config/j413-guest-layout.json')
            subprocess.run(['git','-C',str(root),'add','config'],check=True)
            subprocess.run(['git','-C',str(root),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','fixture'],check=True)
            identity = configure('12345678-9abc-4def-8123-456789abcdef',root)
            out = root/'dist';out.mkdir();(out/'J413_EFI.fd').write_bytes(b'manifest-only fixture')
            manifest = create_manifest(root,out,'debug','physical','off',['J413_EFI.fd'],compiler='test',platform='j413')
            data = verify_manifest(manifest,expected_platform='j413')
            self.assertEqual(data['direct_setup']['partition_uuid'],identity)
            self.assertEqual(data['direct_setup']['mode'],'single-gpt-volume')
            data['direct_setup']['partition_uuid'] = '00000000-0000-0000-0000-000000000000'
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ManifestError,'direct Setup target'):
                verify_manifest(manifest)
