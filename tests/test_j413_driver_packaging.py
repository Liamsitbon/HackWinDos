"""A package needs real ARM64 binaries; an INF-only tree must never look ready."""
from pathlib import Path
import json
import shutil
import struct
import subprocess
import tempfile
import unittest

from tools import package_j413_drivers as drivers

ROOT = Path(__file__).resolve().parents[1]


class DriverPackagingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.inputs = self.root/'input'
        self.output = self.root/'output'

    def fixture(self, name='AppleDockChannel', machine=0xaa64, subsystem=1):
        path = self.inputs/name
        path.mkdir(parents=True)
        hardware = 'APPL0008' if name == 'AppleDockChannel' else 'APPL0002'
        (path/(name+'.inf')).write_text('[Models.NTarm64]\nDevice=Install,ACPI\\'+hardware+'\n')
        data = bytearray(256)
        data[:2] = b'MZ'; data[60] = 64; data[64:68] = b'PE\0\0'
        struct.pack_into('<H', data, 68, machine)
        struct.pack_into('<H', data, 88, 0x20b)
        struct.pack_into('<H', data, 156, subsystem)
        (path/(name+'.sys')).write_bytes(data)
        (path/(name+'.cat')).write_bytes(b'test fixture, not a signed catalog')
        return path

    def test_inf_only_is_not_a_package_and_does_not_mutate_output(self):
        path = self.fixture()
        (path/'AppleDockChannel.sys').unlink()
        report = drivers.audit(self.inputs)
        self.assertFalse(report['packages']['AppleDockChannel']['complete_binary_package'])
        with self.assertRaisesRegex(ValueError, 'No complete ARM64'):
            drivers.package(self.inputs, self.output)
        self.assertFalse(self.output.exists())

    def test_wrong_architecture_or_efi_application_and_empty_catalog_are_rejected(self):
        path = self.fixture(machine=0x8664)
        self.assertFalse(drivers.audit(self.inputs)['packages']['AppleDockChannel']['complete_binary_package'])
        data = bytearray((path/'AppleDockChannel.sys').read_bytes())
        struct.pack_into('<H', data, 68, 0xaa64); struct.pack_into('<H', data, 156, 10)
        (path/'AppleDockChannel.sys').write_bytes(data)
        self.assertFalse(drivers.audit(self.inputs)['packages']['AppleDockChannel']['complete_binary_package'])
        struct.pack_into('<H', data, 156, 1); (path/'AppleDockChannel.sys').write_bytes(data)
        (path/'AppleDockChannel.cat').write_bytes(b'')
        self.assertFalse(drivers.audit(self.inputs)['packages']['AppleDockChannel']['complete_binary_package'])

    def test_complete_bytes_preserved_and_never_claim_hardware_or_all_drivers(self):
        path = self.fixture()
        report = drivers.package(self.inputs, self.output)
        for file in path.iterdir():
            self.assertEqual(file.read_bytes(), (self.output/'AppleDockChannel'/file.name).read_bytes())
        saved = json.loads((self.output/'MANIFEST.json').read_text())
        self.assertFalse(saved['runtime_qualified'])
        self.assertFalse(saved['all_requested_drivers_complete'])
        self.assertIn('wifi', saved['missing_native_implementations'])
        self.assertIn('AppleInput', saved['excluded'])
        self.assertNotIn('AppleInput', saved['packages'])
        self.assertTrue((self.output/'install-drivers.ps1').is_file())
        with self.assertRaisesRegex(ValueError, 'Output already exists'):
            drivers.package(self.inputs, self.output)

    def test_actual_wrapper_cannot_publish_inf_only_sources_as_ready(self):
        # Keep both the legacy and corrected wrapper's derived ROOT isolated.
        (self.root/'scripts').mkdir(); (self.root/'tools').mkdir()
        for file in ['scripts/package-m2-drivers.sh', 'tools/package_j413_drivers.py']:
            shutil.copyfile(ROOT/file, self.root/file)
        for directory, name in [('apple-agx','AppleAgx'), ('apple-input','AppleInput'), ('apple-dockchannel','AppleDockChannel')]:
            path = self.root/'drivers'/directory/'windows'; path.mkdir(parents=True)
            (path/(name+'.inf')).write_text('INF metadata only')
        result = subprocess.run(['sh', str(self.root/'scripts/package-m2-drivers.sh')], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root/'dist/m2-windows-drivers').exists())
        self.assertNotIn('Driver package ready', result.stdout)

    def test_powershell_installer_verifies_hashes_and_rejects_tampering_without_pnp(self):
        pwsh = shutil.which('pwsh')
        if not pwsh:
            self.skipTest('PowerShell is unavailable')
        self.fixture()
        drivers.package(self.inputs, self.output)
        command = [pwsh, '-NoProfile', '-File', str(self.output/'install-drivers.ps1'), '-VerifyOnly']
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('no PnP action', result.stdout)
        (self.output/'AppleDockChannel/AppleDockChannel.sys').write_bytes(b'tampered')
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Hash mismatch', result.stderr)
