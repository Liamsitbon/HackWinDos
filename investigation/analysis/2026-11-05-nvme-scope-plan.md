# IMG_6327: staged direct-volume storage binding

Observed EXP-20261105-J413-052 reaches native Mu/BDS and stops after finding one
PCI root, before the recursive `ConnectController` returns. The picture and the
operator's several-hour wait establish that boundary, not the individual driver.
Current macOS ADT/resources are captured in `2026-11-05-nvme-stall-live-resources.json`.
The internal ESP PARTUUID is remeasured as
`6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB`. No direct MMIO, guest IRQ/timer or live
register snapshot is available after returning to macOS; those values are unknown.

Primary sources inspected, in hardware ownership order:

- Asahi `drivers/nvme/host/apple.c` (AsahiLinux/linux, asahi branch, downloaded
  for inspection only) and Aurora pinned Linux `arch/arm64/boot/dts/apple/t8112.dtsi`:
  native ANS uses RTKit/mailbox/SART and ANS/APCIE power domains. It is not a
  physical standards-compliant PCI NVMe controller exposed directly to Windows.
- Pinned m1n1 `src/nvme.c`, `hv_pci.c`, `hv_nvme.c`, `hv_nvme_queue.c`,
  `hv_autonomous_runtime.c`: m1n1 initializes/owns native ANS, backend DMA and
  recovery, then exposes one synthetic PCI NVMe at segment/bus/device/function
  0/0/0/0, one namespace, ECAM and BAR traps, coherent guest queues and vINTx 64.
  Native backend polls have real counter-based bounds. No backend/IRQ/power change
  is justified by the current picture.
- Mu `J413ConnectTrace.h`, `WindowsAutoBootDxe.c`, BaseCore
  `Core/Dxe/Hand/DriverSupport.c`, `Bus/Pci/PciBusDxe/PciBus.c`,
  `Bus/Pci/NvmExpressDxe/NvmExpress.c`, `NvmExpressPassthru.c`,
  `Universal/Disk/PartitionDxe/Partition.c`, `EnhancedFatDxe`, and generated
  J413 `MCFG`/`DSDT`: BDS owns UEFI driver connection at application TPL.
  Recursive root binding starts all descendants/filesystems before GPT selection.
  This exceeds the direct-volume selection scope. MCFG/ACPI expose the same
  synthetic PCI path to Windows after ExitBootServices.
- UEFI 2.11 Boot Services 7.3.12: `Recursive=FALSE` expands one controller level;
  it does not preempt a hung driver. Do not claim a timer around the call can
  cancel synchronous `Supported`/`Start`.
  https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html
- Microsoft UEFI in Windows: firmware owns pre-OS protocol/device initialization;
  the Windows inbox PCI/NVMe stack takes over later. No Windows driver can repair
  this pre-loader hang.
  https://learn.microsoft.com/en-us/previous-versions/windows/drivers/bringup/uefi-in-windows

The last J413 standalone checkpoint EXP-20261104-J413-037 reached Shell/internal
NVMe mappings, without USB. This trial reaches Mu but not the root connection
return. J313 assisted/standalone source contracts and their CPU/layout checks
remain unchanged; no J313 result is a J413 hardware golden.

Single firmware behavior variable: bind one protocol layer at a time, without
recursive traversal: root -> only the synthetic NVMe PCI function -> its whole
namespace -> only the unique configured GPT partition's filesystem. Reuse an
already published target and filesystem. Reject missing/duplicate identities and
unexpected synthetic PCI/namespace topology. Print entry and return at each
blocking boundary, including full device path. Preserve normal UEFI binding,
security/BDS launch, ARM64 fixed-path validation and existing USB policy.
This fixes excessive binding scope; it is a hypothesis for this hardware hang.

Smallest falsifiable hardware checkpoint: `root enumeration returned`, followed
by `NVMe controller returned`, `namespace returned`, target filesystem ready and
the fixed ARM64 loader selection. A stationary pre-call marker identifies the
remaining owner; do not wait hours. No Windows/USB/GPU success is claimed.
Recovery: manifested previous Mu-reaching e3919fd2 bundle at
`.local/recovery-20261105-before-nvme-scope`, official Asahi bootstrap backup
f4ce681b and the unchanged macOS Startup Options path. No automatic reboot.
