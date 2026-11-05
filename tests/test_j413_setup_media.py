"""Windows dependency validation belongs to the selected loader, not firmware discovery."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class SetupMediaTests(unittest.TestCase):
 def test_no_setup_dependency_gate_or_general_efi_fallback(self):
  source=(ROOT/'mu/Silicon/Apple/AppleSiliconPkg/Drivers/WindowsAutoBootDxe/WindowsAutoBootDxe.c').read_text()
  a=source.index('STATIC EFI_STATUS EFIAPI GetJ413SetupOption(')
  b=source.index('STATIC J413_WINDOWS_SETUP mSetup',a)
  selector=source[a:b]
  self.assertNotIn('HasCompleteSetupMedia',selector)
  self.assertNotIn('gEfiBlockIoProtocolGuid',selector)
  self.assertNotIn('searching all EFI',selector)
