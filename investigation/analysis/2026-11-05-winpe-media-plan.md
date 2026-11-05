# Photographed WinPE entry, missing-media dialog, and input boundary

EXP-20261105-J413-054 and three photographs show the Windows logo, Setup's
Please wait page and then Install driver to show hardware / missing media driver.
The installed bootstrap transaction records SHA256 639d558d. This confirms the
native Setup boundary, not continuing access to the installer volume or target
disk. No disk/PnP/Setup logs or guest registers are available after returning to
macOS. Live ADT is recorded in 2026-11-05-winpe-entry-live-resources.json.

The operator corrected the external-mouse report: its adapter was attached to
the iPad. External USB input is untested. Built-in keyboard/trackpad are reported
unresponsive and the current MTP wrapper is incomplete; do not inject it as a fix.

Sources inspected: Asahi T8112 DTS (ANS/SART, DWC3/DART and DockChannel/MTP),
DockChannel HID source review retained by drivers/apple-dockchannel/README.md;
m1n1 nvme/hv_pci/hv_nvme and explicit AIC2 1112 -> guest 857 IRQ routes;
Mu J413 DSDT/MCFG, DART producer, USB registration and XhcExitBootService;
Windows wrapper PrepareHardware/VHF startup. Native ANS and its DMA/queues are
m1n1-owned; UEFI driver binding is Mu-owned; after ExitBootServices Windows owns
the inbox PCI/NVMe/xHCI/HID stack through the exposed ACPI contract. Input uses
MTP/DockChannel, not J313 SPI. The missing-media dialog alone cannot distinguish
inbox storage binding, platform DMA/IRQ failures, or Setup image discovery.
The last successful standalone contract is the exact 639d558d Setup entry;
J313 assisted observations are not J413 hardware validation.

Official Microsoft interfaces inspected:

- Winpeshl.ini LaunchApps ordering and command-line limit:
  https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/winpeshlini-reference-launching-an-app-when-winpe-starts
- Default Startnet/Wpeinit and PnP initialization:
  https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/wpeinit-and-startnetcmd-using-winpe-startup-scripts
- PnPUtil read-only enumeration:
  https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/pnputil-command-syntax
- Setup logs:
  https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/deployment-troubleshooting-and-log-files

Smallest next experiment: keep firmware/ACPI/IRQ/DMA/power and installer WIM
contents unchanged except image 2's diagnostic startup files. Start a background
collector through supported Winpeshl.ini, then launch the original sources/setup.exe.
After a bounded delay, enumerate disks/volumes, SCSIAdapter/USB/HIDClass PnP state
and registry service/Enum state; copy existing Setup logs. Display the result in
a command window without requiring input. Persist only to the unique volume
carrying this experiment's exact GUID marker, if Windows can read that volume.
Do not run wpeinit twice, load drivers, rescan/reset devices, apply Windows,
create/format partitions, change security, or reboot. No Asahi code is copied.

The source image lacks ping/timeout/choice/sc/findstr, so do not assume a full desktop
command environment. A tiny ARM64 user-mode helper calls only documented
Kernel32 Sleep(30000) and ExitProcess. cmd/pnputil/diskpart/reg/Setup exist in the
actual source WIM. WIM source/ARM64 identity, added bytes, helper PE and final
integrity are checked locally. Native execution remains unqualified until trial.

The collector uses an exact GUID marker filename, not shell expansion of untrusted
file contents; multiple matching volumes disable persistence. Existing logs are
retained under unique per-run directories. Notepad displays the summary from its
first line so a large inventory does not scroll the disk list off the screen.

Checkpoint: the automatically opened Notepad summary shows NVMe/USB PnP status and disk
list, or a precise collector failure. Photograph it, and test external input on
the actual MacBook. Recovery: byte-verified original boot.wim + media metadata,
unchanged Setup-reaching firmware bundle, and macOS Startup Options. Installation
must record exact diagnostic WIM hash/manifest and create recovery copies first.
