"""Bounded planning regression; all disk metadata is supplied in memory."""
import importlib.util
from pathlib import Path
import plistlib
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('provision',ROOT/'scripts/provision-j413-uefi.py')
provision=importlib.util.module_from_spec(spec);spec.loader.exec_module(provision)

class ProvisionBudget(unittest.TestCase):
    def test_resize_leaves_room_for_both_build_growth_and_the_macos_floor(self):
        store={'DeviceIdentifier':'disk0s2','DiskUUID':'STORE','ParentWholeDisk':'disk0','Content':'Apple_APFS','TotalSize':245107195904}
        disk={'DeviceIdentifier':'disk0','Internal':True,'VirtualOrPhysical':'Unknown','DeviceTreePath':'IODeviceTree:/arm-io/ans@0/controller','MediaName':'APPLE SSD','TotalSize':251000193024}
        source={'Internal':False,'FilesystemType':'exfat','DiskUUID':'SOURCE'}
        freed=store['TotalSize']-provision.TARGET_MACOS
        state={'remaining':34_000_000_000}
        def info(path):return {'/':{'APFSContainerReference':'disk4'},'disk0s2':store,'disk0':disk,'SOURCE':source}[str(path)]
        def run(*args):
            if args[0]=='sysctl':return b'Mac14,2\n'
            if args[1:3]==('apfs','list'):
                return plistlib.dumps({'Containers':[{'ContainerReference':'disk4','PhysicalStores':[{'DeviceIdentifier':'disk0s2'}],'CapacityFree':freed+state['remaining']}]})
            if args[1:3]==('apfs','resizeContainer'):return plistlib.dumps({'MinimumSizePreferred':220000000000})
            return plistlib.dumps({'AllDisksAndPartitions':[{'DeviceIdentifier':'disk0','Partitions':[{'Content':p} for p in ['Apple_APFS_ISC','Apple_APFS','Apple_APFS_Recovery']]}]})
        with patch.object(provision,'run',run),patch.object(provision,'info',info),patch.object(Path,'is_file',return_value=True):
            with self.assertRaisesRegex(ValueError,'build headroom'):provision.machine_plan(Path('SOURCE'))
            state['remaining']=40_000_000_000
            self.assertEqual(provision.machine_plan(Path('SOURCE'))['build_headroom'],8_000_000_000)
