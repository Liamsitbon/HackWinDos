# J413 autonomous UEFI experiment

This is a compiled, source-checked boot experiment for MacBook Air M2 J413/T8112.
EXP017 photographs the preceding candidate passing the boot-data placement gate, then stopping on an incorrect framebuffer source-range guard before Mu. The current source-bound correction has not been launched.
The next success criterion is a visible Mu UEFI checkpoint; Windows Setup, Windows CPU/timer progress, USB storage/input,
GPU and accelerated display remain unqualified. See EXP-20261011-J413-014 through EXP-20261011-J413-017 and
[J413 boot-path audit](J413_BOOT_AUDIT.md).

## Build and identity

```sh
scripts/build-j413-boot-experiment.sh
```

Native ARM64 Docker provides GCC 13.3 and pinned Rust 1.85.1. The Rust pin avoids
a bare-metal `wcslen` dependency emitted by Rust 1.99. Both distinct m1n1 stages
are compiled with `M1N1_J413`; the nested image contains the clean J413 DEBUG Mu
FD. Existing prepared Mu firmware can be reused with `J413_SKIP_MU=1`; its
manifest, bytes and exact current Mu overlay/patch digest are verified first.
Changed Mu source requires a fresh firmware build. A postbuild check also rejects
a silently compiled-out J413 stack loop or missing linked boot-data reservations. No disk, boot policy or installer is
changed by this script. Publication replaces the output directory only after
verification, preserving the previous directory on a failed build.

Output: `dist/j413/boot-experiment/boot.bin`, 2,518,496 bytes, SHA-256:
`537dda804f96abbf89e738eb3adeb79dca19e4958c1fc172dcb5ff95a93dce2f`.
Its manifest includes exact artifacts, submodule pins/diffs, J413 source overlay
and patch hash, DEBUG qualification, physical/debug-off profile, and TOOLCHAINS.json.
Nested decompression/CRC checks pass and the decoded FD matches the freshly
built patched J413 firmware byte for byte (SHA
`f2ff3888283fe12b2fbb3c729c5bd5a56f87849e6a96e0be1a2b848cf123e9f9`). These are software checks, not a boot test.

## Proxy is disabled in the current candidate

Both m1n1 stages are compiled with `M1N1_NO_PROXY` and both image manifests use
flags 1: physical display, debug off. Mu's DEBUG build and the manifest's `debug`
qualification label describe an experimental firmware build, not a host transport.
The loader does not open USB gadget debugging, wait for a host, or accept proxy
commands. Bootstrap and guest entry reject virtual-display/UART/full/monitor
profiles before opening their host transport. Guest Type-C platform power remains
required; this does not add a USB0 route or qualify USB1 DMA.

Early proxy entry and the normal startup failure fallback are excluded. A missing
payload or failed launch stops with `J413 STOP` and keeps the preceding failure
lines visible instead of printing `Running proxy...`. Tick-driven host command
polling is excluded; functional guest IRQ/timer paths remain. The shared proxy
entry also stops if reached by an unexpected guest event instead of processing
commands. These stop boundaries preserve hardware safety checks; they do not turn
a failed preflight or unhandled trap into a successful boot.

EXP013 corrects the earlier physical/UART candidate: UART flags 5 actually enabled
proxy takeover, and the inherited startup failure path still entered proxy.
That candidate (SHA `16020107c5bdf2096fcbf68eab2630e35e52dae1c283014d3485ee759f910806`)
is superseded and preserved privately. The operator reported `Running proxy...`,
but supplied no installed hash or preceding trace; its exact failing stage is
not established. Four executable host regressions cover both real startup bodies,
missing/failed payloads, the shared proxy entry, allowed profiles and legacy
startup behavior. Native build/object checks complement those portable checks.

From the clean repository root, the existing ESP installer command is:

```sh
sudo ./scripts/install-esp.sh install --disk disk0s4 --image dist/j413/boot-experiment/boot.bin
```

This verifies the candidate and backs up the old file before replacement. If the
internal ESP still fails to mount, the script stops before replacing its payload.
No raw-disk overwrite or Recovery re-personalization is implied by this command.
Record the actual installed hash and the next visible boot checkpoint in EXP013
or a subsequent launch entry. Installation and a physical boot remain pending.

