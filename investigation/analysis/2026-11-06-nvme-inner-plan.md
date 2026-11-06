# Per-operation binding checkpoints after IMG_6348

Observed native run: `2026-11-06-nvme-start-only-result.json`. The prior
console-routing diagnostic now visibly reaches NvmExpressDriverBindingStart,
but no later existing message appears during the operator's roughly fifteen
minutes. Installation of ce99784c is independently recorded by transaction
EXP-20261106T083052Z-J413-ESP-6b3cf8f2. This is not a Windows/WinPE failure.

## Source-first contract

1. Fresh Mac14,2/T8112 ADT, physical ranges and AIC routes are recorded in
   `2026-11-06-nvme-inner-live-resources.json`. No live register snapshot of the
   failed guest is available; no timer/IRQ/CPU liveness is inferred from pixels.
2. Read Asahi Apple NVMe host implementation and the current Aurora T8112 DTS:
   ANS backend uses RTKit, NVMMU/SART and physical power/DMA ownership; native
   submission queues are not standard PCI NVMe. Existing license/source pins
   are retained; no external implementation is copied.
3. Current pinned m1n1 `hv_pci.c`, `hv_nvme.c`, `hv_nvme_queue.c`, `nvme.c`:
   m1n1 owns the real backend and synthetic ECAM/BAR/front-end queues and IRQ.
   PCI memory enable arms the synthetic NVMe trap. No measured evidence yet
   justifies changing BAR setup, backend locking, IRQ delivery or memory maps.
4. Mu PCI bus PciIoAttributes and NVMe DriverBindingStart/ControllerInit:
   protocol opening, private allocation, PCI attribute reads/DAC enable and
   controller initialization happen between existing start/disable messages.
   Init itself includes capabilities, queue allocations/maps, controller
   transitions and Identify. A successful five-second timer setup does not
   establish guest timer liveness. A caller cannot cancel synchronous binding.
   Inspect generated J413 MCFG/DSDT and prior as-built console library record;
   those mappings and their ownership remain unchanged.
5. UEFI 2.11 PCI I/O protocol Attributes/AllocateBuffer/Map and Microsoft
   boot-phase documentation: these are firmware operations before Windows
   Boot Manager. Do not inject a Windows driver to conceal this failure.
6. Preserve prior EXP054/060 Setup/storage checkpoints, failing EXP064 native
   run, current ce99784c recovery and earlier Setup-reaching 639d558d recovery.
   No J313 assisted checkpoint qualifies this J413 standalone run.

## One independently observable change

Add 29 paired entry/return checkpoints around existing operations in
NvmExpressDriverBindingStart and NvmeControllerInit. Include private allocation
as pointer-returning, all other operations report the actual existing Status.
Use guarded DEBUG_INFO statements through the already selected console library.
No new MMIO reads, protocol calls, register values, timeout/reset/retry, command
ordering, polling, queue sizes, IRQ/DMA/power or Windows changes. There is no
per-block-I/O logging. Original driver copyright/license remains unchanged.

The regression applies the real patch to pinned BaseCore files, removes only
the guarded diagnostics and requires exact byte equality with the originals.
All 29 labels must have a matching entry and return. Existing staging tests
cover nested BaseCore patch preflight, idempotence and unrelated edit rejection.
Record BaseCore commit/diff separately because it is a nested submodule.

## Falsifiable checkpoint and recovery

Build complete Mu/two-stage artifact and verify as-built checkpoints plus the
manifest/hash. Update the pinned owner installation launcher only after that
hash exists. Preserve current WIM and all original firmware/media companions.
Next physical run should show the last operation entered without its returned
status, an explicit error, or binding success. Photograph that last page; a
short stationary observation is sufficient, no fifteen-minute wait is needed.
The result is further localization, not a claimed repair. Recovery through
macOS and the byte-verified bootstrap/FD/manifest backups remains available.

References:
- https://uefi.org/sites/default/files/resources/UEFI_Spec_Final_2.11.pdf (14.4)
- https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/windows-boot-issues-troubleshooting
