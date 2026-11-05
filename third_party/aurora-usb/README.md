# Aurora USB DART admission adaptation

`platforms/j413/mu/Silicon/Apple/AppleSiliconPkg/Include/Library/J413UsbDartReadback.h`
adapts only the all-stream TCR readback loop from `UsbDartVerifyControllerBypass`
in [Aurora Mu at 063c6b34da94801d1ee9085594e5ac71ae1793b9](https://github.com/aurora-silicon/mu/blob/063c6b34da94801d1ee9085594e5ac71ae1793b9/Silicon/Apple/AppleSiliconPkg/Drivers/AppleUsbTypeCBringupDxe/AppleUsbTypeCBringupDxe.c).
The original source declares `(BSD-2-Clause-Patent OR MIT) AND GPL-2.0`.
This adaptation selects MIT and GPL-2.0-only; both full texts are included here.
Retained copyright notices identify Aurora Silicon, AppleWOA, Mark Kettenis,
Asahi Linux contributors and NXP. First-party MIT licensing does not supersede
these file-specific terms. Mu already contains GPL-bearing USB/DART components;
this adaptation is kept in that firmware layer, not a Windows driver.

Compatibility review: the existing ADT-validated `APPLE_DART_INFO` owns register
base/layout/stream count; the adapter reuses those definitions, bounds the stream
count and requires every requested bypass TCR to read back exactly. It runs in
the DART producer before readiness publication. It does not import Aurora's
identity-table acceptance, device-tree resolution, PHY, USB3 or USB4 sequences.
No unsupported generation or identity map is admitted. Failure stops readiness;
there is no new hardware write, IRQ, DMA allocation or power/reset behavior.

Source audit and hardware checkpoint: investigation/analysis/2026-11-05-aurora-integration-plan.md.
No native J413 result is claimed. No Linux, Mesa or Aura implementation is copied
by this adaptation.
