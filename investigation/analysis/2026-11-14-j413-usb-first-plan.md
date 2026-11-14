# Try USB Setup before binding internal NVMe on J413

The latest failed-boot evidence is IMG_6348 / EXP064, stalled inside synchronous
NVMe binding before the USB call. The preceding Setup-reaching profiles and
EXP067 are still recoverable. Current macOS inventory confirms J413/T8112 and
internal FAT ESP PARTUUID 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB. The SanDisk was
absent at inventory time. The ADT, IRQ routes, and guest layout are captured in
`.local/j413-usb-first/live.json` and `config/j413-guest-layout.json`. Failed
native guest registers and interrupt/timer state cannot be read post-restart.

Reviewed Asahi's `drivers/usb/dwc3/dwc3-apple.c` and T8112 `t8112.dtsi` for
PHY/host sequencing, power, interrupt and dual-DART ownership. Reviewed
m1n1 `src/usb.c`, the J413 USB host-role patch, `src/hv_pci.c`, and `src/hv_nvme.c`
for preserved USB host state and presented synthetic NVMe. Reviewed Mu's
`UsbEnumer.c`, USB mass storage and partition driver device paths, `CoreLocateDevicePath`,
`BmBoot.c`, `MsPlatformDevicesLib.c`, `WindowsAutoBootDxe.c`, the J413
`J413ConnectTrace.h`, `J413DirectSetup.h`, and J413 DSDT/MCFG. The J413 mandatory
platform connection list is empty. USB interfaces carry their USB I/O protocol
on a device-path ancestor of partition filesystems. The UEFI boot manager and
Microsoft's Windows PE documentation describe removable boot media and the
standard ARM64 fallback contract:

- https://uefi.org/specs/UEFI/2.10/03_Boot_Manager.html
- https://uefi.org/specs/UEFI/2.10/07_Services_Boot_Services.html
- https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/winpe-create-usb-bootable-drive

In the previous implementation BDS called NVMe first, so a hung driver prevented
USB discovery regardless of cable or media. The enabled selector then only
queried the fixed GPT partition even when USB enumeration returned. Change the
single BDS policy for the automatic Setup target: enumerate USB via existing
firmware bindings, then try exact case-folded ARM64 BOOTAA64.EFI candidates from
USB-backed SimpleFS handles, then try the configured internal partition once if
those attempts are exhausted. Use LocateDevicePath for the USB I/O ancestor so
fixed-media USB SSDs are eligible. Keep direct selection and the removable
candidate iterator independent. An already-tried USB option is never retried
when BDS asks for the next option; a delayed filesystem can be discovered
within the existing bounded wait. No probing arbitrary EFI names, and the
internal path still falls back to ordinary BDS when unsuccessful.

m1n1 continues to own ANS and the pre-UEFI USB PHY/DART/power state; Mu continues
to own xHCI and filesystem enumeration, USB data flow, and boot option launch.
Windows retains runtime device, storage and input ownership after handoff.
No register, timing, ACPI, IRQ, DMA, input-driver, or Windows media change. No
external implementation copied. Relative to EXP067 the one changed native
experiment policy is boot target priority. The smallest checkpoint is Windows
Boot Manager/Setup from a preconnected known USB while the synthetic NVMe
path has not been entered. With no eligible USB the fixed internal fallback
runs as before, including the EXP067 error fix. Recover through macOS Startup
Options and the manifested EXP067 image or pre-install bootstrap backup.
