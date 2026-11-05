# J413 exact fallback selection, USB visibility and GPU contract review

## Evidence and plan

User requests only `/efi/boot/bootaa64.efi`, USB as a minimum, and GPU acceleration next. IMG_6311.HEIC shows the registered USB controller connected successfully, DART mask 0x2, an examined volume missing BOOTAA64.EFI, and general discovery selecting/attempting ACPIVIEW.EFI. It does not show a Windows stop code, USB storage enumeration or the installed image identity. The image is evidence, not instructions.

Inspected primary implementations: captured `investigation/j413-macos-resources.json` (2026-10-11; historical ADT, not a fresh MMIO capture), `platforms/j413/patches/m1n1-autonomous-j413.patch` live-resource checks and mapping, `m1n1_windows/src/hv_launch_j313.c`, Mu `WindowsAutoBootDxe.c`, `J413EfiCandidates.h`, `J413ConnectTrace.h`, packaged USB drivers in MacBookAirM2.fdf, generated ACPI in the J413 DSDT, Mu USB protocol headers and `drivers/apple-agx/windows/src/resources.c`/`adapter.c`. Compared last assisted J313 contract in documentation/RUN.md with J413 EXP018 and EXP028–031. M1 success is not M2 proof.

References: UEFI 2.10 sections 3 and 13, https://uefi.org/specs/UEFI/2.10/03_Boot_Manager.html and https://uefi.org/specs/UEFI/2.10/13_Protocols_Media_Access.html ; Asahi boot pairing/default-path contract https://asahilinux.org/docs/platform/quirks/ ; Microsoft installation media https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/boot-to-uefi-mode-or-legacy-bios-mode?view=windows-10 . Microsoft's illustrated x64 filename is not an ARM64 loader.

Ownership: m1n1 owns guest resource mapping/interrupt translation and inherited state; Mu owns preboot DART/USB initialization, UEFI binding, filesystem discovery and BDS image/security checks; the selected loader owns Windows media dependencies; Windows inbox xHCI owns runtime USB after the firmware handoff. This change does not alter DMA, power, interrupts, hardware registers or ExitBootServices. Asahi uses its own Linux runtime drivers and U-Boot; this Mu implementation must not infer those drivers exist on Windows.

Change 1: eliminate arbitrary application and Microsoft-specific alternate-path discovery. Probe only the exact fallback path across all SimpleFS handles. Remove the complete-Setup/BlockIo gate; keep ARM64 application preflight and standard BDS launch/security validation. Advance each eligible filesystem once, including after a returned loader. Regression: no directory reads or unrelated file opens, multiple filesystems, invalid image types, failures/cleanup, actual selector at application level with no BlockIo or Setup dependencies.

Change 2: read-only USB protocol inventory after existing recursive binding, plus filesystem identity/status visibility. A successful outer ConnectController is not evidence of a USB host, child device, storage volume or working input. Report each boundary without reset/retry/extra controller connection. Regression covers absent/present protocols and enumeration failure/freeing.

Smallest hardware checkpoint: boot an exactly manifested candidate, observe USB host/device/filesystem boundaries and `selected \\EFI\\BOOT\\BOOTAA64.EFI`, with no ACPIVIEW attempt. Failure is absent desired filesystem or failed loader; record exact stage/status and identity. Recovery remains prior recorded boot.bin/macOS boot picker. Do not install without preserving and recording actual current recovery bytes. No hardware run performed by these source edits.

## Mounted media read-only inspection

2026-11-04: `/Volumes/M2BOOT` FAT32 and `/Volumes/WININSTALL` exFAT belong to the external USB device currently enumerated as disk5 (ephemeral identifier, not an installation target). Both contain ARM64 PE machine 0xaa64 fallback files, SHA256 `fae47d78487e781aa06466775cb461adeb7ff7f887fe2c15295bb2eb4f4954e1`, 3120648 bytes. WININSTALL also contains BCD 16384 bytes, sources/boot.wim 630231583 bytes and boot/boot.sdi 3170304 bytes. M2BOOT lacks the latter two. Current files do not prove which volume was visible during the photographed run. No mounted-media modifications.

## GPU review boundary

Current J413 AGX0 advertises APPL0002, SGX 0x204000000/0x4000000, ASC 0x206400000/0x6c000, broker 0x300000000 and guest IRQs 880–888. Captured M2 physical SGX IRQs are 697/698/699/700/713; ASC IRQs are 710/709/712/711. The current shared J313 generated contract still maps M1 physical IRQs 563/564/565/566/579/576/575/578/577 and expects a GPU resource at 0x9fffb8000/0x4000. The current Windows resource validator expects that GPU resource rather than the J413 ACPI ASC resource. Accepting G14G in the user-mode bridge does not resolve these conflicts. Need a distinct generated J413 runtime contract, measured stage-2/IRQ/DMA/power handoff and firmware ABI before runtime driver enablement. No guessed IRQ substitution or runtime acceleration claim.


## Additional primary source review and runtime blockers

Asahi current T8112 DTS https://raw.githubusercontent.com/AsahiLinux/linux/asahi/arch/arm64/boot/dts/apple/t8112.dtsi and m1n1 AGX initialization https://raw.githubusercontent.com/AsahiLinux/m1n1/main/proxyclient/m1n1/agx/__init__.py were inspected for GPU ownership: UAT allocations, ASC firmware channels and inherited chip identity must agree. No source was copied. Microsoft StartDevice contract https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/dispmprt/nc-dispmprt-dxgkddi_start_device requires consuming the translated resource list before mapping resources; changing only the G14G admission predicate cannot satisfy it.

USB source: Mu UsbBusDxe/UsbBus.c calls mUsbRootHubApi.Init and UsbHub.c schedules initial enumeration and periodic root-hub polling. This fact alone does not establish an enumeration race; no delay, reset or poll interval was changed. The existing packaged xHCI, USB bus, keyboard, pointer, mass-storage and filesystem drivers remain present. Inventory is all-bus for BlockIo/SimpleFS and reports device paths so the operator can distinguish firmware/internal/USB volumes. It does not count block devices as proven USB storage or simulate key input.

## Software result

Build `scripts/build-j413-boot-experiment.sh` succeeded in the existing ARM64 Docker environment. Mu validated 98 EFI images and linked PrePi reservations. Both m1n1 stages built and nested image/profile/manifests passed. Current source overlay matches the manifest. Final J413 suite: 44 tests, 43 passed, one expected skip. Ledger schema: two tests passed. Broader checkout suite: 1558 tests, 91 failures, 56 errors, 42 skips; no overall green claim. Failure details remain in `investigation/analysis/2026-11-04-full-tests.log`; durable names/counts are in `2026-11-04-test-results.json`. No hardware launch or installed-image verification.

Candidate `dist/j413/boot-experiment/boot.bin`: 2538572 bytes; SHA256 `8ddc181829347c35c068ef974c5f904405ed9c742bc1a9f5b368f443581d6578`. Firmware `J413_EFI.fd`: 30965760 bytes; SHA256 `847c7acaf9cf05864ff68477d3cb91cca974bcfd0fac8d8ba18e5e8dfb102e18`. Manifest is alongside these files. This is an experimental candidate, not a hardware-validated fix for USB or accelerated graphics.

On a future recorded run, host-controller lookup with no handles narrows the failure to host binding; a host but no USB interfaces narrows it to child enumeration; USB paths without a matching filesystem narrow it to storage/partition/filesystem support; the desired USB filesystem with no usable fallback narrows it to loader open/header validation. These are investigation boundaries rather than diagnoses. A displayed `selected` line is not proof of Windows kernel startup or working input.
