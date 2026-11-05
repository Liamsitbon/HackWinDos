# J413 USB1 host PHY role correction

Photo IMG_6312 shows one xHCI host protocol but zero USB interfaces, and only the built-in virtual disk filesystem. This narrows the failure before media/path discovery. The operator explicitly tested USB1. The current macOS USB0 connection is a distinct observation, not the diagnosis of that test.

Primary-source order inspected: fresh `2026-11-04-j413-live-resources.json` and sanitized IORegistry ancestry; Asahi T8112 DTS USB1 core/PHY resources; Linux `drivers/usb/dwc3/dwc3-apple.c` lines 207–255 (USB2 mode configured before core startup) and `drivers/phy/apple/atc.c` USB2PHY_SIG and `atcphy_usb2_set_mode` (HOST selects bits 14:12, DEVICE clears them); local pinned m1n1 `usb.c`, `usb_dwc3.c`, `hv_autonomous_boot_runtime.c`, `hv.c`; Mu DWC3 core reset/mode, DART ownership, generic xHCI/UsbBus initialization and polling; generated J413 ACPI; Microsoft USB host driver stack documentation. Compared J313 assisted legacy USB handoff in documentation/DEBUGGING.md and J413 EXP028–034/IMG_6312. No imported implementation code.

References:
- https://raw.githubusercontent.com/AsahiLinux/linux/asahi/arch/arm64/boot/dts/apple/t8112.dtsi
- https://raw.githubusercontent.com/AsahiLinux/linux/asahi/drivers/usb/dwc3/dwc3-apple.c
- https://raw.githubusercontent.com/AsahiLinux/linux/asahi/drivers/phy/apple/atc.c
- https://raw.githubusercontent.com/AsahiLinux/m1n1/main/src/usb.c
- https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/usb-3-0-driver-stack-architecture

Observed software defect: m1n1 always writes USB2 PHY SIG `0x01c1000f`. Its role bits are `0x1000`, while the source-defined host role mask is `0x7000`. Mu sets DWC3 host mode but never changes the external USB2 PHY role. Asahi's Linux glue explicitly establishes the matching PHY role before core startup. Hardware causality for IMG_6312 remains a hypothesis until an exact new candidate is run.

Ownership: m1n1 owns platform power/PHY and guest state; Mu owns preboot DART bypass, DWC3/xHCI initialization, device enumeration, media access and BDS; Windows inbox USBXHCI owns runtime USB after ExitBootServices. Interrupt/DMA/clock/reset sequencing remains with those owning layers. No Windows driver workaround.

Smallest change: set the three documented USB2 host role bits in the existing first SIG write, for USB1 only in J413+M1N1_NO_PROXY builds. Preserve existing power/reset sequence, delays, dummy PIPE backend and USB2-only preboot mode. No guessed registers. USB0 and legacy/proxy builds keep prior behavior. Do not conflate support for USB0 with resolving USB1's observed failure.

Regression: execute the actual PHY bringup under mocked power/MMIO across build profiles and indices; assert exact SIG value and ordering, unchanged other registers, and no MMIO after resource/power failures. First run the test against the old function to demonstrate failure. Rebuild both stages with unchanged Mu for an isolated host-role candidate; keep manifests and previous artifacts.

Falsifiable hardware checkpoint: exact manifested candidate in USB1 detects at least one UsbIo child and physical storage filesystem, then selects only EFI/BOOT/BOOTAA64.EFI. Failure: host present with zero children or no PHY role readback; next measurement is root-port state and PHY role before adding resets. Recovery: preserved previous candidate and existing macOS startup picker; exact currently installed ESP still cannot be read without operator privileges. No install or reboot is performed by software verification.

USB0 support and late filesystem selection are separate follow-on changes, deferred from this experiment. The source's Mu UsbRootHubInit already waits for six 100ms polls; adding an arbitrary sleep is not justified by the photo.

## Software result

Implementation commit 5268aa8 (full hash in CHANGES.csv). Actual old-body regression failed, new role/profile/order/resource/power/readback cases pass under fatal ASan/UBSan. All 46 J413 tests ran: 45 pass, one skip. Full suite 1561 tests: 91 failures, 55 errors, 42 skips; no new failure headers versus the earlier recorded baseline. This is not a global green result. Machine-readable details: 2026-11-04-usb1-role-results.json.

Both ARM64 stages rebuilt using J413_SKIP_MU=1 scripts/build-j413-boot-experiment.sh. Mu FD is byte-identical to EXP033. Current source digest, exact install identity, nested CRC/flags and manifest checks pass. Candidate `dist/j413/boot-experiment/boot.bin` SHA256 `910192421b2292b9a8b7531d645295a52e6bb36c5c5a5878c9ddb6cd93f1f4a9`, size 2538660. Complete source profile/IDs in adjacent MANIFEST.json. Preserved preceding candidate under `.local/recovery-20261104-before-usb1-role`. No ESP write, USB-media modification, reboot or guest launch. No direct live MMIO measurements; new PHY diagnostic will only be observed after an operator run.

Expected new line: `USB1: preboot host PHY SIG requested=0x1c1700f readback=0x1c1700f`. Then require a nonzero USB interface count and USB storage path, not the firmware VirtualDisk. If host bits match but no children appear, this host-role correction alone is insufficient; inspect root-port connection/control-transfer state before changing power/reset sequencing. GPU and USB0 are unchanged and unqualified.
