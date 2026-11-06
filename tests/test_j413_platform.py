import json
from pathlib import Path
import struct
import shutil
from unittest.mock import patch
import subprocess
import tempfile
import unittest

from tools.collect_j413 import collect
from tools.j413_platform import ROOT, check_overlay, stage_overlay, stage_m1n1, overlay_sha256, require_current_firmware
from tools.artifact_manifest import create_manifest, verify_manifest, ManifestError


class J413PlatformTests(unittest.TestCase):
    def test_layout_and_firmware_contract(self):
        layout = check_overlay()
        self.assertEqual(layout.virtual_fb_size, 0x1040000)
        self.assertLessEqual(layout.virtual_fb_base + layout.virtual_fb_size, layout.ramdisk_base)
        self.assertEqual(layout.cpu_count, 8)
        source = (ROOT / "platforms/j413/mu/Platform/MacBookAirM2Pkg/AcpiTables/DSDT.asl").read_text()
        self.assertNotIn('Include ("J413AppleInput.asl.inc")', source)
        self.assertNotIn('"APPL0001"', source)
        resources = json.loads((ROOT / 'investigation/j413-macos-resources.json').read_text())
        self.assertEqual(resources['nodes']['uart0']['aic_irqs'], [739])
        self.assertIn('{ 739 }', source)
        self.assertNotIn('{ 1097 }', source)

    def test_inventory_drops_private_properties_and_preserves_raw_addresses(self):
        children = [{"name": n.encode(), "serial-number": b"PRIVATE",
                     "reg": struct.pack("<QQ", 0x82280000, 0x11800),
                     "interrupts": struct.pack("<I", 1112)}
                    for n in ["aic", "usb-drd1", "sgx", "gfx-asc", "dockchannel-mtp"]]
        children.append({"name": b"chosen", "chip-id": struct.pack("<I", 0x8112), "unique-chip-id": b"PRIVATE"})
        report = collect({"IORegistryEntryChildren": children})
        self.assertNotIn("PRIVATE", json.dumps(report))
        self.assertEqual(report["nodes"]["usb-drd1"]["aic_irqs"], [1112])
        self.assertEqual(report["nodes"]["usb-drd1"]["adt_reg_pairs"][0][0], "0x82280000")
        children[-1]["chip-id"] = struct.pack("<I", 0x8103)
        with self.assertRaisesRegex(ValueError, "not T8112"):
            collect({"IORegistryEntryChildren": children})

    def test_staging_is_idempotent_and_rejects_local_edits_before_copying(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            shutil.copytree(ROOT / "config", root / "config")
            shutil.copytree(ROOT / "platforms/j413", root / "platforms/j413")
            mu = root / "mu"
            subprocess.run(["git", "init", "-q", str(mu)], check=True)
            subprocess.run(["git", "-C", str(mu), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-qm", "fixture"], check=True)
            for relative in (
                'Silicon/Apple/T810XFamilyPkg/Library/MemoryInitPeiLib/MemoryInitPeiLib.c',
                'Silicon/Apple/T810XFamilyPkg/Library/MemoryInitPeiLib/MemoryInitPeiLib.inf',
                'Silicon/Apple/AppleSiliconPkg/PrePi/AArch64/ModuleEntryPoint.S',
                'Silicon/Apple/AppleSiliconPkg/Library/DeviceBootManagerLib/DeviceBootManagerLib.c',
                'Silicon/Apple/AppleSiliconPkg/Drivers/WindowsAutoBootDxe/WindowsAutoBootDxe.c',
                'Silicon/Apple/AppleSiliconPkg/Drivers/WindowsAutoBootDxe/WindowsAutoBootDxe.inf',
                'Silicon/Apple/AppleSiliconPkg/Drivers/SimpleFbDxe/SimpleFbDxe.c',
                'Silicon/Apple/AppleSiliconPkg/Library/DeviceBootManagerLib/DeviceBootManagerLib.inf',
                'Silicon/Apple/AppleSiliconPkg/Drivers/AppleUsbTypeCBringupDxe/AppleUsbTypeCBringupDxe.c',
                'Silicon/Apple/AppleSiliconPkg/Drivers/AppleDartIoMmuDxe/AppleDartIoMmuDxe.c',
                'Silicon/Apple/AppleSiliconPkg/Drivers/AppleUsbTypeCBringupDxe/AppleUsbTypeCBringupDxe.inf',
                'Silicon/Apple/AppleSiliconPkg/Drivers/AppleDartIoMmuDxe/AppleDartIoMmuDxe.inf',
                'Silicon/Apple/AppleSiliconPkg/Include/Drivers/AppleDartIoMmuDxe.h',
                'Silicon/Apple/AppleSiliconPkg/AppleSiliconPkg.dec',
                'Silicon/Apple/AppleSiliconPkg/AppleSiliconPkg.dsc.inc',

            ):
                destination=mu/relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(subprocess.check_output(['git','-C',str(ROOT/'mu'),'show','HEAD:'+relative]))
            subprocess.run(['git','-C',str(mu),'add','.'],check=True)
            subprocess.run(['git','-C',str(mu),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','pinned sources'],check=True)
            revision = subprocess.check_output(["git", "-C", str(mu), "rev-parse", "HEAD"], text=True).strip()
            files = sorted(p for p in (root / "platforms/j413/mu").rglob("*") if p.is_file())
            last = mu / files[-1].relative_to(root / "platforms/j413/mu")
            last.parent.mkdir(parents=True)
            last.write_text("developer-edits")
            with patch("tools.j413_platform.MU_REVISION", revision):
                with self.assertRaisesRegex(ValueError, "local edits"):
                    stage_overlay(root)
                first = mu / files[0].relative_to(root / "platforms/j413/mu")
                self.assertFalse(first.exists())
                last.unlink()
                upstream=mu/'Silicon/Apple/T810XFamilyPkg/Library/MemoryInitPeiLib/MemoryInitPeiLib.c'
                original=upstream.read_bytes()
                upstream.write_bytes(b'developer-source-edits')
                with self.assertRaisesRegex(ValueError, 'Mu patch conflicts'):
                    stage_overlay(root)
                self.assertFalse(first.exists())
                upstream.write_bytes(original)
                stage_overlay(root)
                stage_overlay(root)
                self.assertEqual(first.read_bytes(), files[0].read_bytes())
                subprocess.run(["git", "-C", str(mu), "add", "--", first.relative_to(mu).as_posix()], check=True)
                with self.assertRaisesRegex(ValueError, "overwrite upstream source"):
                    stage_overlay(root)

    def test_firmware_reuse_rejects_changed_patch_source(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            overlay=root/'platforms/j413/mu'
            overlay.mkdir(parents=True)
            (overlay/'test.c').write_text('initial source')
            manifest={'platform_overlay_sha256':overlay_sha256(root)}
            require_current_firmware(manifest,root)
            patches=root/'platforms/j413/mu-patches'
            patches.mkdir()
            (patches/'fix.patch').write_text('corrected source')
            with self.assertRaisesRegex(ValueError,'rebuild Mu'):
                require_current_firmware(manifest,root)
            manifest['platform_overlay_sha256']=overlay_sha256(root)
            require_current_firmware(manifest,root)
            (patches/'fix.patch').write_text('another correction')
            with self.assertRaisesRegex(ValueError,'rebuild Mu'):
                require_current_firmware(manifest,root)

    def test_manifest_does_not_label_m2_firmware_as_m1(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "config").mkdir()
            (root / "config/j413-guest-layout.json").write_bytes((ROOT / "config/j413-guest-layout.json").read_bytes())
            overlay = root / "platforms/j413/mu"
            overlay.mkdir(parents=True)
            (overlay / "fixture.dsc").write_text("test-source")
            subprocess.run(["git", "-C", str(root), "add", "config"], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"], check=True)
            out = root / "dist"
            out.mkdir()
            (out / "J413_EFI.fd").write_bytes(b"firmware-test-fixture")
            path = create_manifest(root, out, "debug", "physical", "uart", ["J413_EFI.fd"], compiler="test", platform="j413")
            data = verify_manifest(path, expected_platform="j413")
            self.assertEqual(data["guest_contract"]["virtual_fb_height"], 1664)
            self.assertEqual(data["artifacts"]["J413_EFI.fd"]["role"], "guest-firmware")
            self.assertEqual(len(data["platform_overlay_sha256"]), 64)
            # Boot provenance must include additive m1n1 sources, not merely
            # git diff of tracked submodule files or the Mu overlay.
            (out / "boot.bin").write_bytes(b"experimental-boot-fixture")
            m1n1_overlay = root / "platforms/j413/m1n1"
            m1n1_overlay.mkdir()
            (m1n1_overlay / "fixture.c").write_text("test-loader-source")
            path = create_manifest(root, out, "debug", "physical", "uart", ["J413_EFI.fd", "boot.bin"], compiler="test", platform="j413")
            data = verify_manifest(path, expected_platform="j413")
            self.assertEqual(len(data["platform_m1n1_sources_sha256"]), 64)
            del data["platform_m1n1_sources_sha256"]
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ManifestError, "boot source provenance"):
                verify_manifest(path)
            path = create_manifest(root, out, "debug", "physical", "uart", ["J413_EFI.fd"], compiler="test", platform="j413")
            data = verify_manifest(path)
            with self.assertRaisesRegex(ManifestError, "platform mismatch"):
                verify_manifest(path, expected_platform="j313")
            data["platform"] = "j313"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ManifestError, "guest contract mismatch"):
                verify_manifest(path)
            with self.assertRaisesRegex(ManifestError, "no hardware-qualified release"):
                create_manifest(root, out, "release", "physical", "off", ["J413_EFI.fd"], compiler="test", platform="j413")


if __name__ == "__main__":
    unittest.main()
