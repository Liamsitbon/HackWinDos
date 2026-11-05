# Read existing UEFI evidence when the internal ESP cannot mount

Confirmed workflow defect: the owner ran collect-only and mount failed, so no
log was obtained (EXP-20261105T214802Z-J413-WINPE-4c24cdc4). Rebooting did not
install the separate diagnostic WIM. No new guest result is inferred from the
latest statement alone. Follow-up host commands in EXP058 could not use sudo
without another owner password; neither mount.txt nor a checker was read.

Inspected primary format definitions: pinned Mu
Common/TIANO/FatPkg/EnhancedFatDxe/FatFileSystem.h and Microsoft's EFI FAT32
specification v1.03, BPB/FAT/directory sections:
https://www.cs.fsu.edu/~cop4610t/assignments/project3/spec/fatspec.pdf
No code or specification prose is copied. The Python reader is independently
implemented and is limited to bounded 8.3 evidence-file reads. Existing Asahi,
m1n1, Mu/ACPI and Windows launch/USB ownership contracts are unchanged.

Host collector owns this defect. Re-resolve the exact internal GPT ESP; open its
block device rb, without buffering; align every physical read to diskutil's
measured DeviceBlockSize and bound it by TotalSize. Validate FAT32 BPB geometry,
capacity, active/mirrored FAT semantics, directory identity, chains and budgets.
Read only m1n1/boot.bin (max 8MiB) and m1n1/j413uefi.log (max 64KiB). Verify the
bootstrap SHA against the photographed Setup-reaching candidate before exposing
the log. Refuse duplicate short names, inconsistent mirrored links, cycles,
truncation, unsupported format, oversized files or missing evidence. Report FAT
clean-shutdown flags without changing them. No repair, mount requirement,
filesystem scan, firmware/driver/IRQ/DMA/power/security change or reboot.

Smallest checkpoint: owner reruns the same --collect-only command in macOS;
the collected log names pre-OS USB connection/readiness status. Failure reports
the exact format/identity/chain/read error. Recovery is unchanged Setup-reaching
639d558d bootstrap and original WIM; no native boot or data mutation occurs.