## What changes at launch

The default J313 autonomous path rejects J413/T8112, and a J413 build rejects
J313/T8103, before autonomous USB power setup. J413 runtime also checks live USB1,
DART USB1 and UART register bases/interrupts and the complete CPU ADT topology.
Apple CPU `reg` values 0..3 and 0x100..0x103 are distinct from the architectural
MPIDRs 0..3 and 0x10100..0x10103.

The J413 checkpoint reference is constructed from its guest layout, live RAM
size and shared `hv_guest_cpu_state_prepare` source requirements. It contains
no M1 ADT digest or supposed M2 hardware golden. The wire collector and portable
CPU rules retain their historical J313 names; compiled J413 identity is J413.
The existing collector represents the boot CPU register image intended for
secondaries, not an independent register read from every secondary.

Before copying guest data, a pure planner keeps ADT/FD/bootargs at their fixed
Mu pointers and packs TC, SEPFW and optional log after the 16 KB bootargs slot.
The arena ends at the earlier framebuffer/ramdisk base, not at an artificial
gap before the FD or bootargs. It rejects overflow or overlap before copying.
The unused FD tail is filled using the FDF erase polarity. Mu removes both
boot-data intervals adjacent to the FD from allocatable resource HOBs and adds
reserved allocation HOBs through `top_of_kernel_data`. Failure to find a covering
resource HOB is an error. The PrePi stack is fully cleared, page aligned, and
its original base/size survive cache calls. Real source/property sizes and
planned addresses are printed on each launch.
The host allocator is capped below guest RAM. Live source buffers, loader,
framebuffer and the five T8112 DCP reservations named by kboot.c must be disjoint
from guest RAM. Source reads use full physical DRAM bounds and reject actual MCC protected regions, matching the owning m1n1 MMU contract. Guest allocation still uses normal usable RAM; accepting a display carveout for a source read does not make it guest-allocatable. The exact EXP017 photo values pass the production guard and planner under sanitizers. Oversized, missing or conflicting inputs stop with a named message.
Reservations remain runtime-tested hypotheses; a build does not prove that
Apple's live allocations, all firmware carveouts or DMA contracts are safe.

Shared m1n1 CPU/power/vGIC, USB1/DART, NVMe and display code is inherited for this
first experiment. The patch does not establish their M2 runtime correctness.
The independent M2 RTKit/HID protocol cores are not linked Windows drivers.

## Recovery and the next physical checkpoint

An existing Asahi UEFI installation can provide the machine-personalized stage 1;
a new Asahi installation is not a prerequisite. First identify the screen actually
reached by that entry and the payload it loads. An entry named `UEFI boot`, or an
APFS `Bootable` flag, alone does not identify U-Boot, Mu or Windows progress.

EXP-20261011-J413-012 inspected the original Finish Installation resource, not the
active personalized kernel. It has an m1n1 v1.9.9 marker and a `chainload=` setting
whose PARTUUID matches the existing internal ESP and whose path is `m1n1/boot.bin`.
The preserved ESP copy contains a nested autonomous Windows image, SHA-256
`6c6f7c9d7fd532b9475f07ed2828987fc25a9cbe25f6b7f9d7803a43f2d6983e`.
Its two manifests decode correctly, but its flags, Mu FD and provenance differ
from this clean candidate. It is not established as a working M2 baseline.
Neither these bytes nor the stage-1 staging file prove what the current boot
policy actually launches.

