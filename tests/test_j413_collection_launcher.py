"""The non-root launcher exposes collector output without capturing authentication."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class CollectionLauncherTests(unittest.TestCase):
    def test_caller_owns_output_auth_is_not_logged_and_collector_status_survives(self):
        if os.geteuid()==0:self.skipTest('Launcher intentionally refuses root callers')
        for status in (0,7):
            with self.subTest(status=status),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);(root/'scripts').mkdir();(root/'bin').mkdir()
                launcher=root/'scripts/collect-j413-usb.command'
                launcher.write_bytes((ROOT/'scripts/collect-j413-usb.command').read_bytes())
                fake=root/'bin/sudo'
                fake.write_text('#!/bin/bash\nif [ "$1" = -v ]; then echo AUTH_ONLY >&2; exit 0; fi\n'
                                '[ "$1" = -n ] || exit 90\n'
                                '[ "$2" = /usr/bin/python3 ] || exit 91\n'
                                '[ "$4" = --collect-only ] || exit 92\n'
                                'echo "USB boot connection: Not Found"\nexit '+str(status)+'\n')
                fake.chmod(0o755)
                env=dict(os.environ,PATH=str(root/'bin')+':'+os.environ['PATH'])
                result=subprocess.run(['/bin/bash',str(launcher)],env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,status,result.stderr)
                latest=json.loads((root/'.local/usb-evidence/LATEST.json').read_text())
                log=Path(latest['log'])
                self.assertEqual(latest['exit_code'],status)
                self.assertEqual(log.read_text(),'USB boot connection: Not Found\n')
                self.assertNotIn('AUTH_ONLY',log.read_text())
                self.assertIn('AUTH_ONLY',result.stderr)
                self.assertEqual(log.stat().st_uid,os.getuid())
                self.assertEqual(log.stat().st_mode & 0o777,0o600)
