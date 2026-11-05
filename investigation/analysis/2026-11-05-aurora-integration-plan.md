# Aurora integration: verify USB DART state before publishing readiness

Source pins and file digests: `2026-11-05-aurora-source-pins.json`. This is a bounded compatibility review, not a wholesale Linux-driver import.

## Observed contract and owners

Current J413 T8112 ADT resources and interrupt routes are recorded in `2026-11-05-direct-setup-live-resources.json`; this macOS process cannot read the firmware-time MMIO state. EXP037 remains the latest physical failure: internal storage/Shell alive but no USB filesystem. No newer physical Windows run is observed. Read Asahi-derived Aurora Linux apple-dart.c, atc.c, dwc3-apple.c, core.c, t8112.dtsi and dockchannel-hid.c, then local pinned m1n1 src/usb.c, hv.c and hv_bootstrap.c, Mu AppleDartIoMmuDxe/AppleUsbTypeCBringupDxe, generated J413 DSDT and published DART-ready protocol, and Microsoft USB host-stack documentation. Previous J313 assisted results are not J413 standalone validation.

m1n1 owns early PHY initialization and the hypervisor stage-2/IRQ transport. Mu owns replacement DART state, DWC3 initialization, xHCI binding and the BDS handoff. Windows USBXHCI/UCX/USBHUB3 own runtime standard xHCI transfers/interrupts/power after handoff. The physical DART must actually provide the identity/bypass address contract that firmware and Windows expect. Current Mu marks a bank ready after requested TCR writes without checking them. Aurora Mu explicitly reads every stream TCR and refuses a mismatched bank. A capability bit and a completed MMIO write do not prove the requested bypass latched.

## One change

Adapt Aurora's all-stream readback check in the owning DART producer before BypassMode/ReadyBanks publication. Keep the existing resources, stream bounds (1..256), register constants, writes, TLB deadline, PHY/role/reset, ACPI, IRQ and DMA contract unchanged. Require exact bypass TCR on every stream of both validated banks; do not accept identity mode from a merely valid TTBR because this checkout has no verified identity-table builder/walk. Use a memory barrier before readback. Missing/incorrect readback returns EFI_DEVICE_ERROR and no readiness protocol, so Type-C cannot register xHCI against a false success marker. This fixes a software admission defect; it does not establish that it caused EXP037.

## License and compatibility review

The source file has `(BSD-2-Clause-Patent OR MIT) AND GPL-2.0`, including Aurora Silicon copyright 2026. The adapter remains in this existing GPL-bearing Mu firmware layer with the same notices and explicit GPL-2.0-only selection for the imported portion, plus full license texts/provenance under third_party/aurora-usb. It is not relicensed as first-party MIT. No code is copied into proprietary Windows drivers. Current Aura new contributions are GPL-2.0-only and Linux is GPL-bearing; no Aura runtime or Linux implementation is imported here. Mesa/DRM is not a WDDM implementation. Aurora USB4 Type5 is host-tested and not present in its platform DSC/FDF, so it cannot be treated as production runtime proof. USB3 deferred PIPE completion requires matched m1n1 PHY preparation and Mu consumer ordering, absent from this pinned local m1n1; it is not enabled by this change.

## Falsifiable checks and recovery

Regression: mock a bypass-capable DART whose one stream drops the bypass write; old production initializer incorrectly publishes readiness, new initializer must fail. Run actual-C ASan/UBSan for first/last SID in both banks and normal readiness, then a complete Mu/two-stage build with recorded manifest/SHA. Smallest physical checkpoint is DART-readback success for both USB1 banks followed by nonzero USB interfaces/storage. It is independent of USB3/USB4 acceleration. Failure collects exact bank/SID/TCR and leaves the controller unregistered; no new reset/power operation is attempted. Preserve the previous direct image before rebuilding; no physical install or reboot is part of this integration. Recovery remains prior manifested local bytes and macOS.

References: https://github.com/aurora-silicon/mu/blob/063c6b34da94801d1ee9085594e5ac71ae1793b9/Silicon/Apple/AppleSiliconPkg/Drivers/AppleUsbTypeCBringupDxe/AppleUsbTypeCBringupDxe.c ; https://github.com/aurora-silicon/linux/blob/0041b90bd066315fdcc3a07c39e5a063bd143627/drivers/iommu/apple-dart.c ; https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/usb-3-0-driver-stack-architecture