The preferred integration path, if that existing stage 1 is active, is a backed-up
replacement of the assigned internal ESP's `m1n1/boot.bin`. It preserves stage-1
personalization. An earlier macOS mount attempt failed; the operator has since supplied a photo
of the no-proxy launch. The current mount state and exact installed hash were
not independently inspected. This audit performed no ESP update.
Verify a writable mount and the live old payload before choosing this path;
retain a byte-identical recovery copy and record a separate install experiment.
The raw nested candidate is not a PE/COFF `BOOTAA64.EFI` executable to copy onto
an external drive or launch from a U-Boot UEFI menu. Mu runs under the m1n1 guest
shim in this project; generic UEFI availability does not qualify Windows.
[Official Asahi boot-process documentation](https://asahilinux.org/docs/alt/boot-process-guide/)
describes the personalized stage 1, assigned internal ESP and external UEFI media.

Direct raw-kernel personalization into the existing APFS stub remains an alternate
route when an ESP update cannot be made. It requires the stub's **paired recoveryOS
in 1TR** and changes the boot kernel/path. The locally inspected Asahi
`Finish Installation.app/.../step2.sh` enforces that pairing, requests owner
credentials for bputil/kmutil and ends with a user-confirmed reboot. Do not invoke
it unattended or target the active macOS system volume. Existing UEFI alone does
not require rerunning this step. The previously prepared private Recovery commands
are conditional on deliberately selecting this alternate route. No replacement
or personalization occurred; the mounted APFS stub stayed read only.

Preserve the original raw-kernel staging file and the separately captured
internal ESP image. Returning to macOS uses the power-button startup picker.
Restoring the original staging file also requires rerunning the appropriate
Recovery personalization; a copied backup alone does not restore LocalPolicy.

First run without starting Windows installation. Capture the last visible
J413/PREFLIGHT line or Mu UEFI screen. A failed gate, black screen or reboot is
an inconclusive experiment requiring the actual trace, not permission to remove
checks. If it reaches UEFI, qualify a firmware-visible USB disk next, then ARM64
Windows Setup. The external SSD is currently on physical USB0, while this guest
exposes USB1. Changing to the other port is a separately recorded physical
checkpoint and does not by itself establish controller/DART correctness.

The external exFAT Setup copy and prepared FAT32 sparse image are unchanged.
A physical FAT32 installer partition is still required by the planned media
route; destructive exFAT reconstruction and Windows deployment have not been
performed. See [external setup evidence](J413_EXTERNAL_SETUP.md).

EXP018 photographs Windows Boot Manager Recovery (0xc000000f) with the preceding candidate; exact installed hash was not supplied. The current candidate additionally changes J413 boot presentation only. See [boot UI and recovery limits](J413_BOOT_UI_AND_RECOVERY.md). It has not been physically launched.

EXP019/020 current candidate is text-only: no Windows-like mark or bar. Pre-GOP firmware UART lines use the guest surface, then stop at explicit GOP takeover; invisible host framebuffer logging is disabled. Automatic J413 Setup selection requires all four payload paths and permits removable BlockIo. External FAT32/DMA and built-in input remain unqualified; see the current [UI and media notes](J413_BOOT_UI_AND_RECOVERY.md).


## EXP064: NVMe binding console diagnostics

IMG_6347 shows successful root enumeration and one synthetic PCI function, then
no return after `NVMe controller entered` for the operator's one to two minutes.
This is before Windows/WIM entry. The new diagnostic only routes the existing
NVMe DXE debug messages to the physical console; it is not a confirmed NVMe fix.
Source review: investigation/analysis/2026-11-06-nvme-console-plan.md.

Run on macOS, enter the owner password directly in Terminal:

```bash
bash scripts/install-j413-nvme-console.command
```

Pinned bootstrap SHA256:
`ce99784c8fa96560f896c48bdf26237e735f7f38d3b2fc12e7e9b4048e3def26`.
The installer verifies manifest and exact internal ESP, preserves bootstrap and
firmware/media companions, and updates firmware only. Windows WIM and install
parts are verified and retained. Explicit native FAT mounting is permitted only
for firmware-only/restore when Disk Arbitration fails; no filesystem repair.
Private mounts must unmount successfully or the command fails. The exact
recovery command is printed, including native fallback when selected.

After successful installation, one owner cold launch through HackWinDos UEFI
should show NvmExpressDriverBindingStart and controller/Identify/queue messages
or the actual assertion. Photograph the last screen with elapsed time. No agent
reboot; no new native result is claimed. Original Setup-reaching bootstrap and
matching FD/manifest are at .local/recovery-20261106-before-nvme-console.
