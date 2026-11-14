# Confirmed code defect: NVMe failed Start reported as success

## Evidence and source order

Latest hardware evidence remains IMG_6348/EXP064: about fifteen minutes at
NvmExpressDriverBindingStart with no later existing message. EXP066 operation
checkpoints were prepared, but no new hardware outcome has been supplied.
Current ADT resources/interrupt routes are remeasured in
`2026-11-06-nvme-start-fix-live-resources.json`. Live failed-guest registers,
CPU, timer, IRQ and DMA state are unavailable and are not guessed.

Read Asahi Apple ANS NVMe host driver and current Aurora T8112 device tree,
then local m1n1 nvme.c/hv_pci.c/hv_nvme.c/hv_nvme_queue.c and exception fast
path. Native ANS remains owned by m1n1; Mu sees a standards-facing synthetic
NVMe controller. The queue/backend loops, BAR enable and lock paths were
inspected; no reproduced hardware defect in them justifies changing their
registers, timing, locks or mappings in this trial.

Read Mu NvmExpress DriverBindingStart, queue cleanup, ControllerInit and
Passthru, PCI bus attributes/map/allocate, RootBridgeIo, IoMmuLibNull and DXE
driver-binding/timer implementation; compare generated J413 MCFG/DSDT and
last native Setup/storage results EXP054/060. Existing diagnostic messages
and launch contracts remain; no new logging-only build is being proposed.

Official UEFI Driver Model Start contract requires reporting device startup
failure rather than EFI_SUCCESS when the device was not started. Windows
Boot Manager/Windows drivers run later and cannot own this firmware defect.

## Reproduced defect

The error exit in `NvmExpressDriverBindingStart` assigns
`Status = NvmExpressDriverCleanUpQueues(Private)` and eventually returns it.
Consequently an initialization/Identify/allocation/timer/protocol error can
be replaced by cleanup success, or by an unrelated cleanup error. That tells
the firmware driver framework a failed controller startup succeeded. Cleanup
of a null Private also replaces out-of-resources with invalid-parameter.

The regression compiles and executes the actual error-exit code extracted
from the firmware source, under ASan/UBSan. Before the fix it fails the
original-error assertion with successful cleanup. Afterward it covers
cleanup success, cleanup failure and null allocation, and checks pool/event/
protocol release counts. It separately verifies unchanged non-J413 behavior.
This is software fault injection, not a reproduced native hardware hang.

## Smallest owning-layer correction

For J413 only, save the original status on entry to the existing error exit
and restore it immediately before the final log/return. Keep every cleanup
call and its own error log. Successful Start and the other platform paths
are unchanged. No new retry/reset/deadline, register access, DMA, IRQ, power,
Windows driver, protocol call or queue change. The existing prepared paired
checkpoints stay unchanged. Original upstream license notices remain intact;
this patch is an original correction, not an external code import.

The firmware NVMe driver owns failure propagation and resource cleanup.
m1n1 retains native storage, mappings and interrupts; Mu retains device
initialization; Windows retains its later runtime storage and input drivers.

## Qualification and recovery

The defect is confirmed and corrected in software. It has not been proven
to be the cause of the photographed stall; preserving errors cannot preempt
a lower-layer call that never returns. Do not describe it as boot-qualified.
Hardware checkpoint: existing standalone boot either reaches its previous
Setup phase or reports the actual failed Start operation/status. Recovery:
complete preceding d2c2f465 image/FD/manifest at
`.local/recovery-20261106-before-nvme-start-fix`, ce99784c native diagnostic
and earlier Setup-reaching 639d558d profiles retained. Firmware-only owner
installation must pin the newly built SHA and preserve all companions and
Windows media; no automatic reboot.

Primary specification:
https://uefi.org/specs/UEFI/2.10/11_Protocols_UEFI_Driver_Model.html
