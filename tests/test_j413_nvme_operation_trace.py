"""Apply the actual firmware patch and prove it only adds bounded init logging."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'MdeModulePkg/Bus/Pci/NvmExpressDxe/'


class NvmeOperationTraceTests(unittest.TestCase):
    def test_patch_preserves_every_original_operation_and_pairs_all_checkpoints(self):
        block = re.compile(
            rb'^#ifdef J413_BOOT_CONTRACT\r?\n'
            rb'[ \t]*DEBUG \(\(DEBUG_INFO, "J413 NVMe op: [^\r\n]*\r?\n'
            rb'#endif\r?\n', re.M)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            subprocess.run(['git', 'init', '-q', str(directory)], check=True)
            originals = {}
            for name in ('NvmExpress.c', 'NvmExpressHci.c'):
                original = subprocess.check_output(['git', '-C', str(ROOT/'mu/MU_BASECORE'),
                                                    'show', 'HEAD:'+PREFIX+name])
                target = directory/'MU_BASECORE'/PREFIX/name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(original)
                originals[name] = original
            subprocess.run(['git', '-C', str(directory), 'apply',
                            str(ROOT/'platforms/j413/mu-patches/j413-nvme-operation-trace.patch')], check=True)
            count = 0
            for name, original in originals.items():
                patched = (directory/'MU_BASECORE'/PREFIX/name).read_bytes()
                self.assertNotEqual(patched, original)
                # Exact byte equivalence after removing only the guarded DEBUG
                # statements proves no protocol call/control flow was altered.
                self.assertEqual(block.sub(b'', patched), original)
                entered = re.findall(rb'J413 NVMe op: ([^"\r\n]+) entered\\n', patched)
                returned = re.findall(rb'J413 NVMe op: ([^"\r\n]+) returned %[rp]\\n', patched)
                self.assertCountEqual(entered, returned)
                self.assertEqual(len(entered), len(set(entered)))
                count += len(entered)
            self.assertEqual(count, 29)
