# J413 driver port and automatic servicing

## Sources and observations, in required order

1. Current ADT and routes: `2026-11-06-driver-review-live-resources.json`.
   Latest photographed contract EXP060: WinPE, NVMe Started and hidden FAT32
   ESP present; external/internal input unavailable. EXP061 host installation
   completed; its USB PnP pages have not been supplied. No privileged MMIO or
   Windows IRQ/DMA trace is currently available; no missing register is guessed.
2. Aurora Linux integration/aurora commit
   `0943983df73eb270720a7e6ba13b009ccfd14312`: `drivers/soc/apple/dockchannel.c`,
   `drivers/hid/dockchannel-hid/dockchannel-hid.c`, T8112 device tree. Inspected
   FIFO config/data separation, IRQ demultiplexing, `devm_*` ownership,
   RTKit helper, DART-backed ring, GPIO/firmware and HID publication.
3. Pinned local m1n1 `src/hv.c`, `src/hv_bootstrap.c`, `src/kboot.c`,
   `src/usb.c` and existing standalone source review. No M2 Windows DockChannel
   runtime initializer is present; J313 SPI is not a substitute.
4. Current Mu generated J413 DSDT MTP0 and XHC1 resources and manifests.
   MTP0 exposes two 4 KiB banks, starting 0x24eb00000 and 0x24eb14000.
   Linux identifies IRQ bank 0x24eb14000 and local data bank 0x24eb34000.
   Windows currently maps the first memory resource as FIFO. This is not a
   valid shared resource contract; no incomplete driver will be injected as a
   mouse fix. Hypervisor IRQ translation and MTP helper ownership also remain
   unqualified. Linux FIFO capacity is 0x800; Windows uses 0x1000.
5. Microsoft KMDF EvtDevicePrepareHardware/ReleaseHardware, WdfMemoryCreate,
   WdfWorkItemFlush, VHF and DISM offline servicing documentation; Aurora's
   Windows-driver-samples commit 34c8e967f0fc9bac4febbad50e1999d0d8f5923f
   has no Apple/Asahi/DockChannel/J413/T8112 paths in its complete tree. It is
   a fork of Microsoft's general samples, not an Apple driver package.
6. Preserve the EXP060/061 standalone contracts and firmware 639d558d. No
   current assisted J313 result qualifies the J413 adapter or a full installation.

## Ownership and independently reviewable corrections

Firmware/m1n1 own initialization, stage-2 mappings, interrupt routing and handoff.
Windows owns PnP device lifetime, framework work items, runtime operation and
report publication. Linux `devm_*` is device-managed, not an ExAllocatePool2
replacement with identical semantics. Register/IRQ/power/DMA porting requires
the missing firmware contract and measured checkpoint first.

Confirmed software defect: DeviceAdd allocates StreamBuffer once while
ReleaseHardware frees it; a second PrepareHardware never allocates/resets it.
The actual extracted callbacks reproduce failure in a sanitizer C harness.
Move allocation/reset into PrepareHardware; drain the framework worker before
VHF teardown/unmapping/freeing. Return allocation failure and allow framework
ReleaseHardware to unwind partial preparation. Keep FIFO/MMIO/IRQ behavior
unchanged. No Linux code is copied in this lifecycle correction.

Automatic injection: add a Windows offline-servicing script with explicit
boot.wim and optional install.wim/index inputs. Verify package hashes, ARM64
native SYS, hardware identity, reviewed automatic-injection eligibility and
trusted catalog before servicing a private copy. DISM performs actual driver
store integration and verification; copying SYS files with wimlib is not driver
injection. Do not bypass signature enforcement or modify BCD, original media,
partition layout or the installed experimental firmware. Commit output only
after all selected image indexes succeed. Failure discards private mounts and
retains originals. Incomplete DockChannel/AGX packages remain ineligible; do
not pretend there is a ready Windows USB package to inject.

## License and compatibility

Aurora Linux DockChannel/HID files offer MIT as an alternative to GPL;
T8112 DTS offers MIT as an alternative to GPL. Review file-specific notices
before any future source adaptation and preserve attribution/license text.
The current Windows lifetime fix and servicing script are original Windows
implementations informed by behavior and official documentation. No Linux
implementation is copied. General Windows-driver-samples is MS-PL; no sample
code is copied. Mesa/Linux DRM are not a Windows WDDM driver.

## Smallest checkpoints and recovery

Host regression: real callbacks Prepare/Release/Prepare plus allocation/map
failure, complete frees/unmaps and reset stream. WDK build must separately
compile the actual adapter; host shims alone are not a Windows driver build.
Next physical checkpoint remains EXP061 automatic USB/problem pages, followed
by one owning-layer repair determined by its actual status, not broad injection.
New lifecycle binary must not be installed against the invalid resource ABI.
Original WIM, latest diagnostic WIM and firmware manifest/recovery remain intact.
Automatic injection is implemented only; actual DISM and hardware results must
be recorded when a qualifying package and Windows servicing host are available.

Primary references:
- https://github.com/aurora-silicon/linux/tree/0943983df73eb270720a7e6ba13b009ccfd14312
- https://github.com/aurora-silicon/Windows-driver-samples/tree/34c8e967f0fc9bac4febbad50e1999d0d8f5923f
- https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdfdevice/nc-wdfdevice-evt_wdf_device_prepare_hardware
- https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdfworkitem/nf-wdfworkitem-wdfworkitemflush
- https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/add-and-remove-drivers-to-an-offline-windows-image
- https://learn.microsoft.com/en-us/troubleshoot/windows-client/setup-upgrade-and-drivers/limitations-dollar-sign-winpedriver-dollar-sign
