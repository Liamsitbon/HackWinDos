# Aurora Silicon integration

The integrated change is USB DART **readback admission**, adapted from
[Aurora Mu at the inspected source pin](https://github.com/aurora-silicon/mu/blob/063c6b34da94801d1ee9085594e5ac71ae1793b9/Silicon/Apple/AppleSiliconPkg/Drivers/AppleUsbTypeCBringupDxe/AppleUsbTypeCBringupDxe.c).
The DART producer now requires every stream's bypass TCR to read back correctly
before publishing readiness. A capability flag and requested writes alone no
longer count as success. The host regression reproduces the old false success
by dropping a first/last stream write in either bank. This is software evidence;
no newer J413 physical USB or Windows result is claimed.

The adapter is staged by the normal J413 overlay/build command and delivered
through [the same-volume Setup installer](J413_DIRECT_SETUP.md). No separate
Aurora monitor or Linux kernel is required by this change. Existing hardware
initialization values, IRQ routes, DMA ownership, power and reset sequencing
are preserved.

## Compatibility and licensing

The imported loop stays in the existing GPL-bearing Mu layer. Its original
copyright notices, explicit file-specific license selection, full terms and
compatibility review are in [third_party/aurora-usb](../third_party/aurora-usb/README.md).
The first-party MIT license does not replace those terms. New Aura contributions
are GPL-2.0-only; inherited m1n1 portions retain MIT. No Aura runtime, Linux driver
or Mesa implementation was copied into a Windows driver.

| Upstream work inspected | Integration boundary |
| --- | --- |
| Mu DART/USB admission | Bounded all-stream TCR readback adapted and regression tested |
| Linux DART/ATCPHY/DWC3 | Protocol, bounds and sequencing reference; no wholesale import |
| Mu deferred USB3 PIPE completion | Requires matched m1n1 PHY preparation before Mu core init; current pinned local m1n1 lacks that contract |
| Mu USB4 Type5 core | Upstream describes host tests and excludes it from platform DSC/FDF; no production USB4 claim |
| Linux DockChannel HID | Source for MTP firmware/DART/GPIO/resource and report requirements; existing KMDF adapter remains incomplete |
| Linux/Mesa GPU stack | Requires a Windows WDDM/kernel/firmware ownership adaptation; Linux acceleration is not Windows acceleration proof |
| Aurora installer/diagnostics | Useful architecture references; not installed and no partition/recovery enrollment changes made |

Exact inspected commits, file hashes, the owner contract, differences, test
hypothesis and recovery checkpoint are recorded in
[the source-first integration plan](../investigation/analysis/2026-11-05-aurora-integration-plan.md)
and [source pins](../investigation/analysis/2026-11-05-aurora-source-pins.json).
The latest physical failure remains EXP-20261104-J413-037.
