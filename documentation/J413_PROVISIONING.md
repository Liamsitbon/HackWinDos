# Re-create the measured J413 internal UEFI environment

The operator explicitly requested proceeding with a real boot environment after
the former Asahi/UEFI installation was deleted. This script is a bounded profile
for the measured Mac14,2 with the 256GB Apple SSD and the original three-partition
ISC/macOS/Recovery layout. It stops for a different layout, existing UEFI install,
other disk capacity, wrong source volume, or changed upstream bytes.

```sh
python3 scripts/provision-j413-uefi.py --plan-only
python3 scripts/provision-j413-uefi.py --launch
```

The second command opens Terminal. It preserves the generated local installer
image on the connected USB, verifies the copy, and replaces its original path
with a symlink. Original Microsoft installer files remain at the source. It
then requests administrator authentication through the normal Terminal prompt;
owner authentication for Apple's `bless` is also performed in that Terminal.
Passwords are never sent to the change/experiment ledger.

The reviewed Asahi v0.9.2 archive and UEFI-only package are hash-pinned. The
unmodified official installer owns APFS/stub creation, vendor firmware,
boot-policy preparation and owner authentication. A narrow adapter selects only
the internal measured store and a 9.5GB FAT ESP, labels the new environment
`HackWinDos UEFI`, and sets the macOS container to 233GB (1MiB aligned). It
preserves ISC and Recovery and disables the whole-disk, alternate-disk and
existing-container actions. It never triggers shutdown/reboot or telemetry.

This measured allocation leaves about 34GB free in macOS after moving the
generated image. The wrapper checks a 32GB macOS free-space floor and Apple's live preferred APFS minimum, and now requires an additional 8GB of build
headroom before a future provisioning run. This is an explicit deviation from Asahi's ordinary
38GB free-space policy; it is scoped to this requested development profile.
The completed run initially passed the 32GB planning check, but compiler/VM
activity later left about 27.5GB free. That observed result is retained in the
ledger; the added 8GB admission reserve corrects the insufficient planning
margin for future runs. It does not retroactively change the completed result.
If the actual freed space or resize limits differ, provisioning stops.

After the official host installation, the script reads the **new** ESP PARTUUID,
rebinds/rebuilds the direct firmware for that identity, and uses the existing
transactional installer to back up the official bootstrap, stage complete Setup
on the same ESP and replace the candidate atomically. Build and install phases
append before/after records to `investigation/EXPERIMENTS.md`. Failed provisioning
is not automatically erased, repaired or retried.

Apple's owner-authenticated Recovery enrollment is still required after host
installation. Native Windows boot, USB input/storage and GPU acceleration remain
separate, unqualified checkpoints. The wrapper's success message must not be
interpreted as those outcomes.

Source inspection: official asahi-installer `e93743d52178b3e26e428fa05174ef549abf30cb`
and the actual v0.9.2 package `main.py`, `diskutil.py`, `osinstall.py`, `stub.py`,
`system.py` and boot chain. The adapter calls the official MIT-licensed runtime;
it does not copy a Linux driver or change hardware register/IRQ/DMA behavior.
The full upstream license remains in the pinned installer archive. The current
source/disk plan and byte identities are saved privately under `.local/asahi-uefi`.
Recovery is the original macOS boot chain plus the retained official bootstrap
and manifested development images.
