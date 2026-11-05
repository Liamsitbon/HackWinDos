# Current result

**Not qualified for 100% working native USB/Windows boot.** The last physical trial, EXP-20261104-J413-037, did not enumerate a usable USB boot volume. The new image has not been launched. The operator has since deleted the internal Asahi/UEFI bootstrap; current diskutil metadata confirms its absence. No internal installation, partition creation, boot-policy enrollment or reboot was performed in this verification turn.

## Implemented and checked

- Resolve only `\EFI\BOOT\BOOTAA64.EFI` on every readable SimpleFS, independently of filename case. Resolve just the three named components if canonical Open fails. Never recurse into arbitrary EFI applications.
- Require the actual file header to be AA64, PE32+ and EFI application; standard BDS LoadImage still performs final validation/security.
- Recheck an empty initial filesystem snapshot using application-level event timers for up to 10 seconds, at 200ms intervals. Tests execute the actual scanner while a filesystem appears after three waits.
- On failure, show protocol inventory, UsbBus binding and read-only BAR-bounded xHCI/validated live ADT PHY values for 30 seconds. No new PHY/reset/clock/DMA/IRQ setup. This diagnostic path still needs hardware observation.
- Completed only absent `sources/boot.wim` and `boot/boot.sdi` on the connected M2BOOT FAT partition. Full SHA256 readback and both partitions' four-payload header preflight pass. Existing loader, BCD and m1n1 files were retained. Transaction: EXP-20261105T120605Z-USB-MEDIA-d9d9cb60.
- Full source WIM integrity verification passes. All eight external-media EFI files have AA64 headers. Extracted WinPE `winload.efi` and `ntoskrnl.exe` also have AA64 headers. This does not prove their operation on Apple hardware.

## Build and test identity

`dist/j413/boot-experiment/boot.bin`: 2,541,096 bytes, SHA256 `817b006fb1f5c9c23140dba3410ca2a6caa01fa0b3c73bb590324682289cc4ed`. Full ARM64 Mu and both no-proxy m1n1 stages built; 98 EFI images passed the firmware image checker; linked PrePi guard, nested CRC/profile/image/manifests and current source digests pass. Qualification remains experimental debug/physical/debug-off.

Latest J413 tests: **68 passed, one skipped (69 total)**. Full checkout run: **1,583 tests; 91 failures, 55 errors, 42 skips**. Its failure-header set matches the preceding baseline exactly. Most failures concern other GPU/legacy contracts or missing fixture/dependency paths; they were not suppressed. The last installer-only option/help change is covered by its 15 focused tests; no second complete suite run is claimed. Machine-readable evidence is `2026-11-05-usb-boot-validation.json` and `2026-11-05-test-results.json`; execution logs remain local alongside them.

Fresh macOS link after reconnection: SanDisk VID 0781/PID 5595 is under USB1 at 5Gb/s, bcdUSB 0x0320. This differs from the previous capture at 480Mb/s with the USB2 descriptor. Prior USB2 operation shows fallback capability, but neither macOS link speed proves the Mu USB2-only bring-up works.

## Prepared scripts

- `scripts/complete-j413-usb-media.py`: pinned media identity/content, exclusive creation, never replaces an existing different file; rerun dry-run now reports no missing payloads.
- `scripts/install-j413-usb-discovery.py`: pinned new image, checked backup/restore and atomic ESP replacement; `--verify-only` does not require an installed ESP. A separately recreated ESP must be explicitly identified with `--esp-uuid`; the script never creates partitions or picks a random ESP.

Read-only image verification from this checkout:

```sh
/usr/bin/python3 scripts/install-j413-usb-discovery.py --verify-only
```

No deployment command is recommended as a claim of readiness. Future native validation requires restoring a bootable platform environment and measuring USB host/child/storage/filesystem, exact loader entry and the resulting Windows phase. GPU acceleration, USB runtime handoff after ExitBootServices, storage/input and multiprocessor operation are not qualified by this work. The internal bootstrap is a distinct prerequisite described in the [Asahi boot-chain documentation](https://asahilinux.org/docs/platform/open-os-interop/).
