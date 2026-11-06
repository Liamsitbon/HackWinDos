# NVMe binding observation after IMG_6347

Observed result and photograph hash: `2026-11-06-nvme-bind-stall-result.json`.
The operator waited one to two minutes. Root binding returns and one synthetic
PCI function exists, but its synchronous ConnectController call does not show a
return before the photograph. The cropped background is insufficient to decode
an exception or identify a driver address. No Windows entry was observed.

## Sources, observed contracts and ownership

1. Current T8112 ADT/resources and IRQ routes are recorded in
   `2026-11-06-nvme-console-live-resources.json`; guest registers/CPU/timer state
   at the failed instant is unavailable. Post-run bootstrap has not been read;
   last installer independently verified 639d558d. Do not infer a new image.
2. Read the existing Asahi `drivers/nvme/host/apple.c` primary implementation
   at `.local/nvme-stall/asahi-apple-nvme.c` and current Aurora T8112 DTS.
   Native Apple ANS requires RTKit, SART/NVMMU and power sequencing; it is not
   the standards-facing PCI NVMe device that Mu/Windows see.
3. Read current pinned m1n1 `src/nvme.c`, `hv_nvme.c`, `hv_nvme_queue.c`,
   `hv_pci.c`, previous source/launch contracts. m1n1 owns native storage and
   exposes synthetic PCI NVMe and guest queues/INTx. No storage register,
   backend, interrupt or memory-map change follows from this image alone.
4. Read Mu J413ConnectTrace, DXE Core DriverSupport, NvmExpress driver binding,
   HCI init/disable/enable/Identify/queue setup and synchronous PassThru loop;
   J413 MCFG/DSDT and the current DSC include. Generic command timeout is five
   seconds; controller transitions use CAP.TO. A surrounding timer cannot
   cancel synchronous DriverBinding Start. Existing driver messages go to
   BaseDebugLibSerialPort, not the physical console. UefiDebugLibConOut is
   already supported by this Mu tree and suppresses console access after EBS.
5. UEFI 2.11 Boot Services ConnectController and Microsoft UEFI boot phases:
   firmware owns this pre-loader device binding. Windows input drivers and
   the diagnostic WIM are not executing at the observed boundary.
6. Compare EXP054/060 native Setup/storage and EXP061 host WIM installation.
   The same 639d558d firmware has reached Setup before; do not claim the WIM
   caused a pre-filesystem stall or call that image universally stable.

## One diagnostic change

Define J413_NVME_CONSOLE_TRACE in the J413 DSC and conditionally bind only
NvmExpressDxe to the existing UefiDebugLibConOut. All other platforms keep the
existing DebugLib. Preserve driver code, global print mask and assertion policy;
do not add a speculative timeout, reset, retry, DMA mapping or delay. Existing
DEBUG messages will identify controller disable/enable/Identify/queue progress
or assertion. This adds measured diagnostics only and is not a storage fix.
The first post-call marker remains useful if a binding error returns normally.

The source patch applies in the owning shared DSC include, not in a Windows
driver. This is an original configuration change; no external source copied.
No new register values, physical IRQs or driver interfaces are introduced.

## Checkpoint and recovery

Software: staging remains idempotent, refuses unrelated edits before copying,
and manifest provenance rejects the preceding FD after the DSC patch changes.
Build the complete Mu/two-stage image and verify its manifest/architecture and
NvmExpressDxe library resolution. Preserve complete known Setup-reaching image
and matching FD/manifest at `.local/recovery-20261106-before-nvme-console`.

Physical: one cold launch, last visible inner NVMe message and elapsed time.
Failure is no new trace, console interference, assertion, reset or stationary
operation. Recovery is macOS Startup Options plus recorded bootstrap/FD backup.
No Windows media recopy, repair, security change, injected driver or auto reboot.
New artifact SHA and exact install command are required before installation.

References:
- https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html
- https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/windows-boot-issues-troubleshooting
