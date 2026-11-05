"""One compile regression for the WDK/user CRT header boundary; no hardware."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DockChannelKernelHeaders(unittest.TestCase):
    def test_portable_cores_compile_without_user_crt_in_kernel_mode(self):
        compiler = shutil.which('clang')
        if not compiler:
            self.skipTest('clang is unavailable')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output/'ntddk.h').write_text('''#pragma once
 typedef unsigned char UCHAR;
 typedef unsigned short USHORT;
 typedef unsigned long ULONG;
 typedef unsigned long long ULONGLONG;
 typedef __SIZE_TYPE__ size_t;
 #define MAXULONG 0xffffffffu
 #define NULL ((void*)0)
 ''')
            for header in ('stdint.h','stddef.h'):
                (output/header).write_text('#error User CRT entered a kernel translation unit\n')
            for source in sorted((ROOT/'drivers/apple-dockchannel/core').glob('*.c')):
                subprocess.run([compiler,'--target=aarch64-pc-windows-msvc','-D_KERNEL_MODE=1',
                    '-nostdinc','-I'+directory,'-std=c11','-Wall','-Wextra','-Werror',
                    '-c',str(source),'-o',str(output/(source.stem+'.obj'))],check=True,capture_output=True)
