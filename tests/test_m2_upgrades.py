"""Unit tests for MacBook Air M2 (J413 / T8112) upgrades and integrations."""

import unittest
from pathlib import Path
import json

from tools.j413_cpufreq import (
    pcpu_pstate_command,
    requested_pstate,
    PCPU_MHZ,
    ECPU_MHZ,
    PCPU_MAX_NON_TURBO,
    ECPU_MAX_PSTATE,
)
from tools.artifact_manifest import (
    GUEST_CONTRACTS,
    J413_GUEST_CONTRACT,
    J313_GUEST_CONTRACT,
)
from guest_layout import load_layout

ROOT = Path(__file__).resolve().parents[1]


class M2UpgradesTests(unittest.TestCase):
    def test_m2_cpufreq_pstate_command_and_frequencies(self):
        # Validate P-cluster max non-turbo state (Level 12 -> 3480 MHz)
        self.assertEqual(PCPU_MHZ[12], 3480)
        self.assertEqual(PCPU_MAX_NON_TURBO, 12)

        # Validate E-cluster max state (Level 7 -> 2424 MHz)
        self.assertEqual(ECPU_MHZ[7], 2424)
        self.assertEqual(ECPU_MAX_PSTATE, 7)

        # Test command word encoding for level 12
        cmd = pcpu_pstate_command(0, 12)
        self.assertEqual(requested_pstate(cmd), 12)
        self.assertTrue(cmd & (1 << 25))  # PSTATE_SET bit must be set

        # Invalid p-state should raise ValueError
        with self.assertRaises(ValueError):
            pcpu_pstate_command(0, 13)
        with self.assertRaises(ValueError):
            pcpu_pstate_command(0, 0)

    def test_j413_guest_layout_resolution_and_geometry(self):
        layout_path = ROOT / "config" / "j413-guest-layout.json"
        self.assertTrue(layout_path.exists())

        layout = load_layout(layout_path)
        self.assertEqual(layout.virtual_fb_width, 2560)
        self.assertEqual(layout.virtual_fb_height, 1664)
        self.assertEqual(layout.virtual_fb_stride, 10240)
        self.assertEqual(layout.virtual_fb_base, 0x85E000000)
        self.assertEqual(layout.cpu_count, 8)
        self.assertEqual(layout.virtual_fb_size, 2560 * 1664 * 4)

    def test_artifact_manifest_contracts_include_j413(self):
        self.assertIn("j413", GUEST_CONTRACTS)
        self.assertIn("j313", GUEST_CONTRACTS)
        self.assertEqual(J413_GUEST_CONTRACT["virtual_fb_height"], 1664)
        self.assertEqual(J313_GUEST_CONTRACT["virtual_fb_height"], 1600)

    def test_apple_agx_g14g_definitions(self):
        header_path = ROOT / "drivers/apple-agx/shared/include/apple_agx_win32_device_info.h"
        self.assertTrue(header_path.exists())
        header = header_path.read_text(encoding="utf-8")
        self.assertIn("AgxWin32GpuG14G", header)

        scanout_path = ROOT / "drivers/apple-agx/shared/include/apple_agx_scanout.h"
        self.assertTrue(scanout_path.exists())
        scanout = scanout_path.read_text(encoding="utf-8")
        self.assertIn("APPLE_AGX_SCANOUT_J413_HEIGHT 1664u", scanout)
        self.assertIn("APPLE_AGX_SCANOUT_J413_SURFACE_SIZE 0x1040000ULL", scanout)

    def test_apple_dockchannel_windows_driver_files_exist(self):
        driver_dir = ROOT / "drivers/apple-dockchannel/windows"
        self.assertTrue((driver_dir / "AppleDockChannel.inf").exists())
        self.assertTrue((driver_dir / "AppleDockChannel.vcxproj").exists())
        self.assertTrue((driver_dir / "include/dockchannel_windows.h").exists())
        self.assertTrue((driver_dir / "src/driver.c").exists())
        self.assertTrue((driver_dir / "src/device.c").exists())
        self.assertTrue((driver_dir / "src/vhf_bridge.c").exists())

    def test_j413_dsdt_includes_agx_and_dockchannel(self):
        dsdt_path = ROOT / "platforms/j413/mu/Platform/MacBookAirM2Pkg/AcpiTables/DSDT.asl"
        self.assertTrue(dsdt_path.exists())
        dsdt = dsdt_path.read_text(encoding="utf-8")
        self.assertIn('Name (_HID, "APPL0002")', dsdt)  # AGX GPU
        self.assertIn('Name (_HID, "APPL0008")', dsdt)  # DockChannel Input
        self.assertIn('0x0000000204000000', dsdt)       # M2 SGX MMIO base


if __name__ == "__main__":
    unittest.main()
