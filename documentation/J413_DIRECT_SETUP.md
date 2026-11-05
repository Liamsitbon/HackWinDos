# J413 direct Windows Setup

This is an experimental software build and a prepared local installer volume.
**Native M2 Windows boot, accelerated graphics and built-in input remain
unqualified.** The last physical trial did not enumerate usable USB storage.
No newer physical boot or Windows Setup screen has been observed.

The direct path connects the registered PCI roots for the synthetic NVMe, then
resolves one explicitly configured GPT partition UUID. It opens only
`\EFI\BOOT\BOOTAA64.EFI` on that partition, without a filename case distinction,
and requires an ARM64 PE32+ EFI application. A duplicate target UUID is rejected.
It retains standard BDS image/security checks and the bounded discovery deadline.

## Single-volume contents

A FAT32 volume contains all of the following:

```text
m1n1/boot.bin
m1n1/J413_EFI.fd
EFI/BOOT/BOOTAA64.EFI
EFI/Microsoft/Boot/BCD
boot/boot.sdi
sources/boot.wim
sources/install.swm
sources/install2.swm
setup.exe
J413Setup/MEDIA.json
J413Setup/FIRMWARE-MANIFEST.json
```

The staging tool also preserves the normal Microsoft Setup boot, resource,
language and support files. The large install WIM is split at 3800MiB for FAT32;
each resulting file must be below 4GiB. Every boot/install WIM image must declare
ARM64. Copied file hashes, WIM verification and split-part hashes are recorded.
Automatic unattended installation files and the old unqualified `Drivers`
directory are omitted.

The current development artifact uses a new 12GiB local sparse image, not the
2GB physical `M2BOOT` partition. That partition is too small for the full source.
The image is not directly selectable in Apple's startup picker. It is not an
enrolled internal Asahi/UEFI environment.

## Explicit target and build

Obtain the intended FAT partition's PARTUUID from current disk metadata. Do not
reuse an old `diskNsM` identifier or a UUID copied from another machine/image.

```sh
python3 tools/j413_direct_setup.py --partition-uuid YOUR-PARTITION-UUID
scripts/build-j413-boot-experiment.sh
```

The generated target header is included in the source digest, and the firmware
manifest records `direct_setup.partition_uuid`. The development header currently
names only the local staging image. Rebinding a different internal volume
requires a rebuild; copying its files alone does not change the target identity.

## Prepare an existing volume

Use a FAT32 volume with sufficient free space, about 9GB for the current source.
The script does not format or create partitions and refuses different existing
files before copying. The first command checks identity without changing files.

```sh
python3 tools/j413_setup_bundle.py --source /Volumes/WININSTALL \
  --volume /Volumes/YOUR-VOLUME --partition-uuid YOUR-PARTITION-UUID
python3 tools/j413_setup_bundle.py --source /Volumes/WININSTALL \
  --volume /Volumes/YOUR-VOLUME --partition-uuid YOUR-PARTITION-UUID --apply
```

For an existing Asahi bootstrap, `--without-bootstrap` stages Setup data while
preserving its current `m1n1/boot.bin`. Do not overwrite a working bootstrap by
manually copying an entire development directory.

## Installation script

`scripts/install-j413-direct-setup.py` verifies the image, nested profile,
current source contract, exact partition UUID and same-volume payload hashes.
It preserves a verified recovery copy before replacing the bootstrap atomically.
It never creates partitions or reboots. Use offline verification first:

```sh
/usr/bin/python3 scripts/install-j413-direct-setup.py --verify-only
```

For a separately prepared internal Asahi/UEFI ESP, the explicit installation
form is:

```sh
sudo /usr/bin/python3 scripts/install-j413-direct-setup.py \
  --esp-uuid YOUR-PARTITION-UUID --image-sha256 YOUR-RECORDED-BUILD-SHA256 \
  --setup-source /Volumes/WININSTALL
```

The target must already exist, be an internal FAT ESP and match the rebuilt
firmware. The old Asahi/UEFI installation has been deleted on the current host;
no replacement was installed by this work. The standard small ESP also cannot
hold this complete installer. A suitably sized environment is a separate
deployment step. These commands are not evidence of a successful native boot.

## Driver state

| Function | Current owner or missing work |
| --- | --- |
| Basic display | Firmware GOP/basic Windows display; no M2 acceleration proof |
| USB and external input | Windows inbox USBXHCI/USBHUB3/USBSTOR/HIDUSB after valid platform DMA/IRQ/handoff; native runtime not tested |
| Internal storage | m1n1 synthetic NVMe plus inbox Windows storage; new M2 native run required |
| Built-in keyboard/trackpad | Portable DockChannel cores and incomplete KMDF adapter; MTP helper firmware, DART, IRQ/resource ownership and real HID translation remain |
| Accelerated graphics | Existing AGX work targets J313 contracts; J413 resources/firmware/broker contract not completed |
| Audio, Wi-Fi, Bluetooth, camera | No complete Windows implementations in this checkout |
| Battery, power, external display | No completed J413 Windows runtime implementation |

Three DockChannel logic defects are corrected and covered by actual-source C
regressions: VHF error cleanup, D0 error propagation and distinct concatenated
frame consumption. This does not create the missing hardware transport adapter.
The Windows WDK workflow builds software artifacts only and labels them
unqualified.

`scripts/package-m2-drivers.sh --audit` reports actual gaps. A deployable package
requires real ARM64 native SYS/INF/CAT files; copying INF metadata alone fails.
The J313 SPI driver is excluded. The PowerShell installer checks hashes and
catalog trust, propagates PnPUtil errors and never claims all drivers are complete.

Aurora integration: [USB DART readback and compatibility boundaries](AURORA_INTEGRATION.md).
