# Hardware Experiment Ledger

This append-only ledger is the source of truth for J313 hardware experiments.
Chat transcripts are not a substitute. Every run is entered before launch and
completed after observation.

## Entry template

```text
### EXP-YYYYMMDD-NNN — short title

Status: planned | running | confirmed | rejected | inconclusive | superseded
Created (UTC): YYYY-MM-DDTHH:MM:SSZ
Completed (UTC): YYYY-MM-DDTHH:MM:SSZ

Hypothesis:
Single changed variable:

Source contract:
- Repository / branch:
- Root commit / diff SHA-256 / dirty:
- m1n1 commit / diff SHA-256 / dirty:
- Mu commit / dirty:

Artifact:
- Build command:
- Path:
- Profile:
- SHA-256:
- Recovery artifact:

Run contract:
- Install/launch command:
- Expected checkpoint:
- Failure criterion:
- Evidence paths:

Observed result:
- Boot timing/phases:
- CPU/timer/interrupt evidence:
- Windows stop code:
- Display/input/SSH/RDP/storage:

Verdict:
Next experiment:
```

## Experiments

### EXP-20260813-001 — first passive-monitor hot-path gating run

Status: rejected
Created (UTC): 2026-08-13
Completed (UTC): 2026-08-13

Hypothesis: keeping lock-free monitor snapshots while suppressing most synchronous
diagnostic output would retain observability without disturbing Windows timer
progress.

Single changed variable: the monitor build gated runtime trace output, but this
first artifact still emitted bounded SGI queue messages and was therefore not yet
fully passive.

Source contract:
- Repository / branch: `/Users/pavel/public_windows`, `codex/canonical-public-release`
- Exact source hashes were not preserved in the earlier run metadata; this omission
  is the reason the mandatory ledger rule now exists.

Observed result:
- All eight guest CPUs came online.
- SSH did not become available within 120 seconds.
- The artifact emitted 32 `HV SGI QUEUE` messages.
- Windows stopped with `CLOCK_WATCHDOG_TIMEOUT (0x101)`.
- Bugcheck parameters identified CPU4, the first performance core, as the stalled
  processor: `P1=0x18`, `P2=0`, `P4=0x4`.
- CPU4-CPU6 snapshots contained virtual timer LR state active+pending, including
  `LR1=0x9020020000000012` for INTID 18. CPU4's timer was overdue and its last
  IAR/EOI progress was older than the continuing efficient-core activity.
- Evidence was captured in the assisted-run `hv.log`; the log is append-only and
  must be sliced by byte offset for future comparisons.

Verdict: rejected. The run proves a real P-cluster virtual-timer delivery stall,
but it cannot isolate timer policy from the remaining synchronous SGI logging.

Next experiment: run EXP-20260813-002 with every known synchronous SGI,
timer-rate, spurious-IAR, and PCI configuration trace gated off while preserving
the monitor snapshots. Do not change heartbeat frequency in the same run.

### EXP-20260813-002 — fully passive monitor build

Status: rejected
Created (UTC): 2026-08-13
Completed (UTC): 2026-08-13

Hypothesis: the remaining synchronous hot-path trace output causes or materially
amplifies the P-core timer stall; a fully passive monitor should boot Windows while
retaining post-failure snapshots.

Single changed variable: `HV_RUNTIME_TRACE` and the remaining SGI queue,
timer-rate, and spurious-IAR prints require verbose diagnostics. Timer heartbeat
policy is intentionally unchanged.

Source contract:
- Repository / branch: `/Users/pavel/public_windows`, `codex/canonical-public-release`
- Root commit: `824410251e03b8a112d6b187d8b7dbe3ef1b3388`
- Root diff SHA-256: `d47b954fd051f5114659b63e4413d874fe2b4314fa0dadeb73281278dcc2b81a`
- m1n1 commit: `6dc04339570d272e305b5c94d1ba57ee84d35497`
- m1n1 diff SHA-256: `fa186a43523dcd94d6103668a462eba70a6ac8fa2987de401643862823df52d2`
- Mu commit: `63942398cccbd98127cfecbd7f936af99c837d6f` (clean)

Artifact:
- Build command: `STANDALONE_SKIP_MU=1 ./scripts/build-standalone.sh --debug-build --display physical --debug monitor --apple-input on`
- Path: `/Users/pavel/public_windows/dist/j313/debug-monitor/boot.bin`
- Assisted m1n1: `/Users/pavel/public_windows/dist/j313/debug-monitor/m1n1.macho`
- Guest firmware: `/Users/pavel/public_windows/dist/j313/debug-monitor/J313_EFI.fd`
- Profile: J313, physical display, monitor diagnostics, 8 CPUs, Apple input exposed
- `boot.bin` SHA-256: `7a23a385cb781c1e59036e7b96a81b1ea022311c0d7e82b916e962098a3a855f`
- `m1n1.macho` SHA-256: `aa0334f895b1733b1bc798a736b959aefe8a5277324445a7ebcfb0f7860c38e2`
- `J313_EFI.fd` SHA-256: `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`
- Recovery artifact: the previously hardware-validated production image must remain
  installed or locally available before any standalone installation. This run is
  assisted first and does not replace the ESP image.

Run contract:
- Launch command: `./scripts/run-assisted.sh --proxy
  <CONSOLE_DEVICE> --vuart <VUART_DEVICE>
  --chainload --m1n1 dist/j313/debug-monitor/m1n1.macho --firmware
  dist/j313/debug-monitor/J313_EFI.fd --display physical --debug monitor
  --foreground`.
- Expected checkpoint: all 8 CPUs online, no synchronous PCI/SGI/TIMERRATE trace,
  Windows login and SSH reachable without `0x101`.
- Failure criterion: frozen Windows spinner, missing SSH after 120 seconds, any
  watchdog bugcheck, or recurring active+pending overdue P-core timer state.
- Evidence: `/Users/pavel/public_windows/hv.log`, UART output, Windows minidump if
  produced, and elapsed time to SSH. The public runner truncates `hv.log` when it
  starts, so this experiment owns the complete new file. The initially recorded
  byte offset `118920` applied to the pre-launch file and must not be used.

Observed result:
- The public runner validated the J313 artifacts and launch contract, then
  truncated `hv.log`; the complete run is therefore in that file rather than an
  append-only byte slice.
- Mu reached `bootmgfw.efi`; all eight guest CPUs entered Windows.
- Synchronous trace counts were all zero: `PCI cfg=0`, `HV SGI QUEUE=0`, and
  `TIMERRATE=0`.
- SSH was still unavailable after 109 seconds of probing. No reset or bugcheck had
  occurred at that point.
- A non-destructive Ctrl-C monitor snapshot showed CPU4 and CPU6 with virtual timer
  INTID 18 active+pending (`LR0=0x9020020000000012`), masked timer routing, and
  deeply overdue virtual deadlines. CPU2, CPU3, and CPU5 had current timer progress;
  CPU4 and CPU6 had stale IAR/EOI progress. The guest continued after the snapshot.
- Evidence copies: `/tmp/exp-20260813-002-hv.log` and
  `/tmp/exp-20260813-002-hv-after-snapshot.log`; canonical live log:
  `/Users/pavel/public_windows/hv.log`.

Verdict: rejected. Removing synchronous trace output did not eliminate the boot
stall. It strengthens the conclusion that the P-cluster virtual-timer recovery path
is the root defect; trace overhead was secondary.

Next experiment: increase only the secondary recovery heartbeat from 100 Hz to
1000 Hz, add/update its regression test first, and repeat the same assisted monitor
launch. Do not change LR state transitions in the same experiment.

### NOTE-20260813-001 — host-test invocation correction

The Python vGIC trace contract completed successfully (`8/8`). A subsequent direct
`make` invocation in the nested test directory accidentally used the macOS hosted
clang environment and failed on freestanding `uintptr_t`, `ptrdiff_t`, and `ssize_t`
typedef collisions. This was an invalid test invocation, not a runtime-diag source
failure. Future full nested tests must use
`m1n1_windows/tests/run_host_tests.sh`; do not invoke an assumed Makefile target.

Correction: the script itself resolves source paths relative to the nested m1n1
repository root. The exact valid invocation is `cd m1n1_windows &&
./tests/run_host_tests.sh`. Running it from the public repository root also fails
with missing relative source paths.

### EXP-20260813-003 — 1 ms secondary recovery heartbeat

Status: confirmed
Created (UTC): 2026-08-13T17:12:20Z
Completed (UTC): 2026-08-13

Hypothesis: on T8103 without ECV, a 100 Hz secondary EL2 housekeeping heartbeat
does not recover a masked physical timer route and active+pending guest timer LR
quickly enough. A 1000 Hz heartbeat will bound recovery to 1 ms and prevent the
observed CPU4/CPU6 stalls without restoring the old 5000 Hz all-core overhead.

Single changed variable: `HV_FALLBACK_SECONDARY_TICK_RATE`, from 100 Hz to 1000 Hz.
No LR transition, vGIC, SGI, display, NVMe, Mu, or Windows setting changes are part
of this experiment.

Source contract:
- Repository / branch: `/Users/pavel/public_windows`, `codex/canonical-public-release`
- Root commit: `824410251e03b8a112d6b187d8b7dbe3ef1b3388`
- Root diff SHA-256 at artifact capture:
  `e3328a4124411d285bab793aded132ed914125869f49280a67fca0211456052b`
- m1n1 commit: `6dc04339570d272e305b5c94d1ba57ee84d35497`
- m1n1 diff SHA-256 at artifact capture:
  `5f4fc2fd34af6ac65fdd33d3c8c1b7b26e57b424142f8fb3d98b81fee54741a3`
- Mu commit: `63942398cccbd98127cfecbd7f936af99c837d6f`; Mu source is unchanged by
  this experiment.

Regression evidence:
- RED: the full nested harness passed all preceding tests and stopped at
  `hv_tick_policy_test` asserting that the no-ECV secondary rate must be 1000 Hz.
- GREEN: after changing the policy, the complete valid invocation
  `cd m1n1_windows && ./tests/run_host_tests.sh` passed.

Artifact:
- Build command: `cd m1n1_windows && PATH="$(brew --prefix rustup)/bin:$PATH"
  make -j8`.
- m1n1 path: `/Users/pavel/public_windows/investigation/artifacts/EXP-20260813-003/m1n1.macho`
- m1n1 SHA-256: `7e30162ea81247fe79940f0d8074679da3867db154824b62d317614b32986da2`
- Mu path: `/Users/pavel/public_windows/investigation/artifacts/EXP-20260813-003/J313_EFI.fd`
- Mu SHA-256: `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`
- Profile: assisted J313, physical display, passive monitor diagnostics, 8 CPUs,
  Apple input exposed but its Windows driver not installed.
- Recovery: assisted launch only; the ESP standalone image is not replaced.

Run contract:
- Launch: public `scripts/run-assisted.sh` with `--chainload`, the two recorded
  artifacts above, `--display physical --debug monitor --foreground`.
- Expected checkpoint: log reports `boot=1000Hz secondary=1000Hz`, all eight CPUs
  enter Windows, login and SSH become available, and repeated snapshots contain no
  deeply overdue P-core timer LR.
- Failure criterion: frozen spinner/login, SSH unavailable after 120 seconds,
  `CLOCK_WATCHDOG_TIMEOUT`, or stale active+pending timer state on CPU4-CPU7.
- Evidence: newly truncated `/Users/pavel/public_windows/hv.log`, UART, elapsed SSH
  time, and Windows dump if one is produced.

Observed result:
- Artifact preflight and manifest verification passed. Runtime reported
  `boot=1000Hz secondary=1000Hz`; all eight CPUs entered Windows.
- SSH was not reachable at the initial 143-second boundary but appeared during the
  immediate follow-up, approximately 2.5-3 minutes after handoff. This is too slow
  for a performance success criterion but differs from the unrecoverable EXP-002
  stall.
- The post-boot snapshot showed no active+pending timer LR on any CPU: every LR on
  CPU1-CPU7 was zero, timer mode was unmasked/idle, and queue/drain/IAR/EOI counters
  converged. CPU4 and CPU6 no longer reproduced the stale deadline seen in EXP-002.
- Windows reported 8 processors. Five fresh SSH command latencies were 3597.9,
  523.8, 611.4, 593.4, and 3121.8 ms.
- No bugcheck or reset occurred and synchronous trace counts remained zero.
- Preserved log: `investigation/artifacts/EXP-20260813-003/hv.log`, SHA-256
  `b6ee38455b2b13d586d6f5af97be8158c44a0b023d8204767381a588cb343a24`.

Verdict: confirmed for the narrow timer-recovery hypothesis. A 1 ms secondary
heartbeat removes the reproduced active+pending P-core timer stall. It does not yet
prove acceptable boot time, latency, stress stability, or overall smoothness.

Next experiment: a separately recorded short all-core CPU load followed by another
lock-free timer/vGIC snapshot. Do not change code between the idle and load samples.

### EXP-20260813-004 — short all-core load on the 1 ms heartbeat build

Status: planned
Created (UTC): 2026-08-13
Completed (UTC): pending

Hypothesis: EXP-003 will keep all eight CPUs and their virtual timers progressing
during a bounded 10-second all-core load without `CLOCK_WATCHDOG_TIMEOUT` or an
active+pending overdue timer LR.

Single changed variable: runtime CPU load only; source, binaries, Mu, display,
diagnostics, and heartbeat are identical to EXP-003.

Artifact and source contract: exactly EXP-20260813-003. No rebuild. Use the recorded
`m1n1.macho` SHA-256 `7e30162e...86da2` and its preserved manifest.

Run contract:
- Start eight bounded PowerShell worker jobs over SSH for 10 seconds.
- Verify command completion and SSH availability.
- Immediately capture a non-destructive Ctrl-C monitor snapshot.
- Failure criterion: command timeout, lost SSH, reset/bugcheck, non-converged queues,
  or overdue active+pending virtual timer on any CPU.
- Evidence: the EXP-003 live `hv.log`, copied after the load to the EXP-004 artifact
  directory, plus the SSH duration and result.

Observed result: `kd_liveness.py` sent break-in but received no `STATE_CHANGE64`
within its timeout. Its `finally` path sent KD Continue. No guest reboot or source
change was performed.

Verdict: inconclusive. The virtual UART/KD transport was unavailable in this state;
this does not prove that the Windows kernel stopped, especially because lock-free
vCPU counters had advanced between the preceding snapshots.

Next experiment: resolve the repeated sampled Windows PCs using preserved local
PDB/symbol artifacts. If unavailable, add a lock-free, bounded kernel-base capture
to the monitor rather than increasing synchronous logging.

Offline follow-up:
- Local-only Windows 26100.8037 artifacts were found in the legacy investigation:
  `ntoskrnl.exe` SHA-256
  `5bb49f8383e38b26ef0c18f3087db3be541e99143b80b92d2f83d824b7e5301c` and
  `ntkrnlmp.pdb` SHA-256
  `3a2346d8beb860b74978805c7950ecd0c03f8ce2da32f8df8395835ba09aa090`.
  They are proprietary and must not be copied or committed to the public repository.
- The observed boot PCs and those symbols identify the current kernel base as
  approximately `0xfffff80145800000`.
- Repeated sampled locations resolve to `KiDirectSwitchThread+0x67c`,
  `RtlpImageDirectoryEntryToDataEx+0x28/+0xcc`, and
  `RtlpAmd64xVirtualUnwind+0x398`. Earlier entry samples resolve around
  `KiThawSingleThread`. These samples show real scheduler/unwind progress rather than
  every CPU sitting in one fixed watchdog loop. They do not explain why EOIR progress
  later stops; the next diagnostic must correlate per-CPU LR transitions with trapped
  IAR/EOIR without synchronous logging.

### CORRECTION-20260813-002 — EXP-003 is not a complete timer fix

The first EXP-003 snapshot showed clean LRs and was sufficient to confirm that the
1 ms heartbeat can recover the specific initial stall. It was not sufficient to
claim that the timer defect was eliminated. After the successful SSH probes, SSH
disappeared again. A second non-destructive snapshot showed that every CPU had made
substantial queue/IAR/EOI progress since the first snapshot, proving the guest had
continued to execute, but active+pending INTID 18 returned on CPU0, CPU1, and
CPU4-CPU6. Therefore EXP-003 remains confirmed only for temporary recovery of the
first reproduced stall; it is rejected as a complete fix for sustained operation.

The next code experiment must address the timer LR/EOI state machine using the ARM
GIC architectural contract. Raising heartbeat frequency again is not justified by
this evidence.

### RESULT-20260813-004 — load did not start

Status: inconclusive
Completed (UTC): 2026-08-13

The bounded PowerShell load was never executed: the SSH connection timed out before
the remote command began. This result says nothing about stress stability. The
second hardware snapshot taken after the timeout proves vCPU counters advanced, so
the loss of SSH was not an all-core halt at the instant of capture. Preserve this as
a failed test setup, not as a failed CPU stress test.

### EXP-20260813-005 — KD classification of the sustained stall

Status: planned
Created (UTC): 2026-08-13
Completed (UTC): pending

Hypothesis: Windows is still executing but one or more kernel threads remain in an
interrupt/timer path that never reaches the emulated EOIR, explaining recurrent
active+pending INTID 18. Resolving the sampled PCs and Windows thread state will
distinguish a vGIC lifecycle defect from an unrelated USB/network loss.

Single changed variable: none. This is a read-only classification of the running
EXP-003 guest. Stop only the host UART log reader so KD can own the same virtual UART;
do not rebuild, reboot, or alter Windows configuration.

Run contract:
- Use `tools/kd/kd_liveness.py`, then obtain the kernel base/module and relevant
  execution state with the existing KD tools.
- Every KD operation must send Continue in `finally` so diagnosis cannot leave the
  guest paused.
- Restore passive UART capture afterward if additional boot logging is required.
- Evidence: KD output plus the two EXP-003 lock-free snapshots already in `hv.log`.

Failure criterion: no KD state-change response within the tool timeout. Such a result
is inconclusive and must not be interpreted as a dead Windows kernel because the UART
transport may itself be unavailable.

Observed result: pending.
Verdict: pending.

### RESULT-20260813-005 — KD transport did not classify the stall

Status: inconclusive
Completed (UTC): 2026-08-13

`kd_liveness.py` opened the virtual-UART transport and issued a break-in, but no
`STATE_CHANGE64` packet arrived before its bounded timeout.  Its cleanup path sent
Continue and the passive UART reader was restored.  This did not change source or
guest state and cannot distinguish a stopped Windows debugger transport from a
guest scheduler/timer stall.

### EXP-20260813-006 — exact-source A/B against the accepted morning baseline

Status: in progress
Created (UTC): 2026-08-13

Hypothesis: the recurrent long freezes are a regression introduced after the
accepted 2026-08-13 eight-core checkpoint, rather than a failure of its original
timer/IPI and vGIC correction.  Returning only the assisted m1n1 source to commit
`55531e9d9443e2543e172ed4c7f6ef8a7173a54e` while retaining the byte-identical Mu
firmware will restore the accepted behavior.

Single changed variable: m1n1 binary source.  The preceding EXP-003 guest used the
current dirty diagnostic/input tree.  EXP-006 uses a clean temporary clone at
`55531e9`; Mu remains SHA-256
`0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`.

Baseline provenance:
- Root release record: `5d827ba6b7f50daf538df0a167ed123c9a1f5731`.
- Root gitlink: m1n1 `55531e9d9443e2543e172ed4c7f6ef8a7173a54e`, Mu
  `9dccb0133f244f2e4de7e3862dcb9f0ef7ba4776`.
- The original accepted m1n1 binary SHA `7b735bf1...956d40` is documented but is no
  longer present in `dist/` or `.local/`.  It must not be silently substituted.
- A clean rebuild from the exact m1n1 commit produced SHA-256
  `3bfd9cc8080fc28a381a4c8fce39b5feeb093290b55caa928c8b6d745f069c6c` in
  `/private/tmp/wom1-baseline-55531e9.WLOUx1/m1n1_windows/build/m1n1.macho`.

Preceding failure evidence:
- The final EXP-003 snapshot showed CPUs 0, 1, 4, 5, and 6 retaining virtual timer
  INTID 18 as Active+Pending while their queue/IAR/EOI counters stopped advancing.
- A later SIGTERM snapshot showed the same retained LRs and almost unchanged
  counters; the managed handler then rebooted the Air and returned both USB ports.
- The observed Windows PCs were in scheduler/image-unwind code.  The evidence is
  consistent with the user-visible global pause but does not yet identify which
  post-baseline source change caused it.

Run contract:
- Assisted public launcher; physical display; passive monitor diagnostics; eight
  CPUs; no virtual framebuffer; no AppleInput Windows driver.
- Expected checkpoint: all eight CPUs enter Windows, desktop/SSH becomes available,
  and a bounded idle interval plus snapshots do not reproduce stopped EOI counters
  with overdue Active+Pending timer LRs.
- Failure criterion: frozen spinner/desktop, SSH loss after initial availability,
  watchdog bugcheck, or the same non-advancing LR/counter state.
- Recovery: SIGTERM to the foreground public runner, which captures a final snapshot
  and reboots to proxy.  The ESP is not modified.

Intermediate result:
- The clean `55531e9` m1n1 chainloaded and identified itself on hardware.  It
  initialized the physical panel and returned to proxy successfully.
- All seven physical secondary CPUs reported `Started` during host bootstrap.
- Before guest handoff, the current post-baseline Python launcher raised
  `RuntimeError: secondary CPU startup failed`.  No Windows code ran and this is
  not a baseline stability result.

Verdict so far: test setup rejected.  Reverting only the target binary is not a
valid A/B because the host proxyclient/preflight contract changed after the
  baseline.  Repeat with matching root `5d827ba` launcher and m1n1 `55531e9`; retain
  the identical Mu and hardware/profile variables.

Matching-runtime result:
- A clean matching root `5d827ba` launcher plus clean m1n1 `55531e9` passed host
  preflight and entered Windows Boot Manager.
- CPU0 entered the guest.  CPU1 then stopped after
  `Secondary 1 published entry=...`; `hv_init_secondary` never completed and no
  further secondary CPU entered Windows for more than two minutes.
- SIGTERM also stalled because its rendezvous required the same non-responsive CPU.
  Host processes were terminated and a physical reset was required.

Verdict: rejected as a complete stability baseline.  The morning accepted session
was real, but the same committed source still contains an intermittent secondary
mailbox/wakeup race.  Its own documentation correctly described it as a development
checkpoint with the repeated-cold-boot production gate still open.

### EXP-20260813-007 — atomic secondary mailbox and WFI-to-WFE transition

Status: rejected on hardware
Created (UTC): 2026-08-13

Hypothesis: CPU1 can sleep in the old deep-WFI loop while the boot CPU publishes
plain C `wfe_mode=true` and subsequently uses only SEV for mailbox notification.
SEV does not release that WFI waiter, leaving `smp_call4()` blocked after the
secondary entry is published.  Plain target/flag accesses also form a C data race.

Single changed variable: starting from clean m1n1 `55531e9`, make `wfe_mode`, the
mailbox target, and completion flag use release/acquire atomics; on mode transition,
send a physical IPI to every alive secondary before relying on SEV/WFE.  No timer,
vGIC, PSCI, Mu, display, input, NVMe, or Windows change is included.

Regression evidence:
- RED: two targeted tests failed on the absent release/acquire publication and
  non-atomic WFE transition.
- GREEN: the targeted eight-test secondary suite passed, followed by the complete
  `m1n1_windows/tests/run_host_tests.sh` suite.

Artifact:
- m1n1: `investigation/artifacts/EXP-20260813-007/m1n1.macho`
- m1n1 SHA-256:
  `8ff5562d67cb4b9c462d20c5ddcc67f87909cfceb893ba8abbd8dab1aad918ac`
- Mu: `investigation/artifacts/EXP-20260813-007/J313_EFI.fd`
- Mu SHA-256:
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`
- Build: clean plain `make -j8` after `make clean` in the temporary exact-commit
  checkout, with only the recorded `src/smp.c` diff.
- Recovery: assisted only; physical display and passive monitor; ESP unchanged.

Expected checkpoint: all seven secondary calls reach `Entering guest secondary`
and all eight CPU_ENTRY records appear without any mailbox stall.  This experiment
does not claim to fix the later timer Active+Pending freeze.

Hardware result:
- The matching root `5d827ba` runtime reached Windows Boot Manager and published
  CPU1's guest entry.
- Immediately after `HV: Secondary 1 published ...`, both USB endpoints vanished
  and the machine reset to the proxy.  No `Entering guest secondary 1` marker was
  emitted.
- Disassembly showed that the atomic completion increment introduced an LSE
  `ldaddl` instruction in the first secondary mailbox path.  The reset coincided
  with the first opportunity to execute that changed path.  This is correlation,
  not proof that LSE itself caused the reset, so the entire atomic rewrite is
  rejected rather than retained as a partial fix.
- The original `smp_set_wfe_mode()` already sent an IPI to every live secondary
  before SEV.  Therefore the initial claim that transition used “only SEV” was
  incomplete and cannot explain the baseline race by itself.

Recovery: the Air reset to `Running proxy`; a bounded proxy NOP succeeded.  The
ESP and Windows installation were not modified.

### EXP-20260813-008 — retain IPI/WFI mailbox mode through PSCI bring-up

Status: rejected on hardware
Created (UTC): 2026-08-13

Hypothesis: `hv_init()` switches the m1n1 callback dispatcher to WFE before
Windows starts secondary processors.  `hv_start_secondary()` subsequently uses
three mailbox callbacks (`mmu_secondary_setup`, `hv_init_secondary`, and guest
entry), each awakened by one SEV and acknowledged only indirectly via `flag`.
Keeping the dispatcher in its original deep-WFI/IPI mode removes the unacknowledged
WFE event-register dependency while preserving the known instruction sequence on
the secondary.

Single changed variable relative to clean m1n1 `55531e9`:
- `hv_init()` calls `smp_set_wfe_mode(false)` instead of `true`.
- Bounded console markers surround the first `mmu_init_secondary()` mailbox so a
  failure can be classified as publish, callback execution, or completion.
- EXP-007's atomic mailbox rewrite is completely removed; ordinary loads/stores
  and the original explicit `dmb/dsb` protocol remain.

No timer, vGIC, PSCI topology, Mu, display, input, NVMe, or Windows change is
included.  Expected checkpoint: CPU1 prints both MMU mailbox markers and reaches
`Entering guest secondary 1`, followed by the other six secondaries.

Hardware result:
- CPU1 reached `HV: Secondary 1 MMU mailbox publish` but never reached the matching
  completion marker.  Both USB endpoints then disconnected and the Air reset to
  proxy.
- Keeping WFI/IPI mode therefore does not resolve the failure.  The fault is in,
  or is triggered while waiting for, `mmu_secondary_setup()` itself.

### EXP-20260813-009 — pre-initialize secondary stage-1 before guest entry

Status: rejected on hardware
Created (UTC): 2026-08-13

Hypothesis: the physical secondaries are powered before guest entry but their
stage-1 MMU is initialized only later, inside a Windows PSCI CPU_ON call.  That
callback performs broadcast TLB maintenance while CPU0 is already executing the
guest.  Initialize every live secondary's stage-1 MMU in `hv_init()` instead,
while m1n1 still owns all CPUs; PSCI then performs only per-CPU EL2/vGIC setup and
guest entry.

Single changed variable relative to clean `55531e9`: move
`mmu_init_secondary(cpu)` from `hv_start_secondary()` into a pre-guest loop in
`hv_init()`.  Keep the original barrier-based mailbox and original WFE mode; no
timer, vGIC, Mu, display, input, NVMe, or Windows change.

Hardware result:
- The Air reset immediately after `HV: Pre-initializing MMU on secondary 1`, before
  Mu or Windows was started.
- This proves that the failure is the secondary EL1 MMU setup itself, not guest
  concurrency, PSCI timing, WFE wakeup, or Windows.

### EXP-20260813-010 — leave PSCI secondary EL1 MMU disabled

Status: rejected on hardware
Created (UTC): 2026-08-13

Hypothesis: `mmu_init_secondary()` violates the PSCI handoff contract by enabling
m1n1's EL1 stage-1 regime on a CPU that must enter the Windows secondary startup
trampoline with `SCTLR_EL1.M` clear.  m1n1's dispatcher and `hv_init_secondary()`
execute at EL2 and do not need EL1 stage-1.  Remove the call entirely and let
Windows install its own EL1 translation regime.

Single changed variable relative to clean `55531e9`: remove
`mmu_init_secondary(cpu)` from the PSCI secondary path.  Keep the original SMP
barriers, WFE mode, timers, vGIC, Mu, display, input, NVMe, and Windows unchanged.

Hardware result: CPU1 still reset immediately after its entry was published.
Therefore the next callback, `hv_init_secondary()`, contains an independent reset
trigger.  Removing only EL1 MMU setup is insufficient.

### EXP-20260813-011 — minimal EL2-only secondary initialization

Status: rejected on hardware
Created (UTC): 2026-08-13

Hypothesis: `hv_init_secondary()` copies boot-CPU EL1/EL12 and GXF/SPRR state onto
a fresh PSCI CPU even though the guest startup trampoline expects reset-like EL1
state.  One of those implementation-defined writes resets the CPU/system before
the required EL2 state has completed.

Diagnostic A/B: retain required hypervisor state only (HCR, HACR, VTCR, VTTBR,
MDCR, ACTLR_EL2, CNTHCTL, CNTVOFF, timer routing, vGIC list registers, and EL2
heartbeat).  Temporarily omit GXF setup and copied EL1/EL12 AMX, PAuth, APSTS,
ACTLR, SPRR, GXF, and MDSCR state.  No Mu/Windows/display/input/NVMe change.

Hardware result: reset remained immediately after CPU1 entry publication.  The
trigger is therefore either one of the retained EL2 operations or the mailbox
callback/rendezvous itself.

### EXP-20260813-012 — empty secondary callback control

Status: inconclusive on hardware
Created (UTC): 2026-08-13

Control experiment: make `hv_init_secondary()` return without any register write.
If the Air still resets, the callback dispatch or the following guest-entry
mailbox is faulty.  If it does not, reintroduce required EL2 groups by binary
search.  This build is diagnostic only and is not expected to run Windows safely.

Hardware result: USB still disconnected after CPU1 publication, but the existing
log had no marker between callback completion and the immediately following guest
entry.  The result therefore cannot distinguish those adjacent operations.

### EXP-20260813-013 — hold CPU1 after empty callback

Status: rejected on hardware
Created (UTC): 2026-08-13

Control: retain the empty callback, print and flush a completion marker after
`smp_wait()`, then return from PSCI handling without entering CPU1 into Windows.
This deliberately leaves Windows waiting and is not a boot candidate.  It only
separates mailbox completion from `hv_enter_guest()`.

Hardware result: the completion marker was never emitted and USB disconnected.
An empty callback therefore was never executed; the failure is lost mailbox wake,
not secondary register programming or guest entry.

### EXP-20260813-014 — dual IPI+SEV mailbox notification

Status: successful mailbox fix on hardware; EXP-015 tests stricter IPI cleanup
Created (UTC): 2026-08-13

Hypothesis: a target can observe either side of the global WFI-to-WFE transition,
while `smp_call4()` chooses only one notification from the sender's current view.
The published callback then remains pending forever.  Make notification robust to
that race by always sending both a targeted IPI and SEV, and clear the IPI after
either sleep path returns.

Single changed variable relative to clean `55531e9`: SMP mailbox wake protocol.
No `hv.c`, timer, vGIC, PSCI, Mu, display, input, NVMe, or Windows change.

Hardware result:
- All seven secondary mailboxes completed and all seven cores reached guest entry.
  This removes the repeatable reset immediately after `Secondary 1 published` and
  confirms the WFI/WFE notification race.
- The first bounded log read initially contained `CPU_ENTRY` only for CPUs 2, 4,
  5, 6 and 7.  This was not a reset: the m1n1 proxy endpoint intentionally remains
  available while the guest runs, and `run_uefi.py` returning is normal.
- A later deliberate chainload interrupted the still-live hypervisor.  Its
  pre-rendezvous snapshot proved CPUs 1 and 3 were also online.  All eight CPUs
  had processed tens of thousands of SGIs with matching IAR and EOI counts; no
  no-LR backlog was present.  Never infer guest death from proxy presence or the
  launcher process exiting again.
- Network reachability was not evidence either: the tested Windows installation
  did not acquire/respond at the previously cached address during that window.
- The IPI acknowledgement still lived inside the sleep loop.  EXP-015 keeps the
  proven dual notification and tests stricter cleanup for a target that observes
  its mailbox before sleeping.

Artifacts:
- `investigation/artifacts/EXP-20260813-014/m1n1.macho`
- SHA-256 `9a17a7139a770c63daa5c422e203f1c64f3af913d2a6cca409bbc5e0afda9c53`

### EXP-20260813-015 — dual wake with unconditional IPI acknowledgement

Status: invalid mixed-runtime attempt; superseded by EXP-016
Created (UTC): 2026-08-13

Hypothesis: EXP-014 fixed wake delivery but left a stale physical IPI whenever a
secondary observed the mailbox without entering its sleep loop.  That IPI then
raced Windows' first virtual SGIs after guest entry.  Acknowledge the IPI once,
unconditionally, after the mailbox becomes visible and before executing the
callback.

Single changed variable relative to EXP-014: location of the physical IPI
acknowledgement.  It now runs for both the slept and did-not-sleep paths.  The
baseline remains exact m1n1 `55531e9`; Mu, Windows, timers, vGIC, NVMe, display
and input are unchanged.

Artifacts:
- `investigation/artifacts/EXP-20260813-015/m1n1.macho`
- SHA-256 `f34bbc2cb8d5ef7b4b45b5daa9b233f04ed4acd6c1ac33a905e9c5e9cd552fb7`

Hardware result:
- The image reached proxy, but the current public launcher received `Bad Command`
  for `P_HV_LAUNCH_PUBLISH` before guest launch.  No CPU or Windows conclusion is
  valid from this attempt.
- EXP-016 rebuilds the same SMP change directly from the canonical public tree
  and restores its committed production `hv_init_secondary()` and
  `mmu_init_secondary()` paths, avoiding another mixed-tree launch.

### EXP-20260813-016 — canonical public runtime with EXP-015 SMP wake

Status: CPU/SMP path successful; clean endurance rerun required
Created (UTC): 2026-08-13

Canonical public m1n1 with the full launch-descriptor ABI, production secondary
MMU/EL2/vGIC/timer initialization, and the dual IPI+SEV mailbox wake with
unconditional physical IPI acknowledgement.  Diagnostic-only empty-secondary
experiments and their tests were removed.  The focused Python SMP contract suite
passes 10/10 and the complete C host suite passed before this build.

Artifacts:
- `investigation/artifacts/EXP-20260813-016/m1n1.macho`
- SHA-256 `dd019e4c34db3241bd4e9d1ed6d6bd3db772160b082685da8d1a6410f485be64`
- Mu SHA-256 `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`

Hardware result:
- Launch preflight passed.  CPUs 0 through 7 all emitted `CPU_ENTRY`; every
  secondary mailbox was published, consumed and entered exactly once.
- After more than one minute, a watchdog snapshot showed all eight CPUs still
  executing Windows.  Per-CPU SGI queue, IPI receive, IAR and EOI counters were
  balanced (tens of thousands each), with zero pending SGI masks, zero queue
  depth and zero no-LR events.  This is direct evidence that the earlier
  mailbox/SGI startup failure is removed.
- The subsequent reset was caused by the observer, not the guest:
  `hang_telemetry.py --once` attached as a second proxy client, reported
  `Proxy callback without handler: 3, 3`, then drove m1n1 into an EL2 data abort
  at relative PC `0x51264`.  The target rebooted immediately afterward.
- Do not use standalone `hang_telemetry.py` against a live assisted guest until
  callback/event ownership is fixed.  Presence of both USB interfaces is not a
  failure signal, and an external observer must not compete with the launcher.
- A clean rerun without any second proxy owner again passed preflight and emitted
  `CPU_ENTRY` for CPUs 0 through 7.  It remained alive for the bounded passive
  observation window (more than three minutes), with the same USB generation and
  no bugcheck, watchdog, exception, panic or reset marker.  The old cached Windows
  IP did not respond, so login/desktop responsiveness still requires visual or
  current-network confirmation by the operator; it is not inferred from silence.
- Verification after cleanup: root Python suite 242/242 passed, nested SMP Python
  suite 10/10 passed, and the complete nested C host suite passed.
- Local clean hardware transcript SHA-256:
  `668690622096b14c6258e40f52b7280550576cca4a00404b71851cfb3c0c5308`
  (`investigation/artifacts/EXP-20260813-016/hv-clean.log`, ignored by Git).

### EXP-20260814-017 — operator responsiveness test of unchanged EXP-016

Status: in progress; operator verdict pending
Created (UTC): 2026-08-14

Purpose: give the operator an unmodified, already-recorded EXP-016 assisted boot
for a subjective responsiveness and stability test before any Apple keyboard or
trackpad work begins.  There is no changed firmware variable relative to
EXP-016.  Physical display is enabled; USB framebuffer and external telemetry
observer are disabled.  Debug mode is `monitor` only so no competing proxy owner
is attached after guest handoff.

Artifacts:
- `investigation/artifacts/EXP-20260813-016/m1n1.macho`
- SHA-256 `dd019e4c34db3241bd4e9d1ed6d6bd3db772160b082685da8d1a6410f485be64`
- `investigation/artifacts/EXP-20260813-016/J313_EFI.fd`
- SHA-256 `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`
- Runtime: root `5d827ba` materialized at
  `/private/tmp/wom1-root-5d827ba.WCgcVM`

Launch result so far:
- Launch-contract preflight passed with physical 2560x1600 framebuffer and no
  USB framebuffer or telemetry.
- Mu opened the installed `\\EFI\\BOOT\\BOOTAA64.EFI` and transferred control to
  Windows Boot Manager.
- CPUs 0 through 7 emitted `CPU_ENTRY`; NVMe and xHCI initialized.
- No bugcheck, watchdog, reset, panic, or exception was observed during the
  captured startup window.
- Responsiveness, sustained stability, display, USB input, SSH and RDP results
  remain pending the operator's test and must not be inferred from boot logs.

Process correction: this entry was appended immediately after launch instead of
before it.  That violates the intended pre-run ordering but does not change the
artifact or result.  Future hardware launches must create the entry first.

Operator result:
- Windows reached the desktop but booted much more slowly than the accepted
  morning baseline.
- Continuous pointer micro-stutter returned during ordinary mouse movement.
- The operator classifies this as a definite CPU-path performance regression,
  not an acceptable stability improvement.

Verdict: rejected for performance.  EXP-018 tests the only continuous-rate CPU
policy difference identified against the responsive baseline while retaining
EXP-016's successful secondary-mailbox wake correction.

### EXP-20260814-018 — restore sparse secondary recovery tick

Status: rejected; responsiveness improved but minute-scale timer-progress stall reproduced
Created (UTC): 2026-08-14

Hypothesis: EXP-017's continuous micro-stutter is caused by raising the non-ECV
secondary housekeeping tick from 100 Hz to 1000 Hz.  On J313 this creates about
7000 additional EL2 entries per second across seven secondary CPUs, and the
current secondary FIQ path also performs vGIC resynchronisation.  Restoring the
accepted 100 Hz fallback should restore interactive responsiveness without
reintroducing the intermittent secondary-mailbox startup race.

Single changed variable relative to EXP-017:
- `HV_FALLBACK_SECONDARY_TICK_RATE`: 1000 Hz -> 100 Hz.

Unchanged:
- dual IPI+SEV mailbox notification and unconditional IPI acknowledgement;
- all eight CPUs, secondary FIQ/vGIC correctness path, boot CPU 1000 Hz tick;
- Mu, ACPI, NVMe, xHCI, display, Apple-input passthrough and Windows install;
- physical display, monitor debug profile, no USB framebuffer, no external
  telemetry observer.

Source and artifacts:
- m1n1 commit `90f8545c818ba7bd70063e5ecf3e7711e51c6aa2`;
- `investigation/artifacts/EXP-20260814-018/m1n1.macho`;
- SHA-256 `67773a1c86ca4d41424e217b83ea74fcd39c10c331403b025853741909d60dc4`;
- `investigation/artifacts/EXP-20260814-018/J313_EFI.fd`;
- SHA-256 `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- recovery artifact: EXP-016 m1n1 SHA-256
  `dd019e4c34db3241bd4e9d1ed6d6bd3db772160b082685da8d1a6410f485be64`.

Software verification:
- RED: the tick-policy test failed while the implementation still returned
  1000 Hz.
- GREEN: the complete nested C host suite passed after the change.
- The focused secondary-launch Python suite passed 10/10.
- Clean `make -j8` completed with the canonical Rust path and produced the
  recorded Mach-O hash.

Expected checkpoint: CPUs 0 through 7 enter Windows exactly once, Windows boot
and pointer movement are materially smoother than EXP-017, and no watchdog,
bugcheck, reset, or long global freeze appears during the operator test.

Failure criterion: any missing secondary CPU, boot-time reset, watchdog, or no
observable improvement in the slow boot and continuous pointer micro-stutter.
Recovery: assisted launch only; the ESP is unchanged and EXP-016 remains the
recorded recovery image.

Hardware result:
- Launch-contract preflight passed and CPUs 0 through 7 entered Windows exactly
  once.  NVMe and xHCI both initialized.
- The operator initially observed an improvement over EXP-017, then Windows
  stopped responding completely for at least one minute.  It later recovered
  without a reboot.
- The UART log was quiescent after xHCI route enable.  Two non-destructive
  snapshots were requested through the existing launcher; no second proxy owner
  was attached.
- Across both snapshots, the physical counters advanced but Windows remained in
  a narrow kernel PC range.  The SGI diagnostic queue/IAR/EOI counts did not
  advance between samples (apart from the one diagnostic IPI used to request the
  second snapshot).
- Several CPUs retained a live virtual-timer INTID 18 LR.  The raw LR state must
  be decoded from bits 63:62: `0x502...` is Pending-only, `0x902...` is
  Active-only, and Active+Pending would be `0xd02...`.  EXP-018 contained both
  Pending-only and Active-only timer LRs, but no sampled Active+Pending LR.  Other
  CPUs had no live timer LR, yet none showed normal interrupt progress in either
  sampled interval.
  Queue depth and `no_lr` remained zero.  This excludes NVMe queue exhaustion and
  LR scarcity as the immediate cause.
- The diagnostic IPI briefly advanced the last timer IAR/EOI timestamps and moved
  the live timer LR state between CPUs, but sustained execution was not visible
  during the sampled interval.  The operator later confirmed that Windows did
  recover after a pause of one minute or more.  Because that recovery occurred
  after the diagnostic IPIs, this run cannot distinguish spontaneous timeout
  recovery from recovery assisted by the external wake.

Verdict: rejected for stability.  The A/B establishes that the 1000 Hz secondary
heartbeat in EXP-017 was masking a lost timer/vGIC progress condition while also
creating continuous micro-stutter.  Reducing it to 100 Hz improves responsiveness
but exposes a minute-scale full-system stall.  The next correction must repair event-driven
timer progress; selecting another polling frequency is not an acceptable fix.

Evidence:
- preserved log: `investigation/artifacts/EXP-20260814-018/hv-freeze.log`,
  SHA-256 `7fde0975539dee80628591470687fd3c1b19256ba6e4edfa3efa57ba5ba12289`;
- first and second lock-free snapshots: `HV WATCHDOG CPU` records following the
  two `HV: User interrupt; pre-rendezvous watchdog snapshot` markers.

Decoder correction: earlier experiment prose called raw `0x902...` timer LRs
Active+Pending.  That label is incorrect under `ICH_LR_STATE_SHIFT=62` and
`ICH_LR_STATE_MASK=3`: the sampled state value is 2 (Active-only).  Raw values in
the old records remain valid evidence, but future analysis must use the corrected
decoder above.

### EXP-20260814-019 — level-sensitive guest timer synchronization

Status: rejected after hardware test
Created (UTC): 2026-08-13T23:43:58Z

Hypothesis: EXP-018's minute-scale global stall occurs because the production
timer path treats a live Active INTID 17/18 LR as sufficient ownership and skips
the required level reassertion transition to Active+Pending.  Synchronizing each
sampled timer line directly with LR state, withdrawing stale Pending state on
deassertion, and using one unique deferred owner per timer will preserve every
expiry without a high-frequency recovery heartbeat.

Single changed variable relative to EXP-018:
- event-driven timer/vGIC delivery ownership and LR state synchronization for
  architectural timer INTIDs 17 and 18.

Unchanged:
- all eight CPUs and the race-safe secondary mailbox IPI+SEV protocol;
- boot CPU 1000 Hz and non-ECV secondary 100 Hz heartbeat policy;
- Mu, ACPI, Windows installation, NVMe, xHCI, display, Apple input and memory
  layout;
- physical display, monitor diagnostics, assisted launch, and one USB owner.

Source contract before artifact build:
- root repository `/Users/pavel/public_windows`, branch
  `codex/canonical-public-release`, commit
  `efb93c6be3f362d64eedf2d22ad787cad005d256`;
- root dirty diff SHA-256
  `e110dd7850110333712048a8afbad00de977e7116c4f6bf395f033d553357166`;
- m1n1 commit `2ead84d25644316cb59c552b420396dcbd9d07c2`, clean diff
  SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
- Mu commit `63942398cccbd98127cfecbd7f936af99c837d6f`, tracked-source
  diff SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
  nested Mu checkout markers remain and are not source changes.

Software evidence before artifact build:
- RED `hv_vgic_diag_test`: missing level-result type and sync API;
- GREEN plus mutation check: the test fails when Active+asserted incorrectly
  remains Active-only and passes when it becomes Active+Pending;
- RED `hv_timer_delivery_test`: missing deferred-owner source;
- GREEN unique ownership, withdrawal, FIFO and invalid-INTID tests;
- RED root integration suite: missing synchronizer and EOI timer-drain boundary;
- GREEN root integration suite 11/11, complete nested C host suite, focused SMP
  Python suite 10/10, and complete root Python suite 247/247;
- clean freestanding `make -j8` completed from the canonical public tree.
- the final hot-path refactor removed a redundant second LR-bank scan and VI
  recomputation after `hv_vgic3_inject_irq()`; the complete nested C host suite
  remained green before the recorded post-commit artifact build.

Recorded artifact:
- `investigation/artifacts/EXP-20260814-019/m1n1.macho`;
- SHA-256 `7c9c5a400b3a14cc842119fa7663ef36ab2390bf0b41d3292e75c52963e056c5`;
- provenance manifest
  `investigation/artifacts/EXP-20260814-019/MANIFEST.json`, SHA-256
  `4dc45bc768bee43e688d87f8f5cdba28e3fc19bf0706b628272881c7d1580502`;
- manifest root commit `5c585245162a39d0e0f632a6e8a062c019692838`, root
  diff SHA-256
  `dc75ba5d62525f016d3fbd9dd6b5e7e6e1c7160c455dc94de961f19cfda8ffab`,
  m1n1 commit `2ead84d25644316cb59c552b420396dcbd9d07c2`, and Mu
  commit `63942398cccbd98127cfecbd7f936af99c837d6f`;
- unchanged `investigation/artifacts/EXP-20260814-019/J313_EFI.fd`, copied from
  EXP-018 Mu SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- recovery artifact EXP-016 m1n1 SHA-256
  `dd019e4c34db3241bd4e9d1ed6d6bd3db772160b082685da8d1a6410f485be64`.

Exact build command:

```sh
cd /Users/pavel/public_windows/m1n1_windows
PATH="/opt/homebrew/opt/rustup/bin:$PATH" make clean
PATH="/opt/homebrew/opt/rustup/bin:$PATH" make -j8
```

Post-commit build result: successful.  The warnings are pre-existing in the
tree; the linker produced the recorded Mach-O from clean m1n1 commit
`2ead84d25644316cb59c552b420396dcbd9d07c2`.

Planned launch: canonical `scripts/run-windows.sh` assisted execution with the
recorded EXP-019 m1n1 and unchanged Mu artifacts, physical display, monitor
diagnostics, explicit proxy/vUART devices, and no second observer.

Expected checkpoint: launch preflight passes; CPUs 0 through 7 enter exactly
once; NVMe, xHCI and external USB input remain alive; Windows reaches login or
desktop; timer IAR/EOI progress continues without diagnostic IPIs; no asserted
Active-only timer survives synchronization; and no global pause, watchdog,
reset, or EXP-017 continuous micro-stutter occurs through a bounded ordinary and
CPU/storage stress window longer than the EXP-018 pause interval.

Failure criterion: missing CPU_ENTRY, Windows failing to reach login, any global
pause, `CLOCK_WATCHDOG_TIMEOUT`, reset, timer-progress loss, stale asserted
Active-only LR, or continuous micro-stutter.  Recovery is assisted-only; ESP is
unchanged and EXP-016 remains available.

Evidence paths after launch:
- `investigation/artifacts/EXP-20260814-019/hv.log`;
- existing-launcher SIGINT lock-free snapshots only if progress stalls;
- no standalone `hang_telemetry.py` or competing proxy owner.

Hardware attempt 1: infrastructure-aborted before Windows.  The exact artifact
and manifest preflight passed, all secondaries started in m1n1, guest handoff
occurred, NVMe ECAM/BAR initialized, and Mu reached
`AppleUsbTypeCBringupDxeBringupCallback`.  The host command session then reaped
the detached `run_uefi.py` and UART-reader children; `hv.log` ended mid-line and
both recorded PIDs were gone, with no guest exception or reset record.  Because
the runner disappeared before secondary Windows `CPU_ENTRY`, this attempt says
nothing about the timer correction.  Repeat with the same artifacts and the
canonical launcher held in foreground; do not change the guest variable.

Hardware attempt 2: infrastructure-aborted before guest initialization.  The
proxy was still owned by the live Windows hypervisor left by attempt 1 rather
than by a clean Stage 1.  Chainloading through that live guest raised an EL1
exception and rebooted the target; after reconnect, the launcher continued
against the installed old Stage 1 (`b791225`), which correctly rejected the new
launch-publish opcode as `Bad Command`.  The resulting fresh `Running proxy`
state was verified with `probe.py`.  Repeat unchanged from that confirmed Stage
1; do not classify this as timer behavior.

Hardware attempt 3: clean run in progress.  The exact frozen artifacts passed
manifest verification, m1n1 `2ead84d` chainloaded once from a confirmed fresh
Stage 1, and the foreground runner remained the sole proxy owner.  Mu started
the installed Windows fallback loader; CPUs 0 through 7 entered exactly once;
NVMe reached ready state and xHCI enabled its Windows route.  No bugcheck,
exception, reset, LR shortage, or deferred timer backlog was recorded.

After a passive interval longer than EXP-018's original pause, two lock-free
snapshots showed all eight physical counters advancing and substantial forward
progress in `q`, `iar`, and `eoi` on every CPU.  Live INTID 18 LRs included the
new `0xd02...` Active+Pending state, and `ap_eoi` was nonzero on the CPUs that
had consumed reassertions.  Between snapshots CPU0 `iar/eoi` advanced from
17973/17973 to 41437/41437, CPU1 from 20383/20383 to 55491/55491, and the other
CPUs advanced similarly.  `no_lr=0`, timer queue depth remained zero, and guest
PCs changed.  This directly validates the corrected level transition and shows
that the minute-scale timer-progress loss did not recur in the observed window.

Partial evidence: `investigation/artifacts/EXP-20260814-019/hv-progress.log`,
SHA-256
`7de57f58349fad9c4d313e1669a2488b971769cc72fa9abd2d81be707b9a85de`.
Final verdict remains pending operator confirmation of the physical login or
desktop, pointer/input responsiveness, and the bounded ordinary/stress window.

### EXP-20260814-020 — remove the boot-CPU 1 kHz recovery tax

Status: rejected; early Windows boot requires the 1 kHz boot heartbeat
Created (UTC): 2026-08-14

Hypothesis: after EXP-019 repaired event-driven architectural-timer delivery,
CPU0's remaining 1 kHz EL2 recovery heartbeat is unnecessary and causes the
observable interactive latency.  CPU0 is the only vCPU using 1 kHz; CPU1-7 use
100 Hz.  A Windows QPC affinity test measured CPU0 at 5344.4 ms for a 5000 ms
window with p95 overshoot 56.465 ms and maximum 169.936 ms, while CPU4 completed
in 5000.4 ms with zero measured overshoot.  A follow-up all-core test again
isolated the only non-zero delay to CPU0.

Single changed variable relative to EXP-019:
- boot CPU EL2 recovery tick: 1000 Hz -> 100 Hz.

Unchanged:
- EXP-019 level-sensitive INTID 17/18 synchronization and deferred ownership;
- all eight CPUs, mailbox IPI+SEV protocol, Mu, Windows, NVMe, xHCI, display,
  memory layout, assisted launch and monitor diagnostics;
- secondary non-ECV recovery tick remains 100 Hz.

Pre-change evidence from the live EXP-019 guest:
- Windows Stopwatch/QPC frequency: 24 MHz;
- 100 x 100 ms scheduler waits: total 14264 ms, median 111 ms, p95 168.4 ms,
  maximum 1544.5 ms;
- idle CPU about 1%, DPC 0%, processor queue 0, disk latency 0 ms;
- CPU0 affinity test showed timing loss while CPU4-P was exact;
- the post-test lock-free snapshot showed empty software queues, no LR shortage,
  and continuing IAR/EOI progress on all CPUs.

Expected checkpoint: CPUs 0-7 enter Windows; the same CPU0 and CPU4 affinity
test both complete 5000 ms with negligible overshoot; the 100 x 100 ms scheduler
test no longer contains a large outlier; no timer stall, watchdog, reset or
bugcheck occurs.

Failure criterion: CPU0 remains uniquely delayed, any vCPU loses timer progress,
or Windows fails to reach the desktop.  Recovery uses the immutable EXP-019
artifact; the ESP is unchanged.

Hardware result:
- artifact `m1n1.macho` SHA-256
  `2b9a073435f0f481621e38a7b36f45ab9dc38864c6af7dfb918f8b844194ef1b`
  from m1n1 commit `cf9770180e0122d92b2274081eb7ecebda5a7d2d` passed manifest
  preflight and chainloaded from a clean Stage 1;
- CPUs 0-7 entered once and NVMe reached ready;
- Windows then raised bugcheck `0x7e` with parameter 1 `0xffffffffc0000094`
  (integer divide by zero) at `0xfffff803a06935d0` before reaching login;
- the snapshot placed CPU0 in the stall-check path and showed INTID 18 pending
  on every vCPU; Windows requested PSCI reset immediately afterward.

Verdict: rejected.  The unique 1 kHz CPU0 heartbeat correlates with the measured
CPU0 latency, but reducing it from reset is unsafe.  A valid correction must
retain the startup cadence and switch to sparse/event-driven service only after
an explicit guest-ready milestone; do not tune the static constant again.

### EXP-20260814-021 — two-phase boot CPU heartbeat

Status: rejected as a complete fix; CPU0 tax improved but global pauses remain
Created (UTC): 2026-08-14

Hypothesis: Windows requires CPU0's 1 kHz EL2 heartbeat during early SMP/timer
initialization, but retaining it after device initialization causes the measured
CPU0-only scheduling gaps.  Keep 1 kHz through early boot, then atomically switch
CPU0 to 100 Hz when Windows enables the J313 xHCI hardware IRQ route.  In every
successful EXP-019 boot this milestone occurs after CPUs 0-7 enter and NVMe is
ready; EXP-020 failed before reaching it.

Single changed variable relative to EXP-019:
- CPU0 tick policy becomes two-phase: startup 1000 Hz, post-xHCI-route 100 Hz.

Unchanged:
- secondary ticks and EXP-019 timer delivery state machine;
- Mu, Windows, NVMe/xHCI implementation, display, memory layout and launch mode.

Expected checkpoint: early Windows boot reaches the xHCI route without the
EXP-020 `0x7e`; the log records one cadence transition; SSH returns; CPU0's
5-second affinity timing converges with CPU4; no large scheduler-wait outlier,
bugcheck, watchdog or reset occurs.

Failure criterion: transition occurs before all CPUs/NVMe are ready, Windows
fails to reach SSH, CPU0 remains uniquely delayed, or timer progress is lost.
Recovery is immutable EXP-019; the ESP remains unchanged.

Frozen assisted artifact before launch:
- m1n1 commit `ec7dd42b` (`hv: lower boot tick after guest runtime handoff`);
- `investigation/artifacts/EXP-20260814-021/m1n1.macho`, SHA-256
  `0928ec0a8c342aecca1bf0526059aea5d39a3c647fbc533ef943cb6c6efe9b8f`;
- unchanged Mu `J313_EFI.fd`, SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- manifest SHA-256
  `e5a66d86266c18d10ab6d4608e24ea58f0e5038dea7cc2703196b39f088e39a6`.

Preflight result: manifest roles/profile/layout validated; focused RED tests
failed before the runtime-ready API and xHCI hook existed; after implementation
the complete nested C host suite and the focused root vGIC contract passed.  No
hardware result has been inferred from those host tests.

Hardware result:
- all eight CPUs entered, NVMe reached ready, and the one-time
  `boot tick 1000Hz -> 100Hz` transition occurred only after the Windows xHCI
  route; the EXP-020 early `0x7e` did not recur and SSH reached the desktop;
- CPU0's 5-second affinity window improved from 5344.4 ms to 5002.789 ms;
  CPU0 p95/max overshoot became 30.184/102.074 ms while CPU4 completed in
  5000.009 ms;
- the system scheduler test did not converge: 100 x 100 ms waits still took
  14222.120 ms, median 110.576 ms, p95 364.678 ms and maximum 799.383 ms;
- SSH twice stopped accepting a connection for about 20 seconds and then
  recovered without a reset or bugcheck;
- the snapshot taken during the second timeout showed all eight Windows PCs in
  the idle/WFI path, empty software delivery queues, no LR shortage, and live
  Pending or Active+Pending INTID 18 LRs.  Several CPUs had HCR.VI asserted but
  ISR_EL1 clear.  Timer and SGI counters continued between snapshots.

Verdict: the 1 kHz boot-CPU heartbeat was a measurable CPU0 tax, but changing
its steady-state cadence is not the root fix.  The remaining pause signature is
an idle-wakeup/delivery failure: a virtual timer can be represented in the vGIC
while the physical Apple core remains asleep.  Do not ship EXP-021 as the
stability fix.

### EXP-20260814-022 — trap guest WFI/WFE to isolate idle-wakeup loss

Status: rejected after hardware test
Created (UTC): 2026-08-14

Hypothesis: the long recoverable pauses occur after Windows enters physical WFI
with a deliverable timer LR; changing HCR.VI/LR state does not reliably wake the
Apple core.  The tree already contains the bounded `HV_DIAG_TRAP_WFX` path.
Trapping WFI/WFE and advancing the guest PC prevents physical sleep while
leaving timer, vGIC, NVMe, Mu, Windows, topology and display unchanged.

Single changed variable relative to EXP-021:
- build m1n1 with `DIAG_TRAP_WFX=1`.

Expected checkpoint: the exact CPU0/CPU4 and 100 x 100 ms probes complete
without the 20-second SSH/UI pause, and repeated SSH probes remain responsive.
This build is diagnostic only because idle CPUs busy-poll and power consumption
will increase.

Failure criterion: any global pause remains, Windows bugchecks/resets, or the
WFI trap policy is lost after guest handoff.  Recovery remains immutable
EXP-019; the ESP is unchanged.

Frozen assisted artifact before launch:
- source commit `ec7dd42b`, built with `DIAG_TRAP_WFX=1` and no source change;
- `investigation/artifacts/EXP-20260814-022/m1n1.macho`, SHA-256
  `7c787f54035586d2aa8679e889e0385be41d6ac09358842bb5410d54213703c6`;
- unchanged Mu SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- manifest SHA-256
  `ced7652f769c9b5b6a769f42c084642ed6525d9cab9d8aba0e99b922ea25cfc8`.

Preflight result: clean build completed and manifest roles/profile/layout
validated.  This entry intentionally precedes the hardware launch.

Hardware result:
- all eight CPUs entered, NVMe reached ready, the runtime tick transition and
  xHCI route completed, and the log confirmed that TWI/TWE were active;
- two snapshots roughly 30 seconds apart showed Windows CPUs in idle paths
  with live Pending or Active+Pending timer LRs, but every CPU's timer
  queue/IAR/EOI counters remained unchanged; only the diagnostic snapshot IPI
  counter advanced;
- Windows then bugchecked with `INTERNAL_POWER_ERROR` (`0xa0`):
  `P1=0x618`, `P2=0xffffa20d52c2cb40`,
  `P3=0xffffa603c169a080`, `P4=0x0`.

Verdict: rejected.  Advancing guest WFI/WFE as a busy-poll changes Windows
power-idle semantics, does not restore timer/vGIC progress, and produces a
power-manager bugcheck.  Never enable `DIAG_TRAP_WFX` in a production or
stability candidate.  Continue the investigation at virtual interrupt
delivery/deactivation without replacing architectural WFI/WFE behavior.

### EXP-20260814-023 — identify the global EL2 lock owner during a freeze

Status: completed; hypothesis not confirmed by sampled lock state
Created (UTC): 2026-08-14

Hypothesis: the apparently idle vCPU/timer signature is secondary evidence of
global EL2 lock contention.  In two EXP-021 snapshots CPU0's breadcrumb ended
in `X`, which is emitted immediately before `spin_lock(&bhl)`, while its INTID
18 and INTID 64 LRs and last IAR/EOI state remained byte-for-byte unchanged.
If `bhl` is leaked or held by another CPU, all serialized vCPUs can stop while
physical counters and the lock-free snapshot mechanism remain alive.

Single changed variable relative to immutable EXP-021:
- the lock-free watchdog dump prints the live `bhl.lock` owner and recursive
  `bhl.count`; no timer, vGIC, WFI/WFE, tick, NVMe or guest behavior changes.

Expected checkpoint: during the next operator-visible pause, a non-destructive
snapshot identifies either a concrete owner/count or proves that CPU0's `X`
breadcrumb was not a live bhl wait.  Repeated snapshots must distinguish a
long holder from a permanently leaked lock.

Failure criterion: diagnostic output perturbs boot, the bhl fields cannot be
read locklessly, or no pause occurs during the bounded observation.  Recovery
is immutable EXP-021; the ESP remains unchanged.

Preflight result so far: the focused source-contract test fails because the
watchdog dump does not yet publish bhl owner/count.  This entry intentionally
precedes implementation, artifact creation and hardware launch.

Implementation and frozen artifact:
- m1n1 commit `922bb87` (`diag: expose global hypervisor lock owner`);
- the RED source-contract test failed before implementation and passed after;
- complete nested C host suite passed and the post-commit freestanding build
  completed; `HV_DIAG_TRAP_WFX` is absent from the build configuration;
- `investigation/artifacts/EXP-20260814-023/m1n1.macho`, SHA-256
  `fe0ac8041e5dcb280cb70d40c1212527ed48eb3c6ec1f40e46499a4dc9b7ceda`;
- unchanged Mu SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- manifest SHA-256
  `09d864ad14ce3390b4c04f2bac8986ce1e63fc326a5bd82a21e690d8a5452c34`.

No hardware result is inferred from software tests.  This update is recorded
before the assisted launch.

Hardware result:
- EXP-023 reached the same all-CPU, NVMe and xHCI checkpoints as EXP-021;
- Windows again failed to reach SSH during the bounded boot interval;
- a non-destructive snapshot reported `HV WATCHDOG BHL: owner=0 count=1`.
  The dump itself runs from CPU0 while it legitimately owns bhl, proving that
  CPU0 acquired the lock after the earlier `X` breadcrumb; it does not show a
  permanent leak or a different CPU holding the lock.

Verdict: the snapshot falsifies a permanently leaked bhl at the sampled time.
The `X` breadcrumb is a transient wait marker, not sufficient evidence of the
root cause.  Do not change spinlock semantics from this result.

### EXP-20260814-024 — demand-driven guest IRQ recovery heartbeat

Status: planned; artifact frozen before hardware launch
Created (UTC): 2026-08-14

Hypothesis: on T8103, a synthetic virtual IRQ represented by an LR plus HCR.VI
does not always provide a physical wake after Windows has entered idle.  The
static 1 kHz secondary heartbeat bounded this loss but imposed continuous EL2
overhead; the 100 Hz version restored responsiveness but exposed long stalls.
A 1 ms EL2 recovery tick only while INTID 17/18 is owned by an LR/deferred
delivery should preserve wake progress without polling idle vCPUs at 1 kHz.

Single changed variable relative to EXP-023/EXP-021:
- at the end of a physical FIQ, re-arm the local EL2 tick for 1 ms when that
  CPU still owns an undelivered guest physical/virtual timer interrupt;
- once Windows EOIs and rearms the guest timer, the existing 10 ms secondary
  and 10 ms runtime boot-CPU cadence resumes automatically.

Unchanged: WFI/WFE semantics, vGIC LR state machine, priorities, Mu, Windows,
NVMe, xHCI, display and all eight CPUs.

Expected checkpoint: boot reaches SSH without the long spinner pause; repeated
100 x 100 ms waits have no multi-second outlier; no 0x101, 0xa0, reset or
minute-scale UI freeze occurs.  Normal idle does not pay a continuous 1 kHz
heartbeat because the recovery cadence is conditional on live timer ownership.

Failure criterion: early bugcheck/reset, unchanged long pause, or evidence that
the recovery tick remains at 1 kHz after timer ownership clears.  Recovery is
immutable EXP-021; ESP remains unchanged.

Preflight result so far: the pure tick-policy test and root integration test
fail because the recovery rate/API and conditional FIQ re-arm do not exist.
This entry intentionally precedes implementation, artifact creation and launch.

Implementation and frozen artifact:
- m1n1 commit `0cad7b2` (`hv: bound pending guest timer wake latency`);
- the pure tick-policy test and root FIQ integration test failed before the
  recovery API/calls existed and passed afterward;
- complete nested C host suite, diff check and post-commit freestanding build
  passed;
- `investigation/artifacts/EXP-20260814-024/m1n1.macho`, SHA-256
  `95e0be58ef28430eb7ab9e06ba2a8d760d72ef9db87dd45d35ce4afd4f42eb8d`;
- unchanged Mu SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- manifest SHA-256
  `606c9f70db4465dd899351446a3e0c092b73eac75e9af77b1d7e27fb26e6aded`.

No hardware result is inferred from software verification.  This update is
recorded before the assisted launch.

Hardware result:
- all eight CPUs entered Windows; NVMe reached ready and xHCI routing was
  enabled, with no hypervisor reset or captured bugcheck;
- Windows remained materially slow and did not answer on its previously known
  SSH address during the bounded observation window;
- the non-destructive snapshot showed converged SGI accounting and no queued
  LR exhaustion, but CPU2 held INTID 18 `Active+Pending` while CPU3 held INTID
  18 `Pending`;
- the EXP-024 predicate armed the same 1 ms recovery tick for both states.
  `Pending` may require a physical wake before guest acknowledgement, whereas
  `Active` and `Active+Pending` mean Windows has already acknowledged the IRQ;
  polling EL2 at 1 kHz cannot finish that handler and adds avoidable latency.

Verdict: rejected as the final performance fix.  Demand-driven recovery is
retained, but ownership is too broad; EXP-025 narrows it to an unmasked,
Pending-only timer LR.

### EXP-20260814-025 — pending-only guest timer recovery wake

Status: planned; artifact frozen before hardware launch
Created (UTC): 2026-08-14

Hypothesis: EXP-024 removed continuous 1 kHz polling from completely idle
vCPUs, but continued polling at 1 kHz throughout `Active` and
`Active+Pending` timer handling.  Recovery is useful only while an unmasked
INTID 17/18 LR is exactly `Pending` and HCR.VI is asserted.  Once the guest has
acknowledged the IRQ, the normal 100 Hz secondary cadence must resume until a
new Pending-only delivery actually needs a wake.

Single changed variable relative to EXP-024:
- `hv_guest_timer_recovery_needed()` now scans the live LR bank and selects
  only a priority-deliverable, Pending-only INTID 17/18 while HCR.VI is set;
- Active and Active+Pending timer LRs no longer select the 1 ms recovery tick.

Unchanged: the 1 ms recovery interval itself, 100 Hz normal secondary cadence,
WFI/WFE semantics, LR level state machine, priorities, Mu, Windows, NVMe,
xHCI, display and all eight CPUs.

Expected checkpoint: all eight CPUs, NVMe and xHCI reach their established
markers; Windows reaches the login/desktop materially faster than EXP-024;
there is no long spinner pause, 0x101, 0xa0, reset or minute-scale freeze.

Failure criterion: early bugcheck/reset, unchanged slow boot, or repeated long
stalls with a Pending-only timer LR.  Recovery is immutable EXP-024; ESP
remains unchanged.

Preflight and frozen artifact:
- RED pure-policy and source-contract tests failed before the pending-only
  predicate existed and passed after implementation;
- m1n1 commit `ab3fda9` (`hv: limit recovery wake to pending timers`);
- complete nested C host suite, focused root vGIC contract suite, diff check
  and post-commit freestanding build passed;
- `investigation/artifacts/EXP-20260814-025/m1n1.macho`, SHA-256
  `4c21fe02bf45078949e9821f3b953ef2fc214851f62603d4691b2c6631800b5e`;
- unchanged Mu SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- manifest SHA-256
  `e1e83760881ae8616228da0d38ed49eec8aade1a29682493576eb41f27b1d058`.

No hardware result is inferred from software verification.  This entry is
recorded before the assisted launch.

Hardware result:
- all eight CPUs, NVMe and xHCI reached the expected markers with no captured
  reset or bugcheck;
- Windows remained slow and did not reach its previously known SSH address in
  the bounded interval;
- two non-destructive snapshots 20 seconds apart showed essentially frozen
  guest SGI/IAR/EOI progress.  A timer IAR/EOI advanced only adjacent to the
  diagnostic IPI, while Pending and Active+Pending INTID 18 LRs persisted.

Verdict: rejected as a root fix.  The narrower predicate removes unnecessary
recovery polling after acknowledgement, but the recovery source itself is not
proven to fire while the vCPU is stalled.  EXP-026 measures the host EL2 CNTP
state and arm/fire counts directly.

### EXP-20260814-026 — measure host recovery timer arm and expiry

Status: planned; artifact frozen before hardware launch
Created (UTC): 2026-08-14

Hypothesis: the normal/recovery EL2 CNTP is programmed but either does not
expire, is masked, or expires without producing guest timer progress.  Earlier
snapshots exposed only `CNTP_*_EL02`, which is the guest physical timer view;
they could not distinguish those cases.

Single changed variable relative to EXP-025:
- add per-CPU counters for normal tick arms, recovery tick arms and observed
  host CNTP expiries;
- publish `CNTP_CTL_EL0` and `CNTP_CVAL_EL0` alongside the existing guest
  `CNTP_*_EL02` state in the lock-free watchdog snapshot.

No scheduling, timer interval, vGIC, WFI/WFE, Mu, Windows, NVMe, xHCI, display
or CPU behavior is intentionally changed.

Expected checkpoint: two snapshots identify exactly one of three cases:
recovery is never armed, it is armed but host CNTP does not expire, or it
expires while the pending timer LR/IAR/EOI remains unchanged.

Failure criterion: diagnostic fields perturb boot or cannot distinguish arm
from expiry.  Recovery is immutable EXP-025; ESP remains unchanged.

Preflight and frozen artifact:
- the focused source-contract test failed before the fields/counters existed
  and passed after implementation;
- m1n1 commit `89d41fa` (`diag: measure host timer recovery progress`);
- complete nested C host suite, root vGIC contract suite, diff check and
  successful post-amend freestanding build passed;
- an earlier failed compile could not resolve `MAX_CPUS` through `hv.h`; its
  stale copied binary was detected by the unchanged EXP-025 hash and was
  overwritten.  The artifact below is from the successful post-amend build;
- `investigation/artifacts/EXP-20260814-026/m1n1.macho`, SHA-256
  `ee29ddccd0a96f6aff2994db5e1f33046280324bbd5ba04c3f591b0a8919f6be`;
- unchanged Mu SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- manifest SHA-256
  `0d005d1789327a134ce330288e9362b62fc492fa8fc32292f4b9bc1c8a39f2e5`.

No hardware result is inferred from software verification.  This entry is
recorded before the assisted launch.

Hardware result:
- all eight CPUs, NVMe and xHCI reached their expected checkpoints; no reset or
  bugcheck was captured during the bounded observation window;
- two non-destructive snapshots proved that the host `CNTP_EL0` recovery source
  is armed and expires.  On several secondary CPUs its arm/fire counters grew
  at nearly the 1-ms recovery cadence;
- deliverable Pending timer LRs persisted while the recovery source repeatedly
  fired.  Every such virtual-pending secondary FIQ was forced into the legacy
  slow path and global `bhl`, creating thousands of serialized EL2 entries per
  second across the guest;
- Windows remained slow.  The operator later reported an
  `INTERNAL_POWER_ERROR`; its exact parameters were not captured by this run,
  so it is not attributed as a measured EXP-026 bugcheck.  A prior captured
  `0xA0 / P1=0x618` has the Microsoft-defined meaning "runtime power worker
  blocked too long" and is consistent with, but does not by itself prove, this
  contention mechanism.

Verdict: diagnostic succeeded; rejected as a performance fix.  The missing
event is not the host recovery timer.  EXP-027 removes already-completed local
virtual-interrupt delivery from the global lock path while preserving the live
LR, freshly recomputed HCR.VI and recovery safety net.

### EXP-20260814-027 — return completed local virtual IRQs without global bhl

Status: planned; artifact frozen before hardware launch
Created (UTC): 2026-08-14

Hypothesis: Windows stalls and runtime-power watchdogs because every deliverable
secondary timer IRQ enters the global `bhl` slow path.  EXP-026 measured nearly
continuous 1-ms recovery FIQs on several vCPUs; serializing each one can starve
guest scheduling and power workers even though timer state itself is valid.

Single changed variable relative to EXP-026:
- after local guest-timer/IPI handling and live-LR `HCR.VI` recomputation, allow
  an otherwise eligible secondary to return directly even when a virtual IRQ
  is pending.  Physical FIQs, rendezvous, proxy CPU switches and the
  interruptible CPU retain the serialized path.  Pending timers retain the
  short recovery wake until Windows acknowledges/rearms them.

No timer level-state machine, recovery interval, Mu, NVMe, xHCI, display, CPU
topology, Windows installation, WFI mode or guest memory layout is changed.

Expected checkpoint: normal-duration boot and responsive desktop without the
20-second/minute stalls, `CLOCK_WATCHDOG_TIMEOUT`, or `INTERNAL_POWER_ERROR`.
The host recovery counters may still advance, but completed secondary local
FIQs must no longer contend for `bhl` merely because HCR.VI is asserted.

Failure criterion: early watchdog/reset, lost timer delivery, unchanged slow
boot, or a long stall.  Recovery is immutable EXP-026; ESP remains unchanged.

Preflight and frozen artifact:
- the focused fast-path test failed before Pending virtual IRQs were removed
  from the completion predicate and passed after implementation;
- m1n1 commit `7e84a84` (`hv: keep local virtual IRQs off the global lock`);
- complete nested C host suite, focused root vGIC contract suite, diff check and
  successful post-commit freestanding build passed;
- `investigation/artifacts/EXP-20260814-027/m1n1.macho`, SHA-256
  `d83b0cfa7d44cd5f83b4cf927918b20d7696dd5167692587f179879c02406515`;
- unchanged Mu SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- manifest SHA-256
  `aa9bead3a0928c4e1588428d8020da0d6e55eb17df453f444165838cfedb9d0a`.

No hardware result is inferred from software verification.  This entry is
recorded before the assisted launch.

Preliminary hardware observation (final operator verdict pending):
- the exact frozen artifact reported m1n1 `7e84a84`, reached NVMe ready, xHCI
  route enable and guest runtime cadence; a lock-free snapshot contained live
  state for all eight vCPUs;
- Windows reached its known network address and port 22 responded, although
  the post-reinstallation host key no longer authorized the existing SSH key;
- no bugcheck, reset or hypervisor exception was captured during the initial
  observation plus a subsequent 45-second passive window;
- desktop responsiveness and sustained stability remain unclaimed until the
  operator reports the physical-screen result and a longer workload passes.

Final operator result:
- Windows booted, but was extremely slow and froze immediately after reaching
  the desktop.  The target later returned to proxy and the assisted runner lost
  its USB device; no successful sustained session was observed.
- A lock-free snapshot measured roughly 29,000 host tick expiries and 35,000
  separate recovery-timer arms on several secondaries.  CPU4 and CPU6 did not
  emit their Windows `CPU_ENTRY` diagnostics until after the manual snapshot.
- Five preserved Windows dumps from the same regression family decode as
  `CLOCK_WATCHDOG_TIMEOUT (0x101)` with hung CPU indices 3, 1, 5, 2 and 5.  The
  failure is therefore not tied to one physical core; arbitrary secondary CPUs
  stop processing clock interrupts.

Verdict: rejected.  Letting Pending virtual IRQs bypass the global lock did not
repair delivery and retained the near-continuous 1-ms recovery source.  EXP-028
returns to the accepted virtual-IRQ exit contract and disables that source while
retaining only the independently validated secondary-mailbox wake correction.

### EXP-20260814-028 — accepted timer exit contract plus race-safe SMP wake

Status: planned; software verification complete, hardware not launched
Created (UTC): 2026-08-14

Hypothesis: the responsiveness regression is caused by the post-baseline 1-ms
guest-IRQ recovery source and modified secondary FIQ early-return policy, not by
the independently validated dual IPI+SEV secondary-mailbox fix.  Disabling the
extra recovery source and restoring the accepted rule that both physical FIQ and
HCR.VI must be clear before the abbreviated return will remove continuous EL2
work without restoring the intermittent secondary-start race.

Single changed runtime variables relative to rejected EXP-027:
- guest IRQ recovery tick rate: 1000 Hz -> disabled;
- secondary fast completion again requires no physical FIQ and no HCR.VI;
- the extra fast-boundary `hv_vgic3_update_vi()` scan is removed;
- Apple-input passthrough is disabled for this A/B build only.

Unchanged:
- race-safe secondary mailbox publication using targeted IPI plus SEV and
  unconditional physical IPI acknowledgement;
- eight CPUs, 100 Hz ordinary secondary heartbeat, Mu, ACPI, NVMe, xHCI,
  physical display, Windows installation and guest memory layout;
- assisted launch, one proxy owner and monitor diagnostics.

Software evidence:
- RED: focused fast-path tests failed to compile with the accepted three-input
  completion contract and the tick-policy test failed at recovery rate 1000;
- GREEN: both focused tests passed after the minimal change;
- complete nested C host suite passed;
- focused secondary-start Python suite passed 10/10;
- focused root vGIC contract suite passed 15/15 and both diffs passed checks;
- clean freestanding build with `APPLE_INPUT=0` completed successfully and
  `build/build_cfg.h` contains `HV_DISABLE_APPLE_INPUT`.

Recorded artifacts:
- m1n1 commit `2ae94afc82bbf7667c9959f47bf515b381288343`;
- `investigation/artifacts/EXP-20260814-028/m1n1.macho`, SHA-256
  `d57df4625b3f5e0e760b2c54dc79565d96e53d051d420a43e437974a663816ae`;
- unchanged Mu firmware SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`.

Expected checkpoint: normal-duration boot, CPUs 0 through 7 enter exactly once,
pointer and desktop remain responsive, recovery-arm counters stay zero, and no
long pause, `0x101`, `INTERNAL_POWER_ERROR`, reset or lost SSH occurs during the
bounded interactive test.  ESP remains unchanged; this is assisted-only.

Hardware result:
- all CPUs 0 through 7 entered Windows independently before any diagnostic
  snapshot, NVMe and xHCI reached their ready checkpoints, and every recorded
  guest-IRQ recovery-arm counter remained zero;
- Windows then stopped with `DPC_WATCHDOG_VIOLATION (0x133)`, parameter 1 equal
  to 1.  This parameter means cumulative time at DISPATCH_LEVEL or above
  exceeded the watchdog period, rather than one isolated long-running DPC;
- the reset that followed was a Windows PSCI reset.  No EL2 exception or m1n1
  panic preceded it.

Verdict: rejected as a usable build, but the experiment isolated the next
regression layer.  Continuous 1-ms recovery work was removed successfully; the
post-baseline timer level-state synchronizer still differs from the accepted
morning path and is the only timer-delivery variable removed by EXP-029.

### EXP-20260814-029 — accepted timer delivery plus race-safe SMP wake

Status: rejected after hardware test
Created (UTC): 2026-08-14

Hypothesis: the post-baseline timer level-state synchronizer keeps Windows at
elevated IRQL long enough to trigger cumulative DPC watchdog violations.  The
accepted morning timer latch/re-pend path did not contain that synchronizer.
Restoring it while retaining only the independently proven secondary-mailbox
wake correction should recover the responsive baseline without restoring the
secondary-start race.

Single changed runtime variable relative to rejected EXP-028:
- timer delivery is restored to the accepted `timer_irq_outstanding` latch,
  `timer_repend_live_irq` and maintenance-drain implementation;
- the later `hv_sync_timer_level` state machine and timer-specific EOI drain are
  removed from production.

Unchanged:
- targeted IPI plus SEV mailbox publication and unconditional physical IPI
  acknowledgement;
- disabled 1-ms guest-IRQ recovery source and accepted secondary fast-exit
  predicate;
- eight CPUs, ordinary 100-Hz secondary heartbeat, Mu, ACPI, NVMe, xHCI,
  physical display, Windows installation, guest memory layout and Apple Input
  disabled for this A/B build.

Software evidence:
- RED: focused source-contract tests failed at the level-state synchronizer and
  timer-specific EOI drain;
- GREEN: focused root vGIC tests passed 15/15, the complete nested C host suite
  passed, focused SMP Python tests passed 10/10, and both diffs passed checks;
- m1n1 commit `7f8061c` (`hv: restore accepted timer delivery path`);
- clean freestanding `APPLE_INPUT=0` build SHA-256
  `df8c9127b191317d8ea4ddd795f0e95834eff436b7b4a910c8fa790d90d77efd`.

Expected checkpoint: Windows reaches the login/desktop in normal time, physical
pointer motion is smooth, all CPUs remain live, recovery-arm counters remain
zero, and neither `0x101`, `0x133`, `INTERNAL_POWER_ERROR`, spontaneous reset nor
a long global pause occurs.  ESP remains unchanged; assisted launch only.

Hardware result:
- all CPUs 0 through 7 entered Windows, NVMe and xHCI reached their runtime
  checkpoints, no recovery tick was armed, and no EL2 exception or immediate
  bugcheck occurred;
- Windows reached the lock screen, then repeatedly paused for tens of seconds.
  The operator could enter a password only between pauses; SSH never became
  reachable;
- two in-place snapshots proved that the host heartbeat and guest IAR/EOI
  counters advanced on every CPU, queues remained empty, and the global lock
  was not contended.  The guest therefore was not a dead hypervisor or a single
  permanently stopped secondary;
- the log marks the exact runtime transition `boot tick 1000Hz -> 100Hz`.  This
  policy is not present in accepted baseline `55531e9`, which keeps CPU0 at
  5000 Hz while only the secondaries use the sparse 100-Hz cadence.

Verdict: rejected.  Restoring the accepted timer delivery removed the early
`0x133`, but did not restore responsiveness because the CPU0 service cadence
was still a post-baseline runtime change.  EXP-030 restores that final runtime
difference while retaining the proven SMP wake correction.

### EXP-20260814-030 — exact accepted cadence plus race-safe SMP wake

Status: rejected after hardware test
Created (UTC): 2026-08-14

Hypothesis: reducing CPU0's EL2 service cadence from the accepted fixed 5000 Hz
to 1000 Hz during boot and 100 Hz at guest runtime allows global guest progress
to occur only in bursts.  Restoring the fixed accepted CPU0 cadence while
leaving secondaries at 100 Hz should remove the lock-screen pauses without the
all-core polling overhead that earlier 1000-Hz secondary experiments caused.

Single changed runtime variable relative to rejected EXP-029:
- CPU0 boot and runtime service cadence: 1000/100 Hz -> fixed 5000 Hz.

Unchanged:
- secondary cadence 100 Hz on T8103, guest IRQ recovery disabled, accepted
  timer latch/re-pend delivery, and race-safe IPI+SEV mailbox publication;
- eight CPUs, Mu, ACPI, NVMe, xHCI, physical display, Windows installation,
  guest memory layout and Apple Input disabled for this A/B build.

Expected checkpoint: Windows crosses the lock screen without a long pause,
reaches a responsive desktop, and remains free of `0x101`, `0x133`, power
bugchecks, spontaneous reset and minute-scale freezes.  ESP remains unchanged.

Software evidence:
- RED: focused tick-policy test failed because boot/runtime CPU0 rates were
  still 1000/100 Hz rather than the accepted fixed 5000 Hz;
- GREEN: focused test and complete nested C host suite passed; root vGIC suite
  passed 15/15, focused SMP Python suite passed 10/10, and both diffs passed;
- m1n1 commit `f4dfb0e` (`hv: restore accepted CPU0 service cadence`);
- clean freestanding `APPLE_INPUT=0` build SHA-256
  `847412d2c8e1ebe66052fc0594d394bfd8c3aa5d8999e59d91692219c02423d6`.

Hardware result:
- the artifact reported the required fixed `boot tick 5000Hz -> 5000Hz`, all
  eight CPUs entered, NVMe/xHCI completed, and Windows reached both the network
  and an authenticated SSH session;
- boot progressed faster than EXP-029, but the guest again paused.  SSH stopped
  before the first read-only command and later recovered after a physical
  rendezvous snapshot;
- the freeze snapshot showed CPU1 executing a user virtual address while the
  other CPUs were in Windows idle paths.  Every CPU's host heartbeat and guest
  IAR/EOI counters remained live, queues were empty, recovery remained zero,
  and no EL2 exception or bugcheck occurred.

Verdict: fixed 5000-Hz CPU0 cadence improves boot progress but is not sufficient
to eliminate the pause.  The monitor image samples a large watchdog record and
all virtual LRs every 64 ticks; at 5000 Hz this is about 78 heavy samples per
second on CPU0.  EXP-031 tests the identical runtime in RELEASE, where that
monitor-only hot path must be truly zero-cost.

### EXP-20260814-031 — production runtime without monitor hot-path sampling

Status: software-verified; frozen artifact pending clean provenance manifest
Created (UTC): 2026-08-14

Hypothesis: the clean installer/release profile was visibly smoother because it
did not require monitor snapshots, but the implementation still executes the
snapshot sampler regardless of `RELEASE`.  At the restored 5000-Hz CPU0 cadence
this repeatedly reads architectural timer registers, all LRs and publishes a
large record.  Returning before even the sample counter in RELEASE should make
production diagnostics zero-cost while preserving the monitor build unchanged.

Single source variable relative to rejected EXP-030:
- `hv_watchdog_snapshot_tick()` returns immediately when runtime diagnostics
  are disabled.

Build/profile variable required by the hypothesis:
- `RELEASE=1`, `APPLE_INPUT=0`, assisted physical display, debug off.

Unchanged:
- fixed CPU0 5000 Hz, secondary 100 Hz, accepted timer delivery, disabled
  recovery source, race-safe SMP wake, Mu, NVMe, xHCI and Windows installation.

Expected checkpoint: fast lock-screen/desktop entry and continuous pointer/SSH
responsiveness without monitor sampling overhead, BSOD or reset.  This build
cannot provide an in-place watchdog snapshot by design; failure is judged from
the foreground launcher lifecycle, physical screen and network continuity.

Software evidence:
- RED: the root source-contract test failed while the release path still
  incremented the snapshot sampler before checking runtime diagnostics;
- implementation commit `f397d93abbebb0444df731b55148318652db3228` returns
  before the sampler when runtime diagnostics are disabled;
- GREEN: root vGIC contract suite 16/16, focused release/watchdog/fast-path/tick
  tests, and the complete nested host suite passed;
- clean `RELEASE=1 APPLE_INPUT=0` build completed and produced m1n1 SHA-256
  `0ed330e5da17e0c64b35c2ce46efd41985c405a163bc416c19cf455528e63c77`;
- `build_cfg.h` contains both `RELEASE` and `HV_DISABLE_APPLE_INPUT`.

Hardware result: observation-incomplete.  The clean artifact reached all eight
Windows CPUs, NVMe controller reinitialisation and xHCI discovery without a
recorded reset or EL2 exception.  The known Windows address did not answer on
the network during the bounded interval, but the physical-only profile provided
no independent framebuffer evidence to distinguish a slow boot from a frozen
logo, spinner, login screen or desktop.  This run is not used to accept or
reject the runtime hypothesis.  All subsequent problem investigation must use
the guarded `--observed` launcher mode and `display=both`.

### EXP-20260814-032 — zero-cost release runtime with mandatory framebuffer observation

Status: rejected as a performance verdict; observer transport failed and guest froze
Created (UTC): 2026-08-14

Purpose: repeat EXP-031 without changing m1n1, Mu, Windows, CPU cadence, timer
delivery, storage or USB.  The sole profile change is `physical` -> `both`, so
the same guest framebuffer is consumed by the internal DCP scanout and the
asynchronous USB viewer.  This closes the Windows-logo-to-network blind spot.

Process guard:
- canonical launch uses `--observed`, which defaults to `display=both`, starts
  the viewer at `http://127.0.0.1:8766/`, and rejects an explicit non-`both`
  display;
- code commit `4abdf3996b319b7dd498b734a0a8591d922522f1`;
- RED test rejected the previously unknown `--observed` option; GREEN focused
  test and complete public launcher suite 34/34 passed.

Unchanged artifact payloads:
- m1n1 commit `f397d93abbebb0444df731b55148318652db3228`, SHA-256
  `0ed330e5da17e0c64b35c2ce46efd41985c405a163bc416c19cf455528e63c77`;
- Mu SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- `RELEASE=1`, `APPLE_INPUT=0`, debug off, CPU0 5000 Hz and secondaries 100 Hz.

Expected checkpoint: the viewer visibly progresses through firmware, Windows
logo/spinner, login and desktop; frame generation remains live during animation;
physical display shows the same surface; network becomes available; pointer and
SSH remain continuously responsive without a BSOD, reset or long pause.

Failure classification: a stale viewer generation while the physical screen is
also unchanged is a guest/transport freeze; a live viewer with a stale physical
panel is a DCP issue; a stale viewer with a changing physical panel is a USB
observation failure and does not classify Windows runtime behavior.

Hardware result:
- the unchanged release payload reached all eight CPUs, NVMe and xHCI, and the
  internal DCP surface progressed through firmware and Windows to the lock
  screen;
- the operator observed Windows freeze at the lock screen and the known guest
  address did not answer a bounded SSH probe, so this was not merely a stale
  physical panel;
- the USB viewer stopped earlier at Windows boot logo generation 31/frame 30;
  the sole proxy owner then reported repeated corrupted framebuffer events with
  `type=3 length=16348 wire=0x00000000` followed by long NUL runs;
- 16348 is exactly the data length of a maximum framebuffer chunk: the 28-byte
  framebuffer header plus the current 16320-byte payload.  The complete proxy
  event is 16360 bytes, only 24 bytes below the 16-KiB DWC3 transfer boundary.

Verdict: the Windows freeze is real, but EXP-032 cannot classify its cause or
measure release responsiveness because the mandatory observer itself lost USB
framing before the freeze.  Fix and validate the observer transport before the
next CPU/timer experiment.  Do not use this run to accept or reject the
zero-cost release hypothesis.

### EXP-20260814-033 — bounded framebuffer events with unchanged guest runtime

Status: observer transport confirmed; guest runtime rejected after reproduced freeze
Created (UTC): 2026-08-14
Completed (UTC): 2026-08-14T15:30:00Z

Hypothesis: the framebuffer observer loses CDC framing because its maximum
16360-byte proxy event leaves only 24 bytes below the 16-KiB DWC3 transfer
boundary.  Keeping complete framebuffer events below 4 KiB should preserve the
same frames and cadence while allowing the sole proxy owner and web viewer to
remain synchronized through the Windows freeze.

Single changed variable relative to EXP-032:
- framebuffer payload per proxy event: 16320 -> 4032 bytes; complete maximum
  event: 16360 -> 4072 bytes.

Unchanged:
- m1n1 release runtime, CPU0 5000-Hz cadence, secondary 100-Hz cadence, timer
  delivery, Mu, Windows, NVMe, xHCI, eight CPUs, Apple Input disabled, debug
  off and display `both`;
- ESP remains unchanged and the run is assisted through the sole proxy owner.

Software evidence:
- RED: `hv_fb_stream_usb_limit_test` aborted because the old 16360-byte event
  exceeded the literal 4096-byte safe budget;
- implementation commit `72b2aab8a6089b2099242f3bdb4a8cfd08e1113b` reduces
  only `HV_FB_STREAM_PAYLOAD_SIZE` to 4032 bytes;
- GREEN: focused framebuffer, USB-limit and proxy-event tests passed; the
  complete nested host suite passed; root display/receiver/launcher suite
  passed 54/54;
- clean Docker release build completed with `RELEASE=1` and
  `HV_DISABLE_APPLE_INPUT` in `build_cfg.h`.

Provenance and commands:
- root commit `c471d6cba22ca012a8cf7df9af6b94bc8e82ad78`, m1n1
  commit `72b2aab8a6089b2099242f3bdb4a8cfd08e1113b`, Mu commit
  `63942398cccbd98127cfecbd7f936af99c837d6f`;
- build: `docker run --rm -v /Users/pavel/public_windows:/work -w
  /work/m1n1_windows windows-on-m1-build:local sh -lc 'make clean && make
  -j8 RELEASE=1 APPLE_INPUT=0'`;
- artifact directory `investigation/artifacts/EXP-20260814-033`, m1n1 SHA-256
  `aff6ffc54594ac41b2841fc4bada47c0a39e908bfcba15f74bf788ec5ca0b932`,
  unchanged Mu SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`,
  manifest SHA-256
  `c714885a1a5aa52ef598575e68c8274213ecb667dd694908b08d468dc7af3d5d`;
- launch: `./scripts/run-windows.sh --execution assisted --observed --debug
  off --proxy <CONSOLE_DEVICE> --vuart
  <VUART_DEVICE> --firmware
  investigation/artifacts/EXP-20260814-033/J313_EFI.fd --m1n1
  investigation/artifacts/EXP-20260814-033/m1n1.macho --chainload
  --foreground`;
- recovery artifact: the existing ESP remains unchanged; terminate the sole
  assisted runner and reboot to return to Stage 1.

Expected checkpoint: physical and web displays both advance through firmware,
Windows logo and lock screen without proxy checksum errors or NUL runs.  If
Windows freezes, the web viewer must stop on the same visible state and the
sole launcher must retain valid framing so the next CPU/timer diagnosis can
use trustworthy evidence.

Failure criterion: any checksum error, parser desynchronisation, stale web
frame while the physical display continues, EL2 exception, reset, or inability
to reach the same Windows state as EXP-032.

Hardware result:
- the recorded hashes and manifest passed preflight from a freshly probed Stage 1;
  m1n1 `72b2aab` chainloaded once and remained the sole proxy/event owner;
- the J313 hardware reached the guest handoff, all seven secondary PSCI entries,
  NVMe ready and the xHCI route-enable checkpoint with Apple Input disabled;
- the bounded observer remained correctly framed throughout the run.  Metadata
  advanced from generation 16/frame 15 to generation 75/frame 74 without a
  checksum error, a zero-wire checksum, a NUL run or parser desynchronisation;
- the published framebuffer itself remained byte-identical at CRC32
  `0x99875e96` for more than two minutes and showed the Windows boot logo and
  spinner.  The known guest address `192.168.1.35` answered neither ICMP nor a
  bounded TCP/22 probe;
- no Windows bugcheck, EL2 exception, spontaneous reset or PSCI reset occurred
  before recovery.  Physical display, internal input, RDP and Windows CPU
  enumeration were not independently observed in this clean run and are not
  inferred;
- SIGTERM requested the documented final snapshot/reboot recovery.  The snapshot
  reported `HV WATCHDOG BHL: owner=0 count=1`, the same expected CPU0-owned state
  classified by EXP-023; it is not evidence of a leaked global lock.  The target
  returned to Stage 1 and a post-recovery probe succeeded.

Evidence:
- `investigation/artifacts/EXP-20260814-033/evidence/freeze-fb-info.json`,
  SHA-256 `390909f418fa05ef030c6bea97f83a5a46a870f7266bc6bd585b9a9db44e14ff`;
- `investigation/artifacts/EXP-20260814-033/evidence/freeze-fb.raw`, SHA-256
  `cdbfca1d7d5370ff64fc999c807efa85048ad951c56dd573eb7ffdbf263ae08a`;
- `investigation/artifacts/EXP-20260814-033/evidence/freeze-frame.png`, SHA-256
  `ab3689cd9b2a4a97059eb4e548e9462f492254573169e30509bdb7b4e02f6340`.

Verdict: confirmed for the observer-transport hypothesis and rejected as a
usable Windows runtime.  Keeping complete proxy events below 4 KiB eliminates
the EXP-032 CDC framing failure, while the unchanged release guest still freezes
with a correct, continuously published but byte-identical Windows framebuffer.
This independently excludes Apple Input (compiled out), a stale physical-only
DCP surface, and observer corruption as the root cause.  The next experiment
must retain the validated 4-KiB observer while collecting a bounded, zero-hot-path
CPU/vGIC/timer state transition at the first unchanged-frame interval.

### CORRECTION-20260814-003 — EXP-033 did not fully exclude Apple Input

EXP-033 compiled `HV_DISABLE_APPLE_INPUT` into m1n1, which skipped the
Apple-input ADT preflight, stage-2 identity mappings and physical-to-virtual IRQ
route.  It did **not** remove `AINP` from the unchanged Mu DSDT: firmware still
reported `_HID=APPL0001` and `_STA=0x0F`.  Therefore an already installed
Windows driver could still bind and perform its prepare-hardware MMIO reads.
The sentence claiming that EXP-033 independently excluded Apple Input is
superseded by this correction.  Observer validation remains valid.

### EXP-20260814-034 — true AINP-enumeration exclusion control

Status: confirmed build-pipeline defect; no hardware launch
Created (UTC): 2026-08-14T15:38:05Z
Completed (UTC): 2026-08-14T15:45:00Z

Hypothesis: the regression that began with the J313 keyboard/trackpad work is
caused by Mu advertising `AINP` as present before the Apple SPI3 power, clock,
pinctrl and reset contract is owned by any layer.  An installed Windows
`ACPI\\APPL0001` driver can consequently bind and read SPI/GPIO MMIO even when
m1n1 was built with `APPLE_INPUT=0`.  Removing only the ACPI enumeration should
allow the otherwise identical EXP-033 guest to progress past the frozen Windows
logo.

Single changed variable relative to EXP-033:
- Mu DSDT no longer includes `J313AppleInput.asl.inc`; m1n1, timer/vGIC policy,
  CPU count, Windows disk, NVMe, xHCI, display and observer are unchanged.

Source-first evidence inspected before build:
- live J313 ADT/register read is the first planned diagnostic command below;
- Asahi Linux `arch/arm64/boot/dts/apple/t8103.dtsi` describes SPI3 at
  `0x23510c000`, IRQ 617, a 120-MHz clock, SPI3 pinctrl and `ps_spi3` power
  domain; `t8103-j313.dts` adds the SPI HID transport, AP GPIO 195 and active-low
  nub GPIO interrupt 13;
- Asahi `drivers/spi/spi-apple.c` enables the controller clock before register
  initialization and initializes/reset FIFOs before registering the bus;
- current m1n1 `src/hv_apple_input.c` observes ADT, maps the three MMIO ranges
  and registers a level route, but does not own power, clock, pinctrl or reset;
- current Mu `DSDT.asl` unconditionally includes `AINP` with `_STA=0x0F`;
- current Windows AppleInput driver binds `ACPI\\APPL0001` and reads SPI/GPIO
  registers in `EvtDevicePrepareHardware`; it has no KMDF interrupt object or
  runtime DPC loop;
- official Arm generic-timer guidance, Mu GTDT/AIC sources and Microsoft
  `0x101`/`0x133` documentation were also checked because earlier failures were
  timer-shaped; Mu's only change since the pre-input commit is this DSDT include.

Observed ownership contract before the experiment:
- Mu owns ACPI enumeration and must not report a device usable until its
  dependencies are prepared;
- m1n1 currently owns stage-2 visibility and IRQ virtualization only;
- Windows would own SPI transactions, HID protocol and runtime recovery after
  a supported prepare/start contract exists;
- no current layer owns SPI3 power/clock/pinctrl/reset preparation for Windows.

Source contract before artifact build:
- root `/Users/pavel/public_windows`, branch
  `codex/canonical-public-release`, commit
  `c324955b87b0d4a04c26ba1ac4eb26961c011995`; tracked source outside the
  append-only ledgers is unchanged;
- m1n1 commit `72b2aab8a6089b2099242f3bdb4a8cfd08e1113b`, clean tracked
  diff SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
- Mu commit `63942398cccbd98127cfecbd7f936af99c837d6f`, one experimental
  tracked DSDT diff SHA-256
  `60a5e432ff53016969382c268fa2ca62eeaba9dcb6b3529db61e2f3a5583a41f`;
  existing nested checkout markers are not source changes.

Live evidence before build (read-only, Stage 1):
- the first diagnostic fetched the complete live ADT but stopped after using a
  nonexistent `ProxyUtils.read32` method; it made no controller-MMIO access;
- the corrected read observed `/arm-io/spi3` compatible `spi-1,spimc`, range
  `0x23510c000+0x4000`, child compatible `hid-transport,spi`, AP GPIO phandle
  106/pin 195, nub GPIO parent phandle 108 and interrupt pin 13;
- PMGR device `SPI3` resolves to pstate register `0x23b700258`, value
  `0x000000ff`: desired `0xf`, actual `0xf` (active) in the inherited Stage-1
  state;
- direct SPI controller reads were deliberately skipped: the PMGR observation
  is sufficient to disprove a simple already-powered-off explanation without
  risking an unowned peripheral access.  The narrower remaining hypothesis is
  Windows binding/prepare activity or a later ownership transition, not merely
  an SPI3 domain that was off at this sample.

Exact build command:

```sh
STANDALONE_BUILD_MU_ONLY=1 ./scripts/build-standalone.sh \
  --debug-build --display both --debug off
```

Build checkpoint: the first sandboxed attempt failed before build because Docker
API access was denied.  The approved retry compiled a new `DSDT.aml` without
`APPL0001`, but EDK2's incremental dependency graph left the final FD at its old
August 8 timestamp and old SHA-256 `0dba13c...`; that cached FD is rejected and
must not be launched.  The planned retry adds only Stuart's supported `--clean`
flag to the same DEBUG Mu build:

```sh
docker run --rm -e STANDALONE_IN_CONTAINER=1 \
  -v /Users/pavel/public_windows:/work -w /work/mu \
  windows-on-m1-build:local \
  /work/.build/mu-venv/bin/stuart_build --clean \
  -c Platform/MacBookAirMid2020Pkg/PlatformBuild.py \
  TOOL_CHAIN_TAG=CLANGPDB TARGET=DEBUG 'BLD_*_AIC_BUILD=FALSE'
```

Planned artifact:
- directory `investigation/artifacts/EXP-20260814-034`;
- unchanged m1n1 copied from EXP-033, SHA-256
  `aff6ffc54594ac41b2841fc4bada47c0a39e908bfcba15f74bf788ec5ca0b932`;
- experimental `J313_EFI.fd` and manifest hashes will be recorded after build
  and before launch;
- recovery artifact: unchanged ESP/Stage 1 plus EXP-033 assisted artifacts.

Exact launch command:

```sh
./scripts/run-windows.sh --execution assisted --observed --debug off \
  --proxy <CONSOLE_DEVICE> \
  --vuart <VUART_DEVICE> \
  --firmware investigation/artifacts/EXP-20260814-034/J313_EFI.fd \
  --m1n1 investigation/artifacts/EXP-20260814-034/m1n1.macho \
  --chainload --foreground
```

### EXP-20260814-038 result — LR state preserved and timer stall classified

Completed (UTC): 2026-08-14T16:43:09Z
Status: confirmed diagnostic contract and confirmed root cause

The exact pre-recorded artifact reported m1n1 `3aeef41`; all eight CPUs, NVMe,
guest runtime and xHCI reached their checkpoints.  Windows then remained on the
eight-second disk-check countdown while observer generations advanced from 43
to 64 and the complete framebuffer remained byte-identical at SHA-256
`53b7558e0a93482b4a10570e2efa73a5f1e01eff24278b703965a6106150efa8`.
TCP/22 remained unavailable.  Two explicit diagnostic boundaries advanced the
guest from that timer-dependent screen to black, after which observer generations
continued to 120 with a second byte-identical framebuffer SHA-256
`6992296c77327bc9aaab7ca4758501ce5d2bd2e3c1ec7050f400881ed9ffbdcb`.

The bounded dump change succeeded: every CPU record contains `lrc=8` and
`lr0..lr7`.  Two late snapshots more than ten seconds apart independently show:
- every CPU host tick counter advanced, queues were empty and bhl was not stuck;
- `CNTV_CTL=0x5` and `vinj=1` on the stalled vCPUs: the virtual timer remained
  enabled and expired while m1n1 still considered delivery owned;
- CPUs 1, 2, 4, 6 and 7 held pure Pending INTID 18 LRs
  (`0x5020020000000012`) and HCR.VI was asserted where sampled;
- CPUs 0, 3 and 5 held Active-only INTID 18 LRs
  (`0x9020020000000012`) with HCR.VI clear.  Those Active-only values and stale
  timer IAR/EOI timestamps persisted across both late snapshots;
- therefore the accepted latch's `timer_*_injected == true` branch incorrectly
  treats any live LR as sufficient.  It never reflects the still-asserted timer
  level into the architecturally required Active+Pending state, so EOI cannot
  expose a next Pending interrupt and Windows can wait indefinitely for time.

Preserved evidence:
- `investigation/artifacts/EXP-20260814-038/evidence/hv.log`, SHA-256
  `3429fb6cb7bceb28844b62808d09a1fa9a0f0a4ebd1fa16db1eeecb683882188`;
- `frame-a.raw` and `frame-b.raw`, both SHA-256 `53b7558e...`;
- `frame-c.raw`, `frame-d.raw` and `final-frame.raw`, all SHA-256
  `6992296c...`;
- `final-meta.json`, SHA-256
  `f344216fc22668196f7ee46be62cd423122702fe6d6e8d4489d982ebe0eebec1`.

Verdict: EXP-037's ambiguous timer-delivery hypotheses are resolved.  The
freeze is not caused by Apple Input, observer transport, a global hypervisor
lock, host-tick loss, LR scarcity or a missing timer LR.  It is a violated
level-sensitive PPI state transition in m1n1's vGIC owner: asserted+Active must
become Active+Pending, and deassertion must withdraw that Pending state.  The
diagnostic formatting change is hardware-validated; it is not itself the fix.

Recovery succeeded after the recorded SIGTERM boundary.  Installed Stage 1
`b791225` answered the live probe and reported eight CPUs and 8.0 GiB DRAM.

### EXP-20260814-039 — synchronize live virtual-timer LR level

Status: planned
Created (UTC): 2026-08-14T16:43:09Z

Hypothesis: synchronizing only the live virtual-timer INTID 18 LR with the
sampled CNTV assertion will close the demonstrated stall without restoring the
rejected 1-ms recovery source, changing CPU cadence, or replacing the accepted
timer queue/latch architecture.  Asserted+Active becomes Active+Pending;
deasserted+Active+Pending becomes Active.  Pending, Active+Pending and unrelated
LRs remain unchanged.

Source-first contract inspected:
- live J313 EXP-038 records above are the primary evidence and show the same
  Active-only INTID 18 on CPUs 0, 3 and 5 twice while `CNTV_CTL=0x5`;
- Arm GICv3/v4 Software Overview DAI0492 section 4.2 defines Pending, Active and
  Active+Pending and requires a level-sensitive source to retain its asserted
  state until the peripheral deasserts; the Generic Timer is a per-PE PPI;
- current m1n1 `src/hv_exc.c` masks Apple's virtual-timer FIQ route after expiry,
  then skips LR mutation whenever `timer_v_injected` is already true;
  `src/hv_vgic_diag.c` already has a tested, currently production-unused
  `hv_vgic_diag_sync_level_lr()` transition primitive;
- historical m1n1 `2ead84d` proved Active+Pending and advancing IAR/EOI on all
  CPUs in EXP-019, but it also replaced the queue, both INTID 17 and 18 paths,
  deactivation drains and ownership model.  EXP-039 does not restore that broad
  patch;
- Mu exposes the standard Arm Generic Timer/GIC contract to Windows; Microsoft
  documents that Windows uses built-in Arm Generic Timer support through GTDT.
  Mu, ACPI and Windows do not own m1n1's LR state machine and will not change;
- the Asahi/Linux side uses the architectural per-CPU Generic Timer/GIC PPI
  contract and contains no J313-specific substitute for virtual LR ownership.

Ownership: Windows programs CNTV and acknowledges/EOIs INTID 18; m1n1 owns the
Apple FIQ route, synthetic vGIC LR state, VI output and recovery from LR state;
Mu only describes the standard timer.  The correction therefore belongs in
m1n1's local timer-to-vGIC boundary.

Single changed runtime variable relative to EXP-038:
- reflect CNTV asserted/deasserted level into an already-live INTID 18 LR using
  the existing four-state helper.  Do not change INTID 17, deferred queue
  ownership, tick rates, fast-return policy or diagnostics.

TDD checkpoint: first require the production virtual-timer asserted branch to
synchronize a live LR even while `timer_v_injected` is true and require the
deasserted branch to withdraw a pending bit; observe RED on `3aeef41`.  Add a
mutation-sensitive host test for Active+asserted -> Active+Pending and
Active+Pending+deasserted -> Active, then implement the smallest call-site and
run focused, complete nested and root suites.

TDD and implementation result:
- RED: the new production-path contract failed on m1n1 `3aeef41` because
  `timer_sync_live_irq` did not exist;
- GREEN: the existing mutation-sensitive four-state host test and the new root
  call-site test pass.  Only the already-live virtual INTID 18 LR is synchronized;
  INTID 17, queue ownership, tick cadence and recovery remain unchanged;
- synchronization writes the LR and recomputes VI only when the level transition
  changes the state, avoiding extra LR writes for stable Pending or
  Active+Pending values;
- focused root tests passed 20/20, the complete nested C host suite passed, the
  complete root suite passed 257/257 in the project environment, and both diff
  checks passed;
- m1n1 implementation commit
  `ca6ab37ce0dbbb7c18da40102887aebb58cc9dbb`.

Hardware checkpoint after a clean RELEASE `APPLE_INPUT=0` build: boot through
the disk-check countdown without a diagnostic boundary, reach login and TCP/22,
then maintain continuously changing UI/time and IAR/EOI progress for at least
ten minutes.  Any static frame over two minutes, timer Active-only while
`CNTV_CTL=0x5`, `0x101`, `0x133`, reset or pause over five seconds rejects the
fix.  Recovery remains the unchanged Stage 1 and EXP-038 artifacts.

Pre-launch artifact record (UTC 2026-08-14T16:48:22Z):
- root `fc0a7b922f99beef34c5f42d934ea6af4386e99a`, m1n1
  `ca6ab37ce0dbbb7c18da40102887aebb58cc9dbb`, Mu
  `63942398cccbd98127cfecbd7f936af99c837d6f`; strict manifest records clean
  tracked source;
- exact clean build: Docker `make clean`, then
  `make -j8 RELEASE=1 APPLE_INPUT=0`; build succeeded with pre-existing warnings
  plus the same signedness warning family as the adjacent bounded LR scans;
- `investigation/artifacts/EXP-20260814-039/m1n1.macho`, SHA-256
  `74bbaf481875897e79b673b2813de40e351c019f08a6cd00abf7ece14099c554`;
- unchanged no-AINP `J313_EFI.fd`, SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- `MANIFEST.json`, SHA-256
  `3ac93f65dd7a4a696ed7c70bc618b0f219609d077bdcd4cb1806c6b4768a4f5f`;
  release/display-both/debug-off and both artifact roles verified;
- recovery: installed Stage 1 plus immutable EXP-038 artifacts.

Exact launch command:

```sh
./scripts/run-windows.sh --execution assisted --observed --debug off \
  --proxy <CONSOLE_DEVICE> \
  --vuart <VUART_DEVICE> \
  --firmware investigation/artifacts/EXP-20260814-039/J313_EFI.fd \
  --m1n1 investigation/artifacts/EXP-20260814-039/m1n1.macho \
  --chainload --foreground
```

Hardware result (UTC 2026-08-14T16:55:05Z):
- the exact recorded RELEASE artifact launched and reported m1n1 commit
  `ca6ab37`; all eight CPUs entered, NVMe reached runtime, and xHCI discovery
  completed;
- Windows froze on the same `To skip disk checking, press any key within 8
  seconds` screen.  Observer generations continued from 22 through 49 and 69,
  but the captured framebuffer remained byte-identical for more than two
  minutes at SHA-256
  `bcbcef15c93229fde86d0a5d0f8815ed5e1dae073a1c5056d5acf25feccff742`;
- the 30-, 60- and 120-second raw frames and final frame are under
  `investigation/artifacts/EXP-20260814-039/evidence/`; the 30-second PNG is
  SHA-256
  `31b8857f1a67637dabe72e69620bfdd0ff391217b5877b1d328c54060ea04484`;
- metadata SHA-256 values are
  `f3e5eb076bd38d1a5d7288163cff7c054ae3cacd38bb275d60a52b1fade658a2`
  at 30 seconds,
  `4b1004ed4680017752a0021d6ff9dd859b1a1c9ea47e42b88f7f683544d2b108`
  at 60 seconds, and
  `b3e04ccc36f66a179f01c99b0c73813d75e40d7e7fd6bf9f2b119ed6d62be7ed`
  at 120 seconds/final;
- TCP/22 never appeared.  Occasional observer transport checksum corruption
  appeared in the release console, but generation continued and independently
  saved frames remained byte-identical, so it is not used as the freeze
  criterion;
- SIGTERM was sent only to the verified launcher PID after the failure criterion.
  The final control path printed `BHL owner=0 count=1`; the later guest exception
  occurred during forced reboot and is not attributed as the initiating failure;
- recovery completed successfully: Stage 1 `b791225` responded after reboot and
  reported J313, all eight CPUs and 8.0 GiB DRAM.

Verdict: rejected.  Correcting Active to Active+Pending for an asserted live
INTID 18 is architecturally necessary but is not sufficient to wake/progress the
Windows vCPU.  The next experiment must preserve this correction and observe the
EOI/deactivation and physical wake boundary; it must not restore the rejected
1-ms polling source, trap WFI, or signal HCR.VI for an Active+Pending LR.

Finalized (UTC): 2026-08-14T16:55:05Z.

### EXP-20260814-040 — observe corrected timer level at the release freeze

Status: planned
Created (UTC): 2026-08-14T17:00:05Z

Hypothesis: EXP-039 rejected the sufficiency of the narrow INTID 18 level
correction, but its RELEASE profile could not prove which LR state survived at
the frozen disk-check countdown.  A monitor build of the exact same runtime
source will show either (a) `Active+Pending` now persists and the remaining
failure is after level synchronization, most likely at guest EOI/physical idle
wake, or (b) `Active-only` persists and the new production call site was not
reached for the sampled path.

Source-first contract inspected before the run:
- live EXP-038 J313 records show expired `CNTV_CTL=0x5` with both Pending-only
  `0x502...12` and Active-only `0x902...12` LRs, empty queues, advancing host
  ticks and idle-loop Windows PCs; diagnostic IPIs temporarily advanced the
  guest;
- EXP-039 used m1n1 `ca6ab37` and froze for over two minutes at the same
  countdown while observer generations advanced, but RELEASE intentionally
  omitted LR/IAR/EOI telemetry;
- current `src/hv_exc.c` maps asserted+Active INTID 18 to Active+Pending and
  current `src/hv_vgic.c` maps EOI Active+Pending to Pending before recomputing
  HCR.VI; it deliberately does not signal VI while the LR is still Active;
- upstream Asahi m1n1 keeps Apple's physical virtual-timer FIQ route enabled
  until the comparator asserts, then masks the route while reflecting timer
  state to the guest.  The Windows fork additionally owns synthetic vGIC LR and
  HCR.VI delivery;
- Mu's J313 DSDT contains only commented-out `_LPI` methods, while its GTDT/MADT
  expose the architectural Arm timer/GIC.  Windows therefore uses its inbox Arm
  timer/HAL path; Apple Input remains absent and cannot own CPU wake.

Ownership: Windows owns CNTV programming and IAR/EOI; m1n1 owns Apple timer FIQ
routing, LR state, synthetic VI and the physical wake boundary; Mu owns only
enumeration.  The smallest falsifiable checkpoint is two complete per-CPU
snapshots at least ten seconds apart during the reproduced static frame.

Single changed experimental variable relative to EXP-039:
- RELEASE/debug-off -> DEBUG/monitor, enabling sampled counters and complete LR
  snapshots.  Source commit `ca6ab37`, timer/vGIC policy, cadence, disabled
  recovery timer, disabled Apple Input, Mu/no-AINP firmware, topology, storage,
  xHCI and display layout remain unchanged.

Pre-run provenance: root `298e2c3b6396099af0c215e21acc743e0b64586d`,
m1n1 `ca6ab37ce0dbbb7c18da40102887aebb58cc9dbb`, Mu
`63942398cccbd98127cfecbd7f936af99c837d6f`; all three tracked diffs are empty
at SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

Exact planned build:

```sh
docker run --rm -v /Users/pavel/public_windows:/work \
  -w /work/m1n1_windows windows-on-m1-build:local make clean
docker run --rm -v /Users/pavel/public_windows:/work \
  -w /work/m1n1_windows windows-on-m1-build:local make -j8 APPLE_INPUT=0
```

After the clean build, copy `m1n1.macho` and the unchanged EXP-039 firmware to
`investigation/artifacts/EXP-20260814-040`, create and strictly verify a
DEBUG/monitor/both manifest, and append all hashes before launch.  The assisted
launch will use `--observed --debug monitor` and the same proxy/vUART devices.

Expected checkpoint: reproduce the byte-identical countdown or later freeze,
capture two complete LR banks and counter deltas, then request the final
snapshot/recovery.  Failure to reproduce is inconclusive because monitor
diagnostics can perturb timing.  A `0x101`, `0x133`, reset or exception rejects
the diagnostic as a clean reproduction.  Recovery remains installed Stage 1
and the immutable EXP-039 artifacts.

Recorded artifact before launch (UTC 2026-08-14T17:01:58Z):
- clean Docker monitor build completed from m1n1
  `ca6ab37ce0dbbb7c18da40102887aebb58cc9dbb` with `APPLE_INPUT=0`; warnings
  are the pre-existing signedness/unused-variable families recorded by prior
  monitor builds;
- root manifest commit `9ff74abb2503defb3cc129f35c06424cec9fcac4`, Mu
  `63942398cccbd98127cfecbd7f936af99c837d6f`, all tracked sources clean;
- `investigation/artifacts/EXP-20260814-040/m1n1.macho`, SHA-256
  `2556c430863a1e8b40715e91d1f8b37ef4c6a7ee1e956665df52bd903b102517`;
- unchanged no-AINP `J313_EFI.fd`, SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- `MANIFEST.json`, SHA-256
  `9986ab43b07a4f53bcde08dece1a037b67fb3d9ed052f41128b4cb54a4a979d3`;
  strict DEBUG/monitor/both and artifact-role verification passed.

Exact launch command:

```sh
./scripts/run-windows.sh --execution assisted --observed --debug monitor \
  --proxy <CONSOLE_DEVICE> \
  --vuart <VUART_DEVICE> \
  --firmware investigation/artifacts/EXP-20260814-040/J313_EFI.fd \
  --m1n1 investigation/artifacts/EXP-20260814-040/m1n1.macho \
  --chainload --foreground
```

Hardware result (UTC 2026-08-14T17:08:16Z):
- the exact monitor artifact reported m1n1 `ca6ab37`; CPUs 0 through 7 entered,
  NVMe and xHCI reached runtime, and no bugcheck or initiating EL2 exception was
  captured;
- observer generation advanced from 30 to 71 while two full 16,384,000-byte
  frames remained byte-identical at SHA-256
  `49d3595690a1571dc937594effd1f7a81846c1b3b8a3aa199e55915495f2e165`;
  TCP/22 was absent, confirming the visible countdown was a guest freeze rather
  than a stopped observer;
- after a diagnostic physical IPI boundary, the guest advanced from that
  countdown to a black frame, SHA-256
  `6992296c77327bc9aaab7ca4758501ce5d2bd2e3c1ec7050f400881ed9ffbdcb`.
  This repeats EXP-035/038's wake-assisted progress;
- the first useful complete snapshot proved the EXP-039 correction executes:
  CPU0 and CPU2 contained INTID 18 `Active+Pending` LRs
  (`0xd020020000000012`), while CPUs 1, 3, 4, 5 and 7 contained Pending-only
  `0x5020020000000012` with HCR.VI asserted; queues were empty and no LR
  shortage existed;
- over the next 38.84 seconds, CPU1's host tick count advanced 22378 -> 26260
  at the expected approximately 100-Hz cadence, while its Pending INTID 18 and
  guest SGI lifecycle counts remained unchanged.  Other secondaries showed the
  same live host/idle-Pending pattern;
- each requested physical diagnostic IPI moved timer state: the immediately
  following records show fresh INTID 18 IAR/EOI timestamps, and CPU2 changed
  from Active+Pending to Pending before the next stall.  The guest then returned
  to its idle path with another correctly represented Pending timer;
- complete evidence is
  `investigation/artifacts/EXP-20260814-040/evidence/hv.log`, SHA-256
  `729dda825353a4da58be72d80e5a16a42311b3cf79288a93079ecd612cdb78aa`;
  `frame-a.raw` and `frame-b.raw` have the countdown hash above, while
  `frame-c.raw` has the black-frame hash;
- SIGTERM targeted only the verified `run_uefi.py` PID after the failure
  criterion.  The final guest exception followed the requested recovery reboot
  and is not the initiating failure.  Stage 1 `b791225` then responded with all
  eight CPUs and 8.0 GiB DRAM.

Verdict: confirmed for the missing physical wake classification.  EXP-039's
level correction is effective and must remain, but LR+HCR.VI alone does not
reliably cause an Apple core in the Windows idle/WFI path to enter the virtual
IRQ.  A physical IPI boundary consumes the pending timer and advances the guest.
The next correction will issue one local physical IPI only on the false-to-true
edge of a priority-deliverable timer VI.  It will not poll, trap/skip WFI, signal
Active+Pending, alter timer cadence, or change Windows/Mu/input behavior.

Finalized (UTC): 2026-08-14T17:08:16Z.

### EXP-20260814-038 pre-launch continuation and ledger correction

Recorded (UTC): 2026-08-14T16:33:41Z

Correction: the historical EXP-036 hardware-result block that follows the first
EXP-038 planning text above was inserted out of chronological order; it describes
only EXP-036 (`0cde15e`, release artifact `8f545c13...`) and is not an EXP-038
result.  This appended correction preserves the old text while preventing it from
being interpreted as evidence for the not-yet-launched EXP-038 artifact.

Exact pre-launch source and artifact contract:
- root `d35bbfda6b6182c0c81ecd2a9f90a05ad340e376`, m1n1
  `3aeef41261ee51d7eaa922721773c0d199a44780`, Mu
  `63942398cccbd98127cfecbd7f936af99c837d6f`; manifest records clean tracked
  source (Mu's existing untracked nested markers are not included);
- clean Docker monitor build: `make clean`, then
  `make -j8 APPLE_INPUT=0`; build succeeded with only pre-existing warnings;
- `investigation/artifacts/EXP-20260814-038/m1n1.macho`, SHA-256
  `7a900c9120506b1a47a3740c2b7edd3dcee0b752c285ba82bd75f08d3bae796b`;
- unchanged no-AINP `J313_EFI.fd`, SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- `MANIFEST.json`, SHA-256
  `c28a7a279be1b5de09b376bb346ed59d8f25dd86e4d007b2f633b1ae14a73a69`;
  strict debug/display-both/monitor and artifact-role verification passed;
- recovery artifact: unchanged ESP/Stage 1 and the recorded EXP-037 artifacts.

Exact launch command:

```sh
./scripts/run-windows.sh --execution assisted --observed --debug monitor \
  --proxy <CONSOLE_DEVICE> \
  --vuart <VUART_DEVICE> \
  --firmware investigation/artifacts/EXP-20260814-038/J313_EFI.fd \
  --m1n1 investigation/artifacts/EXP-20260814-038/m1n1.macho \
  --chainload --foreground
```

Expected checkpoint: reproduce the late static framebuffer with advancing
observer generations, capture at least two watchdog snapshots ten seconds apart,
and verify that every CPU record now includes `lrc/lr0..lr7`.  Decode INTID 18's
LR state (Pending, Active, Active+Pending, or absent) on the stalled vCPUs.  A
missing LR bank, failure to reproduce, reset, or inconsistent snapshot is
inconclusive.  The final control action is an explicit SIGTERM snapshot/reboot,
followed by a Stage-1 eight-CPU/8-GiB recovery probe.

Hardware result:
- exact recorded monitor artifact launched and reported m1n1 `0cde15e`; all
  eight CPUs, NVMe, guest-runtime cadence and xHCI route checkpoints completed;
- Windows entered automatic disk checking after the preceding forced recovery,
  then the observed framebuffer became black and remained byte-identical for
  more than three minutes at SHA-256
  `cdbfca1d7d5370ff64fc999c807efa85048ad951c56dd573eb7ffdbf263ae08a`;
  the known TCP/22 endpoint remained unavailable;
- three diagnostic boundaries produced current records for all eight CPUs.
  Between samples every CPU's host tick arm/fire counters advanced and guest PCs
  moved; bhl reported only CPU0's expected print-time ownership, excluding a
  global EL2 deadlock;
- CPUs 2-5 continued updating timer INTID 18 IAR/EOI timestamps.  CPUs 0, 1, 6
  and 7 repeatedly showed `CNTV_CTL=0x5` (enabled and expired), `vinj=1`, the
  virtual-timer physical FIQ route disabled, HCR.VI clear, empty queues and stale
  timer IAR/EOI timestamps.  This localizes the late stall to an owned virtual
  timer delivery whose wake/acknowledgement state no longer progresses on those
  vCPUs;
- the monitor dump's single formatted CPU record exceeded the console formatting
  budget and truncated exactly after `marker`, before `lrc/lr0..lr7`.  Therefore
  the preserved run cannot distinguish a Pending-only LR from Active or
  Active+Pending, the distinction required before changing delivery semantics;
- evidence: `investigation/artifacts/EXP-20260814-037/evidence/hv.log`, SHA-256
  `f9a3c438013ce5c89a2ccae381d21e37d05bdcc949caa07512fc8d82012c9bba`;
  `stall.raw`, SHA-256
  `cdbfca1d7d5370ff64fc999c807efa85048ad951c56dd573eb7ffdbf263ae08a`;
  `final-meta.json`, SHA-256
  `ce215f1157e552373a5a6fad561526aae71defc9b32ceb0a36e82aa1a3111a76`;
- explicit recovery succeeded and the Stage-1 probe again verified eight CPUs
  and 8 GiB DRAM.

Verdict: hypothesis (c), global-lock deadlock, is rejected; host timer loss is
also rejected.  The run confirms a per-vCPU virtual-timer delivery stall but is
inconclusive between hypotheses (a) and (b) because the LR payload was truncated.
Do not alter timer state handling until that final state is captured.

Finalized (UTC): 2026-08-14T16:28:00Z.

### EXP-20260814-038 — preserve LR bank in bounded monitor snapshot records

Status: planned
Created (UTC): 2026-08-14T16:28:00Z

Hypothesis: splitting the existing watchdog CPU record into two bounded `printf`
formatting calls while keeping one newline-delimited logical record will preserve
`lrc/lr0..lr7` without changing sampled data or guest runtime behavior.  Repeating
the monitor run will then determine whether EXP-037's stalled `vinj=1`, VI-clear
vCPUs own a Pending, Active, Active+Pending, or no timer LR.

Single changed variable relative to EXP-037:
- diagnostic snapshot formatting only: CPU/timer/IRQ fields and LR fields are
  formatted in two bounded calls and terminated by the same single newline.

Unchanged: all runtime code and policies, snapshot cadence/content, m1n1 timer and
vGIC delivery, host tick rates, Apple Input disabled, Mu, Windows, CPUs, NVMe,
xHCI and displays.  The formatting executes only after an explicit diagnostic
request and cannot be a production fix.

Falsifiable software checkpoint: update the focused source contract first so the
summary must end after `marker` without a newline and a second call must emit
`lrc/lr0..lr7` plus the newline; observe RED on `0cde15e`, implement only the
split, then run the focused/root and complete nested suites.  The existing
line-oriented stability parser must continue accepting a synthetic split-call
logical record.

After the implementation commit, build the same clean non-RELEASE
`APPLE_INPUT=0` monitor artifact, record all hashes and launch command before
hardware use.  Capture two complete LR-bearing snapshots at the reproduced stall
and recover to Stage 1.

TDD and implementation checkpoint:
- RED: the focused source-contract test failed because the CPU record still
  formatted `marker`, `lrc` and all eight LRs in one oversized call;
- GREEN: the summary call now ends after `marker` with no newline, and a second
  bounded call appends `lrc/lr0..lr7` and the sole newline, preserving the exact
  logical record consumed by the line-oriented parser;
- focused vGIC/platform-stability suites passed 35/35, the complete nested C host
  suite passed, and both diffs passed checks;
- m1n1 implementation commit
  `3aeef41261ee51d7eaa922721773c0d199a44780`; no runtime path changed.

Hardware result:
- exact recorded artifacts launched and m1n1 reported `0cde15e`; all eight CPUs,
  NVMe and xHCI discovery initialized normally;
- unlike EXP-035, the guest advanced without any host diagnostic request from the
  Windows-logo frame SHA-256 `1b02574b...` to `guest runtime ready`, xHCI route
  enable and the Windows lock screen.  This confirms that the restored local VI
  recomputation closes a real early lost-wake window;
- the guest then stopped at the lock-screen frame showing 5:22.  From
  2026-08-14T16:11:48Z through 16:13:47Z, observer generations advanced from 127
  through 182 while the complete framebuffer remained byte-identical at SHA-256
  `6bccade3bf50e472a3b62ba4cac9a15d71a694a38570911d18fa36bdfe373260`;
- TCP/22 at the known guest address remained unavailable throughout.  A manual
  diagnostic boundary did not change the framebuffer hash or restore the network;
- preserved evidence:
  `investigation/artifacts/EXP-20260814-036/evidence/lock-screen.raw` and
  `post-wake.raw`, both with the framebuffer hash above; `final-meta.json`,
  SHA-256
  `a7ff2862fd2c85a16102badbce15480195452f1ee6b9e15da239dfdf26b68455`;
- the release profile intentionally contained no per-CPU watchdog records; the
  control boundary reported only the known CPU0 print-time lock ownership.  The
  exception dump again occurred after the explicit reboot request and is not
  treated as the initiating failure;
- recovery succeeded: both USB serial functions returned, Stage-1 m1n1 `b791225`
  answered, and the live probe verified eight CPUs and 8 GiB DRAM.

Verdict: rejected as the complete freeze fix, but confirmed as a partial
correction.  It moves the independently observed failure from early Windows boot
to the lock screen, proving one stale-VI boundary existed.  A second wake/progress
failure remains and requires a diagnostic-profile run that records live per-CPU
timer, LR, VI, ISR and lock state at the later checkpoint without changing the
accepted timer policy.

Finalized (UTC): 2026-08-14T16:15:48Z.

### EXP-20260814-037 — classify the later lock-screen stall with monitor snapshots

Status: planned
Created (UTC): 2026-08-14T16:15:48Z

Hypothesis: the remaining EXP-036 lock-screen stall is one of three distinguishable
states: (a) a deliverable Pending timer LR with HCR.VI asserted but no physical idle
wake, (b) an expired guest timer with no live/queued delivery, or (c) vCPUs blocked
behind the global hypervisor lock.  A normal monitor build of the exact EXP-036
runtime code will publish enough lock-free per-CPU state to select among these
without changing timer/vGIC policy.

Single changed experimental variable relative to EXP-036:
- RELEASE diagnostics off -> monitor diagnostics on, enabling sampled per-CPU
  snapshots and diagnostic counters but not verbose synchronous hot-path tracing.

Unchanged: m1n1 source commit `0cde15e`, restored fast-boundary VI recomputation,
5000/100-Hz cadence, accepted timer latch/repend path, disabled recovery timer,
Apple Input disabled, Mu/no-AINP firmware, eight CPUs, storage, xHCI and both
display consumers.  This is a diagnostic classification run, not a performance
acceptance build; any observer effect will be recorded.

Source contracts inspected:
- `src/hv_runtime_diag.h`: non-RELEASE enables counters and sampled snapshots;
  `HV_RUNTIME_DIAG_VERBOSE` remains absent, so timer/vGIC console formatting stays
  disabled;
- `src/hv_exc.c`: snapshot records host CNTP, guest CNTP/CNTV, VM timer routing,
  HCR/ICH state, ISR, timer latches/queues, SGI lifecycle, last IAR/EOI, all live
  LRs and breadcrumb; dump reads records without acquiring bhl;
- EXP-026 already validated that these counters distinguish host timer firing from
  guest delivery, while its 1-ms recovery policy is not present here.

Exact planned clean build:

```sh
docker run --rm -v /Users/pavel/public_windows:/work \
  -w /work/m1n1_windows windows-on-m1-build:local make clean
docker run --rm -v /Users/pavel/public_windows:/work \
  -w /work/m1n1_windows windows-on-m1-build:local \
  make -j8 APPLE_INPUT=0
```

Planned artifact directory:
`investigation/artifacts/EXP-20260814-037`; record a DEBUG/monitor/both manifest,
artifact SHA-256 and exact revisions before launch.  The assisted command will use
`--observed --debug monitor` and the same ports, firmware and foreground lifecycle
as EXP-036.

Expected checkpoint: reproduce the later static lock-screen frame, capture two
snapshots at least 10 seconds apart, then classify by deltas.  Failure to reproduce
is inconclusive because diagnostics can perturb timing; a dump with no current
per-CPU records also rejects the instrumentation.  Recovery remains Stage 1 and
the immutable EXP-036 artifacts.

Recorded artifact before launch:
- root `6b1ad9f4ccb9f0d265bd08d8d2aa5e7019c3fb6a`, m1n1
  `0cde15ea76e84e64b8effb37bec4308c2f211c59`, Mu `63942398`;
- `investigation/artifacts/EXP-20260814-037/m1n1.macho`, SHA-256
  `ea8b66aee0aad0629b38debd7b16ff86b22c7ae82d093645ccc50ec027a0ef3e`;
- unchanged no-AINP firmware SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- DEBUG/monitor/both manifest SHA-256
  `152437aeb44c9adb10b3561da80d20352fa963f30fb1f0b515291af590126181`;
  strict role verification passed and all tracked source revisions are clean.

Exact launch command:

```sh
./scripts/run-windows.sh --execution assisted --observed --debug monitor \
  --proxy <CONSOLE_DEVICE> \
  --vuart <VUART_DEVICE> \
  --firmware investigation/artifacts/EXP-20260814-037/J313_EFI.fd \
  --m1n1 investigation/artifacts/EXP-20260814-037/m1n1.macho \
  --chainload --foreground
```

Expected checkpoint: with valid observer framing, Windows must advance beyond
the EXP-033 frozen framebuffer, reach the lock/login screen, acquire the known
network address and remain continuously responsive for at least ten minutes.

Failure criterion: the same byte-identical Windows-logo interval for two minutes,
loss of observer framing, EL2 exception/reset, Windows bugcheck, or any new
failure before the EXP-033 checkpoint.

Planned evidence: `investigation/artifacts/EXP-20260814-034/evidence/`, viewer
metadata/frame, launcher/UART log, bounded ICMP/TCP checks and any Windows dump.
On failure, terminate the sole assisted runner to request the documented final
snapshot and reboot, then verify the Stage-1 probe.

Build and provenance result:
- the clean no-AINP `DSDT.aml` has SHA-256
  `78f50ccf35327f8c98358514bf65befc04fbd14e0ead12a335e11cafe5eca102`
  and contains no `APPL0001` string;
- the clean final FD nevertheless has SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`,
  exactly equal byte-for-byte to EXP-033 and all other assisted freeze artifacts;
- the EXP-033 FD timestamp is August 8, while Mu commit `63942398` adding AINP
  is dated August 13.  A clean build from the same Mu tree with the AINP include
  removed deterministically reproduces that old FD.

Verdict: superseded without a hardware launch.  EXP-033 already ran the
no-AINP firmware control; launching this identical binary again would change no
variable.  The AppleInput Windows driver cannot explain the reproduced EXP-033
freeze because the guest firmware artifact did not enumerate its ACPI hardware
ID.  The root problem remains in the common runtime path.

Recovery: no image was launched or installed; the target remained in Stage 1.

Next falsifiable checkpoint: restore the committed AINP include and perform a
clean Mu build without launching it.  The embedded ACPI payload and final FD
must change.  This packaging check determines whether the input work was merely
absent from artifacts or whether Mu also fails to carry rebuilt ACPI into the
firmware volume.

### CORRECTION-20260814-004 — artifact evidence restores EXP-033 input exclusion

CORRECTION-20260814-003 inferred the guest ACPI contract from Mu source commit
`63942398`, but the actual EXP-033 FD was a cached August 8 artifact.  The clean
no-AINP reproduction above proves that the launched FD was byte-identical to the
pre-input firmware.  Therefore EXP-033 did exclude AppleInput at the guest
artifact boundary, though not for the reason its manifest claimed.  The
observer result remains valid; the provenance/build-cache defect must be fixed
separately and future conclusions must inspect the built ACPI, not only source
commit metadata.

### CORRECTION-20260814-005 — commented ASL include was still expanded

The first EXP-034 control used `// #include`.  Mu's ASL preprocessing pipeline
preserved/exposed that directive in its intermediate input; the subsequent
clean AINP-on build produced the same `DSDT.aml` SHA-256 `78f50cc...`, and
`DSDT.iii` proved that `J313AppleInput.asl.inc` had been expanded.  Therefore
the claimed clean no-AINP reproduction and CORRECTION-004 conclusion are
invalid and superseded.  No hardware image was launched.

EXP-034 is reopened with a real preprocessor guard:

```asl
#if 0
#include "J313AppleInput.asl.inc"
#endif
```

The new Mu tracked diff SHA-256 is
`8fbfc301f9f64885565f621f1de035294fa45ffa419f82b0ee2b9be3385da90b`.
The next clean build uses the already recorded Docker/Stuart `--clean` command.
It is acceptable only if `DSDT.iii` contains neither `Device (AINP)` nor
`APPL0001`, `DSDT.aml` changes hash, and the final FD changes hash relative to
EXP-033.  Otherwise the artifact is rejected before launch.

### CORRECTION-20260814-006 — final EXP-034 packaging verdict

The true `#if 0` build produced `DSDT.iii` with no AINP.  After restoring the
committed include, a final clean build produced:
- `DSDT.iii` SHA-256 `dfd297910e2dbb4f0eaa4c5b1818d88e7736bc273edc36e591eaf7bc717c4d9e`,
  with `Device (AINP)` and `APPL0001` present;
- actual iasl input `DSDT.iiii` SHA-256
  `1734ce548c9ac8e2f115db5a52e1401432f4a1af4cd93173046dfbb724771c55`,
  with both AINP identifiers absent;
- final `DSDT.aml` SHA-256 `78f50ccf...` and FD SHA-256 `0dba13c...`,
  unchanged from the true no-AINP build and EXP-033.

Final verdict: Mu's `Trim --source-code -l` drops the body of the quoted ASL
include between C preprocessing and iasl.  AINP has never entered the tested
firmware artifact, so AppleInput is conclusively excluded as the cause of the
EXP-033 freeze.  CORRECTION-004's conclusion is restored by stronger pipeline
evidence; its earlier reasoning is not reused.  This packaging defect must get
its own TDD fix after runtime stability is restored.

Finalized (UTC): 2026-08-14T15:50:00Z.  No image was launched; Stage 1 remains
the recovery state.

### EXP-20260814-035 — zero-cost release tick diagnostics

Status: planned
Created (UTC): 2026-08-14T15:50:00Z

Hypothesis: commit `89d41fac` added diagnostic writes to every host tick after
the last responsive baseline.  In the release artifact CPU0 atomically updates
one element of a shared counter array at 5000 Hz, all seven secondaries update
adjacent elements at 100 Hz, and every CPU also updates `host_tick_fires`.
These measurements are never consumed because release snapshots return before
sampling.  Eliminating only those release writes should remove the shared-cache
and EL2 hot-path regression while preserving timer/vGIC behavior and all debug
observability.

Single changed variable relative to EXP-033:
- diagnostic tick counters become compile-time no-ops in RELEASE; no timer
  interval, interrupt delivery, guest state, Mu, ACPI, storage, USB, CPU count,
  display or observer change.

Source contract before TDD:
- root commit `c324955b87b0d4a04c26ba1ac4eb26961c011995`, branch
  `codex/canonical-public-release`; only append-only ledgers are dirty;
- m1n1 commit `72b2aab8a6089b2099242f3bdb4a8cfd08e1113b`, clean;
- Mu commit `63942398cccbd98127cfecbd7f936af99c837d6f`, tracked source clean;
- EXP-033 Mu/Windows artifact remains unchanged and already excludes AINP by
  CORRECTION-006.

Falsifiable software checkpoint: extend the real host runtime-diagnostics tests
so a diagnostic counter increments in debug and remains unchanged in RELEASE;
observe RED before adding the helper, then GREEN.  The RELEASE disassembly of
`hv_arm_tick`/FIQ must contain no counter RMW/store while retaining CNTP writes.

Planned build: clean Docker `make -j8 RELEASE=1 APPLE_INPUT=0`; artifact,
manifest, exact hashes and launch command will be recorded before hardware use.
Recovery remains the unchanged ESP/Stage 1 and EXP-033 artifacts.

TDD checkpoint before artifact build:
- RED: focused host compilation failed exactly because
  `HV_RUNTIME_DIAG_COUNT` did not exist;
- GREEN: debug behavior incremented a real counter from 41 to 42, while the
  RELEASE build left it at 41; both focused binaries passed;
- production now routes the two arm counters and `host_tick_fires` through the
  compile-time diagnostic counter contract; timer register writes are unchanged;
- root vGIC/runtime source-contract suite passed 16/16;
- current m1n1 tracked diff SHA-256
  `a3ac7c1d6d4b891696af03596bc0a29116d190e51e884851a5a9dd465387556b`.

Implementation commit and exact post-commit build:
- m1n1 `46c2240df2df467b9ee3d89b86f740f63a452acb`, tracked source clean;
- `docker run --rm -v /Users/pavel/public_windows:/work -w
  /work/m1n1_windows windows-on-m1-build:local make clean`;
- `docker run --rm -v /Users/pavel/public_windows:/work -w
  /work/m1n1_windows windows-on-m1-build:local make -j8 RELEASE=1
  APPLE_INPUT=0`.

Recorded artifact before launch:
- root `7c299066cc62133e9e44661af8042b2d12759aa9`, m1n1
  `46c2240df2df467b9ee3d89b86f740f63a452acb`, Mu `63942398`;
- `investigation/artifacts/EXP-20260814-035/m1n1.macho`, SHA-256
  `30d4c5fdcf724a4f0e516e1b11a349d71349506ebf57bf198c8a69d9c919f08c`;
- unchanged no-AINP `J313_EFI.fd`, SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- manifest SHA-256
  `f494d13c13d64096e128434cb96ed688c3f5356671286fe1d78583e03ed242f5`;
  strict release/display-both/debug-off role verification passed;
- RELEASE object disassembly retains `CNTP_TVAL_EL0`/`CNTP_CTL_EL0` in
  `hv_arm_tick` and has no tick-counter reference or RMW/store.

Exact launch command:

```sh
./scripts/run-windows.sh --execution assisted --observed --debug off \
  --proxy <CONSOLE_DEVICE> \
  --vuart <VUART_DEVICE> \
  --firmware investigation/artifacts/EXP-20260814-035/J313_EFI.fd \
  --m1n1 investigation/artifacts/EXP-20260814-035/m1n1.macho \
  --chainload --foreground
```

Expected checkpoint: all eight CPUs, NVMe and xHCI initialize; the valid viewer
advances beyond EXP-033's Windows-logo CRC, Windows reaches login/network, and
UI/SSH remain continuously responsive for ten minutes.  Failure is a two-minute
byte-identical framebuffer, any checksum loss, bugcheck/reset, or a pause longer
than five seconds.  Evidence goes under the artifact `evidence/` directory;
SIGTERM requests the final snapshot/reboot recovery.

Hardware result:
- the exact recorded m1n1 and Mu artifacts launched through the recorded assisted
  observed command; m1n1 reported commit `46c2240`, all eight CPUs entered, NVMe
  initialized, and xHCI discovery completed;
- the observer remained structurally healthy: metadata advanced from generation
  18/frame 17 to generation 60/frame 59, but the framebuffer stayed byte-identical
  at SHA-256
  `494fe4af7deeecdc4347e1ea314e6c742015f56ba59b181e892c75d96b539f7b`;
- the metadata evidence is
  `investigation/artifacts/EXP-20260814-035/evidence/freeze-fb-info.json`,
  SHA-256
  `219a14cfe23014c743fd80283ba6f517bd9530fa88c1be7c627b5ca7459a81bc`;
  the raw frozen frame is `freeze-fb.raw` with the framebuffer hash above;
- Windows did not reach its known TCP/22 endpoint.  The unchanged frame exceeded
  the two-minute failure criterion, so the release diagnostic writes are not the
  root cause of the freeze;
- when the host requested a diagnostic/recovery boundary, the guest immediately
  advanced far enough for m1n1 to print `guest runtime ready` and the xHCI route
  enable.  This repeats EXP-029's observation that an external EL2 wake can
  temporarily restore guest progress;
- the final control request observed the known diagnostic condition
  `BHL owner=0 count=1` while CPU0 was printing.  The exception dump appeared only
  during the forced recovery/reboot and is not attributed as the initiating guest
  failure;
- recovery completed successfully: the target returned to Stage 1, the probe
  responded, and both USB serial functions reappeared.

Verdict: rejected as the freeze root cause.  The change remains a correct
zero-cost RELEASE cleanup, but EXP-035 proves it is insufficient.  The reproduced
failure and wake-assisted progress localize the next check to the secondary FIQ
return boundary and its synthetic HCR.VI wake contract.

Finalized (UTC): 2026-08-14T16:02:28Z.

### EXP-20260814-036 — resynchronize synthetic VI before secondary idle return

Status: planned
Created (UTC): 2026-08-14T16:02:28Z

Hypothesis: EXP-028 removed the last `hv_vgic3_update_vi()` at the secondary FIQ
fast-return boundary.  `HCR_EL2.VI` is a software-cached output on this Apple-vGIC
implementation.  Most fresh injections update it, but the accepted timer latch
path deliberately does nothing while the same INTID remains live.  If another
guest vGIC transition cleared VI while a timer LR remained Pending, the current
fast path reads the stale clear value, returns to a Windows idle vCPU, and has no
physical event that guarantees a wake.  Recomputing VI from live LR/VMCR state
immediately after local timer/IPI handling should prevent that lost wake without
restoring the rejected 1-ms recovery timer or a global exit scan.

Evidence and source contract inspected before implementation:
- EXP-029 and EXP-035 both show that an external diagnostic wake temporarily
  restores progress; EXP-035 reproduces the freeze with Apple Input absent and
  RELEASE diagnostic writes compiled out;
- m1n1 `src/hv_exc.c`: the secondary fast path services `hv_update_fiq()` and
  `hv_handle_local_ipi()`, then decides from the current physical FIQ and cached
  HCR.VI bits whether to return directly;
- m1n1 `src/hv_vgic.c`: `hv_vgic3_update_vi()` derives the synthetic VI output
  from live Pending LR state, VMCR group enable, PMR, and running priority;
- m1n1 commit `091caeed` performed this recomputation only at the fast-return
  boundary and reached the desktop in EXP-017; commit `2ae94afc` removed it while
  restoring the accepted completion predicate, and the later no-recovery builds
  retain that removal;
- fresh inject/repend helpers update VI, but the `timer_*_injected == true` live-LR
  branch can legitimately retain the LR without recomputing VI.

Ownership contract: m1n1 owns Apple timer FIQ capture, virtual LR state and the
synthetic HCR.VI signal used to wake Windows.  Mu/ACPI owns enumeration only;
Windows owns timer programming and EOI/rearm after delivery.  Therefore the fix
belongs at m1n1's local FIQ-to-guest boundary, not in the input driver, Mu or
Windows.

Single changed runtime variable relative to EXP-035:
- after local timer/IPI service and before testing HCR.VI, recompute the synthetic
  VI line once from live local vGIC state.

Unchanged: 5000/100-Hz host cadence, accepted timer latch/repend path, disabled
guest recovery timer, global serialized exit policy, RELEASE diagnostics, Mu,
ACPI/no-AINP artifact, eight CPUs, storage, xHCI, display and observer profile.

Falsifiable software checkpoint: first change the focused source-contract test to
require one `hv_vgic3_update_vi()` after both local-source helpers and before the
HCR.VI completion read; observe RED on m1n1 `46c2240`, add only that production
call, then require GREEN plus the complete nested host and root vGIC suites.

Planned clean build: Docker `make clean`, then `make -j8 RELEASE=1 APPLE_INPUT=0`.
Record the implementation commit, artifact SHA-256 and strict manifest before
launch.  The exact assisted observed launch shape remains EXP-035 with only the
EXP-036 m1n1/artifact paths changed.  Recovery is the unchanged ESP/Stage 1 plus
the recorded EXP-035 artifacts.

Expected hardware checkpoint: advance past the frozen EXP-035 framebuffer, reach
login and the known network endpoint, then sustain continuous UI/SSH progress for
at least ten minutes with no pause over five seconds.  A byte-identical frame for
two minutes, dead network, bugcheck/reset or long pause rejects the hypothesis.

TDD and implementation checkpoint before artifact build:
- RED: the focused root contract failed on m1n1 `46c2240` because the secondary
  fast boundary contained zero `hv_vgic3_update_vi()` calls;
- GREEN: after adding exactly one recomputation after both local-source helpers
  and before the completion predicate, the focused test and root vGIC suite 16/16
  passed;
- the complete nested C host suite passed, the complete root suite passed 255/255
  when allowed to bind its loopback test server, and both repository diff checks
  passed;
- implementation commit:
  `0cde15ea76e84e64b8effb37bec4308c2f211c59`; m1n1 tracked source is clean.

The exact build now being run is the previously recorded clean Docker RELEASE
build.  No hardware launch is authorized until its artifact and manifest hashes
are appended below.

Recorded artifact before launch:
- root source commit `cd4cc923e2acfe09d6f2c3279f8cc52555ce04af`, m1n1
  `0cde15ea76e84e64b8effb37bec4308c2f211c59`, Mu `63942398`;
- `investigation/artifacts/EXP-20260814-036/m1n1.macho`, SHA-256
  `8f545c136ef77ca7226b66dbf6c16e0e035b0052380fd0743e9487785947afcb`;
- unchanged no-AINP `J313_EFI.fd`, SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- manifest SHA-256
  `38b85ceb72eb507064a4a791c1f69553675bd4b13739eb2d9d3e9573e3876dea`;
  strict release/display-both/debug-off role verification passed and records
  clean source revisions;
- build completed successfully; emitted warnings are pre-existing and unrelated
  to the single added call.

Exact launch command:

```sh
./scripts/run-windows.sh --execution assisted --observed --debug off \
  --proxy <CONSOLE_DEVICE> \
  --vuart <VUART_DEVICE> \
  --firmware investigation/artifacts/EXP-20260814-036/J313_EFI.fd \
  --m1n1 investigation/artifacts/EXP-20260814-036/m1n1.macho \
  --chainload --foreground
```

### EXP-20260814-041 — wake a newly deliverable timer VI with one physical edge

Status: rejected after hardware test
Created (UTC): 2026-08-14T18:11:50Z

Hypothesis: EXP-040 established that Windows can remain indefinitely in its idle
path with a priority-deliverable Pending INTID 18 LR and HCR.VI asserted, while
one physical IPI immediately causes a fresh timer IAR/EOI cycle and guest
progress.  Publishing HCR.VI followed by exactly one local physical IPI on the
clear-to-set edge of a deliverable architectural timer VI will supply the missing
J313 wake event without changing timer cadence, polling, trapping WFI, or
repeatedly interrupting a core while VI remains asserted.

Primary evidence and implementations inspected:
- live J313 EXP-040 telemetry: CPUs 1, 3, 4, 5 and 7 retained Pending-only INTID
  18 (`0x5020020000000012`) with HCR.VI set, empty queues, no LR shortage and
  advancing host ticks; a physical diagnostic IPI produced new timer IAR/EOI
  timestamps and framebuffer progress;
- current fork `m1n1_windows/src/hv_exc.c`, `src/hv_vgic.c`, `src/smp.c` and
  `src/cpu.c`: the fork owns Apple timer FIQ capture, LR state, HCR.VI synthesis,
  local physical IPI send/acknowledgement and the EL2-to-guest return boundary;
- current upstream Asahi m1n1 `src/hv_exc.c`: Apple timer FIQ routing and the
  physical exception boundary establish that a physical event enters EL2 before
  guest virtual interrupt delivery; no source was copied;
- current Mu J313 MADT/GTDT/DSDT generation: firmware exposes the architectural
  Arm GIC/timer contract to Windows and does not own runtime timer delivery;
- Arm GICv3/v4 architecture guidance: a Pending virtual interrupt in an LR and
  the virtual interrupt signal describe virtual distributor/CPU-interface state,
  while physical core wake is a separate implementation boundary;
- Microsoft ACPI system-description guidance and the generated Mu tables:
  Windows consumes the firmware-described architectural timer/GIC path; AINP and
  APPL0001 are absent from the artifact, so the unfinished Apple Input driver
  cannot bind in this experiment.

Observed ownership contract:
- Mu/ACPI owns enumeration; Windows programs CNTV, enters idle/WFI and performs
  virtual IAR/EOI; m1n1 owns physical timer routing, vGIC LR/HCR state and the
  physical wake needed to re-enter the guest;
- DMA is not involved in architectural timer delivery; storage, xHCI, DART and
  display mappings remain unchanged;
- Windows owns guest power policy, but m1n1 must turn a newly deliverable virtual
  timer into a hardware-visible wake edge on this Apple core;
- recovery remains the installed Stage 1 plus the immutable EXP-040 firmware and
  m1n1 artifacts.

Differences reconciled: Asahi/Linux handles its physical timer and idle wake in a
native kernel interrupt path; upstream m1n1 provides the physical EL2 boundary;
this Windows fork additionally virtualizes the GIC and must bridge HCR.VI to a
sleeping guest core.  Mu can describe the timer but cannot repair that runtime
EL2 wake contract, and a Windows input driver is outside the path.

Single changed runtime variable relative to EXP-040:
- when `hv_vgic3_update_vi()` finds Pending INTID 17 or 18 priority-deliverable
  and the previous HCR.VI value is clear, it writes HCR.VI, executes ISB, then
  sends one local physical self-IPI.  An already asserted VI, a non-timer IRQ,
  a masked timer and Active+Pending do not issue a wake.

Unchanged: 5000/100-Hz host cadence, timer comparator programming, live-LR level
synchronization, LR EOI transitions, recovery timer disabled, secondary fast
return, Mu/no-AINP firmware, Windows image, all eight CPUs, NVMe, xHCI, display
layout and observed monitor profile.

TDD and software checkpoint:
- RED: the new helper test failed to compile before the edge predicate existed,
  and the root integration test failed because `hv_vgic3_update_vi()` contained
  no timer edge wake;
- GREEN: the helper covers the true edge and all four suppressed cases; the
  integration contract requires HCR.VI write -> ISB -> local IPI ordering;
- focused root suites passed 49/49, the complete nested host suite passed, the
  complete root suite passed 258/258 in the project environment, and both diff
  checks passed;
- implementation commit `fa42daad5a4e047ed6c9e854f89410bd6b5d723e`;
  root contract/ledger commit `7466592e8011b521fea0ac9b008f5b7eca7b169d`;
  Mu `63942398cccbd98127cfecbd7f936af99c837d6f`; all tracked diff hashes are
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

Exact planned clean build:

```sh
docker run --rm -v /Users/pavel/public_windows:/work \
  -w /work/m1n1_windows windows-on-m1-build:local make clean
docker run --rm -v /Users/pavel/public_windows:/work \
  -w /work/m1n1_windows windows-on-m1-build:local make -j8 APPLE_INPUT=0
```

After the clean build, copy `m1n1.macho` and the unchanged EXP-040 firmware to
`investigation/artifacts/EXP-20260814-041`, create and strictly verify a
DEBUG/monitor/both manifest, and append all SHA-256 values before launch.  The
planned launch is:

Recorded artifact before launch (UTC 2026-08-14T18:14:03Z):
- the exact clean Docker monitor build completed from m1n1
  `fa42daad5a4e047ed6c9e854f89410bd6b5d723e` with `APPLE_INPUT=0`; emitted
  signedness, unused-variable, lifetime and stack warnings are the pre-existing
  warning families also present in EXP-040;
- source manifest root `7720645e2abb5c884f0263c4aad0887a55ff9d82`, Mu
  `63942398cccbd98127cfecbd7f936af99c837d6f`; tracked root, m1n1 and Mu diffs
  were empty before the build;
- `investigation/artifacts/EXP-20260814-041/m1n1.macho`, SHA-256
  `e8ab3d56817d1b1e8223235c0a2de3afa29b5f9af7c210de12768341575c9c7a`, size
  901120 bytes;
- unchanged no-AINP `J313_EFI.fd`, SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`,
  size 30965760 bytes;
- `MANIFEST.json`, SHA-256
  `e0700dbe9147678f1bdcb917ca8b0746d133799d17e163caa413252b68c78834`;
  strict DEBUG/monitor/both verification passed for both required artifact
  roles.  No guest image has been launched at this checkpoint.

```sh
./scripts/run-windows.sh --execution assisted --observed --debug monitor \
  --proxy <CONSOLE_DEVICE> \
  --vuart <VUART_DEVICE> \
  --firmware investigation/artifacts/EXP-20260814-041/J313_EFI.fd \
  --m1n1 investigation/artifacts/EXP-20260814-041/m1n1.macho \
  --chainload --foreground
```

Smallest falsifiable hardware checkpoint: at the first previously freezing
countdown/black/login frame, require autonomous framebuffer change and fresh
timer IAR/EOI activity without a manually requested diagnostic IPI.  Acceptance
then requires all eight CPUs, NVMe and xHCI alive plus continuous UI and TCP/22
progress for at least ten minutes with no pause over five seconds.  A
byte-identical frame for two minutes, dead network, bugcheck/reset, repeated
physical-wake storm or long pause rejects the hypothesis.  On failure, capture
two complete snapshots and frames, terminate only the verified runner PID, and
confirm Stage 1 recovery before any further change.

Hardware result (UTC 2026-08-14T18:21:48Z):
- the exact recorded artifact reported m1n1 `fa42daa`; CPUs 0 through 7 entered,
  NVMe initialized, xHCI reached runtime, and `guest runtime ready` appeared
  without any manual diagnostic boundary;
- Windows then remained at the disk-check `6 second(s)` frame.  Observer
  generation advanced 34 -> 77 while both full frames were byte-identical at
  SHA-256
  `19b3aa768ab56c507b7e63f709f9e1053dc91e0fe1f2a87b737f8b602a3fc947`;
  TCP/22 did not become available.  This exceeded the two-minute failure
  criterion;
- the first controlled physical diagnostic boundary advanced the framebuffer
  to a distinct SHA-256
  `910b80e2b0f62a66922e12c61894ac2e3894656911d5affbd132d7095ec695a9`,
  but the guest stalled again;
- the first snapshot still contained Pending-only INTID 18 with HCR.VI asserted
  on CPUs 1, 4 and 7, and Active+Pending INTID 18 on CPUs 5 and 6.  Queues were
  empty and host ticks advanced;
- between the second and final snapshots CPU1's physical IPI receive count rose
  82698 -> 101283 and CPU2's rose 120324 -> 138970, while their virtual IAR/EOI
  counts remained exactly 44574/44574 and 79472/79472.  CPUs 3, 4, 5 and 7 each
  received approximately 17800 additional physical IPIs with no virtual IAR/EOI
  progress.  CPU6, whose timer remained Active+Pending rather than Pending-only,
  received only one additional IPI, matching the tested suppression rule;
- current source explains the hardware trace: the new self-IPI is emitted inside
  `hv_vgic3_update_vi()` called by the secondary fast FIQ path, then
  `hv_handle_local_ipi()` acknowledges it in the same EL2 exception before the
  eventual guest ERET.  The IPI counter grows, but no wake remains pending at the
  physical return boundary;
- complete final UART evidence is
  `investigation/artifacts/EXP-20260814-041/evidence/hv-final.log`, SHA-256
  `f44417d9da7fa023a0a42fe4d07770119622f534ff28583097a7d4eb99f485f1`;
  the pre-termination snapshot log is `hv.log`, SHA-256
  `17e623c35cba39d4e11407285304c43784c58d97d28b231da56c752210b6bb92`;
- SIGTERM targeted only verified `run_uefi.py` PID 54380 after the failure
  criterion.  The printed guest exception followed the requested recovery
  reboot and is not the initiating freeze.  Stage 1 `b791225` then answered the
  proxy with eight CPUs and 8.0 GiB DRAM.

Verdict: rejected and superseded.  EXP-041 validates the timer-only edge
predicate but falsifies immediate self-IPI emission inside LR/VI publication.
It both consumes the wake before ERET and produces a high-rate EL2 IPI load.  No
release artifact may retain this placement.  The next falsifiable correction is
to latch the same edge, drain current physical sources normally, and emit at
most one deferred IPI at the common final EL2-to-guest return boundary.

Finalized (UTC): 2026-08-14T18:21:48Z.

### EXP-20260814-042 — defer timer wake across the FIQ return boundary

Status: rejected after hardware test
Created (UTC): 2026-08-14T18:27:34Z

Hypothesis: EXP-041 did generate the intended physical self-IPIs, but source and
hardware counters prove that `hv_handle_local_ipi()` acknowledged them inside the
same FIQ before guest ERET.  Retaining the identical timer/priority/HCR.VI edge
classification while deferring the actual self-IPI until after the last local
source drain and `hv_exc_exit()` will leave a physical event pending across ERET;
Windows will then enter its already-published Pending timer interrupt instead of
returning indefinitely to idle.

Sources and contracts inspected before implementation:
- EXP-041 `hv-final.log`: on CPU1 physical IPI receive advanced 82698 -> 101283
  and on CPU2 120324 -> 138970 while virtual IAR/EOI did not advance at all;
- `m1n1_windows/src/hv_exc.c`: the secondary FIQ fast path called
  `hv_update_fiq()` before `hv_handle_local_ipi()`, and the slow tail performed a
  final `hv_handle_local_ipi()` before `hv_exc_exit()`;
- `m1n1_windows/src/hv_vgic.c`: EXP-041 emitted the self-IPI synchronously from
  `hv_vgic3_update_vi()`, placing it before both possible drains;
- `m1n1_windows/src/hv_asm.S`: the C FIQ handler returns directly through saved
  guest-register restoration to ERET, so a send after `hv_exc_exit()` has no
  later C-level IPI acknowledgement before guest entry;
- current upstream Asahi m1n1 physical exception handling, Arm GICv3/v4
  guidance, Mu MADT/GTDT/DSDT generation and Microsoft ACPI timer/GIC contract
  remain as recorded by EXP-041.  No external code is copied.

Ownership is unchanged: Mu enumerates; Windows programs CNTV, idles and performs
IAR/EOI; m1n1 owns physical timer FIQ, LR/HCR.VI state, physical local IPI and the
final EL2 return.  No timer DMA exists.  Windows owns guest power policy while
m1n1 must preserve a physical wake until ERET.  Recovery remains installed Stage
1 plus immutable EXP-040/041 artifacts.

Single changed runtime variable relative to EXP-041:
- immediate `smp_send_ipi()` inside VI publication becomes a per-CPU deferred
  bit; the FIQ tail consumes that bit after `hv_exc_exit()`, performs ISB and
  sends the same local IPI.  The timer edge predicate and all other policy are
  byte-for-byte unchanged.

Unchanged: INTID 17/18 selection, exact Pending-only requirement, VMCR priority
masking, HCR.VI publication, Active+Pending suppression, 5000/100-Hz host cadence,
guest timer comparator and latch behavior, live-level synchronization, disabled
recovery polling/WFI trap, Mu/no-AINP firmware, Windows image, CPUs, NVMe, xHCI,
display and monitor profile.

TDD/software checkpoint:
- RED: the root ordering test failed because no deferred flush function existed;
- GREEN requires VI code to contain no physical send, the flush to order ISB
  before the send, and the final FIQ order to be local IPI drain ->
  `hv_exc_exit()` -> deferred wake flush;
- vGIC/platform suites passed 37/37, the complete nested host suite passed, the
  complete root suite passed 258/258 and diff checks passed;
- implementation commit `bf78a7675480bd1182d261e51c0f8bde15f95587`, root
  contract/ledger commit `d7a2a7ac6c0a7a7d10fc07c211d843a24ebf137b`, Mu
  `63942398cccbd98127cfecbd7f936af99c837d6f`; all tracked diff hashes are
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

Exact planned clean build:

```sh
docker run --rm -v /Users/pavel/public_windows:/work \
  -w /work/m1n1_windows windows-on-m1-build:local make clean
docker run --rm -v /Users/pavel/public_windows:/work \
  -w /work/m1n1_windows windows-on-m1-build:local make -j8 APPLE_INPUT=0
```

Freeze the monitor m1n1, unchanged no-AINP firmware and strict manifest under
`investigation/artifacts/EXP-20260814-042` before launch.  The planned command is:

Recorded artifact before launch (UTC 2026-08-14T18:29:03Z):
- clean Docker monitor build completed from m1n1
  `bf78a7675480bd1182d261e51c0f8bde15f95587` with `APPLE_INPUT=0`; warnings
  match the pre-existing families recorded for EXP-041;
- source manifest root `01e7677bd40a61ba138cb6fc1578942a49be9136`, Mu
  `63942398cccbd98127cfecbd7f936af99c837d6f`; tracked source diffs were empty;
- `investigation/artifacts/EXP-20260814-042/m1n1.macho`, SHA-256
  `d93b7a14db08c39c75d93466bbe3a38ad722c0fd34e292491c692ff22571666c`, size
  901120 bytes;
- unchanged no-AINP `J313_EFI.fd`, SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`,
  size 30965760 bytes;
- `MANIFEST.json`, SHA-256
  `8acb3498f8598c3ef0437ca35c5afb0769e46651bd1748c5a19d090bc315afdf`;
  strict DEBUG/monitor/both verification passed for both roles.  No guest has
  been launched at this checkpoint.

```sh
./scripts/run-windows.sh --execution assisted --observed --debug monitor \
  --proxy <CONSOLE_DEVICE> \
  --vuart <VUART_DEVICE> \
  --firmware investigation/artifacts/EXP-20260814-042/J313_EFI.fd \
  --m1n1 investigation/artifacts/EXP-20260814-042/m1n1.macho \
  --chainload --foreground
```

Smallest falsifiable checkpoint: the `6 second(s)` disk-check frame must change
autonomously without host SIGINT.  At the first later idle point, two snapshots
must show virtual timer IAR/EOI progress rather than physical IPI growth with
unchanged IAR/EOI.  Acceptance requires all eight CPUs, NVMe, xHCI, autonomous
login/TCP/22 and ten continuous minutes without a pause over five seconds.  A
two-minute identical frame, dead network, IPI-only growth, bugcheck/reset or
exception rejects the change.  Failure recovery is two snapshots/frames,
verified runner termination and Stage 1 probe before another modification.

Hardware result (UTC 2026-08-14T18:34:32Z):
- the exact artifact reported m1n1 `bf78a76`; all eight CPUs entered, NVMe and
  xHCI reached runtime, and Windows autonomously advanced beyond EXP-041's
  `6 second(s)` frame to the next disk-check phase;
- it then remained on one full frame from observer generation 27 through 80,
  SHA-256
  `b20c0b4f1f8150e0ad52a5dd7750e40c3d81c3464a323e2015197932a0fec5b6`,
  for more than two minutes.  A physical diagnostic boundary immediately
  changed the frame to the known black-screen SHA-256
  `6992296c77327bc9aaab7ca4758501ce5d2bd2e3c1ec7050f400881ed9ffbdcb`,
  after which it stalled again;
- the first snapshot showed correctly represented timer state: CPUs 4, 5, 6
  and 7 held Pending-only INTID 18 with HCR.VI asserted, while CPUs 0, 2 and 3
  held Active+Pending.  Queues were empty and host ticks advanced;
- across the two snapshots CPU1 physical IPI receives rose 22065 -> 48374 with
  virtual IAR/EOI fixed at 14516/14516; CPU5 rose 19961 -> 45404 with IAR/EOI
  fixed at 9286/9286.  CPU4 received 25438 extra physical IPIs for only 41
  virtual acknowledgements, and CPU7 received 25452 for only seven.  By
  contrast CPU2 remained Active+Pending and received only one additional IPI;
- therefore deferred placement preserves physical events across ERET, but the
  HCR.VI-bit edge is not a stable one-wake-per-delivery identity.  It repeatedly
  re-arms while the same Pending timer remains unconsumed and creates a physical
  FIQ storm that can itself starve guest execution;
- complete final evidence is
  `investigation/artifacts/EXP-20260814-042/evidence/hv-final.log`, SHA-256
  `459948ab3ef3af2df731fbea89cf5e9a7d747d692c11e66ebdb27d4809cdbcc4`;
  the two-snapshot pre-termination log is `hv.log`, SHA-256
  `78a94bd23dc1edc8b87d9a4faf5d4c4c63d2d200a924a60b7e493e729e84d8db`;
- SIGTERM targeted only verified runner PID 74280.  The recovery exception was
  requested, not initiating; Stage 1 `b791225` returned and reported eight CPUs
  and 8.0 GiB DRAM.

Verdict: rejected as a complete fix, but it confirms correct deferred placement.
The remaining violated contract is edge identity: one physical wake must be
associated with one continuous priority-deliverable Pending timer interval, not
with the observable HCR.VI bit.  The next change will retain deferred placement
and replace only the HCR-derived edge with a per-CPU deliverability latch that
resets when the timer ceases to be Pending and deliverable.

Finalized (UTC): 2026-08-14T18:34:32Z.

### EXP-20260814-043 — one deferred wake per deliverable Pending interval

Status: rejected after hardware test
Created (UTC): 2026-08-14T18:38:41Z

Hypothesis: EXP-042 proved that an IPI deferred past `hv_exc_exit()` survives the
EL2 return boundary, but HCR.VI is not a stable delivery identity and generated
over 25000 physical FIQs while one Pending timer remained unacknowledged.  A
per-CPU latch driven by the computed condition `signal && timer_signal` will emit
one deferred physical wake when a Pending INTID 17/18 first becomes
priority-deliverable, suppress all repeats while that exact condition persists,
and re-arm only after IAR, masking or LR removal ends the interval.

Primary evidence/source contract:
- EXP-042 snapshots show Pending-only INTID 18, empty queues and HCR.VI alongside
  CPU1 IPI 22065 -> 48374 with IAR/EOI fixed at 14516, and CPU5 IPI 19961 ->
  45404 with IAR/EOI fixed at 9286;
- `m1n1_windows/src/hv_vgic.c` already computes exact Pending state, VMCR group
  enable, PMR and timer INTID before publishing VI; that computed deliverability
  is the authoritative lifecycle input, not a reread of HCR.VI;
- `src/hv_vgic_diag.c` now models the two-state transition independently, while
  `src/hv_exc.c` retains EXP-042's proven final-FIQ deferred placement;
- J313 live state, upstream Asahi m1n1 physical timer path, Arm GIC guidance, Mu
  MADT/GTDT/DSDT and Microsoft ACPI expectations are unchanged from EXP-040
  through EXP-042.  No external implementation is copied.

Ownership remains m1n1 for physical FIQ, LR/VI, wake identity and recovery;
Windows for comparator, idle and IAR/EOI; Mu for enumeration.  Timer DMA does not
exist.  The input driver and its absent ACPI node remain outside this path.

Single changed runtime variable relative to EXP-042:
- the wake edge source changes from the observed HCR.VI bit to a per-CPU latch of
  continuous priority-deliverable Pending timer state.  Deferred placement, IPI
  primitive and every timer/vGIC policy input remain unchanged.

TDD/software checkpoint:
- RED: the host test failed on the missing transition type/function and the root
  contract failed on the missing per-CPU deliverability state;
- GREEN: false->true defers once, true->true suppresses, loss of deliverability
  resets, and the next false->true defers again;
- vGIC/platform suites passed 37/37, complete nested host tests passed, complete
  root tests passed 258/258 and diff checks passed;
- implementation commit `bce59a28ff72ae750bee52de87c2c3ff03593943`, root
  contract/ledger commit `74d64f0c62477b47b7acd1f6b3e46c7eb9366ae0`, Mu
  `63942398cccbd98127cfecbd7f936af99c837d6f`; tracked diffs are empty at
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

Exact planned build and launch are EXP-042's clean Docker monitor build and
assisted observed command with only EXP-043 paths changed.  Freeze m1n1, the
unchanged no-AINP firmware and a strict DEBUG/monitor/both manifest before use.
Recovery remains Stage 1 and the immutable earlier artifacts.

Smallest checkpoint: autonomously pass both EXP-041's `6 second(s)` frame and
EXP-042's next disk-check frame.  Two idle snapshots must show IAR/EOI progress
or stable physical IPI counts for an unchanged Pending interval; an IPI-only
increase greater than one rejects the latch.  Final acceptance is login/TCP/22
and ten continuous minutes with all eight CPUs, NVMe, xHCI and UI responsive and
no pause over five seconds.  A two-minute frame, bugcheck/reset or exception is
failure.  After this third bounded wake-correction experiment, any rejection
requires an architectural reassessment rather than another incremental wake
patch.

Recorded artifact before launch (UTC 2026-08-14T18:40:08Z):
- clean Docker monitor build completed from m1n1
  `bce59a28ff72ae750bee52de87c2c3ff03593943` with `APPLE_INPUT=0`; only the
  pre-existing warning families were emitted;
- source manifest root `8e20ad298f7fb85355916830ec1ac06eab0a2dfa`, Mu
  `63942398cccbd98127cfecbd7f936af99c837d6f`; tracked source diffs were empty;
- `investigation/artifacts/EXP-20260814-043/m1n1.macho`, SHA-256
  `5de49b72c1028bdd7a35f328173abed3e7b764be6fb8a3ddb5b0ccb3f3cb8bd5`, size
  901120 bytes;
- unchanged no-AINP `J313_EFI.fd`, SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`,
  size 30965760 bytes;
- strict DEBUG/monitor/both `MANIFEST.json`, SHA-256
  `ff230a72213f528f49f40e5874b097876bb0283493ebbca8dfe15e42720aebc5`,
  passed both artifact-role checks.  No launch occurred before this record.

Exact launch command:

```sh
./scripts/run-windows.sh --execution assisted --observed --debug monitor \
  --proxy <CONSOLE_DEVICE> \
  --vuart <VUART_DEVICE> \
  --firmware investigation/artifacts/EXP-20260814-043/J313_EFI.fd \
  --m1n1 investigation/artifacts/EXP-20260814-043/m1n1.macho \
  --chainload --foreground
```

Hardware result (completed UTC 2026-08-14T18:44:10Z):
- Windows autonomously passed both previously frozen disk-check frames from
  EXP-041 and EXP-042 without a host SIGINT or diagnostic IPI.  All eight CPUs,
  NVMe, xHCI and the framebuffer reached guest runtime.
- After the black transition the guest remained active long enough to issue its
  own bugcheck: `DPC_WATCHDOG_VIOLATION (0x133)`, parameters
  `P1=0x1 P2=0x1e00 P3=0xfffff802972083b0 P4=0x0`, seen by CPU0.  Microsoft
  defines parameter 1 value 1 as cumulative extended time at IRQL
  `DISPATCH_LEVEL` or above; this is not evidence for one individually long DPC.
- The bugcheck snapshot no longer shows a persistent Pending architectural
  timer on CPUs 1 through 7: their timer controls are inactive or masked,
  `vinj=0`, virtual queues are empty, and all live LR slots are empty.  CPU0 has
  one active SGI LR.  This rejects the prior repeated-wake storm as the immediate
  final failure while proving that the broader high-IRQL latency defect remains.
- Windows requested PSCI system reset after displaying the blue-screen frame;
  the reset was guest-initiated, not a host recovery action.  The public runner
  then lost the re-enumerating serial endpoint and exited.  Stage 1 recovery was
  subsequently confirmed at commit `b791225` with eight CPUs and 8 GiB.

Evidence:
- `investigation/artifacts/EXP-20260814-043/evidence/hv.log`, SHA-256
  `4b02330d77a0dec1561018e2d220adf5a3825d6ed402deb6972afff58107eb7a`;
- final raw framebuffer, SHA-256
  `a8954ee6116dc33e731281af7d462bbb8d2511670a41a3211a14e6d6a26fb580`;
- rendered blue-screen PNG, SHA-256
  `c3556a02bf04a00ddbe6f4f7f5d868cc566fc54ecb4525a04c6bef59823a1d7a`;
- framebuffer metadata, SHA-256
  `f3f0de08644bdbb8cefe2be7191eba8cb99e6771c3c65ff816532909d4b173d9`.

Verdict: rejected for stability.  The explicit deliverability latch is a valid
classification improvement over EXP-042 and eliminated its repeated physical
IPI storm, but the artifact failed the no-bugcheck acceptance criterion with a
Windows cumulative high-IRQL watchdog.  Per the pre-recorded three-attempt bound,
no further incremental wake patch is justified.  The next step is an
architectural A/B against the exact accepted 2026-08-13 contract and collection
of the new Windows dump before changing timer or vGIC policy again.

### EXP-20260814-044 — accepted-runtime A/B with only the proven SMP wake fix

Status: rejected after hardware test
Created (UTC): 2026-08-14T18:53:41Z

Hypothesis: the recurrent freezes and EXP-043 cumulative high-IRQL watchdog are
caused by the m1n1 timer/vGIC runtime changes after the accepted 2026-08-13
checkpoint, not by Mu, Windows, NVMe, xHCI or the unbound Apple Input driver.
Running exact m1n1 `55531e9` plus only EXP-015's hardware-proven dual IPI+SEV
mailbox wake and unconditional acknowledgement will restore the accepted timer,
vGIC and FIQ contract while removing that checkpoint's intermittent secondary
startup race.

Single changed variable relative to EXP-043:
- the complete m1n1 runtime is replaced by the accepted `55531e9` source contract
  plus the one `src/smp.c` mailbox correction from EXP-015.  Firmware, Windows
  installation, eight-CPU layout, NVMe, xHCI, physical machine and
  DEBUG/monitor/both observation profile are unchanged.  This exact-source A/B
  deliberately removes all later timer/vGIC and Apple-input mapping work as one
  bounded version variable; it is not a new incremental wake patch.

Sources and observed contract inspected before launch:
- live EXP-043 UART/LR/timer snapshot and 0x133 parameters; Microsoft documents
  `P1=1` as cumulative extended time at IRQL `DISPATCH_LEVEL` or above;
- accepted root `5d827ba6b7f50daf538df0a167ed123c9a1f5731`, m1n1
  `55531e9d9443e2543e172ed4c7f6ef8a7173a54e` and Mu gitlink
  `9dccb0133f244f2e4de7e3862dcb9f0ef7ba4776`;
- accepted and current `src/hv.c`, `src/hv_exc.c`, `src/hv_vgic.c`,
  `src/hv_fiq_fast_path.c`, `src/hv_tick_policy.c` and `src/smp.c`;
- EXP-006 through EXP-016 hardware history.  EXP-006 rejected unmodified
  `55531e9` only for the intermittent secondary mailbox race; EXP-014 proved
  dual IPI+SEV wake on all secondaries, and EXP-015 moved acknowledgement outside
  both sleep paths without changing timers or vGIC.

Ownership: m1n1 owns physical FIQ, architectural-timer virtualization, vGIC LR/VI,
secondary mailbox wake and recovery; Windows owns comparator programming,
IAR/EOI, DPC accounting and the crash dump; Mu owns ACPI enumeration and remains
byte-identical.  Timer DMA does not exist.  This m1n1 predates Apple Input
passthrough, and the unchanged no-AINP firmware gives its Windows driver no node
to bind, so input cannot execute in this control.

Artifact provenance:
- historical build command recorded by EXP-015: clean plain `make -j8` from
  `55531e9` with only the exact `src/smp.c` diff SHA-256
  `a474fde3e9bbb12ec17e2bab217a36eafce1df584aedb99f6d1a282937c64f25`;
  the historical compiler version was not recorded and is explicitly marked as
  unknown rather than guessed;
- byte-identical copy of `investigation/artifacts/EXP-20260813-015/m1n1.macho`
  at `investigation/artifacts/EXP-20260814-044/m1n1.macho`, SHA-256
  `f34bbc2cb8d5ef7b4b45b5daa9b233f04ed4acd6c1ac33a905e9c5e9cd552fb7`,
  size 917504 bytes;
- unchanged `J313_EFI.fd`, SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`,
  size 30965760 bytes;
- `investigation/artifacts/EXP-20260814-044/MANIFEST.json`, SHA-256
  `37bdb095ac779e8fddbb6efc68f594936d061e4e91d441e63731cba5397379b4`,
  records root `5d827ba`, m1n1 `55531e9`, the exact dirty diff and the full
  eight-CPU guest layout.  Strict assisted and firmware role verification passed.
- current ledger repository is root `dda63f8fd40d40e1e8ea1aba2f2b8cdb314ad630`,
  m1n1 `bce59a28ff72ae750bee52de87c2c3ff03593943`, Mu
  `63942398cccbd98127cfecbd7f936af99c837d6f`; all tracked diffs are empty.

Exact launch command:

```sh
/private/tmp/wom1-root-5d827ba.WCgcVM/scripts/run-assisted.sh \
  --proxy <CONSOLE_DEVICE> \
  --vuart <VUART_DEVICE> \
  --firmware /Users/pavel/public_windows/investigation/artifacts/EXP-20260814-044/J313_EFI.fd \
  --display both --debug monitor --chainload \
  --m1n1 /Users/pavel/public_windows/investigation/artifacts/EXP-20260814-044/m1n1.macho \
  --foreground
```

Smallest falsifiable checkpoint: all seven secondary mailboxes complete, CPUs 0
through 7 enter once, and Windows autonomously passes the EXP-041/042 frames to
desktop or network without a manual physical IPI.  A mailbox stall, two-minute
static frame, bugcheck/reset or physical-wake storm rejects the control.  If the
guest reaches SSH, preserve the new `MEMORY.DMP` before workload, then require at
least ten continuous responsive minutes and compare its timer/IAR/EOI cadence
with EXP-043.  Recovery is the unchanged installed Stage 1 `b791225`; terminate
only the verified foreground runner and confirm the proxy reports eight CPUs and
8 GiB after any failed run.

Hardware result (completed UTC 2026-08-14T19:00:59Z):
- the exact artifact reported `m1n1 55531e9-dirty`; every secondary mailbox was
  published, entered and consumed, and CPUs 0 through 7 emitted `CPU_ENTRY`.
  NVMe became ready and xHCI enabled its route.  This confirms that EXP-015's
  isolated SMP correction removes the old startup race.
- Windows then remained on a byte-identical black framebuffer for more than two
  minutes.  The last valid frame advanced from generation 40 to 118 while its
  SHA-256 stayed
  `6992296c77327bc9aaab7ca4758501ce5d2bd2e3c1ec7050f400881ed9ffbdcb`;
  TCP/22 was absent and no autonomous bugcheck or reset appeared.
- Two post-failure snapshots showed CPU0 and CPUs 3 through 7 at the same Windows
  idle PCs with unchanged virtual IAR/EOI counters.  CPU3 remained at
  `17005/17005`; CPU4 at `12189/12189`; CPU5 at `12357/12357`; CPU6 at
  `12374/12374`; and CPU7 at `12260/12260`.  Only each requested physical
  diagnostic IPI advanced.  CPUs 1 and 2 sampled newer timer acknowledgements,
  but did not restore system progress.
- CPU0 and CPUs 3 through 7 retained expired INTID 18 Active-only LRs
  (`0x9020020000000012`) with `CNTV_CTL=0x5`, `vinj=1` and empty queues.  Their
  `HCR_EL2` values ended in `0x039` or `0x0b9` and therefore lacked architectural
  `TWI|TWE` (`bits 13|14`) in this plain historical build.  Windows could stay in
  physical WFI even though a virtual timer level needed another delivery phase.
- The old 16 KiB framebuffer event path began emitting the previously documented
  checksum corruption only after the first diagnostic snapshot.  The valid
  byte-identical black-frame failure preceded it, so observer corruption is not
  the guest freeze cause.
- SIGTERM targeted only verified `run_uefi.py` PID 4304.  Its documented
  unhandled diagnostic return produced the printed guest exception and reboot;
  that exception is recovery-induced, not the initiating freeze.  Stage 1
  `b791225` then answered the proxy probe with eight CPUs and 8 GiB.

Evidence:
- raw UART/observer log
  `investigation/artifacts/EXP-20260814-044/evidence/hv.log`, SHA-256
  `3212a48c30fd0048a9d16168ad55f4e17132e374d719ad9c61be63d65862220c`;
- final valid black framebuffer, SHA-256
  `6992296c77327bc9aaab7ca4758501ce5d2bd2e3c1ec7050f400881ed9ffbdcb`;
- rendered PNG, SHA-256
  `880a9a589539b7d9aaeeca93fe1eb9662b5e17e95f2c753d688e72975162af2e`;
- framebuffer metadata, SHA-256
  `ac12ee80e79e99ca08af64199f036538eaff34a592173e4e77e04b8d5b5bef75`.

Verdict: rejected, and the post-`55531e9` regression hypothesis is disproved.
The intermittent freeze exists in the accepted source contract itself.  The A/B
instead exposes a build-contract defect: documentation claims the accepted
checkpoint makes WFI/WFE trapping non-optional, but source keeps `TWI|TWE` behind
`DIAG_TRAP_WFX=1`, and the recorded monitor/plain build does not set that flag.
The next single-variable control is the same exact runtime with only
`DIAG_TRAP_WFX=1`; no timer, vGIC, Mu, Windows or input behavior may change.

### EXP-20260814-045 — make the documented WFI/WFE trap policy real

Status: rejected after hardware test
Created (UTC): 2026-08-14T19:04:01Z

Hypothesis: EXP-044 freezes because its plain build omits `HCR_EL2.TWI|TWE`, so
Windows can remain in physical WFI with an expired Active-only virtual timer LR.
Compiling the byte-identical accepted runtime plus SMP fix with only
`DIAG_TRAP_WFX=1` will enforce the already-documented WFI/WFE trap invariant on
all boot and secondary HCR writers and restore autonomous timer progress without
a physical self-IPI or polling-rate change.

Single changed variable relative to EXP-044:
- build flag `DIAG_TRAP_WFX`: absent -> `1`.  Source diff, timer rates, vGIC LR
  algorithms, SMP correction, Mu, Windows, storage, USB, display, input absence,
  CPU/memory layout and launch profile are unchanged.

Source contract and ownership:
- `src/arm_cpu_regs.h` defines `HCR_TWI=BIT(13)` and `HCR_TWE=BIT(14)`;
- `src/hv.c` applies and verifies those bits in initial HCR, guest preflight,
  secondary HCR state and every `hv_write_hcr()` only when
  `HV_DIAG_TRAP_WFX` is compiled.  `Makefile` maps that macro only from
  `DIAG_TRAP_WFX=1`;
- the accepted platform document says this policy is non-optional, but the old
  build pipeline enables it only for `debug=full`, not `debug=monitor`.  EXP-044
  directly measured HCR without bits 13/14 on every frozen core;
- m1n1 owns WFI trapping and virtual-timer wake.  Windows still owns comparator,
  idle and IAR/EOI; Mu and the unbound Apple Input driver remain uninvolved.
  Timer DMA does not exist.

Software/build checkpoint:
- the complete historical nested host suite passed with the exact EXP-044 source
  diff before build;
- exact build command:

```sh
cd /private/tmp/wom1-root-5d827ba.WCgcVM/m1n1_windows
PATH="/opt/homebrew/opt/rustup/bin:$PATH" make clean
PATH="/opt/homebrew/opt/rustup/bin:$PATH" make -j8 DIAG_TRAP_WFX=1
```

- `build/build_cfg.h` contains exactly `#define HV_DIAG_TRAP_WFX`; compiler is
  Homebrew clang 22.1.8;
- runtime source remains root `5d827ba6b7f50daf538df0a167ed123c9a1f5731`,
  m1n1 `55531e9d9443e2543e172ed4c7f6ef8a7173a54e` plus SMP diff SHA-256
  `a474fde3e9bbb12ec17e2bab217a36eafce1df584aedb99f6d1a282937c64f25`,
  and Mu `9dccb0133f244f2e4de7e3862dcb9f0ef7ba4776`;
- current ledger root `764612f12584789abbefbd66ec1f660eb0da3622` and
  current tracked root/m1n1/Mu diffs are empty.

Artifacts:
- `investigation/artifacts/EXP-20260814-045/m1n1.macho`, SHA-256
  `a4d4a85af2ec08d288fe42c86244f735fadff66e0bb9f1cfdba89772bd396655`,
  size 917504 bytes;
- unchanged `J313_EFI.fd`, SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- strict DEBUG/monitor/both `MANIFEST.json`, SHA-256
  `3f16d164e9975fdcee1a5a743af5f5017cb3831083cf071c655947fb53bc27ab`,
  records compiler plus `DIAG_TRAP_WFX=1` and passed both artifact-role checks.

Exact launch command is EXP-044's matching root `run-assisted.sh` with only both
artifact paths changed to `EXP-20260814-045`.

Smallest checkpoint: preflight must print active diagnostic WFI/WFE traps with
HCR bits `0x6000` set on boot and secondary CPUs, all eight CPUs must enter, and
the framebuffer must autonomously change from EXP-044's black hash without a
host SIGINT.  A two-minute identical frame, watchdog/reset, missing CPU or trap
invariant panic rejects the hypothesis.  If it passes, require at least ten
responsive minutes and preserve the Windows crash dump before any stress.  The
unchanged recovery is installed Stage 1 `b791225`, verified with eight CPUs and
8 GiB after every failed run.

Hardware result (completed UTC 2026-08-14T19:09:09Z):
- preflight printed `HV: diagnostic WFI/WFE traps active
  HCR=0x32480046039`; all secondary mailbox operations completed, CPUs 0 through
  7 entered, and NVMe and xHCI reached runtime.  No WFI/WFE invariant panic
  occurred, so the single build variable was present and remained set.
- Windows autonomously advanced to the disk-check `1 second(s)` frame, SHA-256
  `b70e58f84d430c02c6113ca5822e662b25beb0ca1681c8c3489d8bd02855161e`,
  then remained byte-identical for more than two minutes with no TCP/22,
  bugcheck or reset.  This met the recorded failure criterion without any host
  input.
- the first post-failure snapshot showed every sampled HCR retaining bits
  `0x6000`.  Nevertheless CPUs 1 through 6 still had a Pending-only or
  Active-only INTID 18 LR; CPUs 4 through 6 specifically retained
  `0x9020020000000012` Active-only timers while the comparator was far overdue.
  Those CPUs also had one Pending SGI0, `vinj=1` and one fewer IAR/EOI than queue
  entry.  Trapping idle therefore brings the core to EL2 but the accepted vGIC
  path still does not reflect an asserted level into an already Active timer LR.
- the large queue/IAR/EOI counts (about 45k on CPUs 4 through 7 and 158k-311k on
  CPUs 0 through 3) show that treating every guest WFI/WFE as a no-op creates a
  high exception cadence, but counters remained nearly balanced and no physical
  self-IPI code exists in this artifact.  This is not sufficient as a standalone
  production correction.
- one diagnostic snapshot was requested only after failure.  The old 16 KiB
  observer then corrupted the live raw frame, so the preserved PNG is the last
  valid pre-snapshot `1 second(s)` frame while the preserved raw is explicitly a
  post-snapshot transport artifact.  SIGTERM targeted verified PID 9193 and the
  resulting printed exception is the documented recovery path, not the freeze.
  Stage 1 `b791225` again answered with eight CPUs and 8 GiB.

Evidence:
- `investigation/artifacts/EXP-20260814-045/evidence/hv.log`, SHA-256
  `51c9758f9fae4d931dc0d6e464051e79e1918f31bbd51ce65a844cbfde41a714`;
- valid pre-snapshot rendered frame, SHA-256
  `9707a54053bd499e9c68552a64d3a7a10a24eecaa5204f0ac5827635fc82ef04`;
- post-snapshot raw observer artifact, SHA-256
  `38ee2af1b06f88da8169712e1585dd5e1f39f037e0cd28aa61d555038cfbb327`;
- post-snapshot metadata, SHA-256
  `72f097d231d87871ff4ce42cd460cc14ad436b398c45f37f1ec397dc33bde07f`.

Verdict: rejected as a standalone fix, while confirming one half of the final
contract.  Mandatory TWI/TWE alone cannot correct a timer LR already Active when
the physical level reasserts.  EXP-039/040 proved the complementary level-state
correction (`Active + asserted -> Active+Pending`), and EXP-041 through EXP-043
proved that adding physical self-IPIs creates either a storm or cumulative
high-IRQL watchdog.  The next implementation must combine mandatory WFI/WFE
trapping with live timer level synchronization and remove the entire physical
self-IPI wake experiment.  This is an architectural correction, not a fourth
variation of that rejected wake mechanism.

### EXP-20260814-046 — trapped idle plus architectural timer level

Status: rejected after hardware test
Created (UTC): 2026-08-14T19:18:19Z

Hypothesis: the freeze requires both halves measured independently in EXP-040
and EXP-045.  If every guest WFI/WFE enters EL2 and `hv_update_fiq()` reflects an
asserted CNTV level into an already-live INTID 18 LR, then Windows will receive
the next virtual timer after EOI without a physical self-IPI.  The guest will
pass the disk-check and black-frame stalls, avoid 0x133 P1=1, and remain
responsive for at least ten minutes.

Single changed variable relative to EXP-045: replace its historical runtime with
committed m1n1 `a20425c60786533bd3061eba1cd7bc331608d086`, which retains the
hardware-observed live timer level correction, makes the already-tested TWI/TWE
idle contract unconditional, and removes the complete EXP-041/042/043 timer
self-IPI mechanism.  Mu, Windows, NVMe, xHCI, display, CPU/memory layout, absent
Apple Input mapping, firmware hash and monitor launch profile are unchanged.

Primary contract inspected before implementation:
- live J313 traces from EXP-040 showed CNTV asserted with INTID 18
  Active+Pending and HCR.VI, and one external physical boundary caused Windows
  IAR/EOI progress; EXP-044 showed sleeping cores without TWI/TWE; EXP-045 showed
  trapped entries but stale Active-only timer LRs; EXP-041 through EXP-043
  rejected all three physical self-IPI variants;
- Asahi timer/interrupt and J313 device-tree behavior, current m1n1 exception,
  timer, GXF-HCR, SMP and vGIC implementations, current Mu ACPI/no-AINP exposure,
  and the Microsoft DPC watchdog contract were reviewed in the preceding source
  audit.  Microsoft 0x133 P1=1 means cumulative prolonged execution at or above
  DISPATCH_LEVEL, matching the rejected EXP-043 outcome;
- m1n1 owns HCR idle trapping, physical timer FIQ, live LR state, HCR.VI and
  recovery.  Mu owns enumeration and remains unchanged.  Windows owns CNTV
  programming, idle, IAR/EOI and scheduling.  No timer DMA exists, and the
  unenumerated Apple Input driver owns none of this path.

Implementation and software checkpoint:
- nested implementation commit
  `a20425c60786533bd3061eba1cd7bc331608d086`; root contract commit
  `fbb6c01afaedc11a7f0d54bc93ebb1dc4f73e790`; Mu
  `63942398cccbd98127cfecbd7f936af99c837d6f`;
- root, nested m1n1 and Mu tracked diff SHA-256 are all the empty diff
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
- RED source tests first failed on optional `HV_DIAG_TRAP_WFX` and the physical
  self-IPI latch/flush.  Focused timer/WFX/vGIC tests, the complete nested host
  suite, the complete root suite (258 tests), RFC 4180 change-ledger checks and a
  clean freestanding build all passed;
- exact build command:

```sh
cd /Users/pavel/public_windows/m1n1_windows
PATH="/opt/homebrew/opt/rustup/bin:$PATH" make clean
PATH="/opt/homebrew/opt/rustup/bin:$PATH" make -j8 APPLE_INPUT=0
```

Artifacts:
- `investigation/artifacts/EXP-20260814-046/m1n1.macho`, 917504 bytes,
  SHA-256 `9ec416751707c0a0dcc33c43e047682514a44be8d31b0fe631998afd3baf0eca`;
- unchanged `J313_EFI.fd`, SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- strict DEBUG/monitor/both `MANIFEST.json`, SHA-256
  `a8369f5a9551bd0e096b87a9d6821edfa7c2255fd4a9cb6e9f3ce13e392d6e75`,
  passed profile and assisted-chainload role verification; compiler is Homebrew
  clang 22.1.8 and `build_cfg.h` contains only `HV_DISABLE_APPLE_INPUT`.

Exact launch command:

```sh
scripts/run-assisted.sh --proxy <CONSOLE_DEVICE> \
  --vuart <VUART_DEVICE> \
  --firmware investigation/artifacts/EXP-20260814-046/J313_EFI.fd \
  --m1n1 investigation/artifacts/EXP-20260814-046/m1n1.macho \
  --display both --debug monitor --chainload --foreground
```

Smallest falsifiable checkpoint: preflight prints guest WFI/WFE traps with
HCR bits `0x6000`; all eight CPUs enter once; NVMe and xHCI reach runtime; and
Windows autonomously passes both earlier static frames.  Any missing CPU,
two-minute byte-identical frame, self-IPI growth without virtual IAR/EOI,
bugcheck/reset or HCR-policy panic rejects the hypothesis.  If the checkpoint
passes, require at least ten continuous minutes of changing framebuffer or
responsive SSH/UI and no 0x133.  Evidence paths are
`investigation/artifacts/EXP-20260814-046/evidence/`.  Recovery is the unchanged
installed Stage 1 `b791225`; terminate only the verified foreground runner, then
confirm the proxy reports eight CPUs and 8 GiB.

Hardware result (completed UTC 2026-08-14T19:26:43Z):
- preflight printed `HV: guest WFI/WFE traps active HCR=0x32480046039`;
  every secondary mailbox completed, CPUs 0 through 7 entered, NVMe became ready,
  and xHCI enabled its route.  No HCR-policy panic, guest bugcheck or reset
  occurred;
- the framebuffer published at least 62 complete generations but remained
  byte-identical to the EXP-044 black frame for more than two minutes, SHA-256
  `6992296c77327bc9aaab7ca4758501ce5d2bd2e3c1ec7050f400881ed9ffbdcb`.
  The known `192.168.1.35` TCP/22 endpoint did not appear;
- the first post-failure snapshot showed Pending-only INTID 18
  (`0x5020020000000012`) on CPUs 1 and 3 through 7, Active+Pending INTID 18 on
  CPU0, HCR.VI asserted, open VPMR, empty software queues and expired CNTV on
  those CPUs.  This proves both proposed halves were active at the failure;
- a second snapshot more than 30 seconds later showed every virtual queue,
  IAR and EOI counter exactly unchanged: CPU1 `151471`, CPU3 `106606`, CPU4
  `19875`, CPU5 `19072`, CPU6 `19731`, CPU7 `17244`, and CPU0 `266852`.
  Host ticks advanced substantially and each diagnostic boundary added exactly
  one physical IPI to the secondary CPUs, but neither boundary caused a virtual
  acknowledgement or guest progress;
- the static WFI/WFE policy therefore creates a tight idle-return regime while
  a software-signalled virtual IRQ remains pending.  Correct LR level and a
  permanently asserted trap are jointly insufficient; the physical self-IPI
  path remains absent and no storm occurred;
- SIGTERM targeted only verified `run_uefi.py` PID 19460.  USB re-enumerated and
  installed recovery Stage 1 `b791225` reported eight CPUs and 8 GiB.

Evidence:
- final raw UART/observer log
  `investigation/artifacts/EXP-20260814-046/evidence/hv.log`, SHA-256
  `38118a67274d3dfb219cdb665012f605c5cf878674445f538e01478aef437ca4`;
- valid pre-snapshot raw framebuffer, SHA-256
  `6992296c77327bc9aaab7ca4758501ce5d2bd2e3c1ec7050f400881ed9ffbdcb`;
- pre-snapshot metadata, SHA-256
  `e3c061aa4116c64d9322da82ff4b3f1482ab90ee037848aba1b61318ee1d2256`;
- rendered pre-snapshot PNG, SHA-256
  `16d4591d9bba12f935e2fa088b788c4b7937c78fb17fc99742d29004fe0eef55`.

Verdict: rejected.  The combined static policy does not restore the EL2-to-guest
virtual IRQ boundary.  It also reconfirms EXP-022's warning that continuously
skipping architectural idle is not a production contract.  The next smallest
falsifiable correction is dynamic: preserve real WFI/WFE while no virtual IRQ is
deliverable, and set TWI/TWE only together with HCR.VI.  A physical timer FIQ can
then wake the core normally; if Windows attempts to sleep again while VI is
pending, exactly that WFI/WFE is trapped and returned to the guest.  No polling,
physical self-IPI, timer-rate or LR-state change is justified.

### EXP-20260814-047 — trap only a sleep attempted with VI pending

Status: rejected on hardware; Stage 1 recovered
Created (UTC): 2026-08-14T19:31:04Z

Hypothesis: EXP-046 failed because TWI/TWE converted every Windows idle cycle
into a tight synchronous-exception loop.  Coupling TWI/TWE exactly to HCR.VI will
retain architectural WFI/WFE while idle, let the existing physical timer FIQ
wake the Apple core, and trap only a subsequent sleep attempted after a virtual
IRQ is deliverable.  That bounded trap window will produce fresh IAR/EOI and let
Windows pass the earlier black and disk-check stalls without a physical IPI.

Single changed variable relative to EXP-046: HCR idle policy changes from static
TWI/TWE to `TWI|TWE iff VI`.  Live CNTV level synchronization, WFI/WFE handler,
timer rates, LR/priority algorithms, SMP, Mu, Windows, NVMe, xHCI, display,
absent Apple Input mapping, CPU/memory layout and launch profile are unchanged.

Ownership and source contract:
- EXP-046 supplied the live observation: Pending INTID 18 and VI persisted while
  every IAR/EOI counter remained fixed under static traps; EXP-040 supplied the
  complementary observation that an ordinary physical boundary wakes the no-trap
  guest.  No new register value, interrupt number or power sequence is guessed;
- m1n1 owns HCR, WFI/WFE trapping, the physical timer FIQ and LR/VI publication.
  Windows retains idle, CNTV, IAR/EOI and scheduler ownership.  Mu/no-AINP and all
  hardware drivers remain unchanged.  Recovery remains Stage 1 `b791225`.

Software/build checkpoint:
- m1n1 `f7297e948600371604c7935b0e62fa0333f1ee51`; root
  `b0b4ee5a7d60364026f2844067ee68edc57c7dc7`; Mu
  `63942398cccbd98127cfecbd7f936af99c837d6f`; all three tracked diff hashes are
  the empty SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
- RED helper and source-contract tests failed before implementation; focused
  WFX/timer/vGIC tests, complete nested host suite, complete root suite (258),
  change-ledger tests, diff checks and clean freestanding build passed;
- exact build command is EXP-046's `make clean` then
  `make -j8 APPLE_INPUT=0` with the same Homebrew clang 22.1.8.

Artifacts:
- `investigation/artifacts/EXP-20260814-047/m1n1.macho`, SHA-256
  `6bec6ee34341d49be861cce7829b105aee24da28ccabe2f769e12c5aa471c7c6`;
- unchanged `J313_EFI.fd`, SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- strict DEBUG/monitor/both `MANIFEST.json`, SHA-256
  `ec0a7537c663823b7acdd2088aa9cade17548c7d19cdf3d7b2560ce8d554a863`,
  passed the assisted-chainload role check; `build_cfg.h` contains only
  `HV_DISABLE_APPLE_INPUT` and build tag is `f7297e9`.

Exact launch command is EXP-046's command with both artifact paths changed to
`EXP-20260814-047`.

Smallest checkpoint: guest preflight HCR must lack `0x6000` because VI is clear;
all eight CPUs, NVMe and xHCI must reach runtime; Windows must autonomously pass
the black frame.  A two-minute static frame, bugcheck/reset or invariant panic
rejects the hypothesis.  If a later pause occurs, one snapshot must show TWI/TWE
present exactly on CPUs with VI and absent on CPUs without VI.  Acceptance still
requires login/TCP/22 and ten continuous responsive minutes without a physical
self-IPI.  Evidence is stored under
`investigation/artifacts/EXP-20260814-047/evidence/`.

Hardware result (2026-08-23 retest): rejected.  The strict preflight passed,
all eight vCPUs entered the guest, and NVMe plus xHCI reached runtime, but the
guest never produced a non-black framebuffer and TCP/22 never appeared.  Two
bounded watchdog snapshots taken more than 30 seconds apart showed advancing
host tick counters and physical timers while affected vCPUs remained in the
same Windows idle region.  Their INTID 18 LR was Pending and priority
deliverable, VMCR admitted priority 0x20, HCR.VI was set, and TWI/TWE followed
VI exactly.  Nevertheless every virtual IAR and EOI counter remained bit-for-bit
unchanged across the interval.  Dynamic WFI/WFE trapping therefore obeyed its
source contract but did not wake a core that was already asleep.

The result closes the no-doorbell architectural A/B: EXP-044 through EXP-047
all leave a valid virtual interrupt pending without a physical wake boundary.
The next controlled run must restore exactly the one-wake-per-continuous-
deliverable-timer interval from EXP-043 on top of the current bounded observer,
then treat its later 0x133 P1=1 as a separate high-IRQL defect rather than
changing wake classification again.

Frozen evidence:
- `evidence/20260823-retest/fb-final.raw`, SHA-256
  `6992296c77327bc9aaab7ca4758501ce5d2bd2e3c1ec7050f400881ed9ffbdcb`;
- `evidence/20260823-retest/fb-info.json`, SHA-256
  `470dc70b3c9f604c437800928f229353a1ef34e3fbf79e1cf819f4f8ae289b8d`;
- `evidence/20260823-retest/frame-black.png`, SHA-256
  `16d4591d9bba12f935e2fa088b788c4b7937c78fb17fc99742d29004fe0eef55`;
- `evidence/20260823-retest/hv-pre-recovery.log`, SHA-256
  `c8e242fba2091574999105d41bd578e046feb795faa17f99ff31a5364bd406be`.

Recovery was intentional: the exact runner received SIGTERM, captured its
final diagnostic snapshot, requested an Air reboot, and Stage 1 re-enumerated
on the same proxy/vUART pair.  Checksum errors printed only during that oversized
final recovery snapshot are not runtime framebuffer evidence; all frozen files
listed above were captured before recovery and verified independently.

### EXP-20260814-048 — one physical doorbell per deliverable timer interval

Status: rejected on hardware; Stage 1 recovered
Created (UTC): 2026-08-23T11:11:35Z

Hypothesis: EXP-047 demonstrates that a correctly Pending and priority-
deliverable INTID 18, HCR.VI, and a dynamically trapped subsequent WFI/WFE do
not wake an Apple core that entered WFI before VI was published.  EXP-043
already demonstrated the missing boundary: one physical self-IPI deferred
until the final EL2-to-guest return passes both earlier frozen frames without
the repeated IPI storm of EXP-041/042.  Reintroducing exactly that one-shot
doorbell on the current bounded observer should reach Windows autonomously.

Single changed variable relative to EXP-047: a per-vCPU state machine requests
one deferred local physical IPI when INTID 17 or 18 first becomes Pending-only
and priority-deliverable.  Continuous deliverability cannot request another;
masking, IAR, Active/Active+Pending, or removal closes the interval.  Emission
occurs only after the last local-source drain and `hv_exc_exit`, immediately
before guest return.  Dynamic TWI/TWE coupling, live timer level sync, all timer
rates, LR/priority behavior, Mu, Windows, NVMe, xHCI, display, CPU/memory layout,
and launch profile remain unchanged.

This experiment addresses only the lost physical wake.  If Windows later
reproduces EXP-043's `DPC_WATCHDOG_VIOLATION (0x133)` with parameter 1, that is
a distinct cumulative high-IRQL defect; EXP-048 must capture it without
changing the doorbell lifecycle or guessing another wake policy.

Ownership and safety contract:
- m1n1 owns virtual IRQ publication and the Apple local physical wake; Windows
  continues to own CNTV programming, IAR/EOI, PMR/IRQL, and scheduling;
- the doorbell never carries the Windows virtual INTID and never substitutes
  for GIC acknowledgement; it only creates one physical exception boundary;
- the send is deferred past EL2 source draining so m1n1 cannot acknowledge its
  own wake before ERET, the exact EXP-041 failure;
- per-interval latching prevents the 25,000-IPI storm measured in EXP-042.

Starting checkpoint:
- root `f9f372521a74999197d5531b7ed6b3d7e17fbd7a`; m1n1
  `f7297e948600371604c7935b0e62fa0333f1ee51`; Mu
  `63942398cccbd98127cfecbd7f936af99c837d6f`;
- Mu tracked diff is empty SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
- the root ledger-only diff before this entry is
  `48400766833f2a10aed7139ee13e2b472885d18056685de6e225b53fdf122382`;
- the nested RED-test diff is
  `e7bcdc918d2bdba9a18c5cd60da7b75f0b77babeeaa6d1e23ee6809f586cd9dd`.

RED evidence:
- `hv_vgic_diag_test` fails to compile because
  `hv_vgic_timer_wake_state` and
  `hv_vgic_diag_timer_wake_transition` do not exist;
- the focused public integration contract fails because current production
  contains no `timer_wake_state`, deferred flag, flush API, or post-exit flush.

Smallest checkpoint: both RED tests must pass after the minimum implementation,
the exact artifact must pass the complete host/public suites and strict launch
preflight, then an assisted monitor/both run must pass the former black frame
without repeated per-CPU physical IPI growth.  Acceptance requires login,
TCP/22, ten responsive idle minutes, and a bounded CPU/storage stress window.
A static frame, IPI storm, bugcheck, or reset rejects acceptance and triggers a
single synchronized snapshot before Stage 1 recovery.

Implementation/build checkpoint before hardware launch:
- RED was observed for both the pure interval state-machine and the production
  post-exit integration contract; after the minimum implementation, focused
  GREEN passed, the complete nested host suite passed, the complete public
  suite passed 258/258, and all diff checks passed;
- m1n1 commit is `f9b2a298ca45a836a8bc98c04ae52fe48b1de68d`;
  the only production change is one cache-line-separated per-vCPU interval
  latch/deferred bit, timer-only classification during VI recomputation, and a
  flush after `hv_exc_exit`; Mu remains `63942398cccbd98127cfecbd7f936af99c837d6f`;
- the host lacked Cargo and the stopped Colima runtime initially rejected the
  build; after starting the existing local container runtime, a clean build
  completed with `aarch64-linux-gnu-gcc 13.3.0` / clang 18.1.3 and build tag
  `f9b2a29`; `build_cfg.h` contains only `HV_DISABLE_APPLE_INPUT`;
- `investigation/artifacts/EXP-20260814-048/m1n1.macho`, SHA-256
  `70aa065007914cccd79e6c2cc3dd3bd8ed365d6769f9051fab5a7c0d187a5a21`;
- unchanged `J313_EFI.fd`, SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- strict DEBUG/monitor/both `MANIFEST.json`, SHA-256
  `4ca2bdfc6c48b714d89c605c315330a747b5b8d9afff6a8e3c11e200a14a821d`,
  passed profile, display, debug and assisted-chainload role verification.  It
  records the root ledger/test diff as dirty while m1n1 and Mu are clean.

Hardware result (2026-08-23): rejected.  The artifact passed strict preflight,
entered all eight vCPUs, initialized NVMe and xHCI, passed EXP-047's black-frame
barrier, reached the Windows disk-check screen and then the lock screen.  It did
not become usable: the framebuffer remained byte-identical between observer
generations, TCP/22 did not appear, and an external diagnostic snapshot was the
only event that advanced the guest from the disk-check stall.

Two synchronized watchdog snapshots identify the rejected mechanism rather
than Windows storage as the immediate problem.  Between them CPU1 physical IPI
receives increased from 101152 to 311472 while its ordinary SGI queue increased
from 19323 to 63388; CPU2 IPI increased from 21494 to 198260 while its queue
increased from 16888 to 57456; CPU6 increased from 88808 to 150733 while its
queue increased from 12498 to 35989.  The virtual timer IAR and EOI counters
remained balanced, and all sampled idle CPUs converged in the same Windows idle
region.  The deferred doorbell therefore wakes the guest but adds hundreds of
physical exceptions per second on active timer CPUs, reproducing EXP-043's
cumulative high-IRQL failure mechanism and the reported micro-freezes.

Frozen evidence:
- `evidence/live-rejection/hv.log`, SHA-256
  `f908f4475441f0a66d5fe1a7f0f81be7c8680ae161bcb4496695c3014db48315`;
- `evidence/live-rejection/fb-final.raw`, SHA-256
  `f84df8e7f91fca492895c08e1c7963bc92c7d1dfe9055c6b28f4149ec779fabd`;
- `evidence/live-rejection/fb-info.json`, SHA-256
  `86ff31facd51c095bf6e7dbd6aee895e8e41d1d6654b3706756a83d5cee4e64c`;
- `evidence/live-rejection/lock-screen.png`, SHA-256
  `a05fb3afeaccd203ea96e9f8b11d0350173aaf1601b83b9afa435a2d4254305f`.

The exact runner PID 30796 received SIGTERM only after evidence was frozen.
Stage 1 then re-enumerated and answered a proxy NOP as m1n1 `b791225`, J313,
eight GiB.  The next correction must remove the physical self-IPI entirely; it
must not refine the rejected edge latch again.

### EXP-20260814-049 — emulate guest idle with a real EL2 wait

Status: rejected on hardware; Stage 1 recovered
Created (UTC): 2026-08-23T13:40:00Z

Hypothesis: Windows WFI/WFE must be virtualized as idle, not skipped and not
allowed to put the Apple core to sleep below the virtual interrupt boundary.
Unconditionally trapping guest WFI/WFE, executing the corresponding real wait
instruction in the lock-free EL2 synchronous fast path while no virtual IRQ is
deliverable, then returning after the physical wake will preserve idle semantics
without a synthetic physical IPI.  A Pending VI skips the wait and resumes the
guest immediately.

Single changed variable relative to EXP-048: replace dynamic TWI/TWE plus the
complete deferred timer self-IPI state machine with unconditional TWI/TWE and
lock-free EL2 WFI/WFE emulation.  Live timer level synchronization, timer rates,
LR/priority handling, FIQ fast path, Mu, Windows, NVMe, xHCI, display, CPU and
memory layout remain unchanged.

Architectural and ownership contract:
- the WFI/WFE exception branch is before `hv_exc_entry()` and therefore never
  holds the hypervisor-wide `bhl` while sleeping;
- it synchronizes already-asserted timer state before deciding to wait, closes
  the check-to-wait race with a real physical wait, and synchronizes again after
  wake before guest return;
- WFI waits for a physical interrupt and WFE waits for a physical event; a
  currently deliverable HCR.VI performs neither wait;
- no timer path calls `smp_send_ipi`, and no per-CPU timer wake latch or deferred
  flush remains;
- Windows continues to own timer programming, IAR/EOI and scheduling.  m1n1
  owns the trap, physical wait and virtual interrupt publication.

Smallest checkpoint: RED helper and source-contract tests must fail on EXP-048,
then pass after the minimum implementation.  The complete nested/public suites,
clean freestanding build and strict assisted monitor/both preflight must pass.
On hardware, all eight CPUs, NVMe and xHCI must reach runtime; Windows must reach
login without a host snapshot; physical IPI minus ordinary SGI queue growth must
remain bounded rather than scaling with timer ticks.  Acceptance requires a
changing framebuffer, responsive UI/SSH where available, ten idle minutes and a
bounded CPU/storage stress window without freeze, reset or bugcheck.

Implementation/build checkpoint before hardware launch:
- focused RED failed on the absent static trap/action contract and the remaining
  timer self-IPI source; after the minimum implementation, focused WFx, vGIC
  and platform tests passed;
- the complete nested host suite passed; the complete public suite passed
  258/258 under `proxyenv` (the system Python attempt had only four missing-
  `serial` import errors and did not execute product tests); diff checks passed;
- m1n1 commit is `03b5fc92c70428e9111120fad063c197dafdddd3`;
  Mu remains `63942398cccbd98127cfecbd7f936af99c837d6f`;
- a clean container build completed with `aarch64-linux-gnu-gcc 13.3.0` /
  clang 18.1.3 and build tag `03b5fc9`; `build_cfg.h` contains only
  `HV_DISABLE_APPLE_INPUT`;
- `investigation/artifacts/EXP-20260814-049/m1n1.macho`, SHA-256
  `4fc1e16670d2ddc572965e61bef77098ae9499b362be36be70af32f65079d6cb`;
- unchanged `J313_EFI.fd`, SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- strict DEBUG/monitor/both manifest passed profile, display, debug,
  assisted-chainload and guest-firmware role verification.  m1n1 and Mu are
  clean; the root is intentionally dirty only for the ledger and RED/GREEN
  public contract tests.

Hardware result (2026-08-23): rejected.  The exact frozen artifact passed strict
preflight, entered all eight vCPUs, initialized NVMe and xHCI, and reached the
`guest runtime ready` checkpoint without an external diagnostic wake.  The web
observer continued publishing generations, but every framebuffer sample stayed
byte-identical and completely black for more than 90 seconds; TCP/22 never
appeared.

One synchronized snapshot proves the intended correction and the remaining
failure separately.  Physical IPI receive counts exactly matched ordinary
virtual-SGI queue counts on every CPU (for example CPU1 17460/17460, CPU2
14368/14368 and CPU6 14084/14084), so EXP-048's timer self-IPI excess was fully
removed.  Host timer counters continued advancing and timer IAR/EOI counts were
balanced.  Nevertheless idle CPUs retained Pending-only or Active+Pending
INTID 18 LRs, CPU0 retained an Active INTID 64 NVMe LR, and the guest made no
visible or network progress.  The remaining problem is therefore not a dead
host timer and not the removed timer doorbell storm; virtual SGI wake coalescing
and IRQ Active/deactivation ownership must be classified next.

Frozen rejection evidence:
- `evidence/black-frame-rejection/hv.log`, SHA-256
  `5ce2b23b3e3c36280670de9cc864bc23c2237f1c29168d64dc5861988d176844`;
- `evidence/black-frame-rejection/fb-final.raw`, SHA-256
  `6992296c77327bc9aaab7ca4758501ce5d2bd2e3c1ec7050f400881ed9ffbdcb`;
- `evidence/black-frame-rejection/fb-info.json`, SHA-256
  `fc8db4ef1c2bf32cd435ca50e52caced3e95d770db4457a37b75ebb51dc8378f`;
- `evidence/black-frame-rejection/frame-black.png`, SHA-256
  `16d4591d9bba12f935e2fa088b788c4b7937c78fb17fc99742d29004fe0eef55`.

The exact runner PID 48046 received SIGTERM only after the evidence was frozen.
The Air was then explicitly rebooted through the sole proxy owner; both USB
ports re-enumerated and the role probe confirmed the clean Stage 1 proxy on
`<CONSOLE_DEVICE>` with vUART on the `...43` port.

### EXP-20260814-050 — preserve guest WFE as a native synchronization primitive

Status: rejected after hardware test; Stage 1 recovery pending
Created (UTC): 2026-08-23T11:48:50Z

Hypothesis: EXP-049 incorrectly treats guest WFE as a vCPU halt and executes a
real WFE inside the EL2 trap handler.  WFE is also the architectural event-based
spin/wait primitive; sleeping the trapped CPU in EL2 can strand a Windows lock
owner until an unrelated physical event and produce the observed multi-second
or minute-wide freezes.  Preserving native guest WFE while continuing to trap
only WFI should retain Windows synchronization semantics and keep the tested
lock-free WFI halt path.

Single changed variable relative to EXP-049: HCR traps WFI but no longer traps
WFE; the defensive WFE trap action resumes immediately rather than entering a
physical EL2 WFE.  Timer cadence, LR state, VI publication, SGI routing, NVMe,
xHCI, Mu, display, CPU topology, memory map and launch profile remain unchanged.

Primary implementations and specifications inspected before design:
- current m1n1 `src/hv_exc.c`, `src/hv_wfx_policy.h`, `src/hv_vgic.c`,
  `src/hv_sgi_pending.c` and their host tests;
- upstream Linux arm64 KVM `arch/arm64/kvm/handle_exit.c`, where WFI halts the
  vCPU until an IRQ/FIQ but WFE uses the scheduler spin/yield path rather than a
  physical halt;
- upstream Linux KVM WFI/WFE trap-policy implementation and documentation;
- Arm RVIC signaling contract, which publishes VI while an enabled unmasked
  interrupt is Pending and clears it when no such interrupt remains.

Observed ownership contract: Windows owns WFE/SEV synchronization and WFI idle,
m1n1 owns trapping and the physical WFI wait, and the vGIC owns VI plus LR
publication.  Mu and ACPI do not participate in the WFx runtime decision.  The
recovery path is the sole USB proxy reboot back to Stage 1; no ESP image will be
installed.

Starting checkpoint:
- root `f9f372521a74999197d5531b7ed6b3d7e17fbd7a`; m1n1
  `03b5fc92c70428e9111120fad063c197dafdddd3`; Mu
  `63942398cccbd98127cfecbd7f936af99c837d6f`;
- root ledger/test diff SHA-256
  `94497de9f79e7bd60bfe1a23daf76449ca729bdbf34e0507fe1d11c3d3b30776`;
- m1n1 and Mu tracked diff SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

Smallest falsifiable checkpoint: the host policy and public source contracts
must first fail against EXP-049, then pass when TWE and physical EL2 WFE are
absent while TWI, lock-free WFI and VI skip remain.  After complete suites and a
clean strict monitor/both artifact, hardware must autonomously pass EXP-049's
black frame, reach the lock screen and TCP/22, then remain responsive for ten
idle minutes and a bounded CPU/storage stress interval.  A static frame,
unbounded SGI/IPI growth, reset or bugcheck rejects the hypothesis and requires
one synchronized snapshot before Stage 1 recovery.

Implementation/build checkpoint before hardware launch:
- RED was observed independently: the host helper aborted because the trap mask
  still contained TWE, and the public source contract failed on both HCR_TWE and
  physical `sysop("wfe")` in the synchronous handler;
- after the minimum policy change, both focused GREEN tests passed, the complete
  nested host suite passed, and the complete public suite passed 258/258;
- m1n1 commit is `8229266f668734338d0c86be077bb7e58db10b24`;
  Mu remains `63942398cccbd98127cfecbd7f936af99c837d6f`;
- a clean container build completed with `aarch64-linux-gnu-gcc 13.3.0` /
  clang 18.1.3 and `build_cfg.h` contains only `HV_DISABLE_APPLE_INPUT`;
- `investigation/artifacts/EXP-20260814-050/m1n1.macho`, SHA-256
  `3955949c94f079e7c2ec7c4a8a97dd4880853c226444728a09b33cd740a0bdf1`;
- unchanged `J313_EFI.fd`, SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- strict DEBUG/monitor/both `MANIFEST.json`, SHA-256
  `2070bee1384dc9f01d0a176197918351b4b327c88768ba5c428e76f604af1e95`,
  passed profile, display, debug and both artifact-role checks.  It records
  m1n1 and Mu as clean and the root ledger/source-contract diff explicitly as
  dirty with SHA-256
  `64815d71d4a05265f281ecaf3b1879b930b3f36c54b5e11f70c3a9caf2bd3f56`.

Hardware result (2026-08-23): rejected.  The exact artifact reached all eight
Windows CPUs, initialized NVMe and xHCI, reached the desktop and rendered Steam,
but then reproduced two independent global pauses with byte-identical physical
and USB framebuffer contents for more than 100 seconds.  TCP/22 was unavailable
during the pauses.  A host SIGINT requested the established pre-rendezvous
lockless snapshot; the physical rendezvous IPI briefly restored Windows
progress each time, after which the same pause returned.

The two snapshots rule out an ordinary SGI backlog: on every CPU SGI queue,
physical IPI receive, drain, guest IAR and guest EOI counts were exactly
balanced, queue depths were zero, no pending SGI mask remained and no LR
allocation failed.  Host timer fire counters continued advancing.  CPUs 0, 1,
2, 3, 6 and 7 retained Active+Pending INTID 18 timer LRs, while CPUs 4 and 5
retained deliverable Pending-only timer LRs with `HCR.VI` asserted.  CPU0 also
retained Active NVMe INTID 64 and CPU1 retained Active xHCI INTID 857.  The
rendezvous therefore changes a slow-path boundary while the ordinary local IRQ
queues themselves remain balanced.

The repeating sampled PC `0xfffff800a9b0e320` was symbolized locally against
the matching Windows kernel as `nt+0x30e320`,
`RtlpImageDirectoryEntryToDataEx+0x28`, an ordinary conditional branch.  The
records are independently published last samples rather than simultaneous
stacks, so that hot PC is not itself evidence of an eight-core lock spin.

Frozen evidence:
- `evidence/desktop-freeze-1/fb-meta.json`, SHA-256
  `86018f7cda431b184f624b49808f59bb7fc1a3d97af293b380b3193a211df923`;
- `evidence/desktop-freeze-1/frame.bin`, SHA-256
  `13f3a5f2f52ce9ee769b1a22177f75b5c43f0d5b07f296b17e0cd2c7c0775782`;
- `evidence/desktop-freeze-1/hv-before-snapshot.log`, SHA-256
  `92e73e67b8c1913e10845b19e0b4355db88149f46f3af1041d2ef38726361391`;
- `evidence/desktop-freeze-1/watchdog-snapshot.txt`, SHA-256
  `38f6be6099771f36243c538735a1890f57503650b56cd7240e737a632730e466`;
- `evidence/desktop-freeze-2/fb-meta.json`, SHA-256
  `dccfb8a10554ef259ec90dcfece18e07cb02b39660952518aaf7d7fd99d29ad4`;
- `evidence/desktop-freeze-2/frame.bin`, SHA-256
  `691de5ef48cc537e767b3680db38d49e19bc3a2c32d6f786cc9ca872cf4608df`;
- `evidence/desktop-freeze-2/hv-before-snapshot.log`, SHA-256
  `cbd625208685574646e424b5d0d1c9a937813499ec317795f980577541701a09`.

The provisional `evidence/black-frame-rejection/` directory was captured while
the initial raw framebuffer was still black and is superseded; it must not be
used as the EXP-050 verdict.  Preserve native WFE as an architectural
correctness change, but do not promote EXP-050 as a stability fix.

### EXP-20260814-051 — push lock-free telemetry through the sole proxy owner

Status: software and artifact verified; hardware validation pending
Created (UTC): 2026-08-23T12:17:35Z

Hypothesis: EXP-050 cannot distinguish an NVMe completion/INTx stall from an
idle-wake stall without requesting a diagnostic rendezvous, and that request
temporarily changes the failure.  Pushing the already existing 176-byte EL2
ring sample as one nonblocking asynchronous proxy event every five seconds will
preserve the failure while exposing guest PC, host timers, NVMe queue heads and
tails, NVMe command/completion/INTx lifecycle, xHCI IRQ lifecycle, LR counts and
framebuffer backpressure in the web observer.

Single changed variable relative to EXP-050: diagnostic samples are sent as
`EVT_TELEMETRY=4` to the existing assisted launcher and atomically recorded by
that same process.  The host callback issues no proxy command.  WFI/WFE policy,
timer cadence, vGIC/LR/VI behavior, SGI routing, NVMe, xHCI, Mu, Windows,
display geometry, CPU topology and memory layout are unchanged.

Starting checkpoint:
- root `f9f372521a74999197d5531b7ed6b3d7e17fbd7a`;
- m1n1 `8229266f668734338d0c86be077bb7e58db10b24`;
- Mu `63942398cccbd98127cfecbd7f936af99c837d6f`;
- root tracked diff SHA-256
  `23a888cc4a0f1655e751ea3823a2cc88b44add4a17ae3d1c5cbcd8391d291312`;
- m1n1 tracked diff SHA-256
  `59dd5ea67628ff42ca08341067987f8ade8e86a6634cf018670e3f21279dd8f0`.

RED/GREEN evidence:
- the C test first failed because `hv_diag_tick()` could not return the newly
  published sample;
- host tests first failed because `TelemetryRecorder.accept_event`, event type
  4 and the web `streaming` state did not exist;
- after the minimum implementation, focused C and Python/web suites passed;
- the complete nested C host suite passed and the complete public Python suite
  passed 261/261; nested pytest-only files remain unavailable in the local
  environment because pytest is not installed, while the unittest-compatible
  nested proxy tests executed before that dependency boundary passed.

Smallest hardware checkpoint: telemetry sequence and host tick counters advance
without a host SIGINT, the web `guest diagnostic` field becomes live, and the
first spontaneous pause retains at least four consecutive samples.  A proxy
checksum failure, guest reset, changed framebuffer behavior or missing sample
stream rejects the transport before any functional fix is attempted.

Implementation/build checkpoint (2026-08-23):
- m1n1 commit `2bd02fb2b01201c276a79b8fe7d3feb460be3a37`;
- the callback decodes and records the asynchronous event but sends no proxy
  command, so it cannot recursively enter the USB request/reply transport;
- the complete public Python suite passed 261/261, the complete nested C host
  suite passed, focused telemetry/display suites passed, and `git diff --check`
  passed;
- a clean Docker build with `APPLE_INPUT=0` succeeded;
- frozen m1n1 artifact `investigation/artifacts/EXP-20260814-051/m1n1.macho`,
  SHA-256 `9014731ac09511ec1a2e2ac7b9d61092387ad38cdda0f4de4c610c5283d02472`;
- unchanged Mu artifact `investigation/artifacts/EXP-20260814-051/J313_EFI.fd`,
  SHA-256 `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- manifest SHA-256
  `89cd76cd04ba2a88bd2a4965a5ca7916178b43e02365e2f72208f79f9ca392de`;
- strict manifest verification passed for assisted chainload, eight cores,
  `display=both`, `debug=monitor` and the exact artifact roles above.

Hardware result (2026-08-23): rejected as an observation transport.  The first
hardware attempt enabled the host handler but received no sample while a 4 KiB
framebuffer response occupied USB IN.  The target sent each sample only once and
discarded a failed nonblocking send, so the transport could silently lose the
only evidence of a freeze.  Guest behavior is not a verdict for this experiment.

Frozen rejection evidence:
- `evidence/EXP-20260814-051-transport-drop/hv.log`, SHA-256
  `7067ea18053fed9f4de2148d7257eac939a07a4e05a26a3db5cf82d0df908e04`;
- `evidence/EXP-20260814-051-transport-drop/fb-info.json`, SHA-256
  `e22794613d76245d72b18ef7eef8b7a46fbb6083640ef175cc302bc072756ce1`.

### EXP-20260814-052 — retry one pending telemetry sample under USB backpressure

Status: rejected after hardware test; observability correction retained
Created (UTC): 2026-08-23T13:20:00Z

Hypothesis: retaining exactly one pending 176-byte sample and retrying its
nonblocking asynchronous send until the sole proxy owner accepts it will make a
spontaneous freeze observable without polling, queue growth or guest delay.

Single changed variable relative to EXP-051: asynchronous telemetry delivery
keeps one pending sample until `usb_iodev_send_event()` succeeds.  NVMe, xHCI,
vGIC, timer and WFx policy, Mu, Windows, topology, memory and display are
unchanged.

Software/build checkpoint:
- m1n1 commit `86433fd0dc69ec52d3507e4d05f68d62bf0c0293`;
- TDD first failed because the pending-delivery state and retry operations did
  not exist, then the focused test and complete nested C host suite passed;
- clean `APPLE_INPUT=0` Docker build succeeded;
- `artifacts/EXP-20260814-052/m1n1.macho`, SHA-256
  `3fec8e20e42b00e6a4d1c40b85cca2deed920c877fce09ca579700ecbed801da`;
- unchanged `J313_EFI.fd`, SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- strict `debug=monitor`, `display=both`, assisted manifest, SHA-256
  `54552029199b02891835bd4fdb5af000adbbccea12677343e052ef12255c18a9`,
  passed profile and artifact-role verification.

Hardware result (2026-08-23): telemetry transport validated; guest stability
rejected.  Samples continued every five seconds through an unperturbed global
pause while physical and USB framebuffers remained at the Windows sign-in
screen and TCP/22 was unavailable.  Host FIQ and tick counters advanced.  NVMe
stopped with one unacknowledged CQ entry, Active INTID 64, and xHCI stopped with
Active INTID 857.

The decisive pre-freeze measurement is an NVMe interrupt storm: 10,416,958
inject/IAR cycles for 37,718 completions (about 276 notifications per
completion), while CQ doorbells and completions differed by only one.  xHCI
remained proportional at 3,071 hardware IRQs/injects.  The emulated PCI header
advertises no MSI/MSI-X capability and `hv_nvme_irq_eoi()` immediately injects
the same continuously asserted pin interrupt again before the Windows DPC can
acknowledge CQHDBL.  This matches the NVMe over PCIe transport definition:
wire mode remains asserted until all related CQ entries are acknowledged, and
host software normally masks it in the ISR before deferred processing.

Frozen evidence:
- `evidence/EXP-20260814-052-nvme-intx-storm/hang-telemetry.jsonl`, SHA-256
  `ee46a7c580afb636ce769503cd924ccaed6817c7de7e8d5ad4893fdfb16614f0`;
- `evidence/EXP-20260814-052-nvme-intx-storm/hv.log`, SHA-256
  `0a887fd7643b0e7651784682e20a7f53467b79dac676a89742ba768f53672107`;
- `evidence/EXP-20260814-052-nvme-intx-storm/fb.raw`, SHA-256
  `71d25bf2ab379a459c7439b7987dc527c14e20b8ace54dcd70ea2587e4d9875f`;
- `evidence/EXP-20260814-052-nvme-intx-storm/fb-info.json`, SHA-256
  `76a9bb67bb579e58ea129eca8864b9efc7c579168628fe42d2738fd07040939e`.

### EXP-20260814-053 — latch one notification per NVMe assertion generation

Status: software validation passed; hardware validation pending
Created (UTC): 2026-08-23T14:50:00Z

Hypothesis: the global pauses and low throughput are caused by immediate
re-injection of the same continuously asserted NVMe INTx after every guest EOI.
Remembering that the current assertion generation was already notified, and
allowing another injection only after a real line deassert/reassert transition,
will give the Windows DPC time to process the CQE and ring CQHDBL.  With the
existing one-CQE controller backpressure this preserves every completion while
preventing millions of duplicate notifications.

Single changed variable relative to EXP-052: NVMe INTx delivery generation
ownership.  EOI releases the Active LR but does not make the same logical
assertion injectable again; a true line deassertion rearms delivery.  If a
deassert/reassert transition occurs while the previous LR remains Active, the
new generation waits for EOI and is then injected.  No timer, WFx, SGI, vGIC
priority, xHCI, Mu, Windows, display, topology or memory change is permitted.

Primary references inspected before the hypothesis:
- current `hv_pci.c`, `hv_nvme.c`, `hv_nvme_queue.c`, `hv_vgic.c` and their host
  tests end to end;
- NVMe over PCIe Transport Specification 1.0a sections 3.5 and A.3: pin mode is
  level-sensitive, CQHDBL acknowledges completion state, and ISR masking before
  DPC processing is the recommended software flow;
- QEMU NVMe documentation: its ordinary controller exposes MSI-X vectors and
  uses MSI-X for the normal admin/I/O queue path.

Smallest falsifiable checkpoint: the host test must first fail because EOI
still makes an unchanged assertion injectable.  After the minimum state-machine
change, all suites and a clean strict artifact must pass.  Hardware accepts the
hypothesis only if interrupt injects remain proportional to completions, the
sign-in/desktop stays responsive, TCP/22 becomes available, and repeated idle
plus bounded storage/CPU stress produces no static-frame interval or bugcheck.

Software checkpoint (2026-08-23): the RED test failed because no assertion
generation state existed.  The minimum implementation added one notified latch,
clears it only when the effective line is low (including INTMS masking), and
keeps LR ownership separate until EOI.  The focused NVMe test, complete nested
C host suite (46 programs), and complete public Python suite (261 tests) pass.
No hardware verdict is claimed yet.

Frozen pre-run checkpoint:
- m1n1 commit `9bc8b33f1e25225cb3281d88784d8db9ddc0c5c4`;
- clean Docker `APPLE_INPUT=0` build completed with only the pre-existing
  compiler warnings recorded by earlier experiments;
- `artifacts/EXP-20260814-053/m1n1.macho`, SHA-256
  `cac737ca8d3271fc64dd13eaedfa086fdccc08f59b4c430e571ed4cdd4419d92`;
- unchanged `artifacts/EXP-20260814-053/J313_EFI.fd`, SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- strict assisted `debug=monitor`, `display=both` manifest, SHA-256
  `7550975241673394ddfbf207f906365efe4bd83c3cb66a3ef6128dcf449b7ac5`,
  passed profile, guest-contract and artifact-role verification.

Hardware result (2026-08-23): rejected as the complete correction.  The
one-notification latch reduced the measured NVMe injection/IAR rate from about
276 notifications per completion in EXP-052 to about 1.14 notifications per
completion, so the duplicate INTx storm is fixed.  Windows nevertheless froze
at the sign-in screen.  Asynchronous telemetry stopped advancing guest NVMe,
xHCI and virtual-IAR/EOI counters while host ticks and framebuffer transport
continued.  A lockless snapshot found balanced SGI queues, Active INTID 64 on
CPU0, and Pending or Active+Pending overdue INTID 18 timer LRs on several
vCPUs.  KD break-in produced no state-change packet and its cleanup sent
Continue.  The freeze is therefore a second defect after the NVMe storm, not a
reason to revert the proportional INTx correction.

Frozen evidence is under
`investigation/evidence/EXP-20260814-053-active-timer-stall/`.  The exact runner
was terminated through its managed SIGTERM path only after the evidence was
copied; Stage 1 then returned on the same proxy/vUART pair.

### EXP-20260823-054 — binary A/B against the last private assisted control

Status: rejected; selected legacy binary was not the accepted fast control
Created (UTC): 2026-08-23

Purpose: separate a public m1n1 runtime regression from Mu, launcher and the
current Windows installation.  The user reports that the pre-public assisted
eight-core build reached the desktop in roughly ten seconds and was markedly
smoother.  This control keeps the current public launcher, current Mu firmware,
eight-core guest contract, `display=both`, monitor observation, NVMe, xHCI and
Windows installation byte-identical, and changes only the assisted m1n1 Mach-O
to the last binary from `/Users/pavel/windows/m1n1_windows/build/m1n1.macho`.
The old repository is read-only; its binary is copied and hashed into this
experiment before use.

Hard timing gate: Windows must reach the sign-in screen in no more than 30
seconds after the Mu-to-Windows handoff; the normal target is about ten seconds.
A static frame, spinner or sign-in pause longer than 30 seconds, missing CPU,
bugcheck, spontaneous reset, or unusable desktop rejects the control.  Passing
this control does not promote the historical binary; it identifies m1n1 as the
regression range and triggers a source-level bisect.  Failure with the same
current Mu/Windows layers shifts the next A/B to the historical Mu firmware.

Hardware result (2026-08-23): rejected by the 30-second gate.  The selected
legacy file identified itself as m1n1 `0060186` and required an explicit host
compatibility flag because its successful `hv_init()` and `hv_pci_init()` calls
return zero.  With that compatibility isolated to this experiment, all eight
vCPUs entered Windows and user-mode PCs appeared, but the USB framebuffer stayed
black and TCP/22 never became reachable.  The binary emitted the later
`HV DIAG X18`, `HV LOWER BRK`, timer and xHCI hot-path diagnostics at high volume;
it is therefore a late diagnostic build, not the pre-public fast binary the
experiment intended to select.  Reusing the last file in a mutable legacy build
directory is not valid provenance.

Evidence:
- `evidence/EXP-20260823-054-private-binary-control/hv.log`, SHA-256
  `e19ad4e9a2c2a7cb48cf6e638e7e38ed467134e830e42481ae865fec9eff6ef6`;
- `evidence/EXP-20260823-054-private-binary-control/fb-info.json`, SHA-256
  `436b753d854b8548281b605100ae36f4a9b6f1e10ce416ab8efbc000ea2452da`;
- rendered black frame
  `evidence/EXP-20260823-054-private-binary-control/frame.png`, SHA-256
  `880a9a589539b7d9aaeeca93fe1eb9662b5e17e95f2c753d688e72975162af2e`.

The managed reboot signal could not be decoded by the old target's incompatible
event framing, so the host process was terminated only after evidence capture.
The target then no longer answered proxy NOP; one physical reset is required.

### EXP-20260823-055 — current runtime with release-cost diagnostics

Status: software preparation in progress
Created (UTC): 2026-08-23

Hypothesis: the very slow boot and pervasive micro-stutter are amplified by the
non-release monitor binary rather than by framebuffer consumption itself.  The
current m1n1 runtime, including the validated proportional NVMe INTx correction,
will reach sign-in within 30 seconds when rebuilt with `RELEASE=1`, while the host
still publishes the asynchronous framebuffer for visual timing.

Single changed variable relative to EXP-053: m1n1 build-time diagnostic cost.
Source, Mu, Windows, eight-core topology, NVMe, xHCI, timer/vGIC behavior and
display geometry remain unchanged.  `APPLE_INPUT=0` remains fixed.  The first
hardware gate is only boot latency and basic responsiveness; a later freeze or
bugcheck still rejects this as a complete stability fix.

Software checkpoint:
- current m1n1 source commit `9bc8b33f1e25225cb3281d88784d8db9ddc0c5c4`;
- build configuration contains exactly `RELEASE` and `HV_DISABLE_APPLE_INPUT`;
- complete nested host suite passed (46 programs);
- `artifacts/EXP-20260823-055/m1n1.macho`, SHA-256
  `f574fa8f35776cf09fd575a835c4b00e9b9b722ebaf22ce313e807c45ffe7d23`;
- unchanged Mu SHA-256
  `0dba13c6fa652ec86900c8879babf6b48ac6a723f37f187ab99ee5f676e00ba5`;
- assisted `display=both`, `debug=monitor` manifest SHA-256
  `cd2ac78aec8a5fb8c5a308d9084f57f3b6135c798627f26167a996b291d9ae56`;
  strict artifact-role verification passed.  The monitor host contract remains
  enabled only to publish the framebuffer; the target's release build removes
  synchronous diagnostic work.

### EXP-20260823-056 — validated minimal four-E-core control

Status: validated as the next hardware control
Created (UTC): 2026-08-23

Purpose: freeze the exact configuration that completed a clean Windows 11 ARM64
first boot and reached a responsive desktop after the earlier eight-core and
full-observation runs produced watchdogs, global pauses, slow boot, or a black
screen.

The successful run changed two variables relative to the rejected observed
experiments: Mu exposed only GICC UIDs 0 through 3, and the launcher selected
`display=physical`, `debug=off`, and no USB framebuffer or host telemetry. The
low-memory alias, physical DCP surface, proportional NVMe INTx correction,
current timer/vGIC implementation, xHCI pass-through, and Windows installation
remained enabled.

Exact artifacts:

- `dist/j313/debug-forensic/m1n1.macho`, SHA-256
  `0389bc92d88f1a19049cecc564b929502f7dbce2ab05942a7e6421bef24632c9`;
- `dist/j313/debug-forensic/J313_EFI.fd`, SHA-256
  `8d95d77664346ceb95bbe7a1fca493cc1b1e876fc1acf627c385191fe4df268a`;
- m1n1 source checkpoint `2fe790beebed32658eae753dee3e6d581df97197`;
- Mu source checkpoint `af4c9705cfd42e976bc9602c35830cc2e9072f36`.

Software verification:

- complete public Python suite passed 265/265 using `proxyenv`;
- the focused m1n1 contract suite passed;
- full upstream m1n1 pytest remains environment-limited by the installed LLD
  default image base and a pre-existing Darwin `uname_result` fixture; these
  failures are outside the changed runtime path and are not reported as green;
- all four launch-contract checkpoints completed on hardware.

Hardware result: Windows entered kernel and user mode on all four enabled
vCPUs, completed OOBE, and reached the desktop. The operator reported normal
interactive speed, stable operation, and no observed micro-freezes in the
initial session. No reset or bugcheck was recorded during that session.

This validates the configuration as the control, not as final platform
qualification. Long-duration storage/CPU stress, suspend/resume, and any
Firestorm guest core remain untested. The target m1n1 was compiled from a
diagnostic tree and still emits build-time UART messages even when runtime
debug is off; a quiet rebuilt binary must reproduce this result before it can
replace these artifact hashes.

Regression rule: subsequent work changes one variable at a time. First prove a
quiet rebuild of this exact four-E-core source. Then test one Firestorm core in
isolation. Any boot over 30 seconds, global pause, watchdog, or loss of the
interactive desktop rejects the experiment and returns to this baseline.

### EXP-20260823-057 — read-only Apple input resource scaffold

Status: software preparation in progress
Created (UTC): 2026-08-23T21:36:53Z

Hypothesis: an assisted build from the exact validated four-E-core source
checkpoints can expose the reviewed J313 Apple SPI-HID resources as
`ACPI\\APPL0001\\0`, route physical IRQ 330 to guest INTID 865, and start the
read-only KMDF scaffold without changing the stable ESP or affecting Windows,
NVMe, external USB input, display, or the four enabled guest CPUs.

Single experimental variable: Apple input resource publication and the
read-only Windows scaffold.  The stable standalone image remains installed and
is the recovery path.  The assisted run uses physical plus virtual display and
monitor diagnostics so ACPI enumeration, driver start, and any guest failure
remain independently observable.

Source and package checkpoint:

- root `14207a24a62fadad2ca8173f3d07486892ffa746`;
- m1n1 `2fe790beebed32658eae753dee3e6d581df97197`;
- Mu `af4c9705cfd42e976bc9602c35830cc2e9072f36`;
- all three tracked-tree diff SHA-256 values are the empty-diff hash
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
- GitHub Actions run `32667648804` AppleInput SYS SHA-256
  `bbb6d9b81b20331a46d005709983116cee17eeef28f9aac54b1ae7908342e8f0`;
- CAT SHA-256
  `66f9113788d2370cf4449136ed7aeb9abd6376c10e0a5764c9a3eeaed6c6613f`;
- INF SHA-256
  `be862209af2f68811c68c3fd8dd1f6ab9e0f445944f6ddb0884c5ce666861edc`;
- signer thumbprint `F95C4158B0E63BD26131FD615482898C5592D201`.

Build command: `scripts/build-development.sh --display both --debug monitor`.
Expected artifact directory: `dist/j313/debug-monitor/`.  The artifact manifest
and SHA-256 values must be recorded after the build and verified before launch.

Launch command: `scripts/run-windows.sh --execution assisted --observed
--debug monitor --foreground` with the detected proxy and vUART endpoints.  The
first run does not install the driver.  It passes only if Windows reaches the
desktop within 30 seconds, `APPL0001` exposes exactly three reviewed MMIO ranges
and one INTID 865 interrupt, all four guest CPUs remain available, and external
USB input, display, NVMe, and SSH stay alive.

Only after that gate passes may the CI certificate be imported and the read-only
driver staged.  The scaffold performs no MMIO write, creates no interrupt
object, and publishes no VHF device; therefore built-in keyboard and trackpad
operation is explicitly not an expected result of this experiment.

Recovery: boot the unchanged stable standalone image.  The verified Windows,
BCD, driver-store, and both-ESP snapshot is
`investigation/evidence/rollback/20260823-232304-stable-4e-baseline-verified`.
Current stable Windows has no `ACPI\\APPL0001\\0` devnode and test signing is
off, so the experimental package cannot bind after a normal stable boot.

Failure criterion: any contract mismatch, stage-2/IRQ preflight failure, boot
over 30 seconds, global pause, bugcheck, storage/input/display loss, unexpected
MMIO write, or devnode resource difference rejects the candidate immediately.

Pre-launch software result (2026-08-23T21:52:12Z): the first clean Mu build
reproduced a packaging defect before any hardware was changed.  EDK2 expanded
the generated node in `DSDT.iii`, then `Trim --source-code -l` discarded it
from `DSDT.iiii` because the C-preprocessor attributed the quoted `#include`
body to a different source file.  Consequently the original candidate FD was
byte-identical to the stable FD and did not contain `APPL0001`; it was rejected
without launch.

The single source correction changes that generated inclusion to the native
ASL `Include (...)` form.  EDK2 now flattens the generated body before the C
preprocessor, so `APPL0001` is present once in `DSDT.i`, `DSDT.iii`,
`DSDT.iiii`, and the compiled `DSDT.aml`.  A new binary-AML build gate checks
the unique `AINP`/`APPL0001` identifiers, all three 64-bit MMIO bases, and guest
INTID 865 before any firmware can be packaged.  Its test was observed failing
before the correction and passing afterward.  The focused Apple input suite
passes 32/32.  Decompiled final MADT still enables UIDs 0-3 and disables UIDs
4-7.

Corrected assisted candidate:

- root diff SHA-256
  `d6997ad66d9e7ee37fd832e2442ad03df6842cb9243edad36b1dc997e14982c7`;
- m1n1 diff SHA-256 remains the empty-diff hash;
- Mu diff SHA-256
  `e535e345a5202a944f5b1edc397e656f65f40679ca959914752b288d6fde272b`;
- `m1n1.macho` SHA-256
  `3d41abb1b5b16c09a96c9bebe4244b2e5d88fe084cd786f8289e928920b49a35`;
- `J313_EFI.fd` SHA-256
  `cd591aab2ef0641902f03e1a38aac697e45fc12e466a3cb72f32cd3d68060710`;
- `boot.bin` SHA-256
  `61fef2d71f9f4b46dc787d1db56a2749d22d055bc5e15e0d5c1f6767aa60c58a`.

Artifact-role verification passed for `display=both`, `debug=monitor`.  The Air
was confirmed in m1n1 proxy mode by a read-only identity probe.  The stable ESP
and the Windows driver store remain unchanged at this point.

First assisted hardware gate (2026-08-24): confirmed.  Two launch attempts were
discarded before evaluation: the first mixed a stale guest session with the new
chainload and failed the launch-publish RPC; the second detached the host owner
of `run_uefi.py`, so the process lifetime was not a valid assisted contract.
Neither attempt installed a driver or changed the stable ESP.  After a physical
return to proxy mode, m1n1 `2fe790b` was chainloaded and the corrected firmware
was kept under a foreground host owner for the entire run.

The valid run reached the Windows desktop with all four intended E cores online,
NVMe, xHCI, physical display, asynchronous virtual display, SSH, and monitor
telemetry alive.  The virtual framebuffer published 2560x1600 B8G8R8X8 frames;
generation 93 showed the live desktop and Task Manager with four logical
processors.  No bugcheck, system reset, unhandled exception, or fatal marker was
present in `hv.log` at the checkpoint.  Exact live Windows enumeration:

- instance `ACPI\\APPL0001\\0`, BIOS path `\\_SB.AINP`;
- status Code 28 solely because no compatible driver is installed;
- interrupt resource `0x361` (guest INTID 865);
- memory `0x23510c000..0x23510ffff`;
- memory `0x23c100000..0x23c1fffff`;
- memory `0x23d1f0000..0x23d1f3fff`;
- AppleInput service absent and test signing still disabled.

Verdict: the ACPI packaging correction and no-driver resource publication are
confirmed on hardware.  Boot-to-desktop latency was not independently timestamped
in this manually resumed run, so this result validates the resource gate rather
than replacing the EXP-056 performance baseline.  The next experiment changes
only Windows test-signing state and installation of the already-hashed read-only
AppleInput scaffold.  It must bind and start without MMIO writes, interrupt
creation, child HID publication, storage loss, USB loss, global pause, or
bugcheck.  Recovery remains the unchanged stable ESP plus the verified rollback
bundle above.

### EXP-20260823-058 — enable AppleInput test-signing trust only

Status: hardware run prepared
Created (UTC): 2026-08-23T22:03:58Z

Hypothesis: importing only the public CI signing certificate and enabling Windows
test-signing will preserve the confirmed EXP-057 four-E-core desktop, storage,
xHCI, displays, SSH, and ACPI resources.  No driver is staged or installed in
this experiment, so `ACPI\\APPL0001\\0` must remain Code 28 and the AppleInput
service must remain absent.

Single changed variable: Windows code-signing policy and trust stores.  Firmware,
ACPI, m1n1, Mu, CPU topology, ESP contents, and driver store remain unchanged.

Source state:

- branch `stable/j313-4e-baseline`, root commit
  `14207a24a62fadad2ca8173f3d07486892ffa746`;
- m1n1 `2fe790beebed32658eae753dee3e6d581df97197`;
- Mu `af4c9705cfd42e976bc9602c35830cc2e9072f36`;
- root diff SHA-256
  `ddec3b930f829825b14e374fee5db4687e029517d700a0703f51fa179eb59d1f`;
- m1n1 diff SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
- Mu diff SHA-256
  `e535e345a5202a944f5b1edc397e656f65f40679ca959914752b288d6fde272b`.

The package is the unexpired GitHub Actions artifact
`AppleInput-ARM64-Debug` from run `32667648804`, archive digest
`f9ac49e5a66283a5d47ad7f81078f0b4a9b62815f2f8053fd2b9fd0454c00a80`.
The catalog signer certificate is exported locally by Windows from the already
verified catalog; no private key is copied or created.  Its expected thumbprint
is `F95C4158B0E63BD26131FD615482898C5592D201`.

Preparation commands copy the package into the operator profile, export the
catalog signer, verify its thumbprint, add the public certificate to LocalMachine
Root and TrustedPublisher, and run `bcdedit /set testsigning on`.  The package is
not passed to `pnputil` in this experiment.

Launch after reboot: the same foreground assisted EXP-057 artifacts with
`display=both`, `debug=monitor`.  Expected checkpoint: desktop within 30 seconds,
four logical CPUs, test-signing enabled, APPL0001 exact resources unchanged,
Code 28, service absent, and no bugcheck/reset/global pause.

Rollback: boot the unchanged stable standalone ESP; then remove the two public
certificate-store entries and run `bcdedit /deletevalue testsigning`.  The
verified full rollback bundle remains
`investigation/evidence/rollback/20260823-232304-stable-4e-baseline-verified`.

Hardware result (2026-08-23T22:11Z): confirmed.  The signer certificate with
thumbprint `F95C4158B0E63BD26131FD615482898C5592D201` is present in both
LocalMachine Root and TrustedPublisher, and `{current}` reports
`testsigning Yes`.  The package was copied and hash-verified but was not passed
to `pnputil`; `sc query AppleInput` remained 1060 and APPL0001 remained Code 28.

The same corrected assisted firmware reached SSH on polling attempt 11 at a
two-second interval, approximately 22 seconds after launch.  The 2560x1600
virtual frame showed the live Windows lock screen, all four CPU entry markers
and `guest runtime ready` were present, and no bugcheck, system reset, unhandled
exception, or fatal marker appeared.  APPL0001 still exposed INTID 865 and the
same exact three memory ranges.  Verdict: test-signing/trust is not the source
of a boot, resource, display, USB, storage, or CPU regression.  Proceed with one
live installation of the read-only scaffold; no reboot is required because
test-signing is already active.

### EXP-20260823-059 — bind read-only AppleInput scaffold

Status: hardware run prepared
Created (UTC): 2026-08-23T22:12:00Z

Hypothesis: the signed read-only AppleInput KMDF scaffold will bind to the exact
EXP-057 ACPI resources and enter D0 without changing any hardware register,
creating an interrupt object, or publishing a HID child.  Windows, NVMe, xHCI,
SSH, both displays, and four E cores must remain responsive.

Single changed variable relative to confirmed EXP-058: add and install the
already verified AppleInput INF package.  Firmware, ACPI, test-signing, CPU
topology, ESP, and all other drivers remain fixed.

Package in `C:\\Users\\pavel\\AppleInput-32667648804`:

- `AppleInput.sys` SHA-256
  `bbb6d9b81b20331a46d005709983116cee17eeef28f9aac54b1ae7908342e8f0`;
- `appleinput.cat` SHA-256
  `66f9113788d2370cf4449136ed7aeb9abd6376c10e0a5764c9a3eeaed6c6613f`;
- `AppleInput.inf` SHA-256
  `be862209af2f68811c68c3fd8dd1f6ab9e0f445944f6ddb0884c5ce666861edc`.

Install command: `pnputil /add-driver AppleInput.inf /install`.  Immediate gates:
the devnode is Started with service AppleInput, exactly the reviewed resources
remain assigned, no keyboard/mouse child appears, external USB input remains
alive, SSH remains reachable, the framebuffer advances, and `hv.log` contains no
fatal/reset/bugcheck marker.  Failure includes any Code 10/31/39/52, resource
mismatch, global pause, storage/display/input loss, or bugcheck.

Rollback: boot the unchanged stable standalone firmware, identify the published
OEM INF with `pnputil /enum-drivers`, remove it with `pnputil /delete-driver
oemNN.inf /uninstall /force`, remove the public certificates, and delete the
testsigning BCD value.  The verified full rollback bundle remains unchanged.

Hardware result (2026-08-23T22:13:33Z): rejected safely.  `pnputil` accepted the
catalog, published `oem2.inf`, selected it for `ACPI\\APPL0001\\0`, and attempted
to start the device.  Windows remained responsive with SSH, framebuffer,
telemetry, NVMe, xHCI, and four logical CPUs alive; no reset or bugcheck marker
appeared.  The devnode failed closed with Code 10 and problem status
`0xC0000182` (`STATUS_DEVICE_CONFIGURATION_ERROR`).  AppleInput was registered
but stopped, no HID child was published, and the exact IRQ/MMIO assignments were
unchanged.

Kernel-PnP event 411 and SetupAPI confirmed that package staging, catalog
selection, service creation, and the PnP start request all completed before the
driver returned the configuration error.  Microsoft WDF documentation states
that raw and translated resources are paired in the same order: the raw
interrupt descriptor contains the bus/firmware interrupt, while the translated
descriptor contains the system vector a driver uses at runtime.  The scaffold
incorrectly ignored `ResourcesRaw` and compared translated `u.Interrupt.Vector`
to ACPI GSI 865.  That comparison is invalid even when `pnputil /resources`
correctly reports the firmware GSI.

Verdict: the ACPI and signing contracts remain confirmed; the driver resource
parser is rejected.  The next candidate changes only that parser: validate GSI
865 from the paired raw descriptor, retain the translated vector for future
`WdfInterruptCreate`, validate raw memory identities, and map translated memory
addresses.  The old package remains fail-closed and can be replaced in place.

### EXP-20260823-060 — correct raw/translated KMDF resource pairing

Status: software implementation in progress
Created (UTC): 2026-08-23T22:17:00Z

Hypothesis: with the one confirmed parser defect corrected, the otherwise
byte-equivalent read-only scaffold will start on the exact EXP-057 resources and
remain inert: no MMIO write, interrupt object, VHF child, keyboard, or trackpad
activity is expected yet.

Single changed variable relative to rejected EXP-059: `AiDeviceParseResources`
uses paired raw and translated descriptors according to the WDF contract.  INF,
VHF lower filter, ACPI, firmware, m1n1, Mu, signing mode, topology, and all
read-only validation calls remain unchanged.

Regression test: `test_irq_contract_uses_raw_gsi_and_keeps_translated_vector`
was observed failing because the source ignored `Raw`; after the correction the
focused Windows-package plus ACPI suite passes 15/15.  The test requires the
raw descriptor to validate `J313_APPLE_INPUT_GUEST_VINTID`, the translated
descriptor to supply `Context->InterruptVector`, equal paired list counts/types,
and no comparison of the translated vector to the firmware GSI.

Build and artifact hashes will be appended after the full suite and CI signing
complete.  Hardware gate and rollback are identical to EXP-059; any Code 10,
unexpected child, global pause, storage/input/display loss, or bugcheck rejects
the candidate.

Hardware result (2026-08-23T22:31:41Z): confirmed.  GitHub Actions run
`32670342876` completed successfully at root commit
`401d783a69c33e4f6612fb3e8d352a59f49e57fd`.  Artifact
`AppleInput-ARM64-Debug` has GitHub digest
`sha256:ff512e2d1d7c470149cd4d954df0b38987722f5f443ce00ecd7a6a7a5869e46f`.
The installed package hashes were verified both on the host and on Windows:

- `AppleInput.sys` SHA-256
  `f87dc8a8ab5cbf3e329e434ac10353be8cc621139653a525a56eebf81ddff198`;
- `appleinput.cat` SHA-256
  `57cad98005bd465e2870976a96084bae0459bae00177dfff238d8b749855a61b`;
- `AppleInput.inf` SHA-256
  `2584b7171f255c4a77df7810fb07bd6db443bbc5ef57965421d029255ad7c240`.

The package is signed by WDK test certificate thumbprint
`66BD427FE4704AE3C0FF3F51A1DE26AE0BE8338C`; its exported public certificate
has SHA-256
`095e2bb5d614ea0c098273eac912699f1125b3b63bfb02cd9c53945e3259b3cf`.
After explicitly adding that public certificate to LocalMachine Root and
TrustedPublisher, both CAT and SYS reported `Signature verified`, and
`{current}` still reported `testsigning Yes`.

`pnputil /add-driver AppleInput.inf /install` published `oem4.inf`, selected it
as best ranked over rejected `oem2.inf`, and started `ACPI\\APPL0001\\0`.
The devnode reports `Started`, `CM_PROB_NONE`, and driver version
`22.23.36.653`; `sc query AppleInput` reports the kernel driver `RUNNING` with
zero exit codes.  The exact resources remain IRQ 865 and memory ranges
`0x23510c000..0x23510ffff`, `0x23c100000..0x23c1fffff`, and
`0x23d1f0000..0x23d1f3fff`.  No Apple keyboard, mouse, precision-touchpad, or
other HID child was published, as expected for this read-only checkpoint.

Windows remained reachable over SSH with four logical CPUs; NVMe, xHCI,
external USB input, physical display, and virtual framebuffer remained alive.
The assisted log contains `guest runtime ready` and no bugcheck, reset,
unhandled-exception, panic, or fatal marker.  The unchanged stable ESP and its
verified rollback bundle were not modified.

Verdict: confirmed.  The raw/translated WDF resource-pairing defect was the
complete cause of EXP-059 Code 10.  The next experiment may add exactly one
runtime capability to the now-starting scaffold; built-in keyboard and
trackpad input are still intentionally absent at this checkpoint.

### EXP-20260824-061 — bounded Apple SPI HID transport-only Gate A

Status: hardware run prepared
Created (UTC): 2026-08-24T00:19:00Z

Hypothesis: replacing only the previously validated inert AppleInput package
with the bounded transport-only package will start the passive IRQ worker,
perform Apple SPI HID boot and discovery traffic, and expose header-only
diagnostics without publishing keyboard or trackpad HID children or disturbing
the validated four-E-core Windows baseline.

Single changed variable relative to EXP-060: AppleInput gains the reviewed
SPI3/GPIO transport, constant-work ISR, passive worker with a 32-packet drain
limit, portable protocol discovery, and read-only diagnostic IOCTL.  The stable
ESP, m1n1, Mu, guest firmware, CPU topology, NVMe, xHCI, display, Windows image,
and test-signing policy remain unchanged.  `TransportOnly=1` is present in the
INF and in the device context; no VHF child is created by this candidate.

Pre-state observed over SSH:

- Windows 11 Pro is reachable at `192.168.1.37` with four logical processors;
- BCD reports `testsigning Yes`;
- `ACPI\\APPL0001\\0` is Started on `oem4.inf`, service `AppleInput` is
  RUNNING, and the exact resources remain IRQ 865 plus the three reviewed MMIO
  ranges;
- the current package is the confirmed inert EXP-060 rollback driver;
- the stable ESP is not modified by this experiment.

Source and build checkpoint:

- root branch `feature/j313-native-input`, root commit
  `8177d7972961f7b954e53e7ad2bd6f34cbc6157a`;
- GitHub Actions ARM64 WDK run `32673938270` completed successfully, including
  code-analysis driver build, ARM64 diagnostic-client build, and package
  upload;
- `AppleInput.sys` SHA-256
  `daf714d6311191dae63c354f61f9f1b9a31b6c0b04637704cbdb4d261ce98196`;
- `appleinput.cat` SHA-256
  `3ef247d57b2d22be00abc01e2a558be21e9440dd870ee960851e0f0c569e9e71`;
- `AppleInput.inf` SHA-256
  `1bca70bf9ec35a94f2f564915e2d5490b39b029a09ef88f04ef24fbfee2cd357`;
- `AppleInputDiag.exe` SHA-256
  `9f2895433f8d8c3d3ea5b34f21e0966ff777d498196792ceabbd5ac9deaf8d55`;
- catalog public-certificate SHA-256
  `7e257aa237af27a185be04385a32415c4d680877d55d4cfee82df380dccadc94`,
  SHA-1 thumbprint `44797A7C75ED8D09E7BE3135E700D591F0E3C168`.

Procedure: copy the exact package, CLI, and public certificate to Windows;
verify all hashes on the Air; trust only that public certificate in
LocalMachine Root and TrustedPublisher; install the INF; require the devnode
and service to start; then capture versioned diagnostic snapshots before and
after key/touch activity.  Restart the devnode once only after the initial
checkpoint remains responsive.

Immediate pass gates: Windows remains reachable over SSH, external USB input,
NVMe, physical display, and four CPUs stay alive; no new HID child is present;
interrupt/worker/SPI counters are bounded and coherent; discovery advances or
fails with an explicit bounded counter rather than a hang; no bugcheck, global
pause, storage loss, or repeated interrupt storm occurs.

Rollback: identify the newly published OEM INF, remove it with `pnputil
/delete-driver oemNN.inf /uninstall /force`, and rescan devices so the already
installed confirmed `oem4.inf` package becomes best-ranked again.  Remove only
the new public certificate thumbprint if necessary.  The stable ESP and the
verified full rollback bundle remain unchanged.

Initial hardware result (2026-08-24T00:28Z): the exact package installed as
`oem6.inf`; APPL0001 and AppleInput both report Started/RUNNING, IRQ 865 and all
three MMIO ranges are unchanged, and SSH remained responsive.  The first CLI
binary exposed an independent packaging defect by exiting with `0xC0000135` on
the clean Windows image.  A static-CRT rebuild from run `32674551330` then ran
successfully and returned a version-1 snapshot: phase `WAIT_BOOT`, reset count
1, with interrupt, worker, and SPI counters all zero.

This safely rejects the original runtime candidate before devnode restart or
input publication.  Microsoft documents that `EvtDeviceD0Entry` executes before
the framework enables interrupts and that
`EvtDeviceD0EntryPostInterruptsEnabled` executes afterward.  The installed
candidate reset the input controller in the earlier callback and set
`HardwareStarted` only after the 50-ms boot wait, so its ISR could reject or
miss the short startup event.  Asahi enables the HID interrupt before waiting
for the boot marker.  The next candidate changes only that lifecycle ordering;
`oem6.inf` remains live and responsive until the replacement compiles.

Lifecycle-corrected result: CI run `32674919980` installed as `oem7.inf` and
remained Started/RUNNING with Windows reachable over SSH, but its version-1
snapshot was unchanged: phase `WAIT_BOOT`, reset count 1, and interrupt,
worker, and SPI counters all zero.  This rejects lifecycle ordering as the
remaining cause.

Root-cause checkpoint (2026-08-24T00:04:57Z): the Linux Apple GPIO driver
performs three hardware operations in `apple_gpio_irq_startup`: it selects IRQ
group 0, configures the pin as an input, and unmasks the selected trigger mode.
For `IRQ_TYPE_LEVEL_LOW`, that mode is register value 3.  Our Windows driver
only read pin 13 and acknowledged its group register; it never configured the
pin's group or interrupt mode.  Therefore the controller reset completed but
the nub GPIO controller could not raise the parent IRQ that m1n1 routes to GSI
865.  Reference:
`https://github.com/torvalds/linux/blob/master/drivers/pinctrl/pinctrl-apple-gpio.c`.

Next single-variable candidate: root commit
`d78081e4d3e310375242ce791ede996717cd9a2e` clears pin 13's peripheral/data
configuration, selects group 0, enables input, sets level-low IRQ mode, and
acknowledges stale pending state before the existing controller reset.  It does
not add VHF children, modify the ESP, firmware, CPU topology, display, NVMe,
xHCI, or Windows configuration.  The new regression test failed before the
implementation; the focused package suite passed 14/14 and the complete public
suite passed 277/277 after the change.  Hardware result remains pending the
ARM64 WDK artifact and one-package replacement.

GPIO hardware result (2026-08-24): confirmed.  GitHub Actions run
`32675571980` completed successfully and produced artifact
`AppleInput-ARM64-Debug`, digest
`sha256:e5a836fe213b8908e5661a43ac3edb30c64e3b47e4276232dc2d7f5de8bd9838`.
The host and Air agreed on the package hashes:

- `AppleInput.sys` SHA-256
  `462a398cc490e3e8d981583646841d117bf54a405cc16c9a4eea3b862ec9b976`;
- `appleinput.cat` SHA-256
  `571f16771d99b544412d4f892bd9df193b4f500a2ea4cc23e317c48e33deb6e5`;
- `AppleInput.inf` SHA-256
  `8c439728c8020b190278163af0ec949a4f2a106802d14f1d665d397cfc90b5c2`;
- `AppleInputDiag.exe` SHA-256
  `d8e7343b513aea3a5ce4a4e29a0f58736b61842aed312732f26aca92d12532b9`;
- exported public certificate SHA-256
  `d5f21c3a09201d337835068095ade76c3649b693d1c62e10a91cd2dbf3032d8e`,
  SHA-1 thumbprint `9996D1A92A0F2EC86E7A60227EAC02E82F1CA951`.

After trusting only that public test certificate, the catalog signature was
`Valid`; `pnputil` installed the package as `oem8.inf`.  APPL0001 and the
AppleInput service remained Started/RUNNING and SSH stayed responsive.  The
snapshot changed from phase 1, IRQ 0, worker 0, SPI 0 to phase 2, IRQ 36,
workers queued/completed 4/4, SPI transfers 7, reset 1, and zero timeout, CRC,
fragment, or offline failures.  No built-in HID child was published, as required
by transport-only mode.  This proves the missing pin-13 group-0 level-low GPIO
configuration was the complete cause of the zero-interrupt Gate A failure.

The stable counters after five seconds also expose the next independent defect:
32 interrupts arrived while only four workers were queued, and the transport
remained at identity phase 2.  `AiTransportWorker` calls
`ai_transport_worker_complete`, receives a true result when a coalesced IRQ is
pending, then clears `pending` instead of draining it.  The next candidate will
change only this bounded worker handoff.  `oem8.inf` remains responsive and is
the rollback point for that test; the ESP remains untouched.

Coalesced-IRQ candidate checkpoint: root commit
`af79ed5fa1c90d19509193081e5dd25e55151782` keeps the same 32-packet callback
budget but, when `ai_transport_worker_complete` reports pending work, consumes
that work in the current passive callback instead of clearing it.  The portable
queue contract already required `worker_complete(true)` to be followed by
another `worker_begin`; the Windows adapter was the sole violating consumer.
Microsoft documents that `WdfInterruptQueueWorkItemForIsr` must be queued from
the ISR, so the callback drains already-coalesced work itself rather than
attempting an unsupported self-requeue.  The new regression test failed against
the old adapter, then the focused transport suites passed 16/16 and the complete
public suite passed 278/278.  ARM64 WDK and one-package hardware validation are
pending; `oem8.inf` stays installed until the replacement is verified.

Coalesced-IRQ hardware result (2026-08-24): CI run `32676346545` was rebuilt
after one transient runner restore stall and produced artifact
`AppleInput-ARM64-Debug`, digest
`sha256:e85ffbc10d8815ffb3c59b133d9d5deba8f2db1b484b3ef989c8144f3163f90c`.
The package hashes matched on the host and Air: SYS
`4680a3ac1f66cd290df9f4619349c2ebbe63d224abf94a54359e3359031f7259`,
CAT `3ad1666f7fd27032acd02486bbed70f435505baab0c5984db77d025af88b7819`,
INF `33c45f5b3a8ca266fa17680058a7c67c7ab076b7947b7ef0b645b1e60d6a071b`,
and CLI `c3d41c45ed11e8e18431b43a8a65006e0c8d9325e2d66c801aac45594970f2fd`.
Only the exported public certificate, SHA-256
`173eaeb98a3e0bae1ab5579baf58214d107acc1a1daff17126456871dcf7bcc3`,
thumbprint `F866FBE77A5F882A1AA270DBDA8B7B8DE5E558AE`, was trusted.  CAT and SYS
then verified as `Valid`, and the package installed as `oem9.inf`.

The Air remained reachable and APPL0001 plus AppleInput remained
Started/RUNNING.  Four stable snapshots reported phase 2, IRQ 4, workers 2/2,
SPI 6, reset 1, and zero timeout, CRC, fragment, or offline failures.  Thus the
previous 36-to-4 IRQ/worker loss is gone, but identity still does not advance.
No HID child was published and the stable ESP was not modified.

Diagnostic boundary result: CLI commit `3f50c3f` exposed the already bounded
header ring without changing the driver.  CI run `32677347015` produced CLI
SHA-256 `7038ecf20eb36ea0b2310c62408f5e2fa82d4c0cdb81070c0d1b89194f955d09`.
The live `oem9` snapshot contained exactly two successfully decoded headers:
the boot packet (`flags=0x20`, device `0xd0`, length 4) and a complete identity
response (`flags=0x40`, device `0xd0`, length 99).  Therefore GPIO, interrupt,
SPI read/write, packet CRC, fragmentation, and response delivery all succeed;
the rejection occurs after message decode.

The official Asahi SPI HID implementation initializes `msg_id` to zero and
post-increments it when encoding the first identity request.  Our discovery
state incremented zero to one while accepting the boot marker, then required
the response ID to equal one.  Commit `517aac4` changes only that initial
sequence boundary: accepting boot arms the identity deadline while preserving
request ID zero; subsequent accepted phases continue incrementing normally.
The portable protocol test failed against the old behavior, then focused tests
passed 17/17 and the complete public suite passed 279/279.  Hardware validation
of this one-variable candidate is pending; `oem9.inf` remains the responsive
rollback package.

### EXP-20260824-043 — assisted relaunch before identity-ID validation

Pre-run record (2026-08-24T06:15:41Z).  Hypothesis: the previously validated
four-E-core public launch contract still reaches an interactive Windows desktop
after the user reboot, allowing the message-ID-zero AppleInput package to be
validated without changing firmware, topology, or the stable ESP.  The single
run variable is execution mode: the installed ESP is left untouched and the
paired `debug-forensic` artifacts are chainloaded from the host with both the
physical and USB framebuffer consumers enabled.

- repositories: root `0525c0297a5db15644923dd87a769969266d6b3a`,
  m1n1 `2fe790beebed32658eae753dee3e6d581df97197`, Mu
  `9501de460353b902dbbd3b7de42c703af811f037`, branch
  `feature/j313-native-input`; all three tracked diffs are empty (SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).
- artifacts: `dist/j313/debug-forensic/m1n1.macho`, SHA-256
  `0389bc92d88f1a19049cecc564b929502f7dbce2ab05942a7e6421bef24632c9`,
  and `dist/j313/debug-forensic/J313_EFI.fd`, SHA-256
  `8d95d77664346ceb95bbe7a1fca493cc1b1e876fc1acf627c385191fe4df268a`.
- launch command: `scripts/run-windows.sh --execution assisted --display both
  --debug full --observed --proxy <CONSOLE_DEVICE> --vuart
  <VUART_DEVICE>`.
- recovery: no ESP write; reboot returns to the installed stable image.
  `oem9.inf` remains the confirmed AppleInput rollback package.
- expected checkpoint: explicit `Starting guest...`, live internal and web
  display, interactive Windows desktop and SSH at `192.168.1.37`.  Failure is
  no guest handoff within the launcher's deadline, bugcheck/reboot, or no
  interactive desktop.  Evidence paths are `assisted-runner.log`, `hv.log`,
  the viewers on ports 8765/8766, and the post-boot Windows/AppleInput snapshot.

Post-run result (2026-08-24T06:20Z): inconclusive; no guest defect was
observed.  The wrapper validated and chainloaded the paired artifacts, reached
`Starting guest...`, initialized the NVMe backend, and entered Mu DXE.  The
host execution environment then reaped detached PIDs 1466/1570 after the
launcher command returned.  `hv.log` ended mid-line at 65,008 bytes while Mu
was loading DXE drivers, with no traceback, exception, reset, or bugcheck; both
the runner and vUART reader were dead while both USB ACM nodes remained.  This
left the target inside a host-driven hypervisor with no process servicing the
proxy.  A UEFI-console `reset` write and a 90-second proxy probe could not
recover it, so one physical reboot is required.  Repeat this exact artifact and
contract with `--foreground` in a persistent host session; do not interpret
this run as firmware, Windows, or AppleInput evidence.

### EXP-20260824-044 — persistent foreground repeat of EXP-20260824-043

Pre-run record (2026-08-24T06:25:46Z).  Hypothesis: keeping `run_uefi.py` as a
persistent foreground process eliminates the host-lifecycle truncation seen in
EXP-20260824-043 and permits the unchanged four-E-core guest to reach the
interactive desktop.  The sole changed variable is detached versus foreground
host process ownership.  Root commit is
`0525c0297a5db15644923dd87a769969266d6b3a`; the artifacts and hashes are
unchanged from EXP-20260824-043: m1n1
`0389bc92d88f1a19049cecc564b929502f7dbce2ab05942a7e6421bef24632c9`
and Mu `8d95d77664346ceb95bbe7a1fca493cc1b1e876fc1acf627c385191fe4df268a`.
The fresh proxy passed `probe.py` before launch.

Launch command: `scripts/run-windows.sh --execution assisted --display both
--debug full --observed --foreground --proxy
<CONSOLE_DEVICE> --vuart <VUART_DEVICE>`.
The stable ESP remains untouched and `oem9.inf` remains the input-driver
rollback.  Expected checkpoint and evidence paths are identical to
EXP-20260824-043; failure additionally includes loss of the persistent runner
without a target exception or reset.

Post-run result (2026-08-24T06:29Z): confirmed for the host-lifecycle
hypothesis.  The persistent runner reached Windows, SSH became available at
08:27:10 local time, and a normal Windows restart returned the Air to a
responsive proxy.  No host truncation or guest fatal marker occurred.  This
pre-input `debug-forensic` Mu intentionally has no `ACPI\\APPL0001\\0`, so
AppleInput remained stopped and the run provides no input-protocol evidence.
The next run uses the separately hardware-validated EXP-057 `debug-monitor`
pair that publishes the reviewed input ACPI node.

### EXP-20260824-045 — validate identity-ID zero on the EXP-057 firmware pair

Pre-run record (2026-08-24T06:29:59Z).  Hypothesis: under the exact EXP-057
AppleInput-capable firmware pair, replacing only confirmed rollback `oem9.inf`
with CI run 32677640457 will accept the already observed identity response ID
zero and advance discovery beyond phase 2 without affecting Windows, storage,
USB, display, SSH, or the four enabled E cores.

The launch artifacts are `dist/j313/debug-monitor/m1n1.macho`, SHA-256
`3d41abb1b5b16c09a96c9bebe4244b2e5d88fe084cd786f8289e928920b49a35`,
and `dist/j313/debug-monitor/J313_EFI.fd`, SHA-256
`cd591aab2ef0641902f03e1a38aac697e45fc12e466a3cb72f32cd3d68060710`.
Their manifest records m1n1 commit `2fe790be`, Mu commit `af4c9705` plus diff
SHA-256 `e535e345a5202a944f5b1edc397e656f65f40679ca959914752b288d6fde272b`,
and the previously validated root build state from EXP-057.

Launch command: `scripts/run-windows.sh --execution assisted --display both
--debug monitor --observed --foreground --proxy
<CONSOLE_DEVICE> --vuart <VUART_DEVICE>`.
Driver candidate hashes are those recorded for CI run 32677640457 immediately
above; installation is forbidden until the live APPL0001 node and `oem9.inf`
rollback state are re-confirmed.  The stable ESP remains untouched.  Pass:
interactive desktop and SSH, APPL0001 Started, candidate service RUNNING,
discovery phase greater than 2 with bounded coherent counters and no transport
errors.  Failure: missing resource, driver start failure, phase not advancing,
hang, reboot, bugcheck, or loss of any baseline subsystem.  Evidence: `hv.log`,
ports 8765/8766, Windows PnP/service state, and versioned CLI snapshots.

Post-run result (2026-08-24T06:56:39Z): confirmed.  The unchanged EXP-057
firmware pair reached an interactive Windows desktop with SSH and the 2560x1600
physical/USB framebuffer contract alive.  Installing CI run 32677640457 as
`oem10.inf` changed only AppleInput and advanced discovery from phase 2 to phase
3 with zero SPI timeout, packet CRC, message CRC, fragment, or offline failures.
This validates the message-ID-zero correction from commit `517aac4`.

CI run 32698571320 then supplied read-only snapshot v2 diagnostics from commit
`33ca3d1`.  Host and Air hashes matched: SYS
`4750e732b126649d3c9aedc95557731eb7cf24414353b9071e033d00e74ec317`,
CAT `7e848559fcd2708981a5f29f136162bf0a20372147ced197e87f4b7fb397a8f7`,
INF `17570431916fd3348fa9233c659656ca1f786ca1f5043cd8d7c23d2b18a2e884`,
and CLI `aa81b080bdd24fdc24c8ed43fa4ed085557c6eaedc333c46ceb7c2390d65c43a`.
The user explicitly approved WDK test certificate
`93BE8353D349CD9845916DD72AD23A31524AD941`; the diagnostic package installed
as `oem11.inf`, remained PnP `OK` and service `RUNNING`, and retained
`oem10.inf` as rollback.

The phase-3 snapshot contained a CRC-valid management response
`type=0x10 report=0x02 device=0 id=56 payload_length=8` while the state machine
was waiting for its interface-management response with request ID 1.  Counters
were coherent (`interrupts=5481`, `workers=55/55`, `spi_transfers=122`) and all
transport error counters remained zero.  The bounded packet ring also showed
continuing valid device-2 input packets.  The web viewer remained streaming at
2560x1600 generation 221 and `hv.log` contained no reset, exception, or
bugcheck marker.  This confirms that the strict incoming response-ID equality
test is the next rejection boundary.  The official Asahi implementation uses
IDs only when encoding outbound messages and dispatches inbound responses by
packet direction plus message type/report/device; the next one-variable change
must remove only the Windows-side incoming ID gate while retaining those
structural predicates and outbound ID sequencing.

### EXP-20260824-046 — accept structurally matched responses without echoed IDs

Pre-run record (2026-08-24T07:05:10Z).  Hypothesis: removing only the
Windows-side equality test between the inbound message ID and the current
outbound request ID will allow the already CRC-valid management response to
advance discovery beyond phase 3 while preserving all packet direction,
target, type, report, device, payload, CRC, phase, and outbound-ID checks.  The
single changed variable is the AppleInput SYS built from root commit
`6fe3ee32c7238655b2f0860be4e398ce1a0d0d69`; firmware, topology, display,
Windows, and the installed ESP are unchanged from EXP-20260824-045.

- repository state: root branch `feature/j313-native-input`, root diff SHA-256
  `e4908a5fddbb8b1f012018f40eb398bc5c66c955ebe512f14534465699f42e14`
  contains only the required experiment/change ledgers; nested source commits
  are m1n1 `2fe790beebed32658eae753dee3e6d581df97197` and Mu
  `9501de460353b902dbbd3b7de42c703af811f037`.
- live launch artifacts remain the EXP-057 pair:
  `dist/j313/debug-monitor/m1n1.macho` SHA-256
  `3d41abb1b5b16c09a96c9bebe4244b2e5d88fe084cd786f8289e928920b49a35`
  and `dist/j313/debug-monitor/J313_EFI.fd` SHA-256
  `cd591aab2ef0641902f03e1a38aac697e45fc12e466a3cb72f32cd3d68060710`.
- driver artifact: GitHub Actions run 32699722561,
  `.local/apple-input/no-id-gate-32699722561`; SYS SHA-256
  `580428d9e6623de672d7d1a0da89610aa740f811985ca5447db88a57f4d1fe13`,
  CAT `56866318c65338f939f3d69319154a68861bda538c72bf68fbd412d5bb062d77`,
  INF `712eaf895ecd6c7653149e05c542b34f5ee415cfde9af0b62adf8fa1e87d7a1a`,
  CLI `954d6c768e1afd4f82c9ced3be609ffa180a9045fd61720ed179e7bb6b294cad`.
- install command: import only the package catalog signer approved for this run,
  then `pnputil /add-driver AppleInput.inf /install`; confirmed diagnostic
  `oem11.inf` and the stable ESP remain the recovery paths.
- expected checkpoint: PnP `OK`, service `RUNNING`, discovery phase greater
  than 3 (ideally READY=8), bounded coherent counters, zero transport errors,
  live SSH and both displays, and no fatal `hv.log` marker.  Failure is phase 3
  unchanged, a later structural rejection, service/devnode failure, hang,
  reboot, or bugcheck.  Evidence paths are the version-2 CLI snapshot,
  `hv.log`, ports 8765/8766, and Windows PnP/service state.

Post-run result (2026-08-24T07:08Z): confirmed.  The user explicitly approved
catalog signer `88DBD41B452CC62D2CAFFB4C64B0094F9000E2DF`; host and Air artifact
hashes matched, and the package installed as `oem12.inf` while `oem11.inf` and
the stable ESP remained available for recovery.  PnP reported `CM_PROB_NONE`,
the AppleInput service remained `RUNNING`, and the actual DriverStore SYS hash
was `580428d9e6623de672d7d1a0da89610aa740f811985ca5447db88a57f4d1fe13`.

Discovery immediately completed through phase 8 (READY).  The bounded header
ring contained the boot marker, 99-byte identity response, three interface-info
responses of 43/41/41 bytes, and keyboard/trackpad HID descriptors of 192/120
bytes.  Four snapshots over eight seconds were identical and coherent:
`interrupts=84`, `workers=2/2`, `spi_transfers=21`, `resets=1`, with every SPI
timeout, packet CRC, message CRC, fragment, offline, keyboard-report, and
trackpad-report error/count still zero.  The final accepted descriptor header
was `type=0x20 report=0x10 device=2 id=0 response_length=512
payload_length=110`, independently confirming that responses do not echo the
outbound request IDs.

SSH remained responsive; physical display and the USB viewer remained alive at
the 2560x1600 B8G8R8X8 contract, and `hv.log` had no reset, exception, watchdog,
or bugcheck marker.  Verdict: the strict incoming-ID gate was the root cause and
commit `6fe3ee32c7238655b2f0860be4e398ce1a0d0d69` fixes it on J313.  Native
GPIO/IRQ/SPI/discovery Gate B is now closed.  `TransportOnly=1` remains
intentional, so this result does not claim a Windows keyboard or Precision
Touchpad child; VHF publication is the next separately testable gate.

### EXP-20260824-047 — descriptor ownership Gate C1 with VHF disabled

Pre-run record (2026-08-24T08:27:44Z).  Hypothesis: on the unchanged EXP-057
four-E-core firmware pair, replacing only confirmed rollback `oem12.inf` with
the software-verified package from root commit
`bb426e00ee683be17fd8872cbce050e8db56a58b` will retain both hardware HID
descriptors in driver-owned storage, produce stable metadata-only version-3
snapshots and keep VHF absent because the package default is
`TransportOnly=1`.

- repository state: root branch `feature/j313-native-input`, documentation head
  `27b4d6ebea3f8e857ed926f945d56c9fda4a9e7e`; implementation head represented
  by the package is `bb426e00ee683be17fd8872cbce050e8db56a58b`; m1n1
  `2fe790beebed32658eae753dee3e6d581df97197`; Mu
  `9501de460353b902dbbd3b7de42c703af811f037`.  All three tracked diff SHA-256
  values are `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- firmware remains the validated EXP-057 `debug-monitor` pair:
  `dist/j313/debug-monitor/m1n1.macho` SHA-256
  `3d41abb1b5b16c09a96c9bebe4244b2e5d88fe084cd786f8289e928920b49a35`
  and `dist/j313/debug-monitor/J313_EFI.fd` SHA-256
  `cd591aab2ef0641902f03e1a38aac697e45fc12e466a3cb72f32cd3d68060710`.
- driver package: GitHub Actions run `32705632141`, job `97366009946`, artifact
  `AppleInput-ARM64-Debug`; SYS SHA-256
  `bc457c288cef25eeb1445305629ffb9f8147b7beaf1d7d258c5cc81a2de6104e`,
  INF `0f74306484403b97b81ad1350488cbed7a1af000b8c7d7e4f793cfe1101fe67d`,
  CAT `2adf691aab8f2252601bb6f55dff4bf15c29f52eefc76de058d49e604f95251c`
  and CLI `2e060e2bb050baf6b2a1ccd889f9245d0a4754417e530de162a83fbe434490b8`.
  Both binaries are PE32+ AArch64.  The catalog signer is
  `2172CED45D605B33C0572C30FF69F74C440734A3`; importing it requires explicit
  approval before installation.
- launch command: `scripts/run-windows.sh --execution assisted --display both
  --debug monitor --observed --foreground --proxy
  <CONSOLE_DEVICE> --vuart <VUART_DEVICE>`.
- install contract: use the package installer without `-PublishKeyboard`, then
  confirm `TransportOnly=1`; `oem12.inf`, external USB input and the unchanged
  stable ESP remain the recovery paths.
- pass gates: phase 8; keyboard descriptor payload length 182 and trackpad
  descriptor payload length 110; stable nonzero SHA-256 values across repeated
  snapshots; valid keyboard contract; VHF state absent; zero VHF submissions
  and failures; no new HID child; zero transport-error counters; responsive
  SSH, physical display, USB viewer and external USB input.
- failure gates: boot regression, phase below 8, changing descriptor digest,
  parser rejection, timeout/CRC/fragment/offline count, any VHF child or
  submission, bugcheck, reboot or loss of SSH/display/external USB recovery.
  Evidence paths are `hv.log`, ports 8765/8766, PnP/service state and repeated
  version-3 `AppleInputDiag.exe` snapshots.

Post-run result (2026-08-24T09:07:53Z): confirmed.  The user explicitly
approved catalog signer `2172CED45D605B33C0572C30FF69F74C440734A3`; all four
files transferred to the Air matched the recorded host hashes.  The package
installed as `oem13.inf` without `-PublishKeyboard`; the live registry value
remained `TransportOnly=1`, `ACPI\APPL0001\0` reported `CM_PROB_NONE`, and the
AppleInput service remained RUNNING.  The active DriverStore SYS path was
`appleinput.inf_arm64_0d1ab3b27eec0e54\AppleInput.sys`, with the expected
SHA-256 `bc457c288cef25eeb1445305629ffb9f8147b7beaf1d7d258c5cc81a2de6104e`.

Four version-3 snapshots over the same live device restart were byte-stable at
phase 8.  They reported keyboard descriptor payload length 182, trackpad length
110, `keyboard_contract_valid=1`, digest status zero, keyboard digest
`5ad48fbaddbae4d5806c4dbc27c842e535e2954cd140e208494cf4f17fbc47c7`
and trackpad digest
`9da960157f983b6494a19ce6fde471191c183bbdf54486d9217be4e800abcfef`.
The bounded discovery header lengths remained 4, 99, 43, 41, 41, 192 and 120.
All snapshots reported interrupts 92, workers 2/2, SPI transfers 21, reset 1,
and zero SPI timeout, packet CRC, message CRC, fragment and offline failures.

The fail-closed publication boundary also passed: VHF state was absent; accepted,
rejected, submitted, start-failure and submission-failure counts were all zero;
and a present-device query found no VHF or Virtual HID child.  SSH remained
responsive, the internal lock screen remained visible, the USB viewer stayed
streaming at the 2560x1600 B8G8R8X8 contract, the recent System event query
contained no critical/error event, and `hv.log` contained no reset, exception,
bugcheck or watchdog marker.  Verdict: fixed descriptor ownership, bounded
keyboard contract parsing, version-3 metadata and the `TransportOnly=1`
fail-closed boundary are hardware validated on J313.  This result does not
validate VHF keyboard creation or report publication; Gate C2 remains separate.

### EXP-20260824-048 — publish the native keyboard through VHF Gate C2

Pre-run record (2026-08-24T09:10:12Z).  Hypothesis: on the live Gate
C1-validated `oem13.inf` package, changing only the AppleInput service parameter
from `TransportOnly=1` to `TransportOnly=0` and restarting only
`ACPI\APPL0001\0` will create one VHF keyboard child and publish descriptor-
validated built-in keyboard reports without disturbing the native transport or
the accepted Windows platform baseline.

- repository state: root `b1ae81a0dc5ea7e4d3775e943b40c20b9b742c2f`,
  m1n1 `2fe790beebed32658eae753dee3e6d581df97197`, Mu
  `9501de460353b902dbbd3b7de42c703af811f037`; all tracked diff SHA-256 values
  remain `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- firmware, package, signer and hashes are exactly those recorded and validated
  in EXP-20260824-047.  Active SYS SHA-256 is
  `bc457c288cef25eeb1445305629ffb9f8147b7beaf1d7d258c5cc81a2de6104e`;
  no binary, INF, catalog, ESP, firmware, topology or CPU change is permitted.
- single changed variable: run the same installer with `-PublishKeyboard`,
  which writes `TransportOnly=0`, then restart only `ACPI\APPL0001\0`.
  Rollback writes `TransportOnly=1` and restarts that same devnode; `oem12.inf`,
  external USB input and the stable ESP remain available.
- immediate pass gates: AppleInput PnP OK and service RUNNING; phase 8;
  keyboard VHF state running; exactly one new VHF/HID keyboard child; unchanged
  descriptor lengths/digests and keyboard contract; zero report rejection,
  start failure, submission failure and transport errors.
- behavioral pass gates: built-in letters, numbers, punctuation, both modifier
  sides, repeat, simultaneous chords, Caps Lock, recognized function-row input
  and complete key release; counters accepted/submitted increase together
  without recording input payloads; input resumes after one devnode restart and
  works at Windows sign-in after one controlled reboot.
- failure gates: any stuck key, rejected report, VHF failure, devnode problem,
  unexpected IRQ/worker/SPI rate, hang, bugcheck, reboot or loss of external
  USB, SSH, display, storage or accepted CPUs.  On any failure immediately set
  `TransportOnly=1`, restart APPL0001 and stop the experiment.

Post-run checkpoint (2026-08-24T09:24:36Z).  The single-variable activation
completed without rollback.  The installer retained `oem13.inf`, wrote
`TransportOnly=0` and restarted only `ACPI\APPL0001\0`.  Windows reported the
parent as `OK / CM_PROB_NONE` and created one VHF device with keyboard,
consumer-control and vendor-defined HID collections, all `OK`.

The user then used the built-in keyboard to enter the live Windows session.
The version-3 snapshot after that activity recorded phase 8, VHF state 3
(`Running`), six native keyboard reports, six accepted reports and six
submitted reports.  Rejected reports, VHF start failures, VHF submission
failures, SPI timeouts, packet/message CRC failures, fragment failures and the
offline flag all remained zero.  Descriptor lengths, descriptor digests and
the validated keyboard report contract remained identical to Gate C1.

One subsequent `pnputil /restart-device ACPI\APPL0001\0` completed
successfully.  The parent returned `OK / CM_PROB_NONE`; the same VHF and HID
children reappeared `OK`; and a fresh diagnostic instance again reached phase
8 with VHF state 3 and zero failure counters.  There were no recent critical
or error System events and no fatal marker in the tail of `hv.log`.

Verdict: keyboard publication, sign-in input, report delivery and VHF/PnP
recreation are validated.  Physical typing after the devnode restart was not
performed because the user was no longer beside the machine, and controlled
reboot input plus the bounded 30-minute mixed-input run remain open.  Gate C2
therefore remains a successful partial checkpoint rather than a completed
stability gate.  `TransportOnly=0` remains active; the documented
`TransportOnly=1` rollback and external USB input remain available.

### EXP-20260824-049 — bounded J313 trackpad report capture Gate D1

Pre-run record (2026-08-24T11:11:38Z). Hypothesis: replacing only the live
Gate-C2 `oem13.inf` driver with the isolated capture build from GitHub Actions
run `32714036047` will preserve the validated Apple SPI transport and keyboard
VHF path while allowing at most 16 CRC-validated device-2 reports to be saved
for one explicitly controlled physical gesture at a time.

- repository state: root branch `feature/j313-native-input` at
  `86a3f4390bca95bb0a33d528f98fee3bf5c551f8`, m1n1
  `2fe790beebed32658eae753dee3e6d581df97197`, Mu
  `9501de460353b902dbbd3b7de42c703af811f037`; all three tracked diff
  SHA-256 values are
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- firmware and launch contract remain the accepted EXP-057/EXP-047 pair; no
  ESP, m1n1, Mu, CPU, display, storage or USB change is permitted.
- capture artifact: workflow run `32714036047`, job `97391400734`, artifact
  `AppleInput-Trackpad-Capture-ARM64-Debug`; INF SHA-256
  `208925e026f0f4359f4d53daa2b8f98b87837f7046944356632975c12acaee43`,
  unsigned catalog SHA-256
  `15c6907228db00fa213db4c09b4e3d45cb6041a5a4cf65228409a68bd2265aa6`,
  ARM64 SYS
  `58b24722b68fdb9e5a875c04602c8322efde3cc015a6ad108144cc2a2d1aa780`
  and ARM64 CLI
  `54de5d2959c000eb62c29858029e0822909841981c41d6db055211a20b9317ac`.
  The package is staged, not installed, at
  `C:\Users\pavel\AppleInputTrackpadCapture`; host and Air binary hashes match.
- signing contract: extract and import only catalog signer
  `1DF96731DC3D8DECD712F828B11616C384CBD83A` from the exact recorded catalog;
  Windows test-signing is already enabled. Installation is
  `pnputil /add-driver AppleInputCapture.inf /install`, followed by a query of
  the active published INF, service, PnP tree and capture interface.
- recovery: active `oem13.inf` remains in DriverStore with validated SYS hash
  `bc457c288cef25eeb1445305629ffb9f8147b7beaf1d7d258c5cc81a2de6104e`;
  setting `TransportOnly=1` and restarting `ACPI\APPL0001\0` disables VHF, and
  `pnputil /add-driver` against the preserved oem13 package restores the
  validated driver. External USB input and SSH remain mandatory recovery paths.
- single physical variable per capture: no contact, stationary one finger,
  X-only motion, Y-only motion, physical click, then two contacts. Each raw blob
  is stored only under ignored local evidence and must have the exact trackpad
  descriptor digest from EXP-047, the requested report count, and zero drops.
- immediate pass gates: APPL0001 PnP OK, AppleInput service RUNNING, phase 8,
  keyboard VHF Running, SSH and external USB alive, capture interface present,
  and zero timeout/CRC/fragment/offline/VHF failures. Any mismatch, hang,
  bugcheck, reboot, lost keyboard, lost SSH or dropped report triggers rollback
  before gesture collection.

Post-run result (2026-08-24T14:02:00Z): superseded.  The capture package was
installed as `oem14.inf` with the exact recorded SYS hash and the explicitly
approved catalog signer
`1DF96731DC3D8DECD712F828B11616C384CBD83A`.  The built-in keyboard remained
functional.  Two separate stationary-one-finger attempts both included an
accidental physical click, but that physical difference did not alter the
captured data: each 8320-byte blob contained eight identical 8-byte device-2
reports, `02 00 00 00 00 00 00 01`, and both files had SHA-256
`2997b4b31206f4c008764fa0b0ec43cebbdc7cbc9d61d429e903c37dbd195c7f`.
The ignored evidence paths are
`.local/apple-input/trackpad-captures/EXP-20260824-049/00-rejected-stationary-plus-strong-click.bin`
and
`.local/apple-input/trackpad-captures/EXP-20260824-049/02-stationary-one-finger.bin`.

The exact repetition proves that another gesture retry cannot produce the
missing coordinate frames under this transport state.  Source review found the
violated initialization contract in upstream Linux
`drivers/input/keyboard/applespi.c`: after descriptor discovery the host sends
the Trackpad Info request (`0x1020`) followed by the multitouch-init request
(`0x0252`, command `0x0102`), and the source explicitly records that the latter
is required for pointer movement.  The current Windows transport transitioned
directly from descriptor discovery to READY and sent neither command.  Current
m1n1 and Mu do not own this post-discovery Apple SPI HID command sequence; the
Windows function driver does.  Official KMDF timer and wait-lock documentation
was also checked before designing the Windows retry path: both the passive
interrupt worker and a passive one-shot timer can share one wait lock, while a
waited timer stop must occur before acquiring that lock during teardown.

Verdict: the bounded capture mechanism works, but Gate D1 cannot collect
coordinate evidence until the owner-layer initialization sequence is present.
The next experiment must change only that sequence, retain the capture-only
frontend and exact rollback package, and require INFO then MULTITOUCH response
completion before asking the user for another gesture.  No Precision Touchpad
translation or mouse emulation is justified by this result.

### EXP-20260824-050 — initialize J313 multitouch before coordinate capture

Pre-run record (2026-08-24T11:57:49Z).  Hypothesis: replacing only the live
EXP-049 capture driver with the `ca105432` capture build will send the missing
Trackpad Info and multitouch-init commands after the already validated
descriptor discovery, reach trackpad-init READY in exactly two successful
attempts, preserve keyboard VHF, and cause a stationary contact to generate at
least one device-2 report longer than the repeated 8-byte click-only report.

- repository state: root branch `feature/j313-native-input` at
  `84a98bc1f749e620de31a1d53c4641e1929d89f4`; implementation commit
  `ca105432a811e5eaee08a90b8b24a16f900fed28`; m1n1
  `2fe790beebed32658eae753dee3e6d581df97197`; Mu
  `9501de460353b902dbbd3b7de42c703af811f037`.  All three tracked diff
  SHA-256 values are
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- inspected owner contracts: upstream Linux
  `drivers/input/keyboard/applespi.c` for the observable INFO then MT-init
  sequence; current m1n1 and Mu input ownership; current Windows transport and
  discovery; official Microsoft `WdfTimerCreate`, `WDF_TIMER_CONFIG`,
  `WdfTimerStop` and `WdfWaitLockAcquire` documentation.  Initialization and
  retry belong to the Windows function driver; m1n1 owns guest hardware access,
  Mu exposes ACPI resources, and VHF owns only the Windows HID frontend.
- software verification: exact request bytes and both CRCs plus the portable
  INFO-to-MULTITOUCH state/retry sequence are regression tested.  Protocol and
  package suites pass 28/28; the complete public `proxyenv` suite passes
  290/290; `git diff --check` passes.  GitHub Actions production run
  `32724127630` job `97421554913` and workflow-dispatch run `32724166740`
  jobs `97421675750` and `97421676068` all completed successfully with the
  official ARM64 WDK.
- capture artifact: `AppleInput-Trackpad-Capture-ARM64-Debug`, artifact ID
  `9518923751`, staged only under ignored
  `.local/apple-input/mt-init-run-32724166740`.  INF SHA-256
  `82a2659d4431c7c8320b0decd4a4318b0b9dc3da91425ee2944e82c547f1238c`,
  catalog `e5ccb5795ab3fd73cc699f739cbd266d21323700f97dd0774feb63e1e209b068`,
  AArch64 SYS
  `15c96c26aa929aebda16996dec3e72f79bc911ce8e224da3de88fdac903dd0f6`
  and AArch64 capture CLI
  `ff997f42c029c88af88d5ed4345e44765ff70ca62e7c92a57b4938908442d495`.
  Catalog signer SHA-1 is
  `8BFD8A2FB301F1909BF21446F2E9FB7E71C1E2CD`; it differs from the currently
  trusted signer and must not be imported without explicit approval.
- single changed variable: replace the current capture SYS with the exact new
  package.  Firmware, ESP, Windows image, CPU topology, display, NVMe, USB,
  descriptor discovery, keyboard VHF, capture format and physical gesture are
  unchanged.  The install removes only the current capture OEM INF if Windows
  refuses an equal-version replacement, imports only the explicitly approved
  exact catalog signer, adds the recorded INF with `pnputil /install`, and
  verifies the active DriverStore SYS hash before any contact.
- recovery: the previous EXP-049 package remains preserved at
  `C:\Users\pavel\AppleInputTrackpadCapture` with SYS SHA-256
  `58b24722b68fdb9e5a875c04602c8322efde3cc015a6ad108144cc2a2d1aa780`;
  validated production `oem13.inf`, external USB input and the stable ESP are
  secondary rollback paths.  Remove the new signer after restoring the old
  package.
- immediate pass gate: APPL0001 PnP OK; AppleInput RUNNING; discovery phase 8;
  `trackpad_init_phase=3`, retries 0 and attempts 2; keyboard VHF Running;
  unchanged descriptor lengths/digests; zero timeout, CRC, fragment, offline
  or VHF errors; SSH or external USB and physical display remain alive.
- physical pass gate: one stationary contact produces at least one report
  longer than 8 bytes while the descriptor digest remains
  `9da960157f983b6494a19ce6fde471191c183bbdf54486d9217be4e800abcfef`.
  Any init phase 4, more than two attempts, transport error, missing keyboard,
  hang, bugcheck, reboot or hash mismatch triggers immediate rollback without
  collecting further gestures.

Pre-run correction (2026-08-24T12:05:00Z).  The first recorded artifact from
run `32724166740` was rejected before transfer or installation: its capture
INF still advertised `0.1.1.0`, equal to live `oem14`, so Windows driver
selection could retain the old SYS and invalidate the experiment.  Commit
`c07743a16b2003a58389df53a339ab91c957bf2a` changes only capture `DriverVer`
to `0.1.2.0`; commit
`ff87b40e7aba654b78de12f55a5adff21b4e44f5` indexes that correction.  No
runtime source changed after `ca105432`.

The only installable artifact for EXP-050 is now workflow-dispatch run
`32724933170`, production job `97423982004`, capture job `97423982301`,
artifact `AppleInput-Trackpad-Capture-ARM64-Debug` ID `9519185291`.  Both jobs
passed the official ARM64 WDK.  The ignored staging path is
`.local/apple-input/mt-init-v012-run-32724933170`; INF SHA-256 is
`9ef28a7a70d86d6cc5c5fa5584fbdb51e1afe432319d3bf177bd611bd897663c`,
catalog `46e60354ddd6f78ff985e4ee16e3d6b257c502792df1a333b177e68553507e37`,
AArch64 SYS
`65a3d0c4e169abb411712e18658405322a96b2b5dcba85966a53ffa5d16f1ef1`
and AArch64 capture CLI
`68a4db63c816c6c6a5fece3f7aefc256af46fd3ddbeaea769f96255ac8ae51ee`.
Its exact catalog signer SHA-1 is
`09E7FBD3BF02971B4B21CF56A8C5A9CCB528B97F`; this supersedes the signer and
all hashes in the original pre-run paragraph and still requires explicit user
approval before import.  The higher version allows side-by-side staging and
selection without deleting the `oem14` rollback first.

The matching metadata-only `AppleInputDiag.exe` from production artifact ID
`9519183501` is AArch64 with SHA-256
`72438a90074f033d37045e9d4d8c3096aad35ac5ef661f5f078430ba33a4be50`;
it is staged under ignored
`.local/apple-input/mt-init-v012-production-run-32724933170` and is the only
diagnostic CLI permitted for the new version-3 init fields in this experiment.

Post-run checkpoint (2026-08-24T14:19:00Z).  The exact versioned capture
package was installed as `oem15.inf` after the user explicitly approved its
catalog signer.  The installer reported a false negative only because Windows
rendered `DriverVer=0.1.2.0` as `12.3.59.626`; read-only verification proved
that the selected service binary is the new DriverStore copy with SHA-256
`65a3d0c4e169abb411712e18658405322a96b2b5dcba85966a53ffa5d16f1ef1`.
`ACPI\\APPL0001\\0` remained `OK`, AppleInput remained `RUNNING`, and the
previous `oem14` binary remained present as the rollback package.

The immediate gate passed exactly: discovery phase 8, trackpad-init phase 3,
zero retries, two attempts, keyboard VHF state 3, unchanged descriptor lengths
and digests, and zero SPI timeout, packet CRC, message CRC, fragment, offline,
VHF start or VHF submission failures.  The INFO completion was observed before
the MT-init completion; the latter returned message type `0x0052`, report ID 2,
command ID 1, response length 2 and payload 0.

The first controlled one-finger motion capture is preserved only under ignored
evidence at
`.local/apple-input/trackpad-captures/EXP-20260824-050/03-one-finger-motion.bin`.
It is 8320 bytes with SHA-256
`31b3ab8c14182813a86d81ee2fabd1fc9347edbcfdaa51ba1e9f141d9cc35a9a`,
descriptor digest
`9da960157f983b6494a19ce6fde471191c183bbdf54486d9217be4e800abcfef`,
eight requested reports, zero drops and eight 76-byte device-2 multitouch
frames.  This is a strict behavioral change from EXP-049's repeated 8-byte
service report and proves that the upstream INFO then MT-init contract enables
the coordinate stream.

Verdict: Gate D1 passes.  The transport initialization defect is closed; the
next bounded work is controlled field mapping for X, Y, contact count and
physical click, followed by a separately tested Windows Precision Touchpad
frontend.  This result does not yet claim Precision Touchpad publication.

Controlled-delta completion (2026-08-24T14:31:00Z).  Four additional bounded
captures completed with the same descriptor digest, eight requested reports,
zero drops and no transport error:

- X-only motion:
  `.local/apple-input/trackpad-captures/EXP-20260824-050/04-x-only.bin`,
  SHA-256
  `13f8a744f35f8261f15c0c0bd74772cb26f222a3e6fd5d9ea14022a5029d29cf`,
  eight 76-byte one-contact frames.  Across the recorded sequence absolute X
  changed from -624 to 830 while absolute Y remained within 4901..4950.
- Y-only motion:
  `.local/apple-input/trackpad-captures/EXP-20260824-050/05-y-only.bin`,
  SHA-256
  `a1de99cefc19c825eff5c3a25895742966105521ae3edef9f0710258d302a257`,
  eight 76-byte one-contact frames.  This physically independent capture
  preserves the separately decoded X and Y field positions.
- two contacts:
  `.local/apple-input/trackpad-captures/EXP-20260824-050/07-two-finger.bin`,
  SHA-256
  `aac25aec4094ef3037691bb876210d625888b5000d19546b9ddcc746d39d25f3`.
  Contact count changed from one to two and frame length increased from 76 to
  106 bytes, exactly one additional 30-byte Apple finger record.
- held physical click:
  `.local/apple-input/trackpad-captures/EXP-20260824-050/08-held-physical-click.bin`,
  SHA-256
  `ebeecc64a0305555dab17c3a0ff98250b358f0d3a170ac1faef14800d59485fb`,
  eight 76-byte one-contact frames.  Both independently reported click bytes
  were one in all eight frames; both were zero in every X-only and Y-only
  frame.

The earlier file
`.local/apple-input/trackpad-captures/EXP-20260824-050/06-physical-click.bin`
with SHA-256
`14a455ad0d28cc7f3aa1a18fbebe0d188f8b3982d6e2ba78cc52be3a6495744d`
is explicitly rejected as click evidence: the fixed eight-report window filled
after initial contact but before the user completed the physical press, so both
click bytes remained zero.  Repeating while the click was already held removed
that timing ambiguity.  A no-contact attempt correctly timed out without
creating a partial file.

The observed layout matches the primary upstream Linux `applespi` contract:
the payload begins with the 48-byte touchpad header; byte 1 is `clicked`, byte
30 is contact count and byte 31 is the duplicate click state; each contact is a
30-byte little-endian `tp_finger`.  The validated message decoder removes the
final two-byte message CRC, so a one-contact captured payload is 48 + 28 = 76
bytes and a two-contact payload is 48 + 30 + 28 = 106 bytes.  Controlled X/Y,
click and contact-count deltas independently validate the fields required for
the next parser; no confidence, palm or Windows gesture semantics are inferred
from these captures.

### EXP-20260824-051 — capture the J313 contact-release wire shape

Pre-run record (2026-08-24T12:56:29Z). Hypothesis: the already validated
`0.1.2.0` capture package will record at least one 76-byte one-contact frame
followed by the exact device-2 contact-release representation when a held
single finger is lifted inside one bounded capture. The only changed variable
is the physical transition from one contact to no contact; firmware, ESP,
Windows image, driver, descriptor, capture ABI and publication gates remain
unchanged.

- repository: `paulsmir/windows-on-m1`, branch
  `feature/j313-native-input`, root
  `a50eec9b40c1a673e31eb171e630433833309368`, m1n1
  `2fe790beebed32658eae753dee3e6d581df97197`, Mu
  `9501de460353b902dbbd3b7de42c703af811f037`; all three tracked diff
  SHA-256 values are
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- source contracts: EXP-20260824-050 and the current bounded capture source;
  upstream Linux `drivers/input/keyboard/applespi.c` for the 48-byte header and
  30-byte finger layout; the accepted Precision Touchpad design and
  implementation plan for the requirement to emit an explicit Windows
  tip-clear release.
- active hardware state: `ACPI\APPL0001\0` Started with best-ranked
  `oem15.inf`; service `AppleInput` RUNNING; DriverStore SYS SHA-256
  `65a3d0c4e169abb411712e18658405322a96b2b5dcba85966a53ffa5d16f1ef1`;
  capture CLI SHA-256
  `68a4db63c816c6c6a5fece3f7aefc256af46fd3ddbeaea769f96255ac8ae51ee`.
  The artifact is workflow run `32724933170`, capture job `97423982301`,
  artifact ID `9519185291`; INF/catalog hashes remain
  `9ef28a7a70d86d6cc5c5fa5584fbdb51e1afe432319d3bf177bd611bd897663c`
  and
  `46e60354ddd6f78ff985e4ee16e3d6b257c502792df1a333b177e68553507e37`.
- exact run: from the existing SSH administrator session run
  `AppleInputCapture.exe capture --count 16 --output C:\Users\pavel\j313-release-transition.bin --timeout 60`
  while one finger is already held, then lift immediately after arming. Copy
  the result to ignored
  `.local/apple-input/trackpad-captures/EXP-20260824-051/09-release-transition.bin`.
- pass: zero drops; descriptor digest
  `9da960157f983b6494a19ce6fde471191c183bbdf54486d9217be4e800abcfef`;
  at least one proven one-contact frame followed by an exact zero-contact or
  tip-clear release shape. Fail: timeout, partial file, digest mismatch,
  transport error, reboot, bugcheck or no release transition.
- recovery: no install occurs. On capture failure cancel the IOCTL and delete
  only the new incomplete output. `oem14.inf` and production `oem13.inf` remain
  the recorded driver rollback paths; external USB and SSH remain available.

Post-run attempt 1 (2026-08-24T13:00:00Z): inconclusive and rejected before
fixture creation. The bounded tool saved 16 reports with zero drops, the
expected descriptor digest and local SHA-256
`5e5c576e298c679095523d8f43457301b8ca48a9f1e3ffb8be36124d743db93d`,
but the user reported that the requested initial held contact/release action
was not performed in time. All 16 records were 76-byte `count=1` frames, so
the file cannot establish release behavior. It remains ignored as
`09-rejected-uncontrolled-transition.bin`; no code, driver or hardware state
changed. Repeat only after an explicit `держу` confirmation, using a new
CREATE_NEW output path.

Repeat pre-run (2026-08-24T13:02:00Z): the user explicitly confirmed that one
finger is already held. Artifact, hashes, driver, limits, pass/fail criteria
and recovery are unchanged. The only corrected procedural variable is timing;
the new non-overwriting output is
`C:\Users\pavel\j313-release-transition-2.bin`, copied locally as
`10-release-transition.bin` only if the capture completes.

Post-run attempt 2 (2026-08-24T13:04:00Z): rejected as release evidence but
diagnostic root cause confirmed. With the finger already held, all 16 slots
filled in less than the 250 ms SSH observation interval, before the user could
receive an `отпускайте` instruction. The ignored file is
`10-rejected-window-filled-before-release.bin`, SHA-256
`46561b3f2daa8dd7afcc9cada4b48c2bc5742b98c5e725618e25a4feec8be875`;
it has the expected descriptor digest, zero drops and only active 76-byte
one-contact frames. This behavior is reproducible and proves that a fixed
16-report window cannot capture a human-triggered release at the live report
rate.

Two metadata-only v3 snapshots taken after the user lifted were identical:
`trackpad_reports=27509`, `interrupts=872179`, `workers=26166/26166`, last
message device 2 with payload length 76, and zero SPI timeout, packet CRC,
message CRC, fragment or offline errors. The stopped counters prove quiescence,
but the privacy-safe header cannot expose whether the retained one-contact
payload has zero `touch_major`. Upstream Linux explicitly skips contacts whose
`touch_major` is zero before `input_mt_sync_frame`, so both a 46-byte
zero-contact payload and a 76-byte one-contact/zero-`touch_major` payload are
valid release candidates.

Verdict: the physical hypothesis remains unresolved, while the workflow
hypothesis is confirmed: count-complete capture is the wrong trigger. The next
single change is a diagnostic-only ABI v2 predicate that ignores active frames
and captures the first structurally valid zero-contact or zero-`touch_major`
release candidate. Production AppleInput, firmware, ESP and the live Air remain
unchanged; `oem15.inf` is the rollback before installing any rebuilt capture
package.

Release-trigger continuation pre-run (2026-08-24T13:28:00Z). Hypothesis: an
isolated ABI-v2 capture package that ignores active coordinate frames and arms
for exactly one structurally valid release candidate will record the physical
J313 contact-release representation without a human-timing race. The only
runtime change is the diagnostic capture package; production AppleInput, m1n1,
Mu, ESP, CPU topology, display, NVMe, USB and the physical gesture remain
unchanged.

- repository: root `8d46ac420550dba7b143f0c8737bdb57b63268f3`, m1n1
  `2fe790beebed32658eae753dee3e6d581df97197`, Mu
  `9501de460353b902dbbd3b7de42c703af811f037`; all three tracked diff
  SHA-256 values are
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- software verification: release-classifier tests cover active, count-zero,
  zero-`touch_major`, mixed, malformed-length, excessive-count and null input;
  the complete public suite passes 291/291, ASan/UBSan passes and
  `git diff --check` passes. The first WDK run `32731783429`, capture job
  `97445397225`, correctly rejected a user-mode CRT include in the kernel
  header; no artifact was installed. Kernel-safe correction
  `033fb431c430aadc7f3bad2d5514db795076b009` then passed workflow-dispatch run
  `32732378158`, production job `97447288708` and capture job `97447289066`.
- exact artifact: `AppleInput-Trackpad-Capture-ARM64-Debug`, artifact ID
  `9521969603`, ignored staging path
  `.local/apple-input/wdk-32732378158`. INF SHA-256
  `c50718b453c2c5dd3512e43be770c8660c5ef12a6344c6d7b109ecbb1c722eec`,
  catalog `1108938598dd17333df31c15c0f54aaa36b3641902fd2d4d0df88edac02d60ea`,
  AArch64 SYS
  `4ba2468ecf3194130c135ef1ddc2376ababe2cae438e5f6128bd6d9f03f6c873`
  and AArch64 CLI
  `c6666e2403c199814658cc991318ca8a9772c5a7b53a71b659fe708f5087fc85`.
  The exact catalog signer SHA-1 is
  `550C27C7CEB41FDCA2AE3F94E14132691AD820FE`; extracted public certificate
  SHA-256 is
  `7fbc47adeb20fd89c9183c2c0276f717fa6111051029dc8ac9f4acb9bd162de1`.
- live baseline and rollback: `oem15.inf`, service `AppleInput` RUNNING,
  DriverStore SYS SHA-256
  `65a3d0c4e169abb411712e18658405322a96b2b5dcba85966a53ffa5d16f1ef1`;
  the complete EXP-050 package remains preserved. Install may add the exact
  signer and higher-version package but must not delete `oem15`; any hash,
  PnP, discovery, keyboard, transport, reboot or bugcheck failure restores
  `oem15` before further capture.
- exact physical run: hold one finger stationary, invoke
  `AppleInputCapture.exe capture-release --output C:\\Users\\pavel\\j313-release-trigger.bin --timeout 60`,
  then lift once the tool reports it is armed. Pass requires one report, zero
  drops, descriptor digest
  `9da960157f983b6494a19ce6fde471191c183bbdf54486d9217be4e800abcfef`
  and either a 46-byte count-zero payload or a valid payload containing a
  zero-`touch_major` contact. The raw blob stays ignored; only a reviewed
  minimal sanitized fixture may enter the repository.

Release-trigger installation checkpoint (2026-08-24T13:51:44Z). After the
user explicitly approved installation of the exact test kernel driver and its
catalog signer, the hash-gated installer published the package as `oem16.inf`
and restarted only `ACPI\\APPL0001\\0`. The device returned `OK`, service
`AppleInput` returned `Running`, and the selected DriverStore SYS SHA-256 is
exactly
`4ba2468ecf3194130c135ef1ddc2376ababe2cae438e5f6128bd6d9f03f6c873`.
The active descriptor digest remains
`9da960157f983b6494a19ce6fde471191c183bbdf54486d9217be4e800abcfef`,
discovery phase is 8, trackpad-init phase is 3 and init attempts are 2. The
previous `oem15.inf` package was not deleted and remains the immediate
rollback. No raw capture has been armed yet; the physical release gate remains
open.

Release-trigger post-run (2026-08-24T13:58:55Z): passed. With one stationary
contact already held, the ABI-v2 CLI armed for one RELEASE record. The user
lifted once after the armed instruction and the tool saved exactly one report
with the expected descriptor digest. The ignored raw blob is
`.local/apple-input/trackpad-captures/EXP-20260824-051/11-release-trigger.bin`,
8324 bytes, SHA-256
`19eb38118c455d55096fd448b426895037ccf621141c2ec62a32abc287492b80`.

The capture header is version 2, size 8324, armed 0, complete 1, report limit
1, report-size limit 512, report count 1, dropped count 0 and trigger 1. The
single payload is 76 bytes with contact count one and little-endian
`touch_major` zero at contact offset 16. This is the physical tip-clear release
shape required by the primary upstream Linux `applespi` rule that skips a
contact when `touch_major == 0` before synchronizing the multitouch frame.

The metadata-only post-capture snapshot is ignored as
`11-post-release-status.json`, SHA-256
`eaa8b78f3f15b0501343d0a9f2a9916b41dbccbde9d447ef64b5f566cea70dce`.
It records phase 8, trackpad-init phase 3, two init attempts, keyboard VHF
state 3, 3357 trackpad reports, matched workers 3191/3191 and zero SPI timeout,
packet CRC, message CRC, fragment, offline or VHF errors.

Only the proven 76-byte shape, contact count and zero `touch_major` condition
were retained in
`drivers/apple-input/protocol/tests/fixtures/j313_trackpad_release_sanitized.h`;
timestamp, coordinates, identity and all unrelated fields were zeroed. The
fixture SHA-256 is
`a0eb96c8b4b9961352287176a75e2ff284d1f0339e0e0e3645b0539a554f154d`.
Its test first failed because the fixture was absent; after sanitization the
focused protocol suite, complete 291-test suite, ASan/UBSan run and
`git diff --check` all passed.

Cleanup also passed. Temporary `oem16.inf` was uninstalled and deleted, only
`APPL0001` was restarted, and the exact temporary signer was removed from Root
and TrustedPublisher. The selected package returned to preserved `oem15.inf`;
APPL0001 is `OK`, AppleInput is `Running`, active SYS SHA-256 is again
`65a3d0c4e169abb411712e18658405322a96b2b5dcba85966a53ffa5d16f1ef1`,
descriptor digest is unchanged, phase is 8, MT-init phase is 3, keyboard VHF
state is 3 and transport error counters remain zero.

Verdict: Gate D1 release evidence passes and Task 1 closes. A J313 release can
arrive as a 76-byte one-contact payload whose `touch_major` is zero; the next
bounded task is native descriptor axis metadata parsing. This result does not
publish a Precision Touchpad or infer palm, pressure or gesture semantics.

### EXP-20260824-052 — publish the J313 Precision Touchpad Gate D2

Pre-run record (2026-08-24T17:25:00Z). Hypothesis: the Task 7 production
package can first replace only the driver while preserving the working
keyboard and native axis metadata with `PublishTrackpad=0`; enabling only the
independent trackpad gate afterward will publish a Windows Precision Touchpad
without transport errors or loss of the keyboard. No ESP, firmware, CPU,
storage, USB or display artifact is changed.

- source: root `8afbcf4e6c227dc169b3b95b6702176e3bf5c07e`, m1n1
  `2fe790beebed32658eae753dee3e6d581df97197`, Mu
  `9501de460353b902dbbd3b7de42c703af811f037`; all three tracked diff
  SHA-256 values are the empty-diff hash
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- exact build: workflow-dispatch run `32743605323`; both production and
  explicit capture ARM64 WDK jobs passed. The production INF SHA-256 is
  `caf8a0190369ab158bbe8465ef6596dd630c0c84ad3fec3d13b977bb91734313`,
  catalog `e6de47275954d6b813032626f6ec9fcdffecc687d9fcae0fa6436ac08ecf66ec`,
  SYS `d5db2fceb32bcb189228cf44d935352dcfad9b14396eb59a43c8b561d205c8d0`
  and diagnostic CLI
  `020318609882e4caf7d12bf3cf15aae83c081166bd4a3014c09d34b691a0d24f`.
  Catalog signer SHA-1 is
  `F17DB51F17AB079C7E20618F8C0CE4A24E795FD9`; exported public certificate
  SHA-256 is
  `111324c2234fcbdca10b73c119330904ce827b530add8b2ddfcd682af8ab683c`.
- accepted platform baseline remains the EXP-057/060 four-E-core firmware
  pair: `J313_EFI.fd` SHA-256
  `cd591aab2ef0641902f03e1a38aac697e45fc12e466a3cb72f32cd3d68060710`
  and packaged `boot.bin` SHA-256
  `61fef2d71f9f4b46dc787d1db56a2749d22d055bc5e15e0d5c1f6767aa60c58a`.
  This experiment does not write or remount the ESP.
- live rollback baseline: `ACPI\\APPL0001\\0` is Started on preserved
  `oem15.inf`; service `AppleInput` is RUNNING; active capture SYS SHA-256 is
  `65a3d0c4e169abb411712e18658405322a96b2b5dcba85966a53ffa5d16f1ef1`.
  Diagnostic ABI v3 reports discovery phase 8, MT-init phase 3, two attempts,
  keyboard VHF state 3, descriptor digests
  `5ad48fbaddbae4d5806c4dbc27c842e535e2954cd140e208494cf4f17fbc47c7`
  and
  `9da960157f983b6494a19ce6fde471191c183bbdf54486d9217be4e800abcfef`,
  matched 138/138 workers and zero SPI timeout, CRC, fragment, offline or VHF
  errors.
- first changed variable: trust only the exact new public certificate, stage
  and select the higher-version production INF, then set
  `TransportOnly=0`, `PublishKeyboard=1`, `PublishTrackpad=0` before restarting
  only `ACPI\\APPL0001\\0`. Precision Touchpad publication is forbidden until
  APPL0001, service, ABI-v4 axis metadata, descriptor digest, keyboard and all
  transport error gates pass.
- immediate recovery: set `PublishTrackpad=0`; if the new package or keyboard
  gate fails, uninstall only its newly reported `oemNN.inf`, force-select the
  preserved rollback with `pnputil /add-driver
  C:\\Windows\\INF\\oem15.inf /install`, restart only APPL0001 and remove only
  certificate thumbprint `F17DB51F17AB079C7E20618F8C0CE4A24E795FD9` from
  LocalMachine Root and TrustedPublisher. External USB and SSH remain the
  control paths.

Transport-only/keyboard checkpoint (2026-08-24T17:31:00Z): rejected before
trackpad publication, with rollback complete. The exact candidate installed as
`oem16.inf`; APPL0001 was Started, AppleInput was RUNNING, discovery reached
phase 8, MT init reached phase 3 in two attempts, both descriptor digests were
unchanged, keyboard VHF state was 3 and every transport/VHF error counter was
zero. However ABI v4 reported both `trackpad_axis_x_valid=0` and
`trackpad_axis_y_valid=0`, so the mandatory native-axis contract failed. The
trackpad VHF remained Absent, no trackpad report was submitted and
`PublishTrackpad` was never enabled.

The rejected `oem16.inf` was uninstalled and deleted, only APPL0001 was
rescanned, and the exact new signer was removed from Root and
TrustedPublisher. Windows selected preserved `oem15.inf`; APPL0001 is Started
and AppleInput is RUNNING. This is a clean fail-closed result: no Precision
Touchpad child existed at any point. The next investigation must inspect the
already owned 110-byte native descriptor in the explicit capture package and
compare its collection/axis shape with the parser; changing or hard-coding an
axis transform before that evidence is forbidden.

Descriptor-capture pre-run continuation (2026-08-24T18:02:00Z). Root commit
`1df021587ae453618ab18e89d54dbcbad6ddc6e3` adds only a bounded test-package
IOCTL for the already owned native descriptor; production remains capture-free.
Workflow-dispatch run `32745878677` passed both ARM64 WDK jobs. The exact
capture INF SHA-256 is
`d2c1dcd68f2c4eb1a58bafe59d8242e66f4cfce51309d5e9b1596ded8ab327e1`,
SYS `0ca5ab2543e9ecc611ffea3b5e23e8e108dfaa208f800d9d92996a6e3b72be06`,
catalog `8565c7b1641e4277a8dc5c2bbdaafe1b8749892d278d97491757f04acd702eb1`
and descriptor CLI
`44170927babd305b9b591256203f75f172ebaca291d30912dcd2ae30ebfee4c4`.
The extracted public test certificate SHA-256 is
`1eecf966bf311f50eb8868a2648c850f79e870a89e0ec3078664503a6cde114a`
and signer SHA-1 is `355AC2033CC1130087F1E8B9E28171B71841AAF0`.

The Air reports APPL0001 `OK` on preserved `oem15.inf`; no ESP, firmware,
display, CPU, storage or USB artifact is changed. The single changed variable
is the higher-version explicit capture package with `TransportOnly=0`,
`PublishKeyboard=1` and `PublishTrackpad=0`. It may write only the native HID
descriptor to ignored `.local` evidence. On any hash, PnP, service, keyboard,
transport or capture mismatch, publication remains off and recovery restores
`oem15.inf`, restarts only APPL0001 and removes only signer
`355AC2033CC1130087F1E8B9E28171B71841AAF0` from Root and TrustedPublisher.

Descriptor-capture post-run (2026-08-24T18:24:00Z). The exact capture package
installed temporarily as `oem16.inf` with `PublishTrackpad=0`. It returned the
already owned 110-byte J313 trackpad descriptor at
`.local/apple-input/trackpad-captures/EXP-20260824-052/j313-trackpad-descriptor.bin`.
The captured length is 110 and SHA-256 is
`9da960157f983b6494a19ce6fde471191c183bbdf54486d9217be4e800abcfef`,
exactly matching the discovery-time digest. The descriptor contains a standard
relative Mouse application with X/Y, a Touch Pad application containing only
vendor report `0x3f`, and a second vendor application containing report `0x44`.
It contains no absolute multitouch logical range, physical range, unit or unit
exponent, so `trackpad_axis_x_valid=0` and `trackpad_axis_y_valid=0` were the
correct fail-closed result rather than a parser defect.

Source comparison identifies the violated contract. Current Asahi SPI-HID sends
device 2, request type `0x32`, report `0xd9`, device byte 0 and response length
32 for `HID_REQ_GET_REPORT`; `hid-magicmouse` parses the returned width and
height in hundredths of a millimetre plus signed little-endian minimum and
maximum X/Y values. The current AppleInput INFO phase instead repeats the
descriptor-discovery request (`d0/20/10/02`) and discards its payload. Microsoft
requires logical and physical ranges plus unit and exponent for Precision
Touchpad X/Y; its mandatory sample represents the physical extents as
hundredths of an inch. The next single-variable correction is therefore to
replace INFO with the native `0xd9` dimensions exchange and derive the Windows
axis contract from that validated response. No hard-coded J313 geometry is
permitted.

Cleanup passed. `oem16.inf` and only its signer were removed; preserved
`oem15.inf` is again selected, APPL0001 is `OK`, AppleInput is Running and the
active SYS SHA-256 is
`65a3d0c4e169abb411712e18658405322a96b2b5dcba85966a53ffa5d16f1ef1`.
Verdict: descriptor-axis hypothesis rejected; dimensions-feature-report
hypothesis confirmed by exact hardware evidence and primary source comparison.

WDK build correction (2026-08-24T16:14:26Z). Push run
`32749485673`, source `8721d1fb5a9910459c8142d28f863a133560297a`,
failed before linking because `struct ai_trackpad_dimensions` was introduced in
`apple_spihid.h` before the kernel-only `int32_t` compatibility typedef in
`apple_trackpad.h`. The portable clang build did not expose this ordering error
because standard `<stdint.h>` supplied the type. No package was produced and no
hardware was changed. The correction moves the guarded signed fixed-width
typedefs into the base protocol header before the dimensions structure and adds
a source-contract regression assertion for that ordering.

EXP-20260824-053 pre-run (2026-08-24T16:20:00Z). Gate D2 geometry
preflight will use public root `b4db773b8e339d2a45428be881078e2cd701f651`
and successful official WDK run `32749949709` (job `97504287093`). The
downloaded unsigned-development artifact is kept under ignored
`.local/apple-input/wdk/32749949709/`. Exact production files are:

- `AppleInput.sys` SHA-256
  `13000bf512feb8a45f7ba21b72af1afa4e1d1562ce101298180d1220cf2597b4`;
- `AppleInput.inf` SHA-256
  `dc53ea5e89307052c218d4916b7a26fe1cdc1449210a16b994360143df857bb6`;
- `appleinput.cat` SHA-256
  `a5ad5c5c7f54a97b8fc803516c99f71c9f3540c469d8fa8d2b56ffa03efe6c15`;
- `AppleInputDiag.exe` SHA-256
  `d887630645ae99248af0dee63290665c7a466c353748eac634ba02b942726703`.

The live Air preflight is APPL0001 `OK` / `CM_PROB_NONE`, service AppleInput
Running, and service path under
`appleinputcapture.inf_arm64_ab17b994ad2f5f75`. The preserved rollback is
`oem15.inf`; its active SYS SHA-256 remains
`65a3d0c4e169abb411712e18658405322a96b2b5dcba85966a53ffa5d16f1ef1`.
Current service gates are `TransportOnly=1`, `PublishKeyboard=0` and
`PublishTrackpad=0`. The candidate will first be installed with only keyboard
publication enabled and trackpad publication still zero. Acceptance requires
the exact candidate SYS, APPL0001 and service healthy, phase 8, trackpad init
READY, both axis-valid flags true, nondegenerate scalar ranges and zero
transport errors. Any mismatch immediately restores all gates off and
reinstalls preserved `oem15.inf`; no ESP or firmware component is changed.

EXP-20260824-053 artifact replacement (2026-08-24T16:29:30Z). The pre-run
package above is superseded before any hardware mutation because its diagnostic
CLI cannot expose the scalar geometry needed by the fail-closed gate. Official
WDK run `32750888801` (job `97507322188`) succeeded from source
`34d7440460e2c8bca3cc7bc19b37dd63bcbfb670`; its ignored local artifact is
`.local/apple-input/wdk/32750888801/`. Exact files selected for Gate D2 are:

- `AppleInput.sys` SHA-256
  `01d49454875fea68d352746dc51d4afcac07613c2b8a212d50cfd1a358397a7f`;
- `AppleInput.inf` SHA-256
  `16dc50813350d9c76ad6b69e12aa04c034266b732fad3f01f6163c28d1e00e39`;
- `appleinput.cat` SHA-256
  `c9a6e28c9ddd613eda00bbae64b7b8eb51ab1ef1548b7f3f8c1c539f92fb6dc4`;
- `AppleInputDiag.exe` SHA-256
  `7e6787ea999b888d0bc70d380596029413d67ed4e95d5fb3c87c1b92e3a1a136`.

This replacement changes only diagnostic observability relative to the prior
package: it adds bounded geometry scalars to JSON and does not enable trackpad
publication. The same rollback, live baseline and two-stage gate remain in
force.

EXP-20260824-053 Gate D2a result (2026-08-24T16:43:00Z): passed after one
fail-closed harness correction. The first attempt loaded the exact candidate
SYS but rejected because `Win32_PnPSignedDriver` transiently reported
`oem15.inf` while authoritative PnP state already selected `oem16.inf`; the
harness restored the publication gates and the preserved package. PnP then
proved `oem16.inf` was installed and best-ranked. The harness was changed to
read `DEVPKEY_Device_DriverInfPath`, explicitly deleted only `oem16.inf`, and
verified the exact `oem15.inf` rollback SYS before retrying.

The second attempt also failed closed and restored `oem15.inf`: geometry was
already valid, but keyboard VHF remained absent because production INF defaults
were written after the gates. Moving the gate write after `pnputil /install`
fixed the proven order dependency. The third attempt passed on `oem16.inf` with
exact active SYS SHA-256
`01d49454875fea68d352746dc51d4afcac07613c2b8a212d50cfd1a358397a7f`,
transport phase 8, trackpad init READY, zero retries, zero timeout/CRC/fragment
and offline counters, keyboard VHF running, and trackpad VHF absent. Hardware
dimensions are logical X `[-5318,5787]`, logical Y `[-157,7102]`, physical X
`[0,468]`, physical Y `[0,317]`, HID unit `0x13` and exponent `-2`.

Ignored evidence hashes:
- `axis-gate-pass.remote.json` SHA-256
  `b0eb6ad9f61d770cad3873f3f8535673ce2b9c2367c6da6c726eac9e227131f0`;
- `axis-gate-status.pass.remote.json` SHA-256
  `f6fa002e526398732e8483b1f574b7de28138169b4025d191a365b8170cc739d`.

Verdict: Apple dimensions report `0xd9` produces a valid Windows axis contract
on live J313. Gate D2b may now publish the Precision Touchpad child without
changing firmware, NVMe, USB or the preserved rollback package.

EXP-20260824-053 Gate D2b result (2026-08-24T16:52:00Z): rejected with exact
rollback complete.  Enabling only `PublishTrackpad` started the trackpad VHF
frontend (`trackpad_vhf_state=3`) with valid axes, 148 decoded reports, zero
rejections, zero start failures and zero transport errors.  Windows issued ten
feature requests, but every request completed with NTSTATUS `0xC0000206`
(`STATUS_INVALID_BUFFER_SIZE`); no input report was submitted during the
bounded observation interval.  The publication harness immediately disabled
the gates, deleted only the candidate `oem16.inf`, restored preserved
`oem15.inf`, and verified active SYS SHA-256
`65a3d0c4e169abb411712e18658405322a96b2b5dcba85966a53ffa5d16f1ef1`.

Source inspection localized the rejection to `AiTrackpadVhfGetFeature`, which
required requester-owned output capacity to equal the selected feature-report
length.  Microsoft HID/VHF contracts permit an output buffer larger than the
report and require only sufficient capacity.  The next candidate changes that
single comparison from exact equality to a minimum-capacity check; SET_FEATURE
retains exact input length.  Verdict: transport, geometry and VHF startup
confirmed; GET_FEATURE output-capacity contract rejected.

### EXP-20260824-054 — retry Precision Touchpad publication with the corrected feature-buffer contract

Pre-run record (2026-08-24T17:07:53Z). Hypothesis: accepting a requester-owned
GET_FEATURE buffer whose capacity is at least the selected report size will
remove the only observed `0xC0000206` failure and allow Windows to enumerate the
Precision Touchpad child while preserving the proven keyboard, transport and
rollback contracts. The single driver change is implementation commit
`97cc8f6fea2355b52de66e67eb387f567d89ea54`; no m1n1, Mu, ACPI, CPU, NVMe,
USB, display or ESP behavior changes.

- source: root `7c260ae8f84f7f898d3f9209c15e39b37565e217`, m1n1
  `2fe790beebed32658eae753dee3e6d581df97197`, Mu
  `9501de460353b902dbbd3b7de42c703af811f037`; all tracked diff SHA-256
  values are the empty-diff hash
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- exact build: push-triggered official WDK run `32754271477`, job
  `97518075905`, completed successfully from head
  `7c260ae8f84f7f898d3f9209c15e39b37565e217`. The ignored artifact is
  `.local/apple-input/wdk/32754271477/`; production SYS SHA-256 is
  `7b75873de00a392b6e906edf5776f69c274e86814fb02389414ef557d2b7bdb5`,
  INF `ca844ebf9a0fab6ae4a6aa434033eb487ca246b9248bc4fde968539ca26565cd`,
  catalog `e11befe19ef7b0dac31360b348394a65259dcb12ea7e7b6bd8ca66097dc0187f`
  and diagnostic CLI
  `d842e47ee5b8c9299b3f3ceb8027855c016f28494fb4e0f4be7dc0d801f5c3f7`.
- assisted platform artifact remains the verified `debug-forensic` both/full
  pair: J313 EFI SHA-256
  `cd591aab2ef0641902f03e1a38aac697e45fc12e466a3cb72f32cd3d68060710`
  and m1n1 Mach-O SHA-256
  `e4c073c28d2d008aa0159cf3e64f5daa2afabe0bb712b68198ea8d917381a3a6`.
  Exact launch command is `scripts/run-windows.sh --execution assisted
  --display both --debug full --observed --proxy
  <CONSOLE_DEVICE> --vuart
  <VUART_DEVICE>` from the current proxy-ready state.
- recovery artifact remains installed Windows package `oem15.inf` with active
  SYS SHA-256
  `65a3d0c4e169abb411712e18658405322a96b2b5dcba85966a53ffa5d16f1ef1`.
  External USB and SSH remain the control paths. Any package, PnP, service,
  feature-status, keyboard or transport mismatch must disable both publication
  gates, delete only the new `oemNN.inf`, force-select preserved `oem15.inf`,
  restart only `ACPI\\APPL0001\\0`, and verify the exact rollback hash.
- acceptance checkpoint: exact candidate SYS active; APPL0001 and AppleInput
  running; transport phase 8; trackpad init READY; keyboard and trackpad VHF
  states 3; valid nondegenerate geometry; GET_FEATURE count greater than zero
  with `trackpad_feature_last_status=0`; a Windows HID child bound without a
  problem code; zero timeout, CRC, fragment, offline, VHF start or decode
  errors. A bounded physical touch test follows only after these automatic
  gates pass.

Automatic Gate D2 result (2026-08-24T17:18:00Z): passed after correcting one
harness-only PnP assumption; the physical touch checkpoint remains pending.
The initial combined assisted invocation began while an earlier guest context
still owned the hypervisor and its chainload caused an EL1 guest exception.
After the target returned to the immutable stage-1 proxy, separating the
operations reproduced the proven manual contract: exact m1n1 `2fe790b` was
chainloaded once, followed by Mu/Windows with explicit `--reuse-proxy`.  Windows
reached SSH.  The host runner later lost the `hv_start` reply to interleaved
full-telemetry events (`UartChecksumError`), but the command had executed and
the live guest remained healthy; this host-observation failure did not alter
the firmware or driver gate.

The candidate installed as `oem16.inf` with exact active SYS SHA-256
`7b75873de00a392b6e906edf5776f69c274e86814fb02389414ef557d2b7bdb5`.
With `PublishTrackpad=0`, APPL0001 and AppleInput were healthy, keyboard VHF was
running, trackpad VHF was absent, native geometry exactly matched Gate D2a and
all transport errors were zero. Enabling only `PublishTrackpad` produced:

- keyboard VHF state 3 and trackpad VHF state 3;
- two new healthy `HID\\HID_DEVICE_SYSTEM_VHF*` PnP children;
- two successful GET_FEATURE and four successful SET_FEATURE operations with
  `trackpad_feature_last_status=0` and `trackpad_vhf_last_status=0`;
- zero VHF start/submission failures, SPI timeouts, packet/message CRC errors,
  fragment failures and offline transitions.

The first observation harness incorrectly searched for
`HID\\VID_05AC&PID_0000*`. VHF uses system-generated
`HID_DEVICE_SYSTEM_VHF` instance IDs, so that check rejected an otherwise
successful publication and automatically restored exact `oem15.inf`. The
corrected ignored harness snapshots the keyboard-only VHF topology and requires
new healthy system-VHF children; repeating from the verified rollback passed.
This changed no driver or guest behavior.

Ignored evidence SHA-256 values:

- `axis-gate-pass.remote.json`:
  `7f97bec2f92dc9d99749d703f8139025e30f66ec2c6c3713dae727cc60bea4cf`;
- `trackpad-publish-status.remote.json`:
  `ad982681049f4b76a1c64d23856012751acb9ea4a0ce63d9d48227b2bcb60bcd`;
- `trackpad-publish-pass.remote.json`:
  `9fbd1a8cb8bf2d16db6482f092c7efcac788519c1df3af137bc2102e1c6bc8d1`;
- `trackpad-pnp.remote.json`:
  `11157f878c8162e76702d10a99282368df2bacd3b78ff4be623fd3a8b9c8726a`.

Verdict: the feature-buffer correction and automatic Windows Precision
Touchpad publication contract are confirmed on J313. `oem16.inf` remains
active with both keyboard and trackpad publication enabled. Do not call motion,
click or gesture behavior validated until a bounded physical-input run advances
decoded/submitted reports and the user confirms cursor/click behavior.

Bounded physical-input result (2026-08-24T20:48:00Z): passed for built-in
typing, pointer motion, and an ordinary click. The user exercised the internal
keyboard and trackpad and reported that they worked correctly. The final
metadata-only `AppleInputDiag.exe status --json` snapshot recorded phase 8,
28/28 accepted and submitted keyboard reports, and 7185/7185 decoded and
submitted trackpad reports. Keyboard and trackpad VHF states remained 3;
GET_FEATURE/SET_FEATURE counts remained 2/4 with both final statuses zero; and
all timeout, CRC, fragment, offline, rejected-report, VHF-start, and submission
failure counters remained zero. The ignored evidence file
`.local/apple-input/gate-d2-32754271477/physical-input-status.remote.json` has
SHA-256
`1b87c25e4294b2ccc7083c80648e914bfd3c7c90d6ed2fd81078dce7c7ba0c71`.

Final verdict: the exact WDK-run-32754271477 package is the validated native
J313 input starting point for built-in typing, pointer motion, and ordinary
click. Multi-finger gesture qualification, controlled reboot/disable-enable,
and long-duration mixed-input stress remain later gates and are not claimed by
this result.

Physical qualification extension (2026-08-24): the operator subsequently
confirmed multitouch, left click, right click, and simultaneous built-in
keyboard and trackpad use in the same Windows session. Windows remained stable
and responsive throughout that bounded operator test. This advances the
physical behavior verdict from basic motion/click to usable built-in keyboard
and Precision Touchpad input. It does not replace the still-separate
long-duration stress, power-transition, or complete Windows gesture-suite
gates. The permanent source and recovery checkpoint is recorded as
`j313-native-input-v1` in
`documentation/verification/J313_NATIVE_INPUT_V1.md`.

### EXP-20260824-062 — isolated J313 4E+1P assisted boot

Status: pre-run; no Air or ESP mutation has occurred.

Hypothesis: the validated four-Icestorm baseline can admit exactly one
Firestorm processor without changing the proven timer, FIQ, vGIC, SGI, NVMe,
USB, display, or native-input paths.  This isolates heterogeneous secondary
startup from both additional Firestorm concurrency and later scheduler/power
work.

- source: root `e076d03d7d53f9c8dc741b3ddef26cc8cf53e183`, m1n1
  `2fe790beebed32658eae753dee3e6d581df97197`, and Mu
  `2bd610c9f6184c78abfe0fa5c8cdda1a9fd8f057`;
- exact assisted artifacts: `dist/j313/debug-forensic/m1n1.macho` SHA-256
  `e4c073c28d2d008aa0159cf3e64f5daa2afabe0bb712b68198ea8d917381a3a6`
  and `dist/j313/debug-forensic/J313_EFI.fd` SHA-256
  `ec7a596b2eb28905fc2ae44d99fb7721b8aaf6947bd98398d0350b5eb9df4f00`;
  packed `boot.bin` SHA-256 is
  `032f1ef08895b8759372e7be250ad88ab0dc595b6d4ca8320bca977623408267`;
- build profile: J313 debug, display `both`, diagnostics `full`; the manifest
  verifier passed and records the exact three source revisions above;
- topology gate: both the static source checker and the compiled
  `MADT_Static.acpi` report enabled UIDs `[0, 1, 2, 3, 4]`, efficiency classes
  `{0:0, 1:0, 2:0, 3:0, 4:1, 5:1, 6:1, 7:1}`, and disabled UIDs 5 through 7;
- execution: assisted launch only.  Do not install `boot.bin` on the ESP and do
  not advance a standalone image during this experiment;
- acceptance: guest-entry evidence for CPUs 0 through 4 and none for 5 through
  7; Windows reaches the login screen and desktop; Windows reports five
  processors with CPU4 in the higher performance class; no bugcheck, watchdog,
  reset, EL2 exception, or prolonged boot stall; built-in keyboard and Precision
  Touchpad remain usable; and a short bounded CPU load returns cleanly;
- stop/rollback: stop or reboot the assisted guest at the first watchdog,
  exception, unexpected CPU, input regression, or boot stall.  Return to tag
  `j313-native-input-v1`; its complete restoration contract is
  `documentation/verification/J313_NATIVE_INPUT_V1.md`.

The first build produced the same firmware hash as the final build even though
the source checkout had briefly been reset by the old root submodule update.
Inspection of the compiled MADT resolved the ambiguity: that cached output had
already been compiled from the 4E+1P source.  The build contract was still
corrected so future development builds preserve explicitly selected nested
revisions, while release builds continue to require root-pinned gitlinks.

First hardware result (2026-08-24T20:31:00Z): partially passed.  The initial
attempt was invalid before Mu because chainload entered an interrupted old
hypervisor context; its EL0 guest exception rebooted the machine to the clean
stage-1 proxy.  The next generation entered Mu, then Windows ran a pending C:
filesystem check caused by the prior interrupted guest and requested one
reboot.  Neither generation reached secondary-processor startup and neither is
evidence against the 4E+1P topology.

The unchanged candidate then booted Windows normally.  Windows reported one
processor package, five cores, and five logical processors.  Boot time was
2026-08-24T22:26:01+02:00.  Five bounded PowerShell workers completed an
eight-second arithmetic load; a fresh SSH session succeeded immediately
afterward at 22:30:33+02:00 with unchanged uptime.  The AppleInput kernel
service remained RUNNING with `PublishKeyboard=1`, `PublishTrackpad=1`, and
`TransportOnly=0`.  No bugcheck or reboot occurred during this bounded run.

The `full` telemetry host runner exited during verbose Mu DXE logging at line
987, before Windows requested secondary processors.  The independently running
guest continued and reached Windows, but this observation failure prevented
direct `CPU_ENTRY cpu=4` evidence and left the web framebuffer stale.  Therefore
the experiment is not yet a final validated CPU checkpoint.  Preserve the
working guest for operator input/responsiveness confirmation, then repeat the
same topology with the bounded `monitor` profile so CPU4 entry and the live
display remain observable without full-log USB backpressure.

Windows topology follow-up (2026-08-24T20:43:00Z): the documented
`GetSystemCpuSetInformation` API returned five CPU sets.  Logical processors 0
through 3 reported `EfficiencyClass=0` and `SchedulingClass=0`; logical
processor 4 reported `EfficiencyClass=1` and `SchedulingClass=1`.  None was
parked.  This is direct guest evidence that Windows recognizes UID 4 as the
higher-performance, lower-efficiency core rather than merely counting a fifth
homogeneous processor.

The same read-only snapshot also explained two misleading observations.  Raw
SMBIOS Type 4 correctly contains `MaxSpeed=3228 MHz` and
`CurrentSpeed=0` (unknown), but Windows synthesizes only `~MHz=44` for CPU0 and
no frequency for CPUs 1 through 4.  The platform exposes neither ACPI `_CPC`
nor another Windows-visible Apple DVFS interface, so Task Manager's displayed
44 MHz is metadata/counter fallback, not a measurement of the physical core
clock.  Separately, the brief UI pause reported while opening Task Manager
coincided with eleven `stornvme` Event 129 resets at ten-second intervals from
22:37:06 through 22:38:46 local time.  Treat that pause as an NVMe completion
timeout/reset symptom, not as evidence of a heterogeneous-scheduler stall.

### EXP-20260824-063 — capture the Windows request behind NVMe Event 129

Status: completed; request class identified, queue failure boundary still open.

Hypothesis: the 22:37–22:38 UI pause is caused by one unsupported or lost
virtual-NVMe request, after which `stornvme` performs ten-second hierarchical
reset attempts.  Capturing StorPort's request trace around a bounded read-only
storage query will identify the opcode/SRB boundary without changing firmware,
topology, the ESP, or disk contents.

- source: root `0fed0e3bae72c327e71eace649a32d738617d238`, m1n1
  `2fe790beebed32658eae753dee3e6d581df97197`, and Mu
  `2bd610c9f6184c78abfe0fa5c8cdda1a9fd8f057`; root documentation-only dirty
  diff SHA-256 is
  `76be82494c66a5a1709fea807acd97ad22ef239c8711b0dbd72feda15162e09e`,
  while both nested source diffs are empty;
- running artifact: the unchanged assisted 4E+1P debug-forensic candidate from
  EXP-20260824-062, m1n1 SHA-256
  `e4c073c28d2d008aa0159cf3e64f5daa2afabe0bb712b68198ea8d917381a3a6`
  and J313 EFI SHA-256
  `ec7a596b2eb28905fc2ae44d99fb7721b8aaf6947bd98398d0350b5eb9df4f00`;
- single variable: briefly enable `Microsoft-Windows-StorPort/Operational`,
  issue a bounded read-only Windows storage query/read, collect the trace, then
  disable the analytic channel again;
- evidence: copied EVTX/XML records under ignored `.local/nvme/`, Windows
  System Event 129 and Storage-Storport 500/550 timestamps, SSH continuity,
  and the current guest uptime;
- acceptance: identify the exact request/opcode or queue transition preceding
  the timeout with no guest reboot and no writes to the Windows namespace;
- failure/rollback: stop immediately on a new reset storm, UI freeze, SSH loss,
  or bugcheck.  Disabling the analytic channel restores its original state;
  the firmware/ESP recovery point remains tag `j313-native-input-v1`.

Result (2026-08-24T20:51:00Z): the bounded query completed without a new
System Event 129, reboot, SSH loss, or UI freeze.  The StorPort analytic
channel was returned to its original disabled state.  Its trace contained 36
Event 24 translation records and one provider decoding error, so it did not
expose the NVMe command payload.  The copied ignored evidence is:

- `.local/nvme/storport-exp063.evtx`, SHA-256
  `286847b6b67e91ecef24b76ac43fb4a5e7b8b107b4676abb082ff23a094b71ee`;
- `.local/nvme/storport-exp063.xml`, SHA-256
  `cae00ac2ae5d5e4c9007e636fbf0b156f21890203eea580e02f38a93b832890a`.

The same-time Storage-Storport Event 524 supplied the missing admin-command
boundary: `stornvme` issued opcode `0x02` (Get Log Page), and the virtual
controller returned generic status `SCT=0, SC=2` (Invalid Field).  This event
is not itself a timeout; the bounded query generated no Event 500/550 pair.

Historical Event 500 payloads resolve the actual reset storm.  The timed-out
commands were ordinary SCSI READ(10) and WRITE(10) requests (`0x28` and
`0x2a`) at unrelated LBAs and sizes from 4 KiB through the advertised 128 KiB
MDTS.  Once the first request stopped progressing, one additional outstanding
request timed out every ten seconds.  Each hierarchical reset then generated
an admin opcode `0x0a` (Get Features) Event 524 with Invalid Field.  Therefore
the Get Features error is reset fallout, and neither a particular LBA nor an
oversized transfer explains the incident.  The unresolved first-failure
boundary is now specifically between submission of a valid ordinary I/O and
guest observation of its CQE/INTx; the next diagnostic must capture SQE,
backend return, CQE publication, CQ-head acknowledgement, INTx generation,
injection and EOI in one bounded ring.

### EXP-20260824-064 — wake the synthetic NVMe INTx owner

Status: first hardware run invalidated by host-runner loss; candidate result
still unknown and no hardware mutation was made.

Hypothesis: the first ordinary I/O timeout occurs when a non-boot guest CPU
publishes the next CQE.  The current virtual controller pins the synthetic INTx
LR to CPU0, but `try_raise_intx()` simply returns on every other CPU without
waking CPU0.  A directed host IPI to the owner should make CPU0 leave the guest
and inject the already-pending completion instead of waiting for an unrelated
exit until `stornvme`'s ten-second timeout.

- source bases: root `0fed0e3bae72c327e71eace649a32d738617d238`, m1n1
  `2fe790beebed32658eae753dee3e6d581df97197`, and Mu
  `2bd610c9f6184c78abfe0fa5c8cdda1a9fd8f057`;
- m1n1 candidate diff SHA-256:
  `5b11da8fcb21bee0addac0bd2af3ea09f176fd729358db76975885d52204922d`;
- single variable: when an unmasked, uninjected NVMe INTx generation is ready
  on a non-owner CPU, send exactly one host IPI to `boot_cpu_idx`; owner polling,
  successful injection, or line deassertion clears the kick latch;
- tests: the new generation/latch unit test passed, followed by the complete
  `tests/run_host_tests.sh` suite;
- exact assisted monitor artifacts: `dist/j313/debug-monitor/m1n1.macho`
  SHA-256
  `d13e30b27852caf3e7854a1835143d88fe0e9e27c26ac8cdd89bc2daa8bd9e35`
  and unchanged `dist/j313/debug-monitor/J313_EFI.fd` SHA-256
  `ec7a596b2eb28905fc2ae44d99fb7721b8aaf6947bd98398d0350b5eb9df4f00`;
  packed `boot.bin` SHA-256 is
  `5326895b614ee5ee4d5e28683f340e02785ef259b58c3a4380bd1e480ebee249`;
- profile: assisted only, display `both`, diagnostics `monitor`; the artifact
  manifest verifier passed;
- acceptance: Windows reaches the desktop with five processors; built-in input
  remains usable; a bounded mixed read/write workload and opening Task Manager
  produce no Event 129/500/550, ten-second UI pause, bugcheck, or SSH loss;
- stop/rollback: do not install the candidate on the ESP.  At the first boot
  regression, watchdog, or reset storm, stop the assisted guest and return to
  the unchanged `j313-native-input-v1` standalone recovery point.

First-run result (2026-08-24T23:10:00Z): do not classify this as a candidate
failure.  Chainload, CPU/NVMe initialization and Mu entry succeeded, and the
internal panel reached the Windows logo.  Before Windows displayed its spinner,
both detached host processes (`run_uefi.py` and `uart-reader.py`) disappeared;
`hv.log` ended abruptly during DXE without a Python traceback or orderly-exit
record, while the Air remained at the logo.  Neither USB interface then
answered the proxy NOP probe.  Because the Python hypervisor runner services
guest exits, a guest left behind after that process is killed cannot make
forward progress.  The observation therefore measures detached-process
lifetime in the host execution environment, not NVMe INTx behavior.  Repeat
the identical artifacts with `run-assisted.sh --foreground` held in a
persistent PTY; do not alter or rebuild the candidate between runs.

Foreground-repeat result (2026-08-24T23:35:00Z): also invalid for classifying
the NVMe candidate, but it isolates a host-observer failure.  Windows reached
five online processors and answered SSH at 38 seconds uptime.  The asynchronous
framebuffer published 36 complete 2560x1600 frames, then the shared proxy stream
reported 481 framebuffer checksum failures and finally terminated
`run_uefi.py` with `m1n1.proxy.UartChecksumError` while `hv_start()` awaited its
reply.  The 2.7 MiB host log contains 31,565 IRQ-route console messages and
948,013 NUL bytes from the desynchronised pixel stream.  Once the only proxy
reader died, the guest could no longer service VM exits.  Therefore neither
the later screen freeze nor SSH loss measures the NVMe owner-kick candidate.

### EXP-20260824-065 — keep framebuffer publication off the proxy reader

Status: rejected after extended hardware observation; retained as a useful
host-side mitigation, not a complete transport fix.

Hypothesis: `FrameReceiver.accept()` publishes each complete 16 MiB frame by
writing, flushing and `fsync()`ing `fb.raw` synchronously inside the sole USB
proxy reader.  During that disk wait the host does not drain CDC; combined with
the monitor build's high console volume, a dropped byte permanently shifts the
reply/event framing.  Moving only complete-frame disk publication to a bounded
background worker should preserve ordered chunk assembly while ensuring the
proxy reader never waits for host storage.

- source bases and firmware candidate are identical to EXP-20260824-064;
- host-only candidate diff SHA-256 (exact diff of `run_uefi.py`,
  `virtual_display.py` and `tests/test_virtual_display.py`):
  `bd99d034ace496d3eddf83f2a21f0f3e03c8705f8a37df150f765843b80904a3`;
- single variable: `run_uefi.py` uses asynchronous, single-slot latest-frame
  publication; framebuffer parsing and all m1n1/Mu/NVMe code remain unchanged;
- test: hold the publisher's `fsync()` path blocked and prove the final chunk
  returns immediately, then release it and verify the exact raw frame and
  metadata are atomically published;
- verification: the focused test failed first because the async API did not
  exist, then passed after implementation.  All 304 root Python tests and the
  complete m1n1 host suite pass.  The m1n1 and Mu artifact hashes remain
  `d13e30b27852caf3e7854a1835143d88fe0e9e27c26ac8cdd89bc2daa8bd9e35`
  and `ec7a596b2eb28905fc2ae44d99fb7721b8aaf6947bd98398d0350b5eb9df4f00`;
- acceptance: foreground assisted boot reaches Windows/SSH and exceeds 75
  complete framebuffer generations with zero event/reply checksum failures and
  a live runner;
- stop/rollback: no ESP write.  On any framing error or runner exit, retain the
  evidence, stop the assisted run and revert only the asynchronous host
  publisher before considering any NVMe change.

Result (2026-08-24T23:30:00Z): passed.  A clean chainload of m1n1
`2fe790b-dirty` booted Windows with five logical processors; SSH first answered
at 52 seconds uptime.  The framebuffer advanced through generation 89 (well
past the former failure at generation 36) with zero event checksum failures,
zero reply checksum failures and no traceback.  Both `run_uefi.py` and the
vUART reader remained alive.  The initial attempt before this run was excluded:
it connected to the frozen prior guest's pixel stream and reset into stock
m1n1 `b791225`, which correctly failed the public launch-contract preflight.
The valid run began only after a second clean chainload from stock `Running
proxy`.  EXP-20260824-064 may now continue without conflating observer loss
with guest/NVMe behavior.

Extended result (2026-08-24T23:32:00Z): the original acceptance window was too
short.  The async publisher advanced to generation 144, but then 538 event
checksum failures, one reply checksum failure and a Python traceback killed
`run_uefi.py`; only the independent vUART reader survived.  The first corrupt
event still had a valid type and length, but its four-byte wire checksum was a
framebuffer pixel (`0x8bff1830`) instead of the sentinel.  Thus `fsync()`
blocking amplified the failure but was not its root cause.  During the same
boot Windows logged Event 129 at 23:27:44 and another at 23:31:56.  The bounded
temporary-file workload itself completed in 1.92 seconds, but its result cannot
validate EXP-20260824-064 after observer death.

### EXP-20260824-066 — serialize DWC3 event consumption with CDC writers

Status: rejected after extended hardware observation; the iodev locking remains
a valid local invariant, but it is not the transport root cause.

Hypothesis: `iodev_handle_events()` is the only CDC ring access that does not
hold the per-device lock.  A USB transfer completion may therefore update the
ring's read indices on one CPU while an event writer updates its write indices
on another, dropping a machine word from an otherwise valid framed event.  The
observed first failure—correct 4060-byte event header followed by a missing
four-byte sentinel—is the expected wire signature.  Holding the same recursive
device lock around `handle_events` should make ring consumption and production
mutually exclusive without changing event contents or cadence.

- source bases are unchanged from EXP-20260824-064;
- m1n1 CDC-lock diff SHA-256:
  `86e97694dda2a8080d94c436a7240088b498bb47e312a1b21c0bf4554cb80906`;
- single variable beyond retained EXP065 host mitigation: acquire the target
  iodev lock across its hardware event callback;
- TDD: the existing iodev host harness was extended to assert that the callback
  observes the lock held.  It failed before implementation, passed after it,
  and the complete m1n1 host suite passed;
- exact artifacts: m1n1 SHA-256
  `3e6ac9e19046e03c82e8f3f4ec4ecdd8a5316fc2cb8be3be6fb910a8c602c397`,
  unchanged Mu SHA-256
  `ec7a596b2eb28905fc2ae44d99fb7721b8aaf6947bd98398d0350b5eb9df4f00`,
  packed debug-monitor `boot.bin` SHA-256
  `eba4739d641c9f17009548786f6dae5891e33170dbe877f8cf9468591188db19`;
- acceptance: clean assisted five-CPU Windows boot, live SSH and runner, more
  than 160 framebuffer generations, zero event/reply checksum failures, then a
  bounded temporary-file storage workload with no new Event 129/500/550;
- stop/rollback: no ESP write.  A deadlock, framing error, runner exit, bugcheck
  or new storage reset rejects the candidate and returns to the unchanged
  standalone recovery tag.

Result (2026-08-24T23:55:00Z): rejected.  A clean assisted run booted Windows
with five logical processors and reached framebuffer generation 144 with zero
framing errors.  At generation 149 the stream produced 98 event checksum
errors, one reply checksum error and the same fatal Python traceback as EXP065.
The Windows lock screen then stopped responding because the only host
hypervisor runner had exited.  Serializing the DWC3 callback therefore delayed
neither the byte-loss threshold nor its fatal consequence.

### EXP-20260824-067 — resynchronize past false reply markers after event loss

Status: rejected as a complete transport fix; retained as required parser
hardening.

Hypothesis: the event parser already drops a framebuffer event whose checksum
is invalid, but a missing USB word shifts the stream.  While scanning for the
next frame, arbitrary BGRA pixels can contain the three-byte `ff 55 aa` prefix.
The old parser accepted any fourth byte as a reply command, consumed 32 more
pixel bytes, raised `UartChecksumError`, and killed the sole hypervisor runner.
Only the command currently awaited, the boot notification, and the event
command are valid complete command words at that boundary.  Rejecting every
other candidate before consuming a reply preserves strict control-reply
checking while making optional display-frame loss recoverable.

- source and firmware artifacts are unchanged from EXP066; this is a host-only
  parser change, so rebuilding or changing target firmware would invalidate the
  single-variable comparison;
- TDD: a corrupt framebuffer event followed by a pixel-aligned false marker,
  then a valid event and reply, raised `UartChecksumError` before the change;
  after filtering complete command words it delivers the valid event and exact
  reply;
- verification: all four proxy event checksum tests and all 305 root Python
  tests pass;
- acceptance: the identical EXP066 target artifacts boot five-CPU Windows,
  the runner and SSH remain live beyond framebuffer generation 180, corrupt
  optional events (if any) do not produce a reply checksum traceback, and the
  lock screen remains interactive;
- stop/rollback: no ESP write.  A real expected-command reply checksum failure
  remains fatal and rejects the candidate; do not weaken control-plane checks.

Result (2026-08-25T00:05:00Z): the host parser no longer died.  The identical
target booted all five processors and reached Windows; after 544 corrupt
framebuffer events there was still no reply checksum error, traceback or runner
exit, and complete frames continued to publish intermittently (frame 62,
generation 58).  This proves false-marker recovery, but the raw stream itself
remained badly corrupted and the guest UI stopped responding.  Parser recovery
is therefore necessary containment, not the target-side root fix.

### EXP-20260825-068 — retry the unsent tail of short DWC3 BULK-IN transfers

Status: implemented and host-verified; hardware result pending.

Hypothesis: the CDC producer removes bytes from `device2host` before submitting
the BULK-IN TRB.  DWC3 reports physically unsent bytes in the completed TRB's
remaining-length field.  The BULK-OUT completion path consumes that field, but
the BULK-IN path discarded it and immediately allowed newer ring data.  A
four-byte short host read therefore permanently removes the framebuffer
checksum/sentinel from the wire, exactly matching the captured failures.
Resubmit the unsent portion of the endpoint transfer buffer before dequeuing
new ring data.

- retained host changes: asynchronous publication and EXP067 parser recovery;
- single target variable beyond those retained changes: record each BULK-IN
  buffer offset/submitted length and retry a valid nonzero residual tail at the
  original IOVA before accepting newer bytes;
- TDD: the USB state test now requires a 16 KiB submission with four bytes
  remaining to produce retry offset `16380`, while zero residual and impossible
  residuals produce no retry.  The new assertion failed to compile before the
  helper existed and passed after implementation;
- verification: the focused USB test and complete m1n1 host suite pass;
- frozen assisted artifacts built from the public tree:
  `dist/j313/debug-monitor/m1n1.macho`, SHA-256
  `a55050a4c94ec2e6d33cf749c4dea85833c32f1c24e2d19f983faf1bddeff743`;
  `dist/j313/debug-monitor/J313_EFI.fd`, SHA-256
  `ec7a596b2eb28905fc2ae44d99fb7721b8aaf6947bd98398d0350b5eb9df4f00`;
  `dist/j313/debug-monitor/boot.bin`, SHA-256
  `be42e8569fa047f7aa5fd7b85a8afb848293876291b5cd7ec8a9fb9e1b9bdd8c`;
- acceptance: clean assisted five-CPU Windows boot, runner and UI live beyond
  framebuffer generation 180, zero event/reply checksum errors, and exact
  continuously advancing web frames;
- stop/rollback: no ESP write.  Any framing error rejects the candidate; retain
  EXP067 so an optional-frame error cannot kill the control plane while evidence
  is collected.

Hardware result (2026-08-25): rejected as the root fix.  The exact frozen
artifact booted Mu, all five configured CPUs and NVMe, but its first
framebuffer checksum failure appeared at `hv.log` line 4154.  Corrupt events
then continued into raw pixel bytes despite the BULK-IN residual-tail retry.
Therefore the observed loss is not explained by an ignored nonzero TRB
residual on `XferComplete`; retain the validation/helper, but do not claim a
transport fix.

### EXP-20260825-069 — restore the proven 512-byte DWC3 BULK transfer boundary

Status: validated on J313 and accepted as the new assisted stability baseline.

Hypothesis: commit `e1b12a6` increased each CDC DWC3 transfer from the original
512-byte max-packet boundary to 16 KiB.  The current framebuffer streamer was
already reduced below 4 KiB because hardware observation found framing loss
near that 16 KiB path, yet multiple events are still aggregated into one 16 KiB
TRB.  Restore the original one-max-packet transfer size so every hardware
submission has the historical, proven boundary; leave the 1 MiB software ring,
event format, frame cadence, Windows, CPU, NVMe, Mu and host parser unchanged.

- RED: a focused USB policy assertion must require the DWC3 bulk transfer size
  to equal the USB 2.0 high-speed max packet (512 bytes) and fail before the
  policy constant exists;
- RED/GREEN result: the focused test first failed to compile because
  `USB_DWC3_BULK_TRANSFER_SIZE` did not exist, then passed after defining the
  512-byte policy and wiring `XFER_SIZE` to it; the complete m1n1 host suite and
  development build pass;
- frozen public-tree artifacts: m1n1 SHA-256
  `785b1b0b2d7f8936f81033dd42cf4be67c512772c28095555e424222230d223f`,
  unchanged Mu SHA-256
  `ec7a596b2eb28905fc2ae44d99fb7721b8aaf6947bd98398d0350b5eb9df4f00`,
  boot image SHA-256
  `8d51d2310f9054e7e15e991fcd1e88327926791ddce80f29fa6f962ba2681c23`;
  focused USB diff SHA-256
  `8deccca91bf3281392aa084a1f48de95bca693d6e4b8b0f91c5373a2deb516d7`;
- acceptance: assisted five-CPU Windows boot, runner/UI and exact web frames
  remain live beyond generation 180 with zero new event/reply checksum errors;
- stop/rollback: no ESP write.  Any framing error rejects the candidate.

Hardware result (2026-08-25): the frozen EXP069 artifact booted Mu,
four secondary CPUs (five logical processors total), NVMe and Windows to the
live desktop.  The async viewer published generation 63, representing more
than 1 GiB of exact 2560x1600 framebuffer payload, over an 8-minute soak.  The
frame CRC and Windows Task Manager contents/time continued to change.  Counts
remained zero for event checksum failures, reply/parser failures,
bugcheck/reset, watchdog/stuck capture, NVMe errors, unhandled endpoint events
and invalid residual retries.  Observation then continued through generation
134 (more than 2 GiB of exact framebuffer payload) with the runner still alive
and every listed error counter still zero.  The prior 16 KiB candidate
corrupted its first framebuffer event near the beginning of the run.  The
operator confirmed that Windows was "super responsive" during the same live
session.  This validates the restored 512-byte hardware submission boundary as
the transport root fix and accepts the exact 4E+1P assisted state as the
checkpoint to publish before exposing another core.

### EXP-20260825-070 — expose the second J313 performance core

Status: validated on J313 and accepted as the 4E+2P assisted checkpoint.

Hypothesis: after the validated 4E+1P interrupt, storage and USB transport
checkpoint, Firestorm UID5 can be exposed without changing any other platform
contract.  Windows should classify it with the same higher efficiency and
scheduling class as UID4 and remain as responsive as EXP069.

- recovery point: root `4d0aa9cea18cb12532db41c94c29be2a294cad38`,
  m1n1 `9cd80ac652ac404e92ae279deeaec8c629d7d184`, and Mu
  `2bd610c9f6184c78abfe0fa5c8cdda1a9fd8f057`, all verified on their
  published remote branches;
- branches: root and Mu `feature/j313-4e2p-cpu-stability`; m1n1 remains the
  unchanged published `stable/j313-4e-baseline`;
- single variable: enable only GICC UID5 in J313 MADT.  UIDs 6 and 7 remain
  disabled; CPU timers, vGIC, NVMe, USB, input, framebuffer and diagnostics
  remain unchanged;
- RED/GREEN contract: change the topology test first to require enabled UIDs
  `[0, 1, 2, 3, 4, 5]` with efficiency class 1 on UIDs 4 and 5, observe the
  expected failure, then change only UID5's GICC flag;
- RED/GREEN result: the focused test failed with observed UIDs `[0, 1, 2, 3,
  4]`, then passed after only UID5's flag changed; all 305 public Python tests
  and the complete m1n1 host suite pass;
- frozen assisted artifacts: m1n1 SHA-256
  `3b81d82176b9853228b39eb3bb56ceff018cd0542248e872dd1bc1304c32b82e`,
  Mu SHA-256
  `4faa23597735b5a5aae2bb7f574ad13108bb05820d85ec292f964925ae87f50c`,
  and packed `boot.bin` SHA-256
  `1fa0e798093a8d3d6545c00ec7f462b2e299e2af3e5aaa48afec9f83e2c48c5e`;
  the manifest reports display `both`, debug `monitor`, m1n1 clean at
  `9cd80ac652ac404e92ae279deeaec8c629d7d184`, and only the recorded Mu/root
  experiment diffs dirty;
- hardware profile: assisted `both/monitor`, exact m1n1 from EXP069, freshly
  built Mu, no ESP installation;
- acceptance: Mu and Windows reach the login/desktop within 30 seconds of the
  corresponding boot phase; Windows reports six unparked logical processors
  and classifies UIDs 4 and 5 as higher-performance; built-in keyboard and
  Precision Touchpad remain usable; web frames advance with zero proxy errors;
  no bugcheck, watchdog, NVMe reset, long UI pause or SSH loss during a bounded
  idle and CPU-load observation;
- stop/rollback: any boot slowdown, spinner freeze, bugcheck, watchdog, input
  regression, Event 129/reset or proxy corruption rejects UID5.  Stop the
  assisted guest and relaunch the exact published EXP069 4E+1P artifacts.

Interim hardware result (2026-08-25): the exact candidate reached the Windows
lock screen and desktop without a delayed boot or recovery path.  Windows
reported one package, six cores and six logical processors.  The documented
`GetSystemCpuSetInformation` probe returned logical CPUs 0 through 3 with
`EfficiencyClass=0` and `SchedulingClass=0`, and CPUs 4 and 5 with both values
equal to 1; this directly confirms that Windows recognizes both exposed
Firestorm cores as the higher-performance class.  A six-worker eight-second
CPU load completed, and the guest remained responsive over SSH afterward.
At 386 seconds uptime, Windows had zero new BugCheck, WHEA, stornvme or storage
reset events.  The exact framebuffer advanced through generation 51.  Counts
remained zero for event checksum errors, reply/parser failures,
bugcheck/system-reset/watchdog capture and NVMe errors.  The operator then
exercised the built-in keyboard, Precision Touchpad and desktop UI and reported
the session stable.  The candidate is accepted for commit and publication as
an assisted checkpoint; it has not touched the ESP.

### EXP-20260825-071 — expose the third J313 performance core

Status: validated and accepted for publication.

Run timestamp (UTC): `2026-08-25T07:00:56Z`.

Hypothesis: the validated 4E+2P checkpoint demonstrates correct heterogeneous
startup and scheduling for two Firestorm siblings.  Enabling only Firestorm
UID6 should extend the same proven path to seven Windows CPUs without changing
any other platform behavior.

- recovery point: root `3ba28a21caf21ff396abd854eea6aa8b4a9cfd08`, Mu
  `926f45204e0faffc040f85966b62ef3ec217e61f`, and unchanged m1n1
  `9cd80ac652ac404e92ae279deeaec8c629d7d184`, each verified against its
  published remote branch;
- branches: root and Mu `feature/j313-4e3p-cpu-stability`;
- single variable: enable only GICC UID6.  UID7 remains disabled and all
  timer, vGIC, NVMe, USB, input, display and diagnostic code is unchanged;
- RED/GREEN contract: require enabled UIDs `[0, 1, 2, 3, 4, 5, 6]`, class 0
  for UIDs 0 through 3 and class 1 for UIDs 4 through 6; observe failure before
  changing UID6, then change only its GICC flag;
- RED/GREEN result: the focused test failed with observed enabled UIDs `[0, 1,
  2, 3, 4, 5]`, then passed after only UID6's GICC flag changed; all 306 public
  Python tests and 96 subtests plus the complete m1n1 host suite pass;
- frozen assisted artifacts: m1n1 SHA-256
  `3b81d82176b9853228b39eb3bb56ceff018cd0542248e872dd1bc1304c32b82e`,
  Mu SHA-256
  `62926b4ecf8450e9bdde6c7db64dd20d5622d0a3fa43a6d7b874b5597564b1c8`,
  and packed `boot.bin` SHA-256
  `eea72444e05fec89fa86d65f8fda3db29e4eb5e1e48923d97bb7f62e157e8610`;
  the manifest reports display `both`, debug `monitor`, clean m1n1 at the
  published checkpoint and only the recorded root/Mu experiment diffs dirty;
- hardware profile: assisted `both/monitor`, fresh Mu and exact m1n1 from the
  published checkpoint, with no ESP write;
- build command: `scripts/build-standalone.sh --debug-build --display both
  --debug monitor`;
- launch command: `M1N1DEVICE=<CONSOLE_DEVICE>
  M1N1VUART=<VUART_DEVICE> scripts/run-assisted.sh --proxy
  <CONSOLE_DEVICE> --vuart <VUART_DEVICE>
  --display both --debug monitor --chainload --foreground`;
- evidence paths: `hv.log`, `fb.raw`, `fb-info.json`, Windows System event log,
  `/tmp/cpuset-exp070.ps1`, `/tmp/cpu-stress-exp071.ps1`, and
  `/tmp/health-exp071.ps1`;
- acceptance: Windows reaches the desktop without a delayed spinner, reports
  seven logical processors and P-class on UIDs 4 through 6; internal input and
  SSH remain responsive; a seven-worker bounded CPU test completes; exact web
  frames advance and Windows/hypervisor logs contain no relevant error;
- stop/rollback: any boot delay, freeze, bugcheck, watchdog, storage reset,
  input failure or proxy corruption rejects UID6 and returns to the published
  4E+2P checkpoint.

Interim hardware result (2026-08-25): the exact candidate reached the Windows
lock screen within the 30-second gate and remained available over SSH.  All
secondaries CPU1 through CPU6 entered the guest.  Windows reported one package
and seven logical processors.  `GetSystemCpuSetInformation` returned logical
CPUs 0 through 3 with efficiency/scheduling class 0 and CPUs 4 through 6 with
both classes equal to 1, confirming the third exposed Firestorm core is in the
higher-performance class.  A seven-worker eight-second CPU load completed in
19081 ms including PowerShell job startup/cleanup.  At 222 seconds uptime,
Windows reported zero new BugCheck, WHEA, stornvme or storage-reset events and
remained responsive afterward.  Hypervisor counts were zero for checksum,
proxy/parser, bugcheck/reset and NVMe failures; the only `watchdog` text was the
normal Mu `WatchdogTimer.efi` load line.  The exact framebuffer showed the
live lock screen.  The operator then verified the built-in keyboard, Precision
Touchpad and desktop behavior and reported the session stable and smooth.  The
4E+3P candidate is accepted as the next assisted recovery checkpoint; the ESP
was not modified.

### EXP-20260825-072 — expose the fourth J313 performance core

Status: validated and accepted for publication as the 4E+4P assisted checkpoint.

Run timestamp (UTC): `2026-08-25T07:08:17Z`.

Hypothesis: the published and operator-validated 4E+3P checkpoint demonstrates
correct heterogeneous startup, scheduling and bounded load for the first three
Firestorm siblings.  Enabling only Firestorm UID7 should expose all eight M1
cores without changing any other platform contract.

- recovery point: root `2e7686532c74049d89b8bd7c2ae1a2fd0b755d4d`, Mu
  `b6213a54695ebfabfef38b66bd1b9e1713342a5f`, and unchanged m1n1
  `9cd80ac652ac404e92ae279deeaec8c629d7d184`, each verified against its
  published remote branch;
- binary recovery point: `.local/recovery/EXP-20260825-071-4e3p/`, containing
  m1n1 SHA-256
  `3b81d82176b9853228b39eb3bb56ceff018cd0542248e872dd1bc1304c32b82e`,
  Mu SHA-256
  `62926b4ecf8450e9bdde6c7db64dd20d5622d0a3fa43a6d7b874b5597564b1c8`,
  and packed `boot.bin` SHA-256
  `eea72444e05fec89fa86d65f8fda3db29e4eb5e1e48923d97bb7f62e157e8610`;
- branches: root and Mu `feature/j313-4e4p-cpu-stability`; m1n1 remains the
  unchanged published `stable/j313-4e-baseline`;
- single variable: enable only GICC UID7.  Timer, vGIC, NVMe, USB, input,
  display and diagnostic code remain unchanged;
- RED/GREEN contract: first require enabled UIDs `[0, 1, 2, 3, 4, 5, 6, 7]`,
  class 0 for UIDs 0 through 3 and class 1 for UIDs 4 through 7; observe the
  expected failure, then change only UID7's GICC flag;
- RED/GREEN result: the focused test failed with enabled UIDs `[0, 1, 2, 3,
  4, 5, 6]`, then passed after only UID7's GICC flag changed; all 305 public
  Python tests plus the complete m1n1 host suite pass;
- frozen candidate artifacts: m1n1 SHA-256
  `3b81d82176b9853228b39eb3bb56ceff018cd0542248e872dd1bc1304c32b82e`,
  Mu SHA-256
  `4c5e068f664d8ccc94823880de4226e3f7842e08841bc10fea19cbe9e05a519b`,
  and packed `boot.bin` SHA-256
  `6ab28c09ced56db4e03ad54d755d0f2caae76ca9ff97f2b9fe0d6e71fec5bc30`;
  the manifest reports display `both`, debug `monitor`, clean m1n1 at the
  published checkpoint and only the recorded root/Mu experiment diffs dirty;
- planned build: `scripts/build-standalone.sh --debug-build --display both
  --debug monitor`;
- planned launch: `M1N1DEVICE=<CONSOLE_DEVICE>
  M1N1VUART=<VUART_DEVICE> scripts/run-assisted.sh --proxy
  <CONSOLE_DEVICE> --vuart <VUART_DEVICE>
  --display both --debug monitor --chainload --foreground`;
- expected checkpoint: Windows reaches the lock screen within 30 seconds,
  reports eight logical CPUs, and classifies UIDs 4 through 7 as P-class;
  an eight-worker bounded load completes while input, SSH and frames remain
  responsive with no relevant Windows or hypervisor error;
- stop/rollback: any boot delay, freeze, bugcheck, watchdog, storage reset,
  input failure or proxy corruption rejects UID7.  Relaunch the preserved
  EXP071 4E+3P binary recovery point without writing the ESP.

Hardware result (2026-08-25): all secondaries CPU1 through CPU7 entered
the guest and Windows reached the lock screen inside the 30-second gate.  It
reported one package and eight logical processors.  The official
`GetSystemCpuSetInformation` probe returned logical CPUs 0 through 3 with
efficiency/scheduling class 0 and CPUs 4 through 7 with both classes equal to
1.  An eight-worker eight-second CPU load completed in 21624 ms including
PowerShell job startup and cleanup.  At 314 seconds uptime, Windows reported
zero new BugCheck, WHEA, stornvme or storage-reset events and remained available
over SSH.  Hypervisor counts were zero for checksum, proxy/parser,
bugcheck/reset/watchdog and NVMe failures.  The exact framebuffer advanced to
generation 42 and displayed a clean live lock screen after the load.  A second,
longer eight-worker test kept every worker busy for 20 seconds and completed in
39535 ms including PowerShell job startup and cleanup.  Six independent SSH
round trips made during that load completed in 0.72 to 1.26 seconds, with no
pause or lost response.  At 6418 seconds uptime, Windows still reported eight
logical processors and zero relevant System events.  `AppleInput` remained
RUNNING, `ACPI\\APPL0001\\0` and both VHF children remained healthy, and the
keyboard and Precision Touchpad publication gates remained enabled.  The user
reported the desktop stable and smooth and authorized publication.  This exact
both/monitor assisted candidate is therefore the new eight-core recovery
checkpoint; the ESP was not modified and standalone cold-boot qualification
remains a separate gate.

## EXP-20261011-J413-001 — host-only M2 firmware and research checkpoint

Ledger timing correction: this entry is appended after the host build. The
before-build ledger update required by AGENTS.md was missed; no hardware launch
or installation occurred. The commands, source pins, output hash and preserved
logs below record the actual result without claiming a prospective entry.

Intent: test whether a distinct J413 Mu platform can compile while preserving
the J313 baseline, and whether an AIC2 physical IRQ can be translated into the
existing guest namespace without changing the M1 route. This is a software
checkpoint with several independently host-tested changes, not a combined
hardware experiment.

Source and environment:

- repository `Liamsitbon/windows-on-m2-air`, branch `main`, clean-fork root base
  `1a247525175fce61484e75e0915adc452475a0c2`;
- pinned m1n1 `9cd80ac652ac404e92ae279deeaec8c629d7d184`, with only the two
  root-tracked J413 patches applied; binary diff SHA-256
  `8224428a9b7ac79d69fc6de504f055aa188595546e1d78d0c59fe8a780c4f51c`;
- pinned Mu `8b4dc4b4e3ff8606d0af36163acf9de79b7b4737`; tracked upstream
  files unchanged; staged new overlay SHA-256
  `3778d5e814072dd92e5336e326419d89f8f820c80026eae71b35ebafc58e54d5`;
- host Mac14,2/T8112, macOS 27.0 build 26A5425a; Docker native Linux ARM64,
  Ubuntu 24.04, Python 3.12, Clang 18.1.3 for Mu;
- root source changes were uncommitted during the build. The source overlay
  hash identifies the actual firmware input. The final implementation commits
  are linked in CHANGES.csv; they do not retroactively become the build-time HEAD.

Executed commands:

```sh
python3 tools/collect_j413.py
python3 tools/j413_platform.py --stage-m1n1
make -C m1n1_windows host-tests CC=/usr/bin/clang
scripts/build-j413-firmware.sh
python3 tools/analyze_kext.py --target-j413 --resume \
  --kernel-macho .local/kext-research/BootKernelCollection.kc
python3 -m unittest discover -s tests
```

Observed build result: completed at 2026-10-11 04:20:26 UTC, Mu build duration
2m17s, 97 EFI PE/COFF images accepted by the build verifier. Output
`dist/j413/firmware-debug/J413_EFI.fd`, 30,965,760 bytes, SHA-256
`ba6644179892cf84a9fd0ad5bf55ab66b635a79463c880ff6224dcd0fa114800`.
The DEBUG/physical/uart manifest was subsequently regenerated to include the
mandatory J413 overlay hash; the firmware bytes were not rebuilt or relabelled
as hardware-qualified. Preserved log `.local/j413-firmware-build.log`, SHA-256
`e1a444107e70006039235a17e96e05e1f2d94be69e6964e0ccf879889218f992`.

Direct compiled-MADT inspection found eight enabled UIDs, correct J413 4E/4P
MPIDRs and classes, and 64-bit virtual redistributor base `0xf10000000` with
length `0x100000`. Raw compiler-table checksum is not an installed ACPI checksum.
All m1n1 host tests passed, including M1/M2 route selection, physical-capacity
bounds and reverse EOI. Log `.local/m1n1-host-tests.log`, SHA-256
`deb9ba52c5e6887b2b59bae186c6d16f4b6fe91231ea93de79d36bcb731db88e`.

Read-only bundle research inventoried 27 bundles and 41,172 symbol entries.
Apple binaries remain local. Native kmutil emitted a valid boot Mach-O, then
returned 71 for missing auxiliary/system paths; no complete export is claimed.
Collection SHA-256 and actual DockChannel disassembly findings are recorded in
`documentation/reverse-engineering/`. Fake-FIFO tests validate portable transfer
semantics and bounded calls, not hardware access or a Windows driver.

Hardware result: not run. No Windows stop code, boot phase, live Windows input,
USB/DMA, storage, CPU startup, GPU job, audio, networking or suspend/resume result
exists for this J413 checkpoint. No boot entry, ESP, partition or boot policy
was changed. macOS remains the unchanged recovery state; the firmware component
is not an installable boot.bin. With only the target Air, the original
second-host assisted recovery/logging contract is unavailable.

Verdict: host build and software contracts confirmed; native M2 Windows boot
and drivers remain inconclusive/unqualified. Before the next hardware
experiment, qualify live reservation placement, physical-resource translation,
logging and a reversible recovery path. Do not enable device DMA on the strength
of this build alone. See documentation/J413_STATUS.md for layer ownership and
primary sources.

## EXP-20261011-J413-002 — correct inherited UART ACPI IRQ

Before build, 2026-10-11 04:37 UTC: a final ACPI review found that COM0 retained
physical IRQ 1097 from the M1 template. Live J413 ADT and independently inspected
Asahi `t8112.dtsi` serial@235200000 agree on AIC IRQ **739**. Correct only that
functional descriptor; clean copied-source trailing whitespace and stale
comments without changing other functional fields. Add a regression comparing
the sanitized capture and DSDT. The guest fallback ID is within 0..1019; actual
UART attachment/interrupt delivery is still unqualified.

Root/m1n1/Mu pins and recovery state remain those of EXP-20261011-J413-001.
The overlay hash before/after and final firmware hash will be recorded after the
build. Command: `scripts/build-j413-firmware.sh`, native ARM64 Docker, DEBUG
physical/uart manifest. Evidence: `.local/j413-firmware-build-002.log`.
Expected result: host firmware compilation and new descriptor succeeds; failure
criterion: ACPI/build/manifest rejection. No hardware launch/install command is
planned, and no partition or boot state will be changed.

After build, 2026-10-11 04:39:03 UTC: the incremental Mu build completed in
13 seconds and passed PE/COFF validation. Final overlay SHA-256
`f129ef244f49ccdfe93d6a33d4ab753dc6f9dc76841e7e47b1ed24fa7f818973`.
Firmware `dist/j413/firmware-debug/J413_EFI.fd`, SHA-256
`12409354b231ab22dd3d2c80982d8eb2da8ebcc1a16fdf75e13cbe1983f6098c`.
The J413 DEBUG/physical/uart manifest and guest-firmware role verified. Build
log SHA-256 `ba1a98f2e066d6ac91137ad2ecce34c3d4b080480b00f592ddd81de6dc4a5988`.
Build-time root indexed/tracked diff SHA-256 from the manifest: `56d7a3b89e33bfdb34dd405e6a6337407029d30afa3770bc2f266e96ddfea678`.

The updated UART descriptor regression passed; the complete root suite ran
313 tests, with one expected skip, and passed. The already successful full
m1n1 host suite remains applicable: its source has not changed since EXP001.
No hardware was launched. Verdict: corrected descriptor and host firmware build
confirmed; physical UART and every J413 Windows runtime contract unqualified.
The next hardware experiment and recovery requirements are unchanged.
Final root test log SHA-256: `9741ac8524d351b50891cf8522a2224ff40ce8b2da47f5245504a7c820de6d1b`.

## EXP-20261011-J413-003 — prepare external Windows Setup media, host only

Before preparation, 2026-10-11 UTC: the user requested an external-SSD Windows
Setup boot attempt and identified the attached SanDisk Extreme 2TB, volume
Untitled 2, as the intended disk. Read-only inventory found an exFAT data
partition with ARM64 BOOTAA64.EFI, a 630231583-byte ARM64 Windows PE/Setup boot.wim
and a 7612941295-byte install.wim. Its 209715200-byte FAT32 EFI partition cannot
hold this boot.wim. An internal UEFI-only APFS stub and 500170752-byte ESP exist;
ESP inspection awaits user administrator authentication. No bootloader files,
partition map or security settings have been changed.

Source: clean-fork main 2b4117a7eed6b251e9febfd2a9e039c3a5e659ec; same pinned
m1n1/Mu and staged J413 overlays as EXP002. The autonomous runtime still uses
J313_AUTONOMOUS_LAYOUT and the J313 golden launch snapshots, so the current
J413 FD is not an installable standalone M2 Windows boot image. Do not bypass
that contract or label existing U-Boot as a complete Windows hardware layer.

Plan: create a new 10GiB FAT32 GPT sparse image solely in the ignored local
workspace, copy the existing ARM64 Setup files, split the oversized install.wim
with wimlib into FAT32-sized SWM parts, and verify media contents. Omit the
existing autounattend.xml from this manual Setup test copy; it contains account
credentials and automatic OOBE settings. Do not execute it or publish its
contents. No disk wipe/install command is authorized by this preparation.

Commands: hdiutil create/attach on the new local image only; Python byte copy
excluding metadata directories and install.wim; wimlib-imagex split with 3800MiB
parts; wimlib-imagex verify on source boot.wim and prepared split set. Evidence:
.local/external-winsetup/PREFLIGHT.json, MEDIA.json and preparation log. Expected
checkpoint is intact FAT32 Setup media with ARM64 fallback EFI path and no file
>=4GiB. Recovery is detach/delete this new local image; original SSD contents
and current macOS remain untouched. No hardware launch is planned until M2
bootstrap, USB ownership, resource placement and a recovery path are qualified.

After preparation, 2026-10-11 UTC: the FAT32 copy completed with 964 files.
All byte-copied files matched source SHA-256. The split installation WIM and
ARM64 boot WIM passed wimlib resource verification. No file reaches 4GiB.
- sources/install.swm: 3981883451 bytes; SHA-256 `7a16002f6ac9f2b6d2d4eeb4aa990eb87344b2fa157b8fa23041490393c472b7`.
- sources/install2.swm: 3604356140 bytes; SHA-256 `951cd710136629c9ff0e2fe2237a97782d474ce311a4f2dbd97bd0c61cca64d7`.
- sources/boot.wim: 630231583 bytes; SHA-256 `dcf58a3d6be5d8747ba8b475f6bbc3782a53bc5dc14c7b11e73ff140deeab534`.
Local sparse image: 8528105472 bytes; SHA-256 `5b23eb02d5e40b8439ebcc553add9b1d1404431605f6241a47b870b4da3c17d6`.
- .local/external-winsetup/MEDIA.json SHA-256 `907a982f689de12733b565ca328c66fb8dfd3be69e9a70e56637bb7d8613e18e`.
- .local/external-winsetup/PREFLIGHT.json SHA-256 `3d16a47dcb8d9fc96ed706bd10fc387f87cd80e0bea95e3fcb2e0513cc296079`.
- .local/external-winsetup/prepare.log SHA-256 `ff82353b9763d4f838def4b518793df1451a34cb417826bb9674934cdb0a226e`.
The newly created disk image was detached cleanly. Original external Setup
files were not modified and no physical partition was formatted. Read-only
internal ESP mount and bputil display failed without administrator
authentication; the user was asked to mount the observed disk0s4 read-only.
No password was requested in chat and no Recovery setup was launched.

Verdict: installer file preparation and WIM integrity confirmed; J413 Windows
boot remains unqualified and unattempted. Main blockers are the absent J413
autonomous launch contract and uninspected active internal ESP. The external
SSD has not been deployed with the prepared FAT32 filesystem. No claim of a
Windows boot logo, kernel, Setup UI, USB runtime or installed OS is made.

## EXP-20261011-J413-004 — diagnose existing internal ESP, read only

Timing correction: the initial diskutil verifyVolume command below was run
before this entry was appended. It used fsck_msdos -n; no repair occurred.
The user supplied a failed administrator read-only mount of observed disk0s4.
The device remains the 500170752-byte internal EFI - UEFI partition. Verification
completed all three phases, reported 176 files and 343580 KiB free, and returned
filesystem-check code 0. It requested marking the filesystem clean, answered
no under -n, and left the dirty flag set. That flag alone does not establish
structural corruption or explain the mount failure conclusively.

Root main is 604716d67682fb1e04a7bf99d6ade517172060cb; m1n1/Mu pins and local
staged patches/overlay remain unchanged from EXP002. No native Windows launch
has been attempted. Current macOS and both physical disks are unchanged by this
read-only inspection.

Next diagnostic: attempt a read-only local image capture of this one partition
with hdiutil create -srcdevice /dev/disk0s4 -format UDRO into a new ignored
.local/esp-audit/ path. Expected checkpoint: preserved copy with exact byte
identity for offline inspection. Failure criterion: access denial or failed
read; do not repair, format, change boot policy or touch the partition map.
Evidence will remain under .local/esp-audit/. If authentication prevents capture,
request only the administrator read needed to copy the partition. An image copy
can be inspected separately without mutating the original ESP.

After diagnostic, 2026-10-11 05:05 UTC: the administrator mount failure is
user-observed. The read-only verifyVolume result establishes check exit code 0
and an uncleared dirty flag, not a diagnosed cause for the mount failure.
A filtered unified-log query returned no matching records. DiskImages capture
produced neither image nor log output and remained blocked; the initiating
hdiutil process was stopped (exit 137), and its remaining matching helper was
sent TERM. No image, hash or successful capture is claimed. No repair, writable
mount, partition change or Windows boot occurred. This experiment is inconclusive
on the mount cause; the FAT32 structure check found no reported structural errors.

Next read-only checkpoint, pending user execution: copy the observed partition
via /bin/dd with if=/dev/rdisk0s4 and bs=4m. Redirect standard output as the normal
user to a new .local/esp-audit/internal-esp-20261011-0505.img regular file, with
shell noclobber enabled to refuse overwriting an existing file. Only the dd reader
runs under sudo; no output device argument is used. Expected file size is
500170752 bytes. Do not mount or modify the source; validate size and SHA-256
before offline inspection. This capture is not yet executed or successful.

Capture follow-up to EXP-20261011-J413-004: the user executed the recorded dd
reader and reported 119+1 input/output records, 500170752 bytes in 0.570235s.
The local file independently measures exactly 500170752 bytes and SHA-256
c3c05822c9bdf82ee3fd977621d5e54158662465527a4b64aa6da3b76398384b.
The original partition was read, not repaired or mounted. The dd capture is
confirmed; the cause of the earlier mount failure remains unresolved.

## EXP-20261011-J413-005 — inspect preserved internal ESP offline

Before run, 2026-10-11 UTC: root main is
d67151175f2f39864a37ff80a02a30016ad8f5e3. Firmware submodule pins, J413 overlay
and local patches are unchanged from EXP002; no firmware artifact is launched.
Input is the preserved .local/esp-audit/internal-esp-20261011-0505.img with the
size/hash recorded above. Read-only BPB inspection found FAT32, 4096-byte sectors,
one sector per cluster, 32 reserved sectors, two 119-sector FATs, 122112 total
sectors and root cluster 2. Signature is 55aa. No cause is inferred from this.
Hypothesis: the copied FAT and directory chains can reveal the existing stage-2
boot files without requiring an original-device mount. The only variable is
using the preserved regular file rather than the physical partition. Inspect
bounded FAT32 chains using the BPB/directory/table format confirmed against
m1n1_windows/rust/vendor/rust-fatfs/src/{boot_sector,dir_entry,table}.rs.
No source code from that dependency is copied. Open input only rb, preserve its
hash, save extracted files only under a new ignored local directory. Expected
checkpoint: inventory, boot-file hashes, and identifiable existing boot chain.
Reject parsing if signatures/geometry/chains/paths are invalid. Never execute an
extracted EFI or script. No Windows boot, boot-policy change or repair is planned.

After EXP-20261011-J413-005, 2026-10-11 UTC: offline traversal extracted 145
regular files (directory counts are separate), with bounded valid FAT32 chains.
Both FAT copies match and the backup boot sector matches the primary. The image
SHA-256 remained unchanged. The original ESP was not mounted or modified.
The 2708868-byte m1n1/boot.bin has SHA-256
6c6f7c9d7fd532b9475f07ed2828987fc25a9cbe25f6b7f9d7803a43f2d6983e.
Its bounded XZ stream at offset 1458176 contains a second 2516344-byte m1n1 image,
SHA-256 67f7e2f33e700a191e8012cc3ff9cd750a7d5a603431ac8e4652b173d987e371.
Both carry J313 and automatic Windows entry strings. The inner XZ stream at the
same offset contains a 30965760-byte FV image, SHA-256
fb3f841a18d4e7c1484bc1b697fa559930b60f7696a0628ec7832c20bdf1992b,
with a MacBookAirM2-AARCH64 debug PDB path. That path alone proves neither an
M2 platform contract nor provenance. This is not the new clean-source FD hash.
Internal efi/boot/bootaa64.efi is ARM64 and byte-identical to the external
Setup fallback. BCD names sources/boot.wim and boot/boot.sdi; no sources/boot.wim
exists on this ESP. No U-Boot was identified in the bounded decoded payloads.
These static findings do not establish a working Windows boot or root cause.
Local inventory and extracted binaries remain ignored; Apple recovery/account
metadata and binaries are not published. Verdict: original file preservation
and static inspection confirmed, hardware boot unattempted. Do not launch this
unqualified existing image as a substitute for the clean J413 work.

## EXP-20261011-J413-006 — preserve external SSD files before layout planning

Before run, 2026-10-11 UTC: the user requests external Windows Setup and a separate
future Windows installation partition, plus workspace on the SSD if needed.
The identified SanDisk Extreme 2TB remains disk7 with disk7s2 exFAT Untitled 2.
Read-only resizeVolume disk7s2 limits reports the filesystem cannot be resized.
Local diskutil manual permits resizeVolume on journaled HFS+, not this exFAT;
splitPartition is destructive. Do not substitute a destructive verb for resize.
The live inventory has 1125 regular files, 8533377328 bytes, no scan errors.
The Mac has approximately 18GiB available: enough for one file backup with at
least 4GiB headroom. Copy every inventoried regular file, including hidden files,
into a newly created private ignored local directory. Preserve account XML only
locally with restricted file permissions; do not print or publish its contents.
Single variable: create a normal-file backup, no physical partition operation.
Expected checkpoint: source and destination hashes match for every regular file
and a private manifest records exact paths/sizes/hashes. Reject if any read,
identity, free-space, source-change or hash check fails. Disk7 identity must remain
external SanDisk and exFAT before copying. Recovery remains unchanged original
SSD. No format, erase, unmount, partition write or OS install is authorized by
this diagnostic. Layout reconstruction is a separate reviewable operation.

Additional EXP005 validation: the repository's parse_bootstrap and parse_image
accept the preserved original image, including both CRCs and matching flags 1;
inner layout version is 1. The two nested m1n1 images are the intended bootstrap
format, not a packaging defect. This correction narrows the earlier static
observation; its J313 launch assumptions remain unqualified for live M2.

After EXP-20261011-J413-006, 2026-10-11 UTC: backup completed successfully with
1125 verified files and 8533377328 bytes. Each destination hash equals its source
hash and source size/mtime were stable during copying; no scan errors occurred.
Local destination: .local/ssd-backup-yn0y2psr/files; manifest SHA-256
0a1d6f0e0ea2eb2ad622ee185f6e5e1867c21bef19c44a0f53ee4a8424a83079.
Files are mode 0600 and directories private on local APFS. This is not a raw
external EFI/GPT backup. No SSD partition was modified. A concrete eventual
16GB Setup, 512GB Windows, 16MB MSR, provisional 2GB WinRE and remainder-data
layout is documented. The user's optional size preference remains pending; the
512GB assumption affects planning only. Explicit authorization to reconstruct
the exFAT partition, rather than resize it, is pending. Verdict: file preservation
confirmed; physical layout unchanged.

## EXP-20261011-J413-007 — portable Asahi protocol source adaptations

Before full verification, 2026-10-11 UTC: official Asahi Linux branch asahi was
resolved to 77cb8f24c2381a8abb7272d7bbdec548d6426a8a. Inspected rtkit.c, rtkit.h,
dockchannel.c, dockchannel-hid.c, T8112/J413 DTS and local live resource inventory.
RTKit offers GPL-2.0-only OR MIT; DockChannel HID offers GPL-2.0 OR MIT. MIT is
selected for adaptations, original notices retained and upstream MIT text added.
No Gemini source was read or imported. The existing ESP binary is diagnostic
input only, not a source donor or launch candidate.

Contract: RTKit management owns version negotiation, endpoint-map replies,
system endpoint start words and power ACK state. A pure plan leaves transport
commit and partial-send recovery to the Windows adapter. DockChannel packet
code owns little-endian framing, additive checksum and bounded payload views.
The hypervisor/platform still owns physical resources, IRQ and DART mappings;
Windows integration owns transport, scheduling, buffer lifetime, cancellation,
power, coprocessor reset and HID publication. Source-port packet validation
rejects iface >=16 and invalid body/subheader bounds before exposing any view.
No physical address/IRQ/power value was guessed or exercised.

Windows sources inspected: WdfInterruptCreate, Using Framework Locks and Using
Common Buffers on learn.microsoft.com. No WDF adapter API is implemented yet.
Smallest falsifiable checkpoint: strict host harnesses, sanitizer validation of
untrusted packet snapshots, and Windows ARM64 COFF object machine 0xaa64.
Recovery: delete only generated temporary host/object artifacts. No hardware
launch/build-install, runtime behavior or .sys linkage is claimed.
Timing correction: the first isolated pure-C host and COFF checks passed before
this entry was appended. The complete host suite is now planned before running:
python3 -m unittest discover -s tests. Evidence: .local/asahi-port-tests.log.

## EXP-20261011-J413-008 — stage reproducible artifacts in new SSD workspace

Before run, 2026-10-11 UTC: the user authorizes work on the external SSD when
needed for Mac space. Existing physical partition identity remains SanDisk
Extreme 55AE, 2000365371904 bytes, 512-byte sectors, external disk7. Create only
a new windows-on-m2-workspace directory with a unique artifact-set subdirectory
on the existing exFAT filesystem. Copy the already prepared local FAT32 sparse
image and clean J413 DEBUG firmware component, validating their recorded hashes
before/after. A file inside exFAT is a staging artifact, not a boot partition.
Do not copy recovery/account metadata or original unattended account XML into
this workspace. Do not remove local sources: they are still needed if the user
approves reconstruction of the current data partition. Expected checkpoint:
identical copied artifacts, a local-to-SSD path record and unqualified-boot
status. Reject identity mismatch, existing-file overwrite or hash discrepancy.
No physical partition command, bootloader installation or hardware launch.

After EXP-20261011-J413-007: complete suite ran 317 tests in 6.060s, 316 passed
and one expected skip. Protocol host tests and Windows ARM64 COFF compilation
passed; DockChannel packet harness ran under ASan/UBSan including an independent
byte fixture, invalid lengths/checksums/interfaces, maximum payload and 10000
bounded untrusted snapshots. No actual device, firmware launch or .sys linkage.
Verdict: source-port software checkpoints confirmed, runtime unqualified.

After EXP-20261011-J413-008: both artifacts copied to the new existing-filesystem
workspace windows-on-m2-workspace/artifact-set-dlqdgi30 and their destination
hashes matched the recorded source hashes. WINSETUP-M2.sparseimage is still
8528105472 bytes with SHA-256 5b23eb02d5e40b8439ebcc553add9b1d1404431605f6241a47b870b4da3c17d6;
J413_EFI.fd is 30965760 bytes with SHA-256 12409354b231ab22dd3d2c80982d8eb2da8ebcc1a16fdf75e13cbe1983f6098c.
Local originals retained. No partition was created, resized or erased. No EFI
fallback replacement or OS deployment. Verdict: SSD artifact staging confirmed,
not a bootable physical Windows disk.

## EXP-20261011-J413-009 — resolve live Apple ADT register ranges read only

Before run, 2026-10-11 UTC: root main d67151175f2f39864a37ff80a02a30016ad8f5e3,
plus uncommitted portable protocol and documentation changes. m1n1/Mu pins and
local overlays remain unchanged. Inspected pinned rust/src/adt.rs
get_reg_container and official Asahi T8112 DTS at 77cb8f24. Apple cell groups are
little-endian, with widths from each parent; ranges map complete register
extents through every ancestor. No physical address may be inferred if the
range is absent, overlapping or does not cover the entire region. Add strict
translation to the read-only whitelisted collector while retaining raw pairs;
null represents an inactive zero/zero placeholder, not MMIO.
Timing correction: an initial private IOReg snapshot was read while investigating
resource ancestry before this entry. It did not access MMIO or change hardware.
The new live command is python3 tools/collect_j413.py --output
investigation/j413-macos-resources.json. Expected checkpoint: selected physical
MMIO addresses agree with T8112 DTS, unresolved nodes remain explicit. Separate
selected-SSD diskutil DeviceTreePath places it at usb-drd0; the current J413 ACPI
only exposes usb-drd1 at 0x502280000 with physical IRQ 1112 routed to guest 857.
USB0 physical IRQ 1031 is outside the guest GIC namespace too. Do not change
routes, port ownership, USB role or GPIO/power state as part of collection.
Five translation tests cover nested mixed-width buses, full extent coverage,
identity ranges, disabled placeholders, missing/ambiguous maps and overflow.
No hardware launch or resource qualification follows from a readable inventory.

After EXP-20261011-J413-009: the first strict translation correctly refused
physical addresses because IORegistry's synthetic Root was above the actual
ADT device-tree root and had no address cells. No guessed physical values were
emitted. Added an explicit device-tree root boundary plus a regression for that
wrapper and ambiguous roots; arbitrary missing buses are still rejected.
A new live capture then resolved all selected register pairs, including null
inactive ANS placeholders. Five selected component bases agree with official
T8112 DTS (UART0, AIC, USB0, USB1, and DockChannel IRQ bank); DockChannel's first
ADT bank 0x24eb00000 is not itself the DTS IRQ bank. HID config/data derive as
0x24eb30000/0x24eb34000. Aggregate ADT/DTS extents differ and are not declared
interchangeable. The source-port document records these limits.
Six translation regressions plus four existing J413 tests passed. No MMIO,
IRQ route, DART, USB role, power, guest layout or firmware overlay was changed.
Verdict: strict offline/live inventory translation confirmed; runtime resource
ownership and the USB0 SSD versus guest USB1 mismatch remain unqualified.

Final source verification for EXP007/EXP009: complete root suite ran 323 tests
in 5.960s, 322 passed and one expected skip. The packet sanitizer harness and
Windows ARM64 object checks passed. .local/asahi-port-tests-final.log SHA-256
476d38b91417647453c85fd776834264eefb9b42d7a08cc60dd04d6c095f4d0d. No further firmware build or hardware launch was performed.
EXTERNAL_SETUP/ASAHI_PORTS document the backed-up unchanged physical partitions,
new directory-only artifact staging, source licenses, root wrapper correction,
USB0/USB1 mismatch and remaining autonomous/DMA/driver contracts. Deletion and
reconstruction of disk7s2 remains pending user approval; no .sys or GPU support
is claimed. All Apple binaries, installer binaries, backup account XML and raw
IORegistry captures remain untracked local/private artifacts.

## EXP-20261011-J413-010 — build a board-specific autonomous UEFI experiment

Before run, 2026-10-11T10:46:12Z: main 17f4f907ac4f92f6ebdc7cee1e64b0d9951f871f; m1n1 9cd80ac652ac404e92ae279deeaec8c629d7d184 and Mu 8b4dc4b4e3ff8606d0af36163acf9de79b7b4737 with the previously recorded root overlays/patches. Inspected hv_autonomous_runtime.c, hv_launch_golden_j313.c, hv_launch_j313.c, hv_guest_cpu_state.c, heapblock.c, smp.c, hv.c, hv_vgic.c, Mu PrePi/MemoryInit and J413 FDF/PCDs; compared with the pinned Asahi T8112/J413 DTS, live resource capture and prior Microsoft ARM64/UEFI requirements. The installed image is not a clean-source M2 launch reference.

Hypothesis: the clean autonomous pipeline can be compiled for the actual J413 layout and source-required CPU/IRQ invariants, without impersonating the hardware-validated J313 snapshot. Change only the autonomous board contract and bounded boot-data placement; preserve existing shared CPU, display, vGIC, USB1/DART and NVMe initialization for this initial UEFI experiment. Host owns physical initialization, guest memory and interrupt translation; Mu owns guest topology and firmware allocation; Windows runtime remains unqualified. Fixed guest reservations must fit live RAM and stay above a bounded host heap, with copied boot data fitting the firmware/bootargs gaps before any guest write.

Build/verification intended: new portable planner regressions; root suite; existing m1n1 host suite; scripts/build-j413-boot-experiment.sh using the native ARM64 Docker image and pinned overlays, two distinct stages, current J413 DEBUG FD, physical display/UART only. No hardware launch/install command is authorized by this experiment entry: leave ESP, boot policy and partitions unchanged. Recovery artifact remains the privately captured internal ESP image SHA c3c05822c9bdf82ee3fd977621d5e54158662465527a4b64aa6da3b76398384b plus macOS. Record build source diff, artifact manifest and hashes afterward. Expected software checkpoint: nested CRC/size checks and truthful J413 metadata; next physical checkpoint must be visible UEFI, with stop messages photographed if it rejects live reservations. Failure criteria: source contract mismatch, planner overlap, compiler errors or unverifiable artifacts. A source contract is not a J413 golden hardware capture and no successful Windows boot is claimed.

EXP010 first build result: GCC rejected the previously added T8112 IRQ-capacity call in hv.c because aic.h was not included; the earlier host IRQ tests did not compile that hardware translation unit. No artifact or launch resulted. Add its owning declaration include to the IRQ patch and retry the same build. Planner/source-contract tests and the legacy J313 board guard passed (12 focused J413 tests). This is a compile correction, not a change in hardware sequencing.

EXP010 second build result: all new J413 C translation units compiled, but Rust 1.99.0 (b940084d7 2026-09-28) emitted an undefined wcslen in adt_get_reg; this bare-metal link has no corresponding libc symbol. No complete boot image or launch. Pin the Docker Rust toolchain to 1.85.1 rather than adding an unreviewed libc shim, rebuild the image, and retry. The pin is a build reproducibility change, not a hardware protocol change.

EXP010 third build result: Rust 1.85.1 eliminated the freestanding link error; both stages linked and nested image size/CRC validation passed. Publication stopped before copying to the final output because artifact_manifest.py could not import tools.j413_platform in direct-script mode. Correct its repository import path and add a provenance regression. No image was installed. Before retry, extend the existing source-overlap gate to require the five T8112 DCP carveouts named by kboot.c to be disjoint from guest RAM; absence or overlap must stop before copies rather than make those regions allocatable to Mu. The fixed reservations remain hypotheses checked at runtime.

EXP010 fourth build result: two stages and verified J413 boot.bin produced with Rust 1.85.1. Offline comparison with the live CPU inventory then found a new validation defect before any hardware run: ADT reg encodes P cluster/core as 0x100..0x103, while architectural MPIDRs are 0x10100..0x10103. The initial gate compared the two namespaces and would always reject this Air. Correct only that gate, add independent live-value regressions, and rebuild; supersede the preceding unlaunched candidate hash 9d8ca1d9ceb6364c6cd46126877099d02ec37cb29f4ba87689ce730ed94c83b0. No hardware state changed.

EXP010 final source review before retry: compiled Mu PcdFdSize is 0x1e00000 while J413_EFI.fd is 0x1d88000. Reserve the entire declared FD slot when placing SEPFW/log, fill the unused trailing blocks with FDF ErasePolarity=1, and clean that complete interval. Add a regression that SEP starts at 0x852eb4000 instead of the shorter file end. The previous unlaunched candidate is superseded. This does not establish that copied Apple firmware is operational; it keeps the guest memory layout internally consistent.

After EXP-20261011-J413-010: final J413 source compiled with GCC 13.3.0 and Rust 1.85.1 (4eb161250 2025-03-15). Both stages linked, nested decode/CRC/size verification passed, and the decoded FD matched clean J413_EFI.fd SHA 12409354b231ab22dd3d2c80982d8ebcc1a16fdf75e13cbe1983f6098c exactly. Final boot.bin is 2688096 bytes SHA 16020107c5bdf2096fcbf68eab2630e35e52dae1c283014d3485ee759f910806; stage0 SHA 3bfb1265382ec030e7a941c173f2cbaf46f2122789b7dde42039cdb2adc6c53b; stage1 SHA f4e4cb631a0a6a418fa768b017019beb514c3e8b3e8b588f19e453b1337a0319. Artifact path dist/j413/boot-experiment; profile DEBUG physical/UART, manifest flags 5; no USB proxy host required by this profile. TOOLCHAINS.json SHA baf2dd449fd89d3a6dea65502898e0755bbca18e716daa3a237411b440500172. MANIFEST.json SHA 38d554b7d0474ea80afd8df4a8c364ebc4cbfd29a8eadce55950abb250520b16.

Full root suite ran 325 tests, 324 passed and one expected skip. Complete existing m1n1 C host suite passed, plus new sanitizer-covered planner/source-contract and J313-rejection regressions. The five DCP reservations are checked before guest writes. Compiled collector still inherits a boot-CPU register template for secondaries rather than individually reading their registers; shared DMA/controller/CPU/power behavior remains unqualified. No independent J413 golden capture was created. No hardware launch, stop code, CPU_ENTRY, storage/input or accelerated frame exists. Verdict: complete experimental-image build confirmed; native Windows boot remains inconclusive until physical testing.

Recovery inspection: the UEFI APFS stub is mounted read only. Its original Finish Installation resource boot.bin is 3866760 bytes SHA 9108947c13d9275fafa80dd4c996b63d3c86c9d9a071eaa4de35e1953bda410c. The stock step2 script personalizes its resource kernel from paired 1TR with interactive owner credentials. A raw J413 experiment can use that route without writing the unmountable internal ESP, but changes to boot policy and the eventual reboot require the operator in Recovery. No replacement or step2 execution occurred. The separately preserved ESP image remains unchanged. Next experiment: operator installs the recorded candidate into this stub only, preserves the old staging file, enters paired Recovery and records the visible preflight/UEFI checkpoint. Physical FAT32 SSD reconstruction remains separately pending.

## EXP-20261011-J413-011 — preserve the Recovery staging kernel and copy the experiment bundle

Before run, 2026-10-11T11:00:00Z: prepare a private directory on the already selected external SanDisk without changing partitions. Copy verified experimental boot artifacts and an original APFS raw-kernel staging backup; rehash each destination. Include Recovery instructions tied to this candidate, not a runnable unattended install. Root/submodule source pins remain those of EXP010 with the recorded edits; no live guest or MMIO access. Preserve both local originals. Expected checkpoint: byte-identical candidate/backup copies and clearly pending boot-policy/media actions. Never publish Apple/Windows binaries, owner information, raw plist or the old kernel backup to GitHub.

After EXP011: the initial copy2 attempt copied one metadata file then stopped because exFAT rejected chflags metadata (EINVAL); no partition or existing file was changed. Retried within the same new private workspace using byte copies, verified all eight binary/manifest/toolchain/original-kernel files by SHA-256, and included static source status plus Hebrew Recovery instructions. Local originals retained. The original staging-kernel and candidate hashes match EXP010. Instructions target the existing stub and were not executed; the stub stayed read only. No partition, boot policy, resource replacement, reboot or Windows launch occurred. Verdict: private experiment preparation confirmed; operator Recovery and physical runtime evidence remain required. Preserve/regenerate this workspace too before any future SSD reconstruction.

Before final compatibility build for EXP010: build the unchanged J313 configuration with the applied shared safety/declaration patch using the same native Docker/GCC/Rust toolchain, make clean then make -j4 without J413 or stage role flags. This verifies that conditional J413 objects/identity/planning do not break the default build. Do not package, publish as a release, install or launch this compatibility binary; recorded J413 dist artifacts remain untouched.

After final EXP010 compatibility build: default J313/development configuration compiled and linked successfully with the shared patches, GCC 13.3 and pinned Rust. No compatibility artifact was installed or promoted. J413 dist hashes stayed unchanged. J413 additive sources/patches SHA 7bc71f96cfe4cc470d2f23671cf4f6c18a5890986a548a092e8549208d346573 matches its manifest. Root and submodule test/build logs remain private .local artifacts.

## EXP-20261011-J413-012 — identify the existing Asahi bootstrap without changing it

Before run, 2026-10-11T11:18:35Z: user reports an existing Asahi UEFI boot installation. Root main 14875ecd095f57f962e605378702d0828d2c4b0d; submodule pins and applied source hashes unchanged from EXP010. Hypothesis: the original stage-1 resource identifies the existing internal ESP, so a new Asahi installation or Recovery re-personalization should not be assumed necessary. Read only the original staging binary, diskutil partition metadata, preserved ESP copy and clean candidate; compare hashes, extract the bounded chainload setting and decode both nested manifests. Do not inspect owner credentials, alter LocalPolicy, mount writable, update ESP, reboot or launch Windows. Recovery artifacts are the unchanged ESP capture and original staging kernel recorded in EXP010. Expected checkpoint: matching stage-1 destination PARTUUID and clear differentiation of installed payload from clean candidate. A matching configuration is not proof of the active personalized kernel or a successful UEFI boot. Record a private sanitized result; ask which screen actually appears.

After EXP-20261011-J413-012: read-only audit confirmed the original resource's m1n1 v1.9.9 marker and chainload PARTUUID matches the existing internal ESP, targeting m1n1/boot.bin. Original resource SHA remains 9108947c13d9275fafa80dd4c996b63d3c86c9d9a071eaa4de35e1953bda410c. Preserved ESP payload SHA 6c6f7c9d7fd532b9475f07ed2828987fc25a9cbe25f6b7f9d7803a43f2d6983e differs from the clean candidate SHA 16020107c5bdf2096fcbf68eab2630e35e52dae1c283014d3485ee759f910806; both outer and inner CRCs decode, with old flags 1 and candidate flags 5, different Mu FD hashes. Private sanitized result .local/asahi-existing-audit.json SHA 855c981cbcdb6f218f62c83f88de723ef3730ceb7cb2165ee3798ad0aae1b792. No live raw partition read/write, active-kernel inspection, mount mutation, MMIO access, boot policy change or reboot. Verdict: staging configuration identified; active UEFI path and M2 hardware behavior remain inconclusive. Correction to EXP010/EXP011 next-step wording: existing stage-1 personalization can be reused if active; Recovery raw-kernel replacement is an alternative, not a mandatory consequence of trying this candidate. Await actual screen identification and a verified ESP access path before installation.

## EXP-20261011-J413-013 — eliminate proxy takeover and fallback in the J413 image

Before run, 2026-10-11T11:29:20Z: root main dcdc2c10df5f30755a8ef3675d70d7f46bf63932; pinned submodules unchanged from EXP010. User reports seeing Running proxy... during a physical boot. Exact installed hash, earlier failure lines and elapsed time were not supplied, so this is an inconclusive operator-reported launch, not proof which candidate or stage ran. Inspected main.c/run_actions, hv_bootstrap.c, hv_autonomous_boot_runtime.c/profile.c, uartproxy.c/run, hv.c/hv_tick and hv_exc.c before changing behavior. Confirmed source defect: the J413 builder selected physical/UART flags 5, enabling host transport/takeover, and main.c enters proxy on autonomous/bootstrap failure or missing payload. The prior statement that UART meant no host proxy was incorrect. No Asahi/Mu/Windows MMIO, DMA or hardware ownership contract changes are needed for this policy correction; pinned primary sources and guest firmware remain those of EXP010.

Hypothesis: a physical/debug-off flags-1 candidate with a compiled M1N1_NO_PROXY boundary can automatically attempt the same guest and stop visibly on failure without opening an interactive command transport. Change only host interaction policy; retain normal guest IRQ/timer handling, USB platform power, physical display and original hardware safety gates. Reject transport-dependent manifests in both bootstrap and guest stages. Disable early/fallback proxy entry and tick-driven host command polling; guard the shared uartproxy entry for unexpected exceptions. Preserve previous image/manifest privately and the original ESP/staging-kernel recovery artifacts. Intended verification: executable host startup and proxy-entry regressions, flags/profile tests, full root suite, both native ARM64 stage builds with unchanged Mu FD, nested CRC/hash checks and symbol/callsite checks. Build command J413_SKIP_MU=1 scripts/build-j413-boot-experiment.sh. No install/reboot command will be executed by this run; sudo ./scripts/install-esp.sh install --disk disk0s4 --image dist/j413/boot-experiment/boot.bin is the later operator checkpoint. Expected physical result is Mu UEFI or the last failure line followed by J413 STOP; a visible stop is not successful Windows boot. Logs and manifests remain .local/dist; raw source pin/diff hashes are recorded by the build manifest.

EXP013 verification before compatibility run: both no-proxy stages linked and the nested image was packaged successfully. New candidate is 2513640 bytes SHA 0f498e74e76912c906e48bdb556405433f3c193ab3f82d33fbb4a5446726ebdd; both manifest flags are 1 (physical/debug-off), decoded Mu FD unchanged. Four new executable regressions pass, including both stage roles, missing payloads, startup/exception proxy entry and legacy startup behavior. Root suite ran 329 tests, 328 passed and one expected skip. Native ARM64 main.o does not reference uartproxy_run or USB gadget initialization; uartproxy.o does not reference proxy_process, iodev_read or command polling. Before final compatibility verification: run the unchanged m1n1 host suite and rebuild the default J313/development image without M1N1_NO_PROXY; do not install/package it. Keep J413 dist artifacts fixed and store the object-boundary evidence before make clean.

After EXP-20261011-J413-013: full m1n1 host suite passed; default J313/development configuration also compiled and linked without the no-proxy macro. All root platform patches apply in order to the exact clean pinned m1n1 source and each reverse-check succeeds after the full stack; staging is idempotent. The additive loader/patch source hash matches the candidate manifest. Original Mu FD and platform hardware layout are unchanged. Native boundary checks and portable tests establish command transport is disabled in this new image, not that the operator reached Mu or Windows. No installation, boot policy mutation, SSD reconstruction or physical relaunch was performed. The earlier UART profile is superseded as an inappropriate host-interaction policy. No actual Windows stop code, CPU_ENTRY, input/storage or GPU success was captured. Verdict: software policy correction and build confirmed; reported prior proxy boot remains inconclusive as to its precise source/failed stage. Next: operator installs the recorded no-proxy candidate through the existing ESP script, records the installed SHA and preceding failure line or visible Mu screen.

EXP013 private log .local/j413-no-proxy-build.log SHA-256 f8f5506eac2978039c255230f9f3add4b72574a40d1a21dac9774c189309d579.

EXP013 private log .local/j413-no-proxy-root-tests.log SHA-256 75c52def67231ea8a69ab8cd03d645ed283781f1e85e0179659a15b1f5857c0a.

EXP013 private log .local/j413-no-proxy-host-tests.log SHA-256 791f1dba59e067504434beb3eacad3ef031f7ce98b27a231cc1f6b90bdbf9fee.

EXP013 private log .local/j413-no-proxy-arm64-symbols.log SHA-256 7ed74656122010959f4d549f6fa5534ec4bbc4b83358f69a656af0f7f59d6249.

EXP013 private log .local/j413-no-proxy-j313-build.log SHA-256 bc000e337f82298df6eaf5c57f1109c14530b52bffee24e41a77a07bf3850045.

EXP013 exact final artifacts: {"J413_EFI.fd": {"role": "guest-firmware", "sha256": "12409354b231ab22dd3d2c80982d8eb2da8ebcc1a16fdf75e13cbe1983f6098c", "size": 30965760}, "TOOLCHAINS.json": {"sha256": "baf2dd449fd89d3a6dea65502898e0755bbca18e716daa3a237411b440500172", "size": 160}, "boot.bin": {"role": "standalone-bootstrap", "sha256": "0f498e74e76912c906e48bdb556405433f3c193ab3f82d33fbb4a5446726ebdd", "size": 2513640}, "m1n1-stage0.bin": {"role": "autonomous-stage0", "sha256": "2cbdb1567b140d81cdabecc1533b46a9ed02b7cdfb678b7bf86768523d378813", "size": 1294336}, "m1n1-stage1.bin": {"role": "autonomous-stage1", "sha256": "ec35f3587a24a9a95f1513f97476e84229a4efa80ba5b64661277dc03f116634", "size": 1294336}}. Loader source/patch SHA 75bd0487c301ff75dded4beed226f7ccb878c63e332e59d4fbac50625a097237. TOOLCHAINS GCC 13.3 / Rust 1.85.1; source root dcdc2c10df5f30755a8ef3675d70d7f46bf63932 with the recorded policy edits and unchanged submodule pins; full tracked source diff hashes in MANIFEST.json. Both manifest flags 1. Public sources will be committed separately from private Apple/Windows/compiled artifacts.

Before EXP013 private staging: create a separate no-proxy bundle on the confirmed SanDisk, leaving the previous UART bundle and ESP backup untouched. Copy and SHA-verify the complete current candidate artifact set and original staging-kernel backup; include existing ESP install instructions. No boot/partition writes.

After EXP013 private staging: new no-proxy bundle created separately from the preceding UART bundle; all current artifacts, manifests, documentation and original staging backup copied byte for byte and verified. Candidate SHA remains 0f498e74e76912c906e48bdb556405433f3c193ab3f82d33fbb4a5446726ebdd. Private path is recorded in .local/j413-no-proxy-bundle.json. Existing ESP install/restore commands are instructions only; not executed. No physical boot or partition mutation occurred.

## EXP-20261011-J413-014 — operator photo and boot-data contract audit

Before software run, 2026-10-11T11:53:43Z: root main a762e582754777bb146f546d3b2218fc6035e9f1; pinned m1n1/Mu unchanged. Operator supplied IMG_5745.HEIC SHA eb307a72f19d32a338f2d6b82990beca9ce27d7d6d6b933336c8ea3b5077b8ef after booting the no-proxy path. Retrospective observation: image-valid compressed=0x102340 firmware=0x1d88000; flags=1; source-required J413 gate; PRE_HV_INIT PASS; cpufreq PASS; J413 STOP: live boot data does not fit fixed Mu slots; launch returned stage=3 error=2; proxy disabled. Guest RAM end 0xa00000000 and size 0x1b0000000; display 2560x1664 depth 30 base 0xbe18b0000. Exact installed hash, TC/SEP sizes and elapsed time were not supplied. This proves the reported failure precedes Mu; the shared message cannot distinguish missing source properties from a failed placement plan. No Windows stop code or Mu/CPU_ENTRY was observed. Raw photo/IORegistry remain private.

Hypothesis: keeping only Mu's ADT/FD/bootargs pointers fixed while placing dynamically sized TC/SEP/log after bootargs in a bounded arena avoids artificial gap limits. Mu must reserve the entire corresponding boot-data span before DXE allocation. Inspected pinned Asahi load_raw/layout, m1n1 boot data/source gates and Mu AppleDTLib, MemoryInitPeiLib, PrePi assembly and ArmLib cache entry points. Boot loader owns copies and checked guest intervals; Mu owns allocation/HOB exclusion. No hardware registers, IRQs, DMA or Windows driver behavior changes. Preserve prior candidate and recovery images. Add size/property-specific diagnostics and executable planner/HOB regressions. Intended build scripts/build-j413-boot-experiment.sh (including fresh Mu); test root and host suites and exact patch reapplication; record hashes before operator command sudo ./scripts/install-esp.sh install --disk disk0s4 --image dist/j413/boot-experiment/boot.bin. No install/partition/reboot by this run. Expected checkpoint: BOOTDATA sizes/placement and entry past the photo's stop, or a precise source/arena rejection. Hardware verdict stays inconclusive until the next photo.

## EXP-20261011-J413-015 — audit Mu PrePi stack initialization

Before software run, 2026-10-11T11:53:43Z: same pins. Independent source defect: _ClearStack compares its high-DRAM cursor to the stack size rather than its end; its adjusted cursor is passed as stack base. Cache calls also clobber caller-saved registers. Correct only the J413 stack contract, retain legacy branch, compare cursor to exclusive end and pass saved base/size after calls. Exercise actual assembly natively with guard pages/canaries and cache-call clobber stubs. Include this independently tested prerequisite in the next candidate and explicitly record it alongside EXP014; a future hardware failure cannot be attributed to one fix from a combined candidate alone. No runtime success claimed.

EXP014/015 first build result: Mu C compiled, but checking the preprocessed PrePi assembly showed the legacy stack loop. ASM_FLAGS applies after preprocessing; add J413_BOOT_CONTRACT to PP_FLAGS instead. Native assembly regression using Mu Clang passed, including guard pages and deliberately clobbered caller-saved registers. m1n1 stage build then rejected MIN (no owning macro in its freestanding utilities); use an explicit minimum expression. No final boot.bin published or installed. The preceding preserved candidate remains unchanged. Repeat the same build with these toolchain corrections and inspect the generated assembly and memory HOB diagnostics before publishing.

## EXP-20261011-J413-016 — PSCI topology bookkeeping audit

Before software run: inspected hv_psci_init/update_power_level_limits/get_parent_nodes/coordinate_power_states and current ARM Trusted Firmware psci_setup.c/psci_common.c (BSD-3-Clause reference only; no external source copied). Confirmed two inherited C defects: the previous-parent array is uninitialized during topology counting, and state coordination uses node zero's sibling count instead of the selected parent's. They can corrupt bookkeeping independently of actual M2 power register behavior. Initialize both traversal arrays and select the actual parent count; no registers, advertised capabilities or suspend policy changes. Execute the actual affected functions with the independently observed 4+4 J413 core grouping under sanitizers and poisoned automatic variables; verify cluster counts 4 and system count 8 and full-node selection. Include this independent prerequisite in the combined EXP014/015 candidate and report the combination explicitly. Hardware CPU_ON/suspend remains unqualified. No installation or reboot.

After EXP014/015/016 software verification, 2026-10-11T12:05:55Z: corrected build completed. Fresh Mu CLANGPDB DEBUG plus both GCC 13.3/Rust 1.85.1 J413 no-proxy stages linked and nested CRC/size checks passed. Both flags=1; decoded FD matches fresh J413_EFI.fd exactly. Generated PrePi .ii has cmp x12,x1/b.lo and saved x23/x24 arguments; linked Sec contains reservation diagnostics. Complete root suite ran 334 tests: 332 passed, two skips (existing optional test and native ELF assembly); the actual ARM64 assembly test passed separately in the native Docker container. Complete m1n1 host suite passed and default J313/development build linked without J413/no-proxy macros. Exact clean pinned clones accepted all five m1n1 patches and the Mu patch; reverse checks and byte comparisons match every modified compiled file. Staging is idempotent. Private native PSI sanitizer run initially lacked Clang compiler-rt; run the portable PSCI regression with GCC sanitizer runtime instead (Mac Clang sanitizer run already passed), keeping actual Mu assembly with Clang. No test failure is claimed as hardware evidence.

EXP014 final artifacts: {"J413_EFI.fd": {"role": "guest-firmware", "sha256": "cbeb2c6e39b59eb0fed4e18ee249dd682d2ee6d855a3fa4543b62cbf7565d15f", "size": 30965760}, "TOOLCHAINS.json": {"sha256": "baf2dd449fd89d3a6dea65502898e0755bbca18e716daa3a237411b440500172", "size": 160}, "boot.bin": {"role": "standalone-bootstrap", "sha256": "a5f180de1b24c79fdedd39ee2944862b366dace275b1df5d0dbcaabb5219c800", "size": 2513984}, "m1n1-stage0.bin": {"role": "autonomous-stage0", "sha256": "fb8e0a898e92e1e122f71b40f2724775e9c66a22d577a985c1d4f4e48105e0e1", "size": 1294336}, "m1n1-stage1.bin": {"role": "autonomous-stage1", "sha256": "7980478da6a2f77c515ce894be0acf225977dfa703e0f0afdbf290184f479ab9", "size": 1294336}}. Mu source/patch SHA f78e1017ba1a2917e0a065e89866ffb1370e72d77ee868723ba0a9f191f93af6. Loader source/patch SHA 96acbcbbd16ef6538b8a54635d7f83360a8b755996e6b8ed99ae357d5679e1a2. Root build source was a762e582754777bb146f546d3b2218fc6035e9f1 with manifest-recorded dirty diffs and exact pins. Previous no-proxy image 0f498e74e76912c906e48bdb556405433f3c193ab3f82d33fbb4a5446726ebdd preserved in .local/boot-before-bootdata-fix and its previous private SSD bundle. Original ESP image SHA c3c05822c9bdf82ee3fd977621d5e54158662465527a4b64aa6da3b76398384b remains recovery evidence.

Verdict: source defects and software corrections confirmed; the photo proves a pre-Mu stop only. New artifact not installed or launched; no Windows stop code, CPU_ENTRY, USB storage/input or GPU frame. The next operator experiment uses the existing ESP install command recorded above and captures BOOTDATA sizes/addresses and the last preflight/Mu checkpoint. This candidate combines three independently tested prerequisites; no isolated hardware attribution is claimed. No boot policy, partitions or physical Setup media changed.

EXP014/015/016 final native regression result: all four tests passed using GCC ASan/UBSan for C and Mu Clang for actual AArch64 assembly. Implementation commit 3c7c5ee84aaece2acf991887895efe356b64a5be contains the source corrections; no physical relaunch occurred.

Private verification log .local/j413-bootdata-build-final.log SHA-256 163088b2c5c94cd2b042191c67b588708ca8ef3e480a5263d355842385479ece.

Private verification log .local/j413-bootdata-root-tests-final.log SHA-256 7a46e36d08bb3b64a1b2d485f40530954690385db88fecd49842fb6f63d4835b.

Private verification log .local/j413-bootdata-host-tests.log SHA-256 791f1dba59e067504434beb3eacad3ef031f7ce98b27a231cc1f6b90bdbf9fee.

Private verification log .local/j413-bootdata-j313-build.log SHA-256 a843f4e16a645b54dfbbefa13c87a3277d06e0e29e926fcbec0982f724b9ba20.

Private verification log .local/j413-bootdata-native-tests-final.log SHA-256 b292677ada81b137e5503359026d0127c29b0611c144126743323a94ae6bfd25.

Before EXP014 private staging: create a distinct byte-verified boot-data candidate bundle on the confirmed SanDisk volume UUID, preserve original staging backup and older bundles, include current install/restore instructions and audit. Copy only within a new private directory; no partition, boot policy or ESP updates. Source archive will reference the final committed tree.

After EXP014 private staging: distinct bundle /Volumes/Untitled 2/windows-on-m2-workspace/uefi-bootdata-r4o2vt98 created on the confirmed SanDisk; all 10 artifact/metadata/backup/document copies SHA-verified. Original staging backup and both older experiment bundles retained. Current candidate SHA a5f180de1b24c79fdedd39ee2944862b366dace275b1df5d0dbcaabb5219c800. Install/restore instructions were written but not executed; no boot policy, ESP, partition or media reconstruction changed. Source archive will be added after the ledger commit is fetched; it does not affect the artifact.

EXP014 private staging completion: committed source archive source-44123be.tar (99840000 bytes; SHA 0c351576c3116c75a8d02efa6b304dfd6870786a8fc7efaadc4057a6d26dfb74) added to the distinct private bundle. All eleven listed files rehashed successfully after source commit 44123beec7d868993f9eb446ca0e9481b4dce78b was fetched; tracked implementation/ledger match origin/main. Root change-ledger schema still passes; only intentionally staged-source submodules are dirty. No install, launch or partition action occurred.

## EXP-20261011-J413-017 — replay framebuffer source rejection and compare upstream

Before software run, 2026-10-11T12:19:07.334826+00:00: main dd06c633b611327cbe28560153c899df99fb29b3; m1n1/Mu pins unchanged. New operator photo IMG_5747.HEIC SHA 272dcad3f72961191f96bef9c6960017525eb6ca8c694bbe4a936195705d17b5 shows compressed=0x10242c, firmware=0x1d88000, flags=1; PRE_HV_INIT and cpufreq pass. BOOTDATA sizes ADT=0x5c000 TC=0x58000 SEP=0x5dc000 log=0x40000; placement TC=0x8533ec000 SEP=0x853444000 log=0x853a20000 top=0x853a60000 limit=0x85e000000. Then source region 2 overlaps guest or is outside RAM; stage=3/error=2; proxy disabled. Region 2 is the physical framebuffer 0xbe18b0000; normal usable RAM ends 0xbde568000. No Mu entry or Windows stop code; exact installed hash/duration unavailable. Thus EXP014 packing is observed to pass, while the source gate wrongly treats usable memory as the full readable DRAM extent. The framebuffer address was available in the preceding photo and this mismatch should have been caught earlier.

Source comparison: pinned memory.c maps ram_base=ALIGN_DOWN(phys_base,BIT(32)) through mem_size_actual, including non-TZ carveouts; mcc.c unmaps protected TZ regions and records them. Assisted hv/load_raw also uses mem_size_actual for RAM mapping and preserves normal usable mem_top for guest allocation. sysctl reports 17179869184 installed bytes on this Air. Fix only source-range validation: use the same full physical mapping extent, reject overflow/guest overlap and MCC protected regions, retain the normal-RAM guest allocation cap. Execute actual source validator with the photo values and negative cases, replay all visible boot-data dimensions, inspect following gates against available live values, then build both no-proxy stages reusing byte/source-verified unchanged Mu. Build J413_SKIP_MU=1 scripts/build-j413-boot-experiment.sh. Preserve previous candidate and original ESP backup. No hardware launch or installation; next artifact is experimental, not a claim of boot success.

Read current primary project evidence: paulsmir/windows-on-m1 README and STABLE_8CORE_INPUT document Windows desktop/eight-core success on J313 via assisted launch; standalone cold boot requires separate qualification and only J313 is supported. GPU work is on a separate M1 branch and not performant. NT-for-ASi is the upstream project; the deprecated AppleWOA pointer is obsolete. No reproducible autonomous J413 Windows result was found in the searched primary sources. No external implementation copied.

After EXP017 software verification, 2026-10-11T16:32:43.464096+00:00: native build completed; unchanged Mu reuse passed exact overlay/source and byte identity checks. Both nested flags=1 and decoded FD matches cached verified firmware. Complete root suite: 335 tests, 333 passed, two expected skips. The actual source guard passes the photographed framebuffer and rejects out-of-DRAM, guest overlap, protected TZ overlap and overflow under ASan/UBSan; all photographed packing destinations reproduce exactly. Fresh ioreg -a -l capture confirms eight CPU reg/cpu-impl-reg container sizes, eleven nonempty arm-io ranges, and seven protected/DCP intervals disjoint from guest RAM. USB1/DART1/UART resolved bases and IRQs match the preflight constants. Raw capture remains private; only whitelisted properties appear in investigation/j413-source-memory-audit.json. These checks do not execute RVBAR writes, EL2 mappings, DMA or Mu. Idempotent staging and current source digests match the manifest.

EXP017 artifacts: {"J413_EFI.fd": {"role": "guest-firmware", "sha256": "cbeb2c6e39b59eb0fed4e18ee249dd682d2ee6d855a3fa4543b62cbf7565d15f", "size": 30965760}, "TOOLCHAINS.json": {"sha256": "baf2dd449fd89d3a6dea65502898e0755bbca18e716daa3a237411b440500172", "size": 160}, "boot.bin": {"role": "standalone-bootstrap", "sha256": "96478bacc22198e9b039549e6ed65cadfef004b418577d168f472c8734500efa", "size": 2514260}, "m1n1-stage0.bin": {"role": "autonomous-stage0", "sha256": "942529835381d563b9b35593364f466733b2edfad1b3a7f7b3f725ca34cdca1b", "size": 1294336}, "m1n1-stage1.bin": {"role": "autonomous-stage1", "sha256": "3b060885526982f9890c46622de75b1908fb126b3707ec46458f2e6e85d92c0b", "size": 1294336}}. Loader source digest 7f6581537be10a20d95c1a9f25d1b559ce06326074b7875d80f94cfd7c8c4949; Mu digest f78e1017ba1a2917e0a065e89866ffb1370e72d77ee868723ba0a9f191f93af6. Private logs SHA-256 {"j413-source-build.log": "c1ecc9b73fe68cb0b9c99b3b3e95d61ee1ecc27b3ac66d5aaba187995411eb51", "j413-source-root-tests.log": "50d52cb3c39b4b4dd9c79c8dc74d557b44c731cb5f2670d0e90f0c2fbe4d0534"}. Previous candidate and original recovery copies preserved. No install, boot-policy, partition or reboot operation. Verdict: confirmed source defect corrected; new physical boot remains inconclusive. Next hardware checkpoint is J413 SOURCES followed by later preflight/Mu or a named stop; no Windows stop code, CPU_ENTRY, USB or GPU runtime evidence.

Before EXP017 private staging: create a new source-bound candidate directory on the confirmed SanDisk VolumeUUID; copy and hash all artifact files, current audit/operator instructions and preserved original staging backup. Preserve all earlier bundles. No ESP, boot policy, partition or recovery installation.

After EXP017 private staging: /Volumes/Untitled 2/windows-on-m2-workspace/uefi-source-o9yqdxq1 created; 12 artifact/metadata/audit/recovery copies byte-verified. Current boot.bin SHA 96478bacc22198e9b039549e6ed65cadfef004b418577d168f472c8734500efa. Original staging backup and older bundles retained. Install/restore instructions saved but not executed. No partition, ESP, boot-policy or reboot operation.

EXP017 publication: implementation commit 0bbfefd6ecf05ffde4bfc122281b590e6686acbf owns the tested correction and primary-source comparison; CHG-20261011-022 records status implemented. Exact clean pinned clone accepts all five m1n1 patches, reverse checks pass and all modified tracked source bytes match the native build. Private SSD source bundle is prepared; physical launch remains pending.

## EXP-20261011-J413-018 — first photographed Windows boot manager and local boot UI

Before software run, 2026-10-11T16:49:40.001122+00:00: main 8e28e4abe8af777cf256d45ac51287ec024564aa, unchanged submodule pins. Operator reports about one minute with lit black panel, Mu color bars then Windows Recovery; built-in keyboard/trackpad unresponsive. IMG_5754/5755 SHA 4b407c5c3b660085ecb1ca53e37ee74b0d9732a0a37136d4e4bbc9e23afef8b7, e5572aeac74bb6f64aaa884c763cae45d07d7990f6177f2849e88685ee5e53fd. IMG5755 shows 0xc000000f and required device inaccessible; no kernel stop code or proof kernel ran. Installed hash unavailable. This confirms physical firmware/Windows boot-manager progress beyond EXP017 source rejection, not Windows Setup/driver qualification.

Owning sources inspected: m1n1 fb/main/display/hv_autonomous_runtime/vuart; Mu SimpleFbDxe, DeviceBootManagerLib, BootGraphicsProviderLib, ColorbarsDxe/ColorBarDisplayDeviceStateLib, WindowsAutoBootDxe and J413 DSC/FDF. Color bars are intentional device-state presentation, not framebuffer corruption. Internal ESP audit BCD references absent boot.wim/boot.sdi; exact runtime-selected volume remains unobserved. M2 HID is DockChannel/RTKit and no linked J413 Windows/UEFI input driver exists. Microsoft BCDEdit /set documents sos and bootlog; neither is arbitrary live kernel printf nor useful before kernel entry.

Single observable change: boot presentation/diagnostics only. Replace m1n1 Asahi mark with text UEFI BOOT, preserve visible local console, draw milestone bar and guest Windows-shaped mark before DCP presentation; use a J413-only Mu boot graphic provider and null color-bar display with explicit experimental-state text, print firmware handoff checkpoints. No security policy, USB/DART, guest memory, input driver or boot-selection changes. Build fresh Mu and both flags-1 stages, preserve previous candidate, verify linked UI/patch application and existing suites. No ESP/boot-policy/partition writes or reboot. Expected physical checkpoint: UEFI BOOT, named stages, logo/firmware handoff then same loader outcome. Kernel text remains a separately documented supported Windows boot-option task, not simulated output.

EXP018 software attempts: initial build could not connect to stopped Docker after operator reboot; restarted the existing Colima build environment. Initial root staging test fixture lacked the three newly patched pinned Mu files; extend its source fixture, preserving edit-rejection assertions. Native fresh Mu build succeeded, including the J413 provider and null color-bar display instance. Added pre-presentation guest text/cache clean, explicit inherited-logo clearing and framebuffer flush; executable tests cover actual host logo body, guest stride/canaries and production BMP header/pixels plus warning-resource fallback. Rebuilt both m1n1 stages after these corrections using byte/source-verified unchanged new Mu. No intermediate image installed or launched.

After EXP018 software verification, 2026-10-11T16:57:37.211059+00:00: final build succeeds; 338 root tests, 336 passed and two expected skips. Three actual UI renderer tests pass under ASan/UBSan. Clean pinned clones accept/reverse all six m1n1 patches and both Mu patches with changed-source byte comparisons. Final nested CRC/flags=1, exact FD bytes, artifact/source/overlay digests verified. Artifacts {"J413_EFI.fd": {"role": "guest-firmware", "sha256": "d55c03ec48008fd6e7f79b447176f44f53620153b768392c10f9ae3f93fe58cd", "size": 30965760}, "TOOLCHAINS.json": {"sha256": "baf2dd449fd89d3a6dea65502898e0755bbca18e716daa3a237411b440500172", "size": 160}, "boot.bin": {"role": "standalone-bootstrap", "sha256": "a451be44591ec389e3654e85e45b809b10bde781a7a81fa8d3124def2f21f3d9", "size": 2520312}, "m1n1-stage0.bin": {"role": "autonomous-stage0", "sha256": "129c2c473cbb74e602d062745b682052601cd561234c9f8521e68b155c0568e8", "size": 1310720}, "m1n1-stage1.bin": {"role": "autonomous-stage1", "sha256": "8c74d1bf98eda3dc8b4d3e0ae6e170aaee8603b5a17e30b31404bf7e133525d9", "size": 1310720}}. Private log SHAs {"j413-ui-build-final.log": "56bfdc2d8650bafa8652b641429d49b2044489b5534b99861bd33a8ece58efbd", "j413-ui-build.log": "4e59a830d0894518118323d4ba3bd61823e78a820249666d42a002624263715a", "j413-ui-render-tests-final.log": "7359942312121d7d0da2226e68cb0953c752bf164e0cdcd90ac0ac41a9cbbcae", "j413-ui-root-tests-final.log": "a865daebf0a5308ee4a07b470f2409bc6d1f4f5268f96392affd71c64113becc"}. Current loader digest e1a32da006aa90fdeefc8a4042bbeeaffb632fb67f011b39166fd74d25bbd740; Mu digest 784d57aeafac1205aada8968586db0d3757a9d575aa4f92db50dcda033053fe0. Previous image preserved in .local/boot-before-ui-change and prior SSD bundle. Microsoft BCDEdit helper is authored but not executed; no Windows environment available to qualify it.

Verdict: photographed progress to Windows boot manager confirmed; kernel/Setup/driver execution remains unobserved. Current UI implementation software-verified but not hardware-launched. Built-in input only was tried; no USB input verdict. Recovery device/BCD selection remains unresolved and is compatible with audited missing internal Setup payloads. No raw image, ESP, boot-policy, partition, security setting, install or reboot action.

Before EXP018 private staging: create a distinct candidate bundle on the confirmed SanDisk VolumeUUID, hash all artifact/docs/backup copies and preserve prior bundles. No partition changes or ESP writes.

After EXP018 private staging: /Volumes/Untitled 2/windows-on-m2-workspace/uefi-ui-x3__dlj9 contains 13 hash-verified artifact/document/helper/recovery copies. Current candidate SHA a451be44591ec389e3654e85e45b809b10bde781a7a81fa8d3124def2f21f3d9. Older candidate directories and original staging backup retained. No operator install/restore/BCDEdit command executed.

EXP018 publication: implementation 69eee4514ad07c06152d4f41dc0556cd520cc780 owns the UI and explicit Windows boot-detail helper. CHG-20261011-023/024 are implemented only; first Windows boot-manager photograph is not proof of new UI runtime, kernel, USB input or working M2 built-in input. No operator commands executed.

## EXP-20261011-J413-019 — remove boot art and repair firmware log presentation

Before software run 2026-10-11T17:16:14.138026+00:00: main c584f5a2bb7b92d353beac5250ccebd95d824309. Operator reports same Windows loader error, static bar and stage text; requests no Windows-like mark. No new photo/hash or exact timings. The J413 keyboard warning is descriptive, not a gate disabling a driver. Source fb_update copies the whole framebuffer; hv_vuart formats each firmware byte separately and fb_console_write flushes each write. At 2560x1664 this can cause a 17 MB copy for every byte to a surface DCP no longer displays. This confirms avoidable software work, not measured attribution of the entire boot delay.

Owning change: remove marks and bars; line-buffer actual Mu UART logs and render bounded rows on the live validated guest surface only before SimpleFbDxe takes ownership. Explicit serial ownership marker disables host/guest framebuffer logging before GOP writes; preserve ordinary logs and no-proxy profile. Add real stage timestamps, not simulated progress. Preserve Mu warning graphics through FV; skip normal boot graphic. Execute actual line buffering/ownership and raster bounds under sanitizers; fresh Mu and both stages required. No Windows framebuffer overlay, security changes or input driver claim. Preserve current image before build. No install, ESP, partitions or reboot.

## EXP-20261011-J413-020 — stop selecting incomplete internal Setup media

Before software run: WindowsAutoBootDxe currently checks only BOOTAA64.EFI and explicitly excludes removable media. Preserved internal ESP has that loader and BCD but no boot.wim/boot.sdi, consistent with 0xc000000f; actual selected BCD/volume remains unknown. J413 experiment targets Setup: require loader plus EFI Microsoft BCD, sources/boot.wim and boot/boot.sdi on the same readable filesystem; accept removable BlockIo for this target only and print missing paths before handoff. Keep legacy J313 behavior unchanged. This fixes selection prerequisites, not exFAT support or WIM/BCD semantic validation. Execute the owning predicate with missing-file/open-failure/complete-media cases. Included in combined candidate at user request; any hardware result cannot isolate presentation from media-selection changes. Physical FAT32 reconstruction is not performed.

EXP019/020 software attempts: initial private editor script lacked root PYTHONPATH after writing source edits; completed staging from root before compiler use. Existing Colima build environment restarted after operator reboot. Fresh Mu and both stages linked. Inspected memory.c cache primitives: change display DMA clean to dc_cvac (point of coherency), then rebuild stages using verified unchanged fresh Mu. No intermediate image installed or launched.

After EXP019/020 software verification 2026-10-11T17:21:53.133268+00:00: 340 root tests, 338 passed and two expected skips. Five focused owning renderer/log-buffer/media-gate tests pass ASan/UBSan after final cache primitive correction. Source-buffer guest stride/canaries and permanent post-GOP non-writing checks pass. Actual media predicate closes handles correctly on every missing path and failed OpenVolume; complete media passes. Bounded 255-byte fragments preserve takeover state; subsequent log lines cannot draw over GOP. Fresh Mu build and final stages pass nested flags=1/CRC/exact FD bytes/source digests; clean pinned clone patch application/reverse and changed compiled-source byte comparisons pass. Artifact identities {"J413_EFI.fd": {"role": "guest-firmware", "sha256": "f2ff3888283fe12b2fbb3c729c5bd5a56f87849e6a96e0be1a2b848cf123e9f9", "size": 30965760}, "TOOLCHAINS.json": {"sha256": "baf2dd449fd89d3a6dea65502898e0755bbca18e716daa3a237411b440500172", "size": 160}, "boot.bin": {"role": "standalone-bootstrap", "sha256": "537dda804f96abbf89e738eb3adeb79dca19e4958c1fc172dcb5ff95a93dce2f", "size": 2518496}, "m1n1-stage0.bin": {"role": "autonomous-stage0", "sha256": "57e00fa6f52f9ac8a25ffa6a2267b37f83b9b3d1de21f61232b307bbfe3f8b22", "size": 1310720}, "m1n1-stage1.bin": {"role": "autonomous-stage1", "sha256": "376d5ba692b30cab2de2ba228821fb85628c520989096311bccff45347352419", "size": 1310720}}. Loader source digest fd1cd6b8255444f01d07f5a69c4c8c5bd104c6635e648b12b6fc4eb9238e1c31; Mu overlay digest 92a1e1ba76633b103e585367c73f919761576bf4d188e9e713bccaabd88779ad. Private logs SHA {"j413-text-build-final.log": "2a8193df2804eff9f4374bf290bdabeac047652b701ebd692e633f152e45b602", "j413-text-build.log": "d34cf8a309f3119348dbb0e619968e339b90381d952768544ef8f1b931763e51", "j413-text-guards-final.log": "e60d4b3eddca6e0358f8e5b960ab614d4b4ad9fec39311a07d382e6413da36ec", "j413-text-root-tests.log": "2feda74d6953b88de3eaa9a581f02c70e6204ab144157093424dadc678eef614"}.

Verdict: source-level presentation/performance defects corrected and media-selection prerequisites enforced; no new hardware timings, exact installed hash or physical UI/log/Setup result. Existing user report is not current-artifact validation. Faster boot, USB enumeration and Windows Setup remain unqualified. Built-in input still needs a J413 DockChannel/RTKit driver; its diagnostic message does not disable an implemented driver. Previous image and SSD bundle preserved; no kernel text simulated, no OS-owned framebuffer writes, ESP/partition/boot-policy/security changes or reboot. Next physical checkpoints: actual Mu log lines, GOP transition, complete-media selection or precise missing paths.

Before EXP019/020 private staging: copy final candidate, audit/operator instructions and prior original staging backup into a new directory on confirmed SanDisk UUID; verify hashes and retain all earlier bundles. No physical media reconstruction.

After EXP019/020 private staging: /Volumes/Untitled 2/windows-on-m2-workspace/uefi-text-bn5ri8or created with 12 hash-verified artifact/document/recovery copies. Original staging backup and earlier bundles retained. SSD physical data filesystem remains exFAT; no physical FAT32 reconstruction. Operator commands saved but not executed.

EXP019/020 publication: implementation 9045c216a9b4eac153f108879c047e9f0f3eb357 recorded by CHG-20261011-025/026/027 as implemented. Linked SimpleFbDxe binaries contain the dedicated takeover marker. No new physical timing or Windows Setup result; external installer filesystem and built-in input remain unresolved prerequisites.


## EXP-20261011-J413-021 — DockChannel receive/discovery components

Before extended diagnostic verification (2026-10-11): root main 4aabee58811b581e00775b9068d8acb28b9bca73; m1n1/Mu pinned gitlinks unchanged with prior staged source patches. Hypothesis: bounded caller-owned assembly can preserve fragmented and concatenated HID packets, and INIT blocks can expose descriptor/GPIO views without out-of-bounds reads or partial output. No hardware variable changed. Source inspected: official Asahi dockchannel-hid.c at 77cb8f24c2381a8abb7272d7bbdec548d6426a8a (header/send/init/ready sections), existing FIFO/packet cores, live J413 resource inventory, existing hypervisor USB/input mappings and Mu J413 ACPI. This is portable protocol work; no Windows interface or MMIO/DMA ownership introduced. MIT selected from upstream dual license; attribution retained. Adapter owns power/helper startup, FIFO/IRQ serialization, timeout/reset, DART firmware transfer, discovery accumulation and HID publication. Firmware and Windows Boot Manager input need their own adapters; a Windows-only driver cannot handle pre-kernel Recovery.

Initial focused verification: seven protocol/FIFO/RTKit tests passed, including ASan/UBSan execution of actual new cores and Windows ARM64 COFF compilation. Extended command: python3 -m unittest discover -s tests. No boot image rebuilt, installed or launched; current boot.bin remains 537dda804f96abbf89e738eb3adeb79dca19e4958c1fc172dcb5ff95a93dce2f. Prior recovery files retained. No physical register accesses or media changes. Hardware checkpoint remains bounded live DockChannel receive under established helper/IRQ ownership; current code is not attached to hardware.

After EXP021 extended verification: Ran 342 tests in 38.748s  OK (skipped=2) Event checksum error: dropping type=3 length=6 wire=0x00000000 expected=0xd0decade computed=0x4475f019 Event checksum error: dropping type=3 length=6 wire=0x00000000 expected=0xd0decade computed=0x4475f019 Actual portable C passed ASan/UBSan and ARM64 COFF checks. Verdict: implemented protocol components; no Windows input enumeration or hardware qualification. Implementation 99f3399dfdfb5b63ae798f0914f21ab05de4008b; CHG-20261011-028.


## EXP-20261011-J413-022 — USB firmware initialization and DART contract fixes

Before build/extended diagnostics: 2026-10-11T17:46:35.979144+00:00. Root main 931daf813c36819b2ad7d70f68e92f041a60dbfa; pinned m1n1 9cd80ac652ac404e92ae279deeaec8c629d7d184 and Mu 8b4dc4b4e3ff8606d0af36163acf9de79b7b4737 with intentional staged overlays. Hypothesis: USB registration must not encode failure status as a callback; T8110 flush must use command offset 0x80 and opcode zero; invalid ADT banks/compatible/stream counts must not reach MMIO. J413 USB driver dispatch must wait for both USB1 DART banks to finish flush and bypass. Combined software candidate, not an isolated hardware attribution experiment. Sources: live whitelisted J413 ADT (USB1 DART banks 0x502f00000 and 0x502f80000, each 0x4000, dart,t8110), pinned Mu USB/DART drivers and headers, AppleDTLib, NonDiscoverableDeviceRegistrationLib/protocol, m1n1 guest map/resource gate, Mu J413 DSDT/FDF; official Asahi Linux apple-dart.c at 77cb8f24 (TLB_CMD 0x80, FLUSH_ALL operation 0, 100us bounded poll). Older Asahi u-boot source itself contains the inherited offset/operand confusion; current Linux used to resolve it. No foreign source text copied; existing source license retained.

Owning firmware fixes: EFI_STATUS initializer + checked synchronous init + NULL registration callback; validate translated controller window; initialize/validate both DART bank resources; bounded known compatible; exact Apple MIDR; stream count 1..256; T8110 command offset/opcode; return timeout after 100 one-us polls; J413-only readiness protocol DEPEX prevents USB DXE dispatch until both USB1 banks enter bypass. Legacy platform DEPEX remains TRUE. No USB0/PHY/DART handoff claim; no GPU/HID device claim. Command scripts/build-j413-boot-experiment.sh; private .local/j413-usb-dart-build.log. Previous artifact preserved .local/boot-before-usb-dart-fixes, SHA 537dda804f96abbf89e738eb3adeb79dca19e4958c1fc172dcb5ff95a93dce2f; original ESP recovery retained. No install/launch command executed. Expected software checkpoint: production mocked firmware entry functions pass sanitizer guards and fresh Mu/stages/manifest verify. Hardware checkpoint: logs show DART ready then USB1 registration/media discovery; timeout or absent readiness is explicit failure. Hardware remains unrun.

Focused diagnostics before build: seven USB/platform tests passed after correcting test-discovered foreign-vendor DEBUG assertion handling. Initial --stage-overlay typo rejected before staging; corrected --stage succeeded.

EXP022 portable input extension: read pinned Asahi dchid_cmd/dchid_handle_ack/dchid_get_firmware; MIT selected with attribution. Add command matching/cancel/sequence and bounded HIDF preparation without transport or Windows interface assumptions. Eight focused actual-core/Mu tests pass ASan/UBSan plus Windows ARM64 COFF compilation. No live firmware upload or HID publication.

EXP022 first fresh build failed before compilation: INF does not accept !ifdef conditional Depex syntax. Corrected design: keep standard TRUE dispatch and enforce J413 readiness in EndOfDxe callback via LocateProtocol before any controller MMIO/registration. Missing protocol or absent USB1 mask returns explicitly; legacy C branch remains unchanged. Removed unnecessary DSC macro. The before-run DEPEX plan is superseded by the callback gate; test now covers missing readiness and wrong mask. Second build retains the same firmware ownership requirement without unsupported INF syntax.

EXP022 intermediate full build succeeded: 97 EFI images verified and nested physical/debug-off image 77b9a541ca17bdf6d6925d860261d7ba07e992dc27a10ccfd67c5e14b23fbe16 packed; no install/launch. Final review of pinned BaseLib shows MemoryFence is DMB SY, not DSB SY. Preserve the original DART DSB SY completion barrier; host mocks intercept inline asm instead of weakening firmware ordering. Intermediate image superseded before publication. Incremental build uses the same successfully prepared native build environment and direct stuart_build through private derived script (setup/update/pip skipped, source staging and compiler/PE checks retained), followed by verified-firmware-only stages rebuild. Command docker run --rm -e J413_IN_CONTAINER=1 -v repository:/work -w /work windows-on-m2-build:local sh .local/build-j413-firmware-incremental.sh; then J413_SKIP_MU=1 scripts/build-j413-boot-experiment.sh.

After EXP022 final verification 2026-10-11T18:21:45.113900+00:00: 346 root tests, 344 passed and two expected skips. Final actual owning-function tests and staging tests pass after DSB correction. Fresh Mu PE validation verifies 97 EFI images; native linked-map disassembly identifies both flush functions with DSB SY, T8110 command offset 0x80/value zero and 100 bounded retries. Clean pinned patch application/exact staged source/reversal verified for three Mu patches/13 files; additive bytes match. Root patch whitespace scan flags inherited upstream context/deletion lines; actual Mu source diff whitespace and patch application checks are the relevant checks. Native case-insensitive MANIFEST.json/manifest.json alias copy raised SameFileError after successful pack; no separate copy needed and final independent verification passed.

Final artifact {"J413_EFI.fd": {"role": "guest-firmware", "sha256": "0062c185cd31bff99777d49f0402b7d5e8c4c3ebe41d21a9abfeccbb161379ac", "size": 30965760}, "TOOLCHAINS.json": {"sha256": "baf2dd449fd89d3a6dea65502898e0755bbca18e716daa3a237411b440500172", "size": 160}, "boot.bin": {"role": "standalone-bootstrap", "sha256": "6030cfb4010f4eb20e691f20ca3bea040cc6af30d754402515228f5b609ed27c", "size": 2518812}, "m1n1-stage0.bin": {"role": "autonomous-stage0", "sha256": "57e00fa6f52f9ac8a25ffa6a2267b37f83b9b3d1de21f61232b307bbfe3f8b22", "size": 1310720}, "m1n1-stage1.bin": {"role": "autonomous-stage1", "sha256": "376d5ba692b30cab2de2ba228821fb85628c520989096311bccff45347352419", "size": 1310720}}. Overlay digest 4db31da5226f1596107aa760e7beab27d8a6c380b353b6a132a12155abd84642; m1n1 digest fd1cd6b8255444f01d07f5a69c4c8c5bd104c6635e648b12b6fc4eb9238e1c31. Completed compiler/PE build metadata Git recursion stalled; stopped the finished build container during metadata only and generated/verified the same source snapshot with the normal native manifest tool. Its full Git checks completed. Packing reuses unchanged verified stage bytes/source digest and immediately fresh firmware source snapshot; only payload bytes and manifest artifact identities change, then nested CRC/profile/exact FD/source validation passes. The intermediate stale-manifest read was rejected while metadata was still being updated; no rejected metadata used. No intermediate candidate installed. Private logs {"j413-usb-dart-incremental-build.log": "35698aefb70f63ce2c0f2543ea32c47c56079b470cb4fff756cdff3cd137ddc4", "j413-usb-input-root-tests-final.log": "b7211a8538531cf9c7ae523acf559f57c25c42fa2a8bf886902088e3b7167180", "j413-usb-native-disassembly.log": "e7603996024e857feb7c84fd142fe8ec8900e9437d983ea7cc0cda733671d6ff", "j413-usb-owning-functions-final.log": "78d4eb40b2759aaab03c9b204fcb4f32e1554279155ca7a8dcbf89c46cb26564"}.

Private staging: /Volumes/Untitled 2/windows-on-m2-workspace/uefi-usb-dart-lj9g_cf4 with 10 hash-verified source/artifact/recovery copies; SanDisk UUID checked, no device identifier assumption or physical media reconstruction. Original staging recovery hash retained. Implementation 3dbe5cefb298792386fdd4d447fca6d1e664d501. Verdict: implemented owning firmware fixes and portable input components; no new hardware run, USB enumeration, DMA operation, internal input, GPU, kernel or Setup result. Original 0xc000000f observation remains prior evidence. Next physical checkpoint requires complete readable Setup media and qualified USB port; further HID integration requires measured helper/DART/IRQ startup. No ESP/LocalPolicy/security changes, destructive disk operation or reboot.


## EXP-20261011-J413-023 — readable exFAT Setup without shell input

Before software run 2026-10-11T18:38:16.944785+00:00: operator reports UEFI Shell in a small console and no built-in input; Xbox controller available, no external keyboard/mouse. Installed artifact hash and USB port unknown; this observation does not qualify the latest candidate. Live SanDisk UUID EB47E8DD-5FE0-3F5B-B6D4-6E2FA290D53A remains exFAT with 209.7 MB FAT ESP. Owning J413 FDF has EnhancedFatDxe only; automatic selector requires four Setup paths through SimpleFS. Hypothesis: embed separately licensed read-only EfiFs ARM64 exFAT driver to expose existing complete media without changing disk layout. Primary sources: pbatard/EfiFs v1.12 release, GPLv3+ license/README, J413 FDF/WindowsAutoBootDxe, pinned Mu dispatch rules. Single variable: exFAT filesystem support; USB0/input unchanged. Artifact dependency pinned by release SHA, machine/subsystem verified before firmware build. Preserve existing boot and manifest. Expected software checkpoint: dependency verification, FV driver presence and exact source/artifact manifests; physical checkpoint is readable SSD plus Windows loader handoff. Failure remains absent USB or incomplete media. No ESP writes, repartition, installation or reboot.

After verification 2026-10-11T18:44:30.592809+00:00: native Mu build succeeds, 98 PE images verified; generated FV driver section exactly matches EfiFs release SHA and DEPEX TRUE/END. Root suite 349 tests: 347 passed, two expected skips. Final boot SHA dd08eacd8e0f73b7f54a14fc177a9c42f116f41e1b328fa97ce6aa70973cd06b size 2534792; fresh FD SHA 9cdc55c04ad61d84258f9b10e54e835aad7359bbaa4690e518396ebeea3cf3ec; overlay 63ea14bf52c6a4a09adf2c585141c254bb5bad31cf43166389a7ae1a4c0fd07a. Reused verified unchanged source/hash m1n1 stages and repacked fresh FD; normal native manifest full Git checks completed. Initial precheck incorrect manifest key rejected before fresh FD copy; stale private pack superseded before copying/install. Corrected key and final nested CRC/flags=1/exact FD/source manifests verified. Compiler identities corrected to actual GCC 13.3/Clang 18.1.3. Initial SSD copy2 metadata chflags failed on exFAT; retried in fresh bundle with copyfile and hash checks. Final bundle /Volumes/Untitled 2/windows-on-m2-workspace/uefi-exfat-4t9aie4g with 12 verified candidate/source/license copies and prior recovery image. Live IOService ancestry confirms SSD usb-drd0; current firmware excludes it, so other connector USB1 required. Implementation 09dfccb859d873c2302fcc0631887cb245f73b66. Verdict implemented, no physical launch, built-in/Xbox input, kernel/Setup qualification, ESP/partition/boot-policy writes or reboot. Next physical checkpoint USB1 readable exFAT then automatic loader handoff.


## EXP-20261011-J413-024 — BDS application-level Setup selection and installation provenance

Before software run 2026-10-11T18:53:36.653536+00:00: main 78786919d1600e93c281f93c235bd1422d701b80, unchanged Mu/m1n1 pins. Sources inspected: WindowsAutoBootDxe, DeviceBootManagerLib, MsPlatform priority boot, BDS entry, UefiBootManagerLib BmBoot, CoreLoadImage and official UEFI services TPL table (LoadImage/StartImage strictly below TPL_CALLBACK). Current filesystem and ReadyToBoot callbacks execute at TPL_CALLBACK and call both image services. Owning change: J413 publishes a Setup selector protocol; application-level DeviceBootManagerPriorityBoot requests an ephemeral load option, standard BDS executes image and ReadyToBoot sequencing. Do not lower TPL inside callback, change security policy, or write BootOrder. Also source-confirmed installer verifies an adjacent manifest without checking requested image membership; exFAT preparation always redownloads notices despite cached binary. Each receives regression coverage; combined source candidate, no isolated hardware attribution. Recovery image copied before build. Expected checkpoint: owning selector tests, standard BDS path and fresh native firmware/manifests; physical automatic complete-media handoff remains untested. No ESP/partitions/boot-policy writes or reboot.

Operator photo update 2026-10-11T19:07:27.282109+00:00: IMG_5759/5760 show UEFI BOOT console ready followed by no complete readable Windows Setup volume found and four-path prerequisite. This confirms selector failure before Windows handoff, not absent files on host or proven USB enumeration. Exact installed artifact and port remain unobserved. Lower console contains pre-GOP SimpleFbDxe/HiiDatabase loading text retained on screen; it is not proof those drivers crashed. Photo SHA256 98ec4d9c66c9d9640c1afcc763d7168158ed301babefc751737ebfc9aff2550b, befd22fe42d0806bdcf59513f9e7e223984c5186bd3f2ef511a524fbb882dae2. Current BDS source change not yet built or installed; photo uses the older callback-path diagnostic.

After verification 2026-10-11T19:10:00.403157+00:00: source suite 355 tests, 353 passed/two skipped; three additional Setup preflight tests passed after added during suite execution (358 distinct total, 356 passed/two skipped). Actual owning selector ASan/UBSan and cache/installer regressions pass. Initial native build interrupted by operator reboot during precompiler Git metadata discovery; no new image installed. Restarted existing build environment with diff.ignoreSubmodules=all scoped to container metadata discovery only; full source provenance generated separately by normal native manifest tool without that configuration. Fresh native Mu build succeeds, 98 PE images verified, J413 BDS/selector branch linked. Reused hash/source-verified unchanged m1n1 stages; final nested flags=1/CRC/exact fresh FD/overlay and exact installer identity verify. Boot SHA 101c9de0cccbfce84022e42938c7760f7ba630956ad64fff13149373d45745bc size 2535532; FD SHA bcf686dd8f5c90b11473879994052c68dec8e6081f705bfbfebb77bff5103d1c. Hash-verified SSD bundle /Volumes/Untitled 2/windows-on-m2-workspace/uefi-bds-88b520dn includes separate GPL notices and prior candidate recovery. Implementation 5f9891bafe79b52bec747d50faa24356426321d0. Operator confirms photo attempt used unchanged USB0 socket; current live ancestry agrees. This explains inaccessible SSD for excluded controller, not proof remaining USB1/Windows path works. Photos still do not establish artifact identity. No current candidate hardware launch, input/Windows qualification, ESP/partition/boot-policy writes or reboot. Verdict implemented.

Operator update 2026-10-11T19:17:05.518879+00:00: subsequent attempt reached UEFI Shell. Installed SHA and visible selector/USB/DART status not supplied. Live macOS ancestry now confirms SanDisk on usb-drd1; do not attribute current failure to unchanged USB0. Current local candidate SHA 101c9de0cccbfce84022e42938c7760f7ba630956ad64fff13149373d45745bc. Need Shell FS/BLK mappings and prior status lines to distinguish USB, filesystem, selector and loader failure. No new firmware installation or build.


## EXP-20261011-J413-025 — bounded EFI phase log on internal ESP

Before software run 2026-10-11T19:27:25.041831+00:00: user authorizes persistent EFI diagnostics readable from macOS. Sources: current Mu selector/file/BlockIo/device path implementations, nvme backend write path, internal FAT32 read-only audit, UEFI EFI_FILE_PROTOCOL and NVMe messaging device-path definitions. Variable emulation is enabled, so guest NVRAM is not a persistent macOS log channel. Owning design: bounded 16 KiB ASCII phase buffer in WindowsAutoBootDxe, written only at application-level selection checkpoints to a writable NVMe SimpleFS with existing m1n1/boot.bin anchor. Only m1n1/j413-uefi.log is created/updated; no APFS or disk-layout change. Save file with fixed 16 KiB bound, check short writes/flush and close every handle; if no writable internal ESP exists, print failure and continue normal boot selection. macOS read-only FAT32 reader extracts owned log without mounting or modifying partition. Expected software checkpoint: owning writer mocks/sanitizers, FAT bounds/cycle regression, fresh firmware and manifests. Full UART/pre-DXE/kernel/crash logging is outside this phase log. Recovery candidate retained, no install or reboot.

After verification 2026-10-11T19:33:55.784815+00:00: root suite 362 tests, 360 passed and two expected skips. Actual bounded EFI writer runs under ASan/UBSan with NVMe/read-only/anchor filtering, create/position/write/short-write/flush failures and all closes; FAT reader tests cover extracted text, zero padding, cycles, size, malformed geometry and short source. Read-only old internal ESP image parses and reports owned log absent as expected; no new candidate hardware run. First build attempt found stopped Docker after reboot; existing environment restarted. Fresh native Mu build succeeds with 98 PE images. Container Git metadata-only ignoreSubmodules config used; normal native manifest provenance retains full Git/source checks. Unchanged source/hash-verified stages repacked with fresh FD; nested CRC/profile flags=1/exact firmware/source/installer identity verified. Boot SHA dd537ea3b2514f93b87b2890b2885b06803ec5306211f0b0f78372975f5ab375 size 2537240; FD SHA 68b3108021519c1c8e91b87caf60dfebe0fbc021c45776d7c59dc7ad20b8b965; overlay 18e6f3695a0f765200ac6ed3b934f3675d8733e3857559eece8e99dacc560d74. Private hash-verified bundle /Volumes/Untitled 2/windows-on-m2-workspace/uefi-phase-log-djspf1hv includes separate license/source notices and previous recovery image. Implementation 80a12d7448ea8eeff14290e650389710b36457d7. Verdict implemented, persistence to physical internal ESP not qualified. Future user-authorized EFI log writes are limited to anchored internal m1n1/j413uefi.log; no current physical ESP/partition/security writes, install or reboot. User must install candidate, reach BDS selector, return to macOS and run read-efi-log.sh --disk disk0s4. A pre-BDS/storage failure cannot produce this phase log.


Operator hardware update 2026-10-12T04:07:11.878076+00:00: user confirms latest logging candidate installed and boot stops at photographed console, IMG_5762/5763. macOS read-efi-log reports J413UEFILOG absent. Photos show DeviceBootManagerAfterConsole banner and retained SimpleFbDxe/HiiDatabase debug text, no phase-log saved/not-saved message. Source correction: banner originates inside BDS AfterConsole; absence of selector checkpoint does NOT prove pre-BDS failure. Selector first checkpoint follows EfiBootManagerConnectAll, so a hang during connection or between AfterConsole and priority selection remains possible. Exact installed image hash unmeasured. No exception/stop code is visible, no Windows handoff observed. Verdict inconclusive; next diagnostic should bracket AfterConsole completion, priority selector entry, and ConnectAll entry/return, with pre-connection console output; do not infer HiiDatabase crash from retained pre-GOP text. No new build/install/reboot.


## EXP-20261012-J413-026 — console checkpoints before device connection

Before software run 2026-10-12T04:08:42.315032+00:00: main 2dedae8eb9bef91bbd022f00f70fc290074ea0c7; unchanged Mu/m1n1 pins. User reports stationary AfterConsole banner; source proves banner is in BDS, first persistent checkpoint follows ConnectAll. Hypothesis: bracketing TPM confirmation, AfterConsole return, priority selection and ConnectAll distinguishes last entered owning operation without assuming driver crash. Single diagnostic change: console-only checkpoints, no new storage access before connection, no timeout/security bypass. Sources: DeviceBootManagerLib.c, WindowsAutoBootDxe.c, MsPlatform.c priority boot. Recovery .local/boot-before-connect-trace with existing manifest/SHA. Expected: actual selector regression confirms print before ConnectAll even when connection never returns; native build and source-verified repack. No firmware install/reboot.

After software run 2026-10-12T04:13:47.399726+00:00: 362 tests, 360 passed/two expected skips; actual selector sanitizer harness asserts diagnostic banner precedes ConnectAll. Native Mu succeeds, 98 PE images validated, linked PrePi checks passed. Stopped Docker restarted after operator reboot. Normal native source provenance checked, unchanged m1n1 stage source digest and artifact hashes verified before reuse; fresh FD repacked with debug off/physical/noProxy flags and exact installer identity verified. Boot SHA d31368f12749f8033e227e3ec383ae1ccd7cb20ca7f29c6fa2cb124a90fde2d7 size 2537524; FD SHA c151d96acd164c894924625d9c5e7711163beb4ea47d93714249b45cd4ae6255; overlay 3ea4d78118ce47ab3a4dcb11c56b437425e94b191b7c1eeb823279ad429ecb10. Hash-verified candidate/recovery/separate EfiFs notice bundle /Volumes/Untitled 2/windows-on-m2-workspace/uefi-connect-trace-r7wufr0u. Implementation c93d01ff4718776dc4b855879198f4a88239209c. Verdict implemented, no hardware launch or identified hang cause. Console markers intentionally precede device connection without adding potentially hanging filesystem access; persistent log still begins after connection. No ESP/partition/security write or reboot. Next operator checkpoint is last stationary UEFI TRACE marker.


Operator hardware result 2026-10-12T04:24:11.291991+00:00: IMG_5764 shows AfterConsole return, priority boot entry, Setup protocol lookup Success, and Setup selector entered; connecting controllers, with no connection-return marker. User reports stationary display. Narrows EXP-20261012-J413-026 hang to EfiBootManagerConnectAll or its callees. Does not yet identify default console connection, recursive controller Start, or DXE dispatch. Exact installed SHA not measured; diagnostic strings match current candidate. No Windows launch or persistent checkpoint observed.

## EXP-20261012-J413-027 — trace each controller connection and DXE dispatch

Before software run 2026-10-12T04:24:11.292220+00:00: main 5c62568484eb7a0c598d327fecd401eb7672a78c; pins unchanged. Source inspected: pinned MU_BASECORE BmConnect.c, public UefiBootManagerLib/DevicePathLib/DxeServicesTableLib declarations and current J413 selector. Single diagnostic change: J413-local version of existing ConnectAll algorithm prints default-console entry/return, controller index/handle/device path entry/return and Dispatch entry/return. Preserve recursive connection, dispatch-until-error and final console connection; do not skip drivers, cap dispatch or change security. Add checks for failed handle enumeration rather than using uninitialized buffer. License BSD-2-Clause-Patent, preserve Intel notice from source algorithm. Expected: actual helper sanitizer test verifies operation order, enumeration error handling and per-controller pre-call output; native build/repack; physical last stationary marker identifies owning operation. Recovery .local/boot-before-controller-trace. No install/reboot.

After software run 2026-10-12T04:27:39.021182+00:00: root suite 363 tests: 361 passed/two expected skips. Actual diagnostic connection helper executes under ASan/UBSan and verifies pre-call markers for console/controller/dispatch, multi-pass ordering, nonfatal individual connection error and enumeration failure before buffer access. Native Mu build successful with 98 PE EFI images verified; normal native full source manifests and unchanged m1n1 stage digest/hashes verified; fresh FD repacked, exact installer identity and physical/debug-off profile verified. Boot SHA 21b006560e488e8390574bc762a89b099eb0f29e574c442e16c947042d3a1a64 size 2538560; FD SHA 3e6c051ba84ebac239d2723affcad5c51cf07b65ffdc4c8097fa17282f512c25; overlay c56f68aa80cf948d9e9533c7daca0d59aaba3e48053fa0cceaca6a1431fb2494. Hash-verified bundle /Volumes/Untitled 2/windows-on-m2-workspace/uefi-controller-trace-rtv2870_ includes previous recovery and separate EfiFs notices. Implementation 764f9802ef734771ddcf71ba2d872ab2ce49f934. Verdict implemented; no hardware launch, driver identified or hang fixed yet. No ESP/partition/security write/reboot. Next checkpoint last stationary UEFI CONNECT entry and device path.


## EXP-20261012-J413-028 — connect Setup boot storage without global ConnectAll

Before software run 2026-10-12T04:33:09.938272+00:00: main 51b0b358a36c2c98bd6c5795ab5659c6c2edd96a, unchanged pins. User requests autonomous correction without another hardware attempt now. Sources inspected: BmConnect/BmConsole, J413 Apple USB registration (only qualified USB1 non-discoverable xHCI), NonDiscoverableDevice protocol/registration, generic bridge and Xhci binding, BDS selector, NVMe namespace/queue, official UEFI ConnectController recursive contract https://uefi.org/specs/UEFI/2.10/07_Services_Boot_Services.html. Physical evidence locates failure inside global ConnectAll, not individual driver. Owning correction: J413 Setup selector connects only registered non-discoverable xHCI boot-storage roots recursively, scans existing SimpleFS as before. Avoid global all-handle connection, repeated default-console connection and DXE dispatch loops; actual storage/input descendant drivers still bind through normal recursive UEFI connection and security policy is unchanged. Record actual connection EFI_STATUS instead of assumed success. This removes unnecessary global dependency, does not claim to repair an unidentified xHCI or NVMe driver. Recovery .local/boot-before-targeted-usb. Expected tests: mixed controller types, protocol failures/nulls, recursive USB connection/status, untouched unrelated controllers, native build/manifests. No install/reboot or new hardware request.

After software run 2026-10-12T04:36:07.431408+00:00: 363 root tests, 361 passed/two expected skips. Actual targeted helper under ASan/UBSan connects only xHCI recursively, ignores other types/null interfaces and preserves failures; actual selector integration passes. Native Mu succeeds, 98 EFI images verified. Native full source manifests, unchanged m1n1 source/hash checks and exact installer profile pass after fresh FD repack. Boot SHA 194bb132fecfaf7210fefbeaa98ef110d2a5cd2fc10487bf6f7562c1a128b330 size 2537524; FD SHA 810000c87cf586aae29f446e2a6d599a3549f151452a43a1b53c6ade968790fa; overlay 562aca5dcb815be5de69c9f14f192575459b20a35c66408d7ba0649da2bff0a5. SSD bundle creation failed before any file copy because external volume no longer mounted. Hash-verified local candidate/recovery/separate EfiFs notice bundle /Users/liamsitbon/Documents/ChatGPT/windows m1n1/windows-on-m2-air/.local/release-bundles/uefi-targeted-usb-qttmzsr9. Implementation cd2a7578708521774baf7abc281ab08ea7e3cac8. Verdict implemented; unnecessary global connection path removed, original individual driver cause and hardware resolution unqualified. USB driver can still hang; no unsupported preemption/bypass claimed. Optional internal log unavailable unless NVMe filesystem already exposed. No install, security/partition/ESP writes or reboot; no new operator trial requested.

Operator hardware update 2026-10-12T04:50:17.605046+00:00: IMG_5765 shows controller connection returned, phase log not saved Not Found, one examined incomplete volume missing EFI/BOOT/BOOTAA64.EFI, final Setup selection failed Not Found. No UEFI CONNECT boot USB controller entered marker visible; targeted connection may have no registered xHCI roots. User explicitly confirms USB1; do not attribute failure to USB0. Live macOS four Setup files still exist and pass header preflight on external volume. Missing path warning does not establish SSD file absence or SSD enumeration. New path passed previous global-hang point, but physical Setup boot still failed. Exact installed hash unmeasured; banner matches candidate. No Windows launch observed.


## EXP-20261012-J413-029 — DWC3 core identity and early USB outcome visibility

Before software run 2026-10-12T04:51:16.100936+00:00: main 01daf719bcf6e2f09c3c917942b542706b25b25d; pins unchanged. IMG_5765 passes connection entry but no registered USB root marker; physical cause unresolved. Local SSD headers/files valid. Source-confirmed core filter recognizes only DWC31 ALT ID despite defining standard DWC3 ID; also applies pre-1.90a workaround using GSNPSID low bits on DWC31 where this register is an IP signature rather than DWC3 revision. Sources: Mu Dwc3XhciCoreInit/header, actual callback/readiness tests, Linux official drivers/usb/dwc3/core.c core_is_valid/core_setup_global_control (https://raw.githubusercontent.com/torvalds/linux/master/drivers/usb/dwc3/core.c), pinned DART and macOS ADT resources. Owning change: accept both already declared supported core signatures, restrict DWC3 revision workaround to DWC3 IP; reject unknown IP before reset/write. Add console visibility of controller registration lookup, connected root count, DART presence/mask. No unknown hardware registers or identities introduced, no DART safety bypass. Single core-family correction plus diagnostics; no isolated hardware attribution. Recovery .local/boot-before-usb-core-id. Expected actual core sanitizer cases for both signatures and invalid IPs; full suite/native build. No install/reboot.

After software run 2026-10-12T04:54:44.624741+00:00: root suite 364 tests: 362 passed/two expected skips. Actual core function under ASan/UBSan accepts DWC3 old/new revisions and DWC31 signature, applies old-revision workaround only to DWC3, rejects zero/all-ones/unknown signatures before reset or MMIO writes. Existing targeted binding/DART/selector tests pass. Native Mu succeeds with 98 EFI images verified. Full native source provenance, unchanged m1n1 stage digest/hashes and exact installer flags/identity verified after fresh FD repack. Boot SHA 232d67ad29f0c89db338cd6a95f0f5cc209eca6536c771320ac066ee4eec71af size 2537836; FD SHA 1627c0d6f00f60bbc6ccfa153482807d825d60912774b2733d4df9c64bbe775a; overlay 73f9a3cc769c11f32baaf5a8bb8b31e3e080ca059821e0a33fb313d2402efa5b. Hash-verified candidate/recovery/separate EfiFs notice bundle /Volumes/Untitled 2/windows-on-m2-workspace/uefi-usb-core-id-29uv581e. Implementation fbacc5d33327be939719846e5fb5ecaa48f4d365. Verdict implemented. Physical core identity not observed; cannot attribute IMG_5765 to rejected signature yet. Console now distinguishes missing registered controllers from DART readiness and Setup files. No install/reboot/ESP/partition/security write or SSD Setup modification.


Operator hardware update 2026-10-12T11:23:02.232380+00:00, EXP-20261012-J413-029: IMG_5767.HEIC SHA256 8e43202115ae9445944ab1af1bc78be8b1403f14d645dd4f40a346f262f36c03; IMG_5772.HEIC SHA256 e0e90fd92e711ed2c0402a52343d5e570b4ab5814cbb3f5e5134dfa74a6f41f9. IMG5767 shows registered controller lookup Not Found, handles 0; DART readiness Success, ready mask 0x2; connection returned; log not saved Not Found; examined volume missing EFI/BOOT/BOOTAA64.EFI; Setup selection Not Found. IMG5772 later shows UEFI Shell with internal NVMe and firmware/virtual mappings only, no USB device path. Operator waited minutes before school and found Shell on return; transition time unknown. No Windows launch observed. Installed SHA not independently measured; console strings match EXP029. DART readiness confirmed, USB root registration absent; missing file warning does not identify external SSD.

## EXP-20261012-J413-030 — honor measured USB controller aperture

Before software run 2026-10-12T11:23:02.232380+00:00: main 10985d853d6bd60b8b806ee05e2d905dc6449af6, unchanged m1n1/Mu pins. Captured translated macOS ADT usb-drd1 base 0x502280000, extent 0x11800; current callback requires >=0x100000 and clamps registration to that guessed extent, necessarily rejecting measured J413 resource before core initialization. Prior test mocked a one-megabyte USB resource and missed this defect. Sources inspected: captured j413-macos-resources.json, Asahi t8112.dtsi dwc3_1, m1n1 ADT translation, Mu DWC3 register/header and CIO offsets, NonDiscoverable registration and PCI IO exact AddrLen bounds. Owning change: validate extent covers the actual last accessed global/CIO registers; preserve reported extent with addition overflow checks. No copied Asahi code, MMIO guesses, new initialization sequence or Windows driver. Single changed variable: controller aperture qualification/registration. Recovery .local/boot-before-usb-aperture, expected actual callback sanitizer regression with captured base/extent and boundary failures, native build/manifests. Physical checkpoint: one registered USB1 xHCI root then normal recursive enumeration; failure beyond registration remains unqualified. No ESP install, security or partition writes/reboot.

After software run 2026-10-12T11:30:19.245471+00:00: 364 tests, 362 passed/two expected skips; actual owning callback uses captured base/0x11800 extent and real register header, exact registration descriptor and truncated/unaligned/overflow resources, failed core init and absent readiness. Initial near-overflow mock used an unaligned synthetic base and exposed sanitizer UB; added alignment rejection, aligned boundary cases and fatal sanitizer recovery, then complete suite passes. Native Mu succeeds, 98 EFI images and linked PrePi validated. Normal native full source manifest checks completed; unchanged m1n1 digest/hashes verified before repacking fresh firmware. Final identity {"artifacts": {"J413_EFI.fd": {"role": "guest-firmware", "sha256": "92745fd599ce47abd6b7b9060546fbfe6374526be7aa796e0a4aa29ae69a9055", "size": 30965760}, "TOOLCHAINS.json": {"sha256": "baf2dd449fd89d3a6dea65502898e0755bbca18e716daa3a237411b440500172", "size": 160}, "boot.bin": {"role": "standalone-bootstrap", "sha256": "fb7ecd0c2691c0d130afbb69022fdf0e6f1e4c34004c2c96cbbc748a4e98f226", "size": 2538040}, "m1n1-stage0.bin": {"role": "autonomous-stage0", "sha256": "57e00fa6f52f9ac8a25ffa6a2267b37f83b9b3d1de21f61232b307bbfe3f8b22", "size": 1310720}, "m1n1-stage1.bin": {"role": "autonomous-stage1", "sha256": "376d5ba692b30cab2de2ba228821fb85628c520989096311bccff45347352419", "size": 1310720}}, "overlay": "28d1b42b0a68037cac7fadfd8dbece1dedb925fe294ee97ac6dab051c99779b5"}. Implementation 0cf8431901237aef6a7fccd3c1d5057c89d1fb80. Verdict implemented; deterministic rejection of measured J413 aperture removed, physical core/xHCI/SSD success not yet observed. Recovery .local/boot-before-usb-aperture preserved. No install, ESP/partition/security writes or reboot. User additionally requests general EFI discovery; record separately in EXP031.


## EXP-20261012-J413-031 — general ARM64 EFI application discovery

Before software run 2026-10-12T11:31:54.523444+00:00: user explicitly requests boot from EFI files regardless of vendor, path or filesystem location. Main 8102e0fd6c92ee94ee7c4034064efa30119e3bd9; pins unchanged. Recovery .local/boot-before-efi-discovery. Sources: UEFI 2.10 media file Open/Read/SetPosition/directory-entry contract and ARM64 PE32+ application definition; pinned FileInfo.h, FileProtocol, Mu standard BDS EfiBootManagerBoot and MsPlatform priority flow, current selector and targeted USB helper. New owning selection policy: complete Setup remains first preference, then standard fallback/Windows loader paths across all readable SimpleFS handles and recursive case-insensitive .efi search anywhere, without BlockIo/partition/name/vendor filtering. Preflight ARM64 PE32+ EFI applications only, normal BDS full validation/security and ReadyToBoot unchanged. Returned/failed apps advance without persistent BootOrder writes. Bounds: 32 directory levels, 1024 path chars, 100000 directory entries per filesystem, 256 applications; report limit hits, no unbounded rescans or repeated candidate. No arbitrary EFI driver starts or unsupported CPU emulation. No new hardware MMIO sequencing; USB aperture fix retained. Expected actual scanner/selector/BDS-loop sanitizer regressions, full suite and native build/source manifests. Physical EFI application/Windows success not claimed. No ESP install/partition/security change or reboot.

After software run 2026-10-12T11:38:16.064606+00:00: 366 tests, 364 passed/two expected skips. Actual scanner/header and BDS-loop execute under fatal ASan/UBSan: preferred and arbitrary nested/root paths across two filesystems; case/dedup; x64 and EFI-driver rejection; malformed record and grown buffer; read/path/option failures; all closes/frees; failed/success/security-status application returns each advance once through standard EfiBootManagerBoot. Actual selector keeps complete Setup preference then generic fallback without repeated USB connection. Initial test harness unused counters/obsolete failure expectations corrected before final suite. Native Mu succeeds, 98 EFI images validated plus linked PrePi. Normal native full source provenance checked, unchanged m1n1 source digest/artifact bytes verified before fresh FD repack; exact image SHA/size/profile/nested CRC and noProxy flags verified. Identity {"artifacts": {"J413_EFI.fd": {"role": "guest-firmware", "sha256": "bd0b67ee1c9e917584e86426c82cd285b2ccb153920b9ff256e8abce7747a859", "size": 30965760}, "TOOLCHAINS.json": {"sha256": "baf2dd449fd89d3a6dea65502898e0755bbca18e716daa3a237411b440500172", "size": 160}, "boot.bin": {"role": "standalone-bootstrap", "sha256": "9fed3c1969eceb9b292f88dd13e657700ebb11c44016b3e35e87ed4853922231", "size": 2539228}, "m1n1-stage0.bin": {"role": "autonomous-stage0", "sha256": "57e00fa6f52f9ac8a25ffa6a2267b37f83b9b3d1de21f61232b307bbfe3f8b22", "size": 1310720}, "m1n1-stage1.bin": {"role": "autonomous-stage1", "sha256": "376d5ba692b30cab2de2ba228821fb85628c520989096311bccff45347352419", "size": 1310720}}, "overlay": "8211e1525c86b9a68d22871aa2032478342351c6e9c78cf08057ca6a8e48fb22"}. Implementation 21b346cc67c496932c7e0a44fedac3469bdd34c4. Hash-verified bundle /Volumes/Untitled 2/windows-on-m2-workspace/uefi-efi-discovery-f34a8pfr contains 21 candidate/recovery/source/EfiFs notice copies; volume matched UUID, no disk-number assumption. Verdict implemented, no physical attempt of this image; generic EFI handoff, SSD and kernel remain unqualified. Complete Setup loader still preferred; generic candidates need ARM64 application format, not Windows media dependencies. Bounded directory/path/entry/candidate limits documented and reported. Existing input limitations unchanged. No ESP install/partition/security write/reboot.


## EXP-20261104-J413-032 — user-supplied photo and exact fallback policy

Recorded retrospectively from operator-provided IMG_6311.HEIC; no pre-run identity/timing was available and this is not an agent-initiated hardware trial. Photo SHA256 168b212426a30744ac1a728d92a60ab21b0e2828f9d92d3b85de1df5c2efc81d. Controller registration/connect Success, DART readiness Success/mask 0x2, incomplete examined filesystem, then ACPIVIEW.EFI selected/attempted. Windows stop code/parameters, all CPUs, IRQ/timer, storage and input liveness unobserved; firmware display alive. Verdict: general EFI selection confirmed; USB media and Windows startup inconclusive. Corrects the untested EXP031 policy at the user request; does not reinterpret its old result.

Before software verification 2026-11-04T16:09:44.079832+00:00: root master 73884963694696ab3d80e9e6baafa7112cd6b299, pinned Mu/m1n1 retained with existing dirty overlays. Exact-path selector change only; test command python3 -m unittest discover -s tests. Source plan and ownership: investigation/analysis/2026-11-04-exact-boot-usb-gpu.md. No firmware build/install/launch yet; no new artifact or hardware result. Hardware hypothesis: exact fallback policy cannot choose ACPIVIEW. Recovery untouched.


## EXP-20261104-J413-033 — exact-path firmware with USB boundary inventory

Before build 2026-11-04T16:11:40.095447+00:00: source identity/diff hashes in investigation/analysis/2026-11-04-build-source-state.json. Independent observables: exact-path policy from EXP032 plus explicitly read-only protocol diagnostics; no attempt at physical attribution between these changes. Hypothesis: candidate selects only BOOTAA64.EFI and reports USB host/interfaces/block/filesystem device paths after existing binding. Command: scripts/build-j413-boot-experiment.sh > /tmp/m2-build-20261104.log 2>&1 ; output dist/j413/boot-experiment, physical/debug-off/M1N1_NO_PROXY, profile debug. Prior local artifacts preserved at .local/recovery-20261104-exact-boot with SHA256.json; they are recovery candidates, not newly validated known-good images. No install/launch command executed. Expected checkpoint: build/manifests validate; physical checkpoint deferred. Failure criterion: compile/manifest mismatch. Full suite returned 1558 tests: 91 failures/56 errors/42 skips, including unchanged GPU contracts and missing external source dependencies; details preserved in analysis test log. Focused exact loader tests passed under sanitizers.

After software run 2026-11-04T16:14:39.418292+00:00, EXP-20261104-J413-032/033: build succeeded, Mu 98 EFI images verified and linked PrePi guard checked; both m1n1 stages built and nested physical/debug-off image/profile/manifests verified. Exact overlay SHA256 5497cc49120052b842bba51b95a437a5546f48dbb7624c458e6a8edd156e227f matches current sources. boot.bin SHA256 8ddc181829347c35c068ef974c5f904405ed9c742bc1a9f5b368f443581d6578 size 2538572; J413_EFI.fd SHA256 847c7acaf9cf05864ff68477d3cb91cca974bcfd0fac8d8ba18e5e8dfb102e18 size 30965760; manifest dist/j413/boot-experiment/MANIFEST.json. Final J413 suite 44 tests/43 passed/one skipped; ledger two passed. Full checkout failures and errors recorded in analysis/2026-11-04-test-results.json and full log; cannot claim global green or driver qualification. Firmware logs in analysis/2026-11-04-build.log. No observed physical phases/times, Windows stop, CPU/IRQ/timer or display/USB input/SSH/RDP/storage liveness for this new candidate; none launched. Verdict: software implementation verified; hardware hypothesis inconclusive. Recovery local bytes preserved under .local/recovery-20261104-exact-boot with SHA256.json; no ESP/partition/boot-policy/USB-media changes. Next justified experiment: record installed exact hash and recovery, then observe USB protocol paths and exact loader selection before GPU work. GPU runtime blocked by documented ACPI/driver/IRQ contract differences.


## EXP-20261104-J413-034 — USB discovery audit after operator not-found report

Before read-only diagnostic 2026-11-04T16:37:15.884675+00:00: operator reports only EFI not found; no exact final trace, installed hash or elapsed time provided. Source IDs/diff hashes: investigation/analysis/2026-11-04-usb-audit-state.json. Hypothesis to distinguish: macOS sees valid USB media but firmware host/child/filesystem binding or selection fails. Commands: python3 tools/collect_j413.py --output investigation/analysis/2026-11-04-j413-live-resources.json ; system_profiler SPUSBDataType -json (sanitize to topology/speed/name only) ; python3 tools/check_j413_setup.py /Volumes/WININSTALL ; inspect existing local logs and manifests only. No direct MMIO reads or physical register writes, no mount repair, install, power/reset or launch. Existing candidate dist/j413/boot-experiment/boot.bin SHA256 8ddc181829347c35c068ef974c5f904405ed9c742bc1a9f5b368f443581d6578; manifest same directory, debug/physical/off. Recovery .local/recovery-20261104-exact-boot. Evidence paths analysis/2026-11-04-* ; expected checkpoint: fresh translated USB/DART/IRQ and current media contract, not firmware USB runtime proof.

After read-only diagnostic 2026-11-04T16:47:53.751600+00:00, EXP-20261104-J413-034: fresh ADT capture reproduces USB1 0x502280000/0x11800 IRQ1112 and USB0 0x382280000/0x11800 IRQ1031; DART banks/IRQs recorded. Current macOS ancestry places SanDisk on usb-drd0. system_profiler returned empty USB inventory; IORegistry is the actual ancestry evidence. WININSTALL four headers valid; installed ESP identity unavailable because sudo noninteractive read-only mount required a password, no mount/repair performed. No firmware register sampling or reboot. Verdict: current port0 exclusion confirmed; does not establish the port used in the prior trial.

Operator update 2026-11-04T16:47:53.751600+00:00: IMG_6312.HEIC SHA256 e34d91d5a0ba5b02c40f1306107502afa138e5c2eb6ea0928ff9f1df521c91b0. User explicitly moved media to usb-drd1. Photo shows host-controller protocol present (one), DART Success/mask0x2, zero UsbIo interfaces, one VirtualDisk BlockIo/SimpleFS, zero BOOTAA64 candidates. This supersedes any inference that changing to USB1 alone fixes discovery. Driver-binding success is confirmed; no physical USB child/storage or Windows launch shown. Installed SHA and elapsed time unmeasured; strings match EXP033 candidate. No Windows stop code/parameters, CPU/timer/IRQ counters, SSH/RDP/input liveness available. Display alive. Next checkpoint must be physical child enumeration/port-state, before filesystem policy.


## EXP-20261104-J413-035 — match USB1 PHY role to preboot xHCI host

Before software build 2026-11-04T16:49:47.427294+00:00: source IDs and diff hashes analysis/2026-11-04-usb1-role-build-state.json; plan analysis/2026-11-04-usb1-phy-role-plan.md. Hypothesis: missing external USB2 PHY host bits prevent USB1 child enumeration despite bound xHCI in IMG_6312. Single functional variable: initial PHY role bits, USB1 in J413+M1N1_NO_PROXY only; add non-destructive SIG readback diagnostic. No changes to PHY reset/power/delay, DWC3 core, DART, ACPI, IRQs, discovery policy or Windows drivers. Regression against old actual initializer failed the first SIG-value assertion; new function passes role/profile/order/failure cases under ASan/UBSan. Build command J413_SKIP_MU=1 scripts/build-j413-boot-experiment.sh > /tmp/m2-usb1-role-build.log 2>&1 ; output dist/j413/boot-experiment, profile debug/physical/off and both no-proxy stages. Mu SHA remains 847c7acaf9cf05864ff68477d3cb91cca974bcfd0fac8d8ba18e5e8dfb102e18. Previous candidate SHA 8ddc181829347c35c068ef974c5f904405ed9c742bc1a9f5b368f443581d6578 preserved under .local/recovery-20261104-before-usb1-role with RECOVERY_HASHES.json. Current actual installed ESP could not be read without operator sudo; macOS remains recovery. No install/launch command executed. Expected software checkpoint: matching source/nested/profile manifests. Hardware checkpoint pending: SIG host mask readback, UsbIo count nonzero then USB storage and exact BOOTAA64 loader. Failure criterion: host present but still zero children; collect root-port/PHY state before changing another variable.

After software build 2026-11-04T16:53:59.018514+00:00, EXP-20261104-J413-035: success. Both m1n1 ARM64 stages rebuilt. boot.bin 2538660 bytes SHA256 910192421b2292b9a8b7531d645295a52e6bb36c5c5a5878c9ddb6cd93f1f4a9; manifest dist/j413/boot-experiment/MANIFEST.json, debug qualification/physical/debug-off; outer and inner profile/CRC, exact image identity, current m1n1 source digest verified. Mu unchanged at SHA256 847c7acaf9cf05864ff68477d3cb91cca974bcfd0fac8d8ba18e5e8dfb102e18. 46 J413 tests: 45 pass/one skip; full suite 1561 tests, 91 failures/55 errors/42 skips, no new failure headers compared with earlier baseline; ledger two tests pass. Logs and results under analysis/2026-11-04-usb1-role*. No new hardware phases/time, stop code/params, CPU/IRQ/timer or USB input/storage/SSH/RDP liveness measured; no launch. Display evidence remains IMG_6312 from prior image. Verdict: implemented and software-verified; causal hardware hypothesis inconclusive. Recovery candidate .local/recovery-20261104-before-usb1-role retains previous manifested bytes; no ESP or USB-media write. Next operator checkpoint: exact installed hash, new PHY SIG readback then nonzero UsbIo and physical filesystem path; do not call this a working boot until observed.


## EXP-20261104-J413-036 — prepare a pinned install/rollback script

Prepared 2026-11-04T17:00:06.378180+00:00: user explicitly requests an installation script with every build. No hardware installation initiated. Owning sources inspected: scripts/install-esp.sh (current local copy includes automatic fsck), tools/verify_install_image.py, tools/artifact_manifest.py, current MANIFEST.json and live diskutil UUID metadata. Workflow plan: independent installer scripts/install-j413-usb1-phy.py, pinned to boot.bin SHA256 910192421b2292b9a8b7531d645295a52e6bb36c5c5a5878c9ddb6cd93f1f4a9 and recorded internal Asahi ESP PARTUUID 3953DFAE-A571-42D9-9FC7-F962BC4CE923; resolve device by UUID, verify image before mount, preserve and verify fresh backup, stage/verify/rename atomically, print checked rollback command. Existing modified installer remains untouched. Actual installs/restores append before/backup/after entries automatically with commits/diff hashes, command, artifact identity and recovery bytes; never infer a guest boot. No firmware/IRQ/DMA/power/platform changes.

After software verification: seven simulated-ESP tests and three image-identity tests passed. Backup/rename failure keeps original bytes, temporary payload is cleaned, wrong UUID and tampered recovery are rejected, rollback restores exact prior bytes, dry run has no mount or filesystem mutation. Live --dry-run passed under both default Python and /usr/bin/python3 and resolved current disk0s4 by UUID; this was metadata/artifact inspection only. Verdict implemented; no ESP/USB-media write, repair, reboot or runtime validation. Candidate and manifest remain unchanged from EXP035. Next actual command, if operator chooses: sudo /usr/bin/python3 scripts/install-j413-usb1-phy.py ; installation will create its own unique experiment entry and recovery directory.


## EXP-20261104T170037Z-J413-ESP-0ec4f438 — install J413 payload

Before 2026-11-04T17:00:37.913297+00:00: target disk0s4, PARTUUID 3953DFAE-A571-42D9-9FC7-F962BC4CE923; source $PROJECT_ROOT/dist/j413/boot-experiment/boot.bin; SHA256 910192421b2292b9a8b7531d645295a52e6bb36c5c5a5878c9ddb6cd93f1f4a9; source state {"Mu": {"branch": "", "commit": "8b4dc4b4e3ff8606d0af36163acf9de79b7b4737", "diff_sha256": "909433ee62241c9d784b01188b1f79dc1bbd43c007759f38f65df230f9de2cf1"}, "m1n1": {"branch": "", "commit": "9cd80ac652ac404e92ae279deeaec8c629d7d184", "diff_sha256": "c21fa5b54fdd085ed09614abdef38fc86697c9a5efc13949a420c9928b8ee6a8"}, "root": {"branch": "master", "commit": "3f47900686aaa16721c12d6af418ae9b1d97dc1b", "diff_sha256": "ae9df3a12b54a257bdcbbca3f4d3e381d03f3a72553d3e80b63d54d7ce9b7948"}}. Command $PROJECT_ROOT/scripts/install-j413-usb1-phy.py. Recovery destination $PROJECT_ROOT/.local/esp-installs/EXP-20261104T170037Z-J413-ESP-0ec4f438/boot.bin.before. Expected checkpoint: verified atomic payload replacement only; no guest launch. Failure criterion: target, mount, backup, copy or hash verification fails. Evidence: this entry and backup directory; no format, repair, boot-policy change or reboot.

Before replacement EXP-20261104T170037Z-J413-ESP-0ec4f438: recovery $PROJECT_ROOT/.local/esp-installs/EXP-20261104T170037Z-J413-ESP-0ec4f438/boot.bin.before, SHA256 8ddc181829347c35c068ef974c5f904405ed9c742bc1a9f5b368f443581d6578; backup verified. Existing bootability is not newly qualified; macOS startup picker remains recovery.

After 2026-11-04T17:00:38.812081+00:00, EXP-20261104T170037Z-J413-ESP-0ec4f438: installed /Volumes/EFI - UEFI/m1n1/boot.bin, SHA256 910192421b2292b9a8b7531d645295a52e6bb36c5c5a5878c9ddb6cd93f1f4a9; byte verification passed. Verdict: installed; boot/USB/Windows result inconclusive. No boot phases, Windows stop/parameters, CPU/IRQ/timer or display/input/storage/SSH/RDP liveness measured; no reboot or launch. Next checkpoint: operator records this exact image boot and USB1 PHY/child enumeration.


## EXP-20261104-J413-037 — operator cold-boot checkpoint after verified install

Before operator run 2026-11-04T17:03:21.511301+00:00: user reports executing installer and asks whether to reboot. Independent read of /Volumes/EFI - UEFI/m1n1/boot.bin confirms SHA256 910192421b2292b9a8b7531d645295a52e6bb36c5c5a5878c9ddb6cd93f1f4a9; disk0s4 PARTUUID 3953DFAE-A571-42D9-9FC7-F962BC4CE923. Manifest dist/j413/boot-experiment/MANIFEST.json, debug qualification, physical display/debug-off/both M1N1_NO_PROXY stages. Source state {"Mu": {"commit": "8b4dc4b4e3ff8606d0af36163acf9de79b7b4737", "diff_sha256": "909433ee62241c9d784b01188b1f79dc1bbd43c007759f38f65df230f9de2cf1"}, "m1n1": {"commit": "9cd80ac652ac404e92ae279deeaec8c629d7d184", "diff_sha256": "c21fa5b54fdd085ed09614abdef38fc86697c9a5efc13949a420c9928b8ee6a8"}, "root": {"commit": "3f47900686aaa16721c12d6af418ae9b1d97dc1b", "diff_sha256": "929e0a583569eb541ade71dc7b2ca04c09e482a5941ad119439b5697f757c11e"}}. Build command from EXP035: J413_SKIP_MU=1 scripts/build-j413-boot-experiment.sh. Install command and before/after transaction: EXP-20261104T170037Z-J413-ESP-0ec4f438. Installer recorded verified backup .local/esp-installs/EXP-20261104T170037Z-J413-ESP-0ec4f438/boot.bin.before, SHA256 8ddc181829347c35c068ef974c5f904405ed9c742bc1a9f5b368f443581d6578; backup directory root-only, not independently reopened by this user-level process. Recovery command printed by installer; macOS startup picker remains available.

Hypothesis: USB1 external PHY host role correction permits child enumeration. Single functional variable relative to IMG_6312 candidate is initial USB1 PHY SIG host bits; Mu and other hardware setup unchanged. Intended launch: operator saves work, shuts down fully, connects installer to tested USB1, holds power for Startup Options and selects UEFI boot. No agent reboot command. Expected first checkpoint: USB1 host PHY requested/readback=0x1c1700f; then USB interfaces nonzero and physical USB storage filesystem, followed by EFI/BOOT/BOOTAA64.EFI. Failure: mismatch/readback failure, zero USB children, missing storage/loader, hang/reset or Windows stop. Capture photo/video of PHY and USB inventory plus last screen; record elapsed time and any stop parameters. Verdict pending, no launch outcome yet. Do not equate successful ESP write with working USB or Windows.

After operator run 2026-11-04T17:14:08.826093+00:00, EXP-20261104-J413-037: user reports EFI not found again and supplies IMG_6313.HEIC SHA256 31b82919ed3210af8a0172ea62389d7d4851ed4f07d36350a4e97cf34b761b93. Photo shows UEFI Shell mappings for firmware memory, VirtualDisk and internal NVMe partitions; no USB device path/filesystem shown. Early PHY/USB inventory not captured. Pre-run installed hash was independently verified; no post-run hash yet. No Windows stop/parameters or CPU/IRQ/timer/USB input/storage/SSH/RDP liveness measurement. Display and Shell alive; internal storage appears mapped. Verdict: PHY role change alone did not deliver the requested USB boot in this run; the early readback and exact child/port failure remain inconclusive. Do not silently call EXP035 a working USB fix. Next justified step: inspect the connected device and snapshot the controller/PHY/port state without changing another power/reset variable.


## EXP-20261104-J413-038 — inspect USB1 media and hardware-state measurement plan

Before read-only diagnostics 2026-11-04T17:14:08.828234+00:00: inspect current USB1 IORegistry ancestry/descriptors, disk metadata, four Setup payloads and WIM integrity; read existing optional logs. No direct macOS MMIO access, mounted-media writes, repair, reset, ESP install or reboot. Firmware probe design follows current primary source before adding any hardware-changing workaround. Candidate/recovery identities remain EXP035 and EXP-20261104T170037Z-J413-ESP-0ec4f438.


After read-only inspection, EXP-20261104-J413-038: prior-turn descriptor capture is analysis/2026-11-04-usb1-current-descriptors.json. SanDisk was at 480Mb/s on USB1 with SCSI Bulk-Only interface; WININSTALL fallback and payloads checked, boot.wim verification reported success. The temporary WIM verifier log is no longer present in the resumed environment; no fresh integrity verification is inferred. No media write or firmware launch. Verdict: valid media layout on WININSTALL at that inspection; M2BOOT lacks boot.wim/boot.sdi. Firmware enumeration remains unresolved.


## EXP-20261105-J413-039 — bounded discovery and case-insensitive fallback resolution

Before software verification 2026-11-05T11:51:48.693275+00:00: source IDs and dirty diff hashes in analysis/2026-11-05-usb-discovery-source-state.json. Root master; pinned Mu and m1n1 retained. Primary sources and ownership in analysis/2026-11-04-usb-discovery-plan.md with current addendum to follow. Functional variable: discovery policy only (bounded asynchronous publication window and exact component matching). Hardware reset/power/DMA/IRQ/PHY writes unchanged. Hypothesis: a later SimpleFS and mixed-case standard ARM64 fallback are selected; arbitrary names and wrong architectures remain rejected. Command python3 -m unittest discover -s tests -p test_j413*.py . Old mixed-case regression fails on prior source; new actual C passes under sanitizers. Current hardware inspection shows hubs only, no external disk, as captured in analysis/2026-11-05-current-usb.json. No install or launch; existing EXP035 candidate and recovery remain unchanged. Physical USB enumeration success is not inferred.


After software verification 2026-11-05T11:59:39.934431+00:00, EXP-20261105-J413-039: 57 focused tests, 56 pass/one skipped. Actual delayed filesystem scanner, mixed-case exact path, malformed records and wrong PE architecture/subsystem, timer failure cleanup and bounded read-only probes passed ASan/UBSan. New source commits 8bf40f448858b6ae35750f0b25a00bf1c1db4de2 and 0f1bc5b; no hardware launch or install. Verdict implemented; hardware causality inconclusive.


## EXP-20261105-J413-040 — build bounded ARM64 USB discovery candidate

Before build 2026-11-05T11:59:39.934431+00:00: identities and dirty diffs analysis/2026-11-05-usb-build-source-state.json; plan analysis/2026-11-05-usb-boot-plan.md. Single functional firmware variable: loader discovery policy; read-only diagnostic overhead explicitly recorded. Command scripts/build-j413-boot-experiment.sh > investigation/analysis/2026-11-05-usb-build.log 2>&1 . Output dist/j413/boot-experiment, debug qualification/physical/debug-off, both stages no-proxy. New SHA pending build and mandatory before any install. Prior boot.bin SHA 910192421b2292b9a8b7531d645295a52e6bb36c5c5a5878c9ddb6cd93f1f4a9 and full manifested candidate copied to .local/recovery-20261105-before-discovery with RECOVERY_HASHES.json; this is a recovery candidate, not hardware-validated Windows. Previously installed bytes and backup remain EXP037. Expected checkpoint: complete Mu/two-stage build, source/nested/CRC/manifest validation. Failure criterion: compile/contract/manifest mismatch. No launch/install/reboot initiated. Hardware checkpoint deferred to physical USB child/filesystem/selection and resulting Windows phase.


## EXP-20261105T120605Z-USB-MEDIA-d9d9cb60 — complete FAT WinPE payloads

Before 2026-11-05T12:06:06.059922+00:00: command scripts/complete-j413-usb-media.py; source /Volumes/WININSTALL UUID 6EF78F22-8A6D-454C-880E-1DDD706CADE4; target /Volumes/M2BOOT UUID D0E51975-0AE3-45C5-8EE0-85C51B0FCC78; root branch master; source state {"Mu": {"branch": "", "commit": "8b4dc4b4e3ff8606d0af36163acf9de79b7b4737", "diff_sha256": "5be9691f92479414347b9e30a257d130cc530825a9b13b2c13a33db769aa7321"}, "m1n1": {"branch": "", "commit": "9cd80ac652ac404e92ae279deeaec8c629d7d184", "diff_sha256": "c21fa5b54fdd085ed09614abdef38fc86697c9a5efc13949a420c9928b8ee6a8"}, "root": {"branch": "master", "commit": "4e6dff47bd2493e7309651a88964f13a25a3b4fe", "diff_sha256": "9b981d5ad6c4271725aabb2582fc9b365a664906f59ee68cb136f856bb31bd0b"}}; manifest/recovery record $PROJECT_ROOT/.local/usb-media/EXP-20261105T120605Z-USB-MEDIA-d9d9cb60/MANIFEST.json; SHA256 0c5dd2a3e625315629270ee5eb5a1fd33dea5754b8a9118e3b5c98e38cb91961; payload hashes {"boot/boot.sdi": "cd2c00ce027687ce4a8bdc967f26a8ab82f651c9becd703658ba282ec49702bd", "efi/boot/bootaa64.efi": "fae47d78487e781aa06466775cb461adeb7ff7f887fe2c15295bb2eb4f4954e1", "efi/microsoft/boot/bcd": "b90ef16b94c3dda7d76cc39840befaa9786887517445c3b6f47ebc806d0ab105", "sources/boot.wim": "dcf58a3d6be5d8747ba8b475f6bbc3782a53bc5dc14c7b11e73ff140deeab534"}. Hypothesis: adding only missing ['sources/boot.wim', 'boot/boot.sdi'] completes the FAT partition WinPE relative paths. Existing loader/BCD and all firmware/partitions unchanged. Expected checkpoint: matching destination hashes and four valid headers; no firmware launch.

After 2026-11-05T12:07:58.484485+00:00, EXP-20261105T120605Z-USB-MEDIA-d9d9cb60: verified ['sources/boot.wim', 'boot/boot.sdi']; four boot headers valid; verdict implemented, physical boot inconclusive. No boot phases, stop code, CPU/IRQ/timer, USB input/SSH/RDP/storage liveness measured; no reboot.


After software build/verification 2026-11-05T12:16:22.931135+00:00, EXP-20261105-J413-040: full ARM64 Mu and two m1n1 stages built; image 817b006fb1f5c9c23140dba3410ca2a6caa01fa0b3c73bb590324682289cc4ed size 2541096; Mu 41d910d08439e5fd0c902af4d9164675f25ddabd4d3f6d0482e572c3ed9daa8f size 30965760; manifest dist/j413/boot-experiment/MANIFEST.json, debug qualification/physical/off, both no-proxy stages. Current overlay/source digests, nested launch/CRC and image identity verified. Latest focused suite 69 tests, 68 pass/one skipped. Full run 1583 tests in 128.509s has 91 failures/55 errors/42 skips; failure-header set exactly matches previous 1561-test run, recorded in analysis/2026-11-05-test-results.json. Last installer-only addition verified by focused tests; no second full run claimed. Build/logs and machine-readable summary analysis/2026-11-05-usb-boot-validation.json. WIM integrity passed; all eight USB EFI files, extracted WinPE winload.efi and ntoskrnl.exe are ARM64. No native boot phases/times, Windows stop, CPU/IRQ/timer or display/input/USB/SSH/RDP liveness for this candidate. Verdict implemented; hardware outcome inconclusive. Recovery artifacts remain .local/recovery-20261105-before-discovery.

Operator clarification 2026-11-05T12:16:22.931135+00:00: prior internal Asahi/UEFI installation was deleted. Fresh diskutil list confirms no internal ESP or stub installation. This supersedes only the current availability assumption from EXP037; it does not rewrite the earlier observed boot/install result. New script scripts/install-j413-usb-discovery.py pins current bytes; offline --verify-only passes. Its target preflight correctly rejects the absent old UUID before any disk mount/write. --esp-uuid supports a separately recreated and explicitly identified ESP. No repartition, bootstrap recreation or reboot performed, consistent with the operator request to verify before reinstalling. Native 100 percent functionality cannot be inferred before a physical boot and is not claimed.

Software test-harness correction: while extending installer tests, the first inherited fixture patched the old module instead of the new module. It attempted local backup-directory setup and was denied before any disk mount or payload write. The fixture now patches each selected module and asserts temporary-root/backup isolation; all 15 installer tests pass. No internal ESP was present or modified.

Final read-only cross-check 2026-11-05T12:19:06.035816+00:00: source overlays/manifests still match image SHA817b006fb1f5c9c23140dba3410ca2a6caa01fa0b3c73bb590324682289cc4ed; new installer --verify-only passes under /usr/bin/python3 and all 15 installer tests pass. Fresh USB1 descriptor/link is 5Gb/s with bcdUSB 0x0320, not the previous 480Mb/s descriptor; recorded in analysis/2026-11-05-current-usb-after-reconnect.json. Previous USB2 fallback observation remains historical capability evidence only. Operator explicitly requires verification before reinstalling; no bootstrap recreation or internal payload installation/reboot performed. Validation summary analysis/2026-11-05-usb-boot-validation.md states all remaining physical/runtime limits.


## EXP-20261105-J413-043 — direct same-volume installer and driver ownership audit

Before read-only source/software diagnostics 2026-11-05T12:33:41.651169+00:00: source identity/diff hashes analysis/2026-11-05-direct-setup-driver-source-state.json; root master; pinned submodules unchanged. User confirms the current goal is Windows Setup, not an installed OS, and asks for fixed same-volume boot plus missing drivers. Capture current macOS ADT and disk topology; inspect Asahi implementations, pinned m1n1 stage/variable handling, Mu ACPI/BDS/storage, Microsoft WDK/VHF/WinPE interfaces and prior EXP037/040. No hardware MMIO writes, install, formatting, partition creation, driver deployment or reboot. Current candidate SHA817b006fb1f5c9c23140dba3410ca2a6caa01fa0b3c73bb590324682289cc4ed, manifest dist/j413/boot-experiment/MANIFEST.json, physical/off/debug qualification; recovery .local/recovery-20261105-before-discovery. Expected checkpoint: a falsifiable direct-boot design tied to an explicit partition identity, and source-backed driver gaps; no invented runtime completion.


## EXP-20261105-J413-044 — local single-volume Setup artifact

Before local artifact build 2026-11-05T12:54:06.351774+00:00: source states/diffs analysis/2026-11-05-direct-media-before.json. Functional variable is Setup packaging/target identity, no hardware configuration. Create only .local/direct-setup/J413SETUP.sparseimage as a new 12GiB GPT/FAT32 disk image; obtain its partition UUID from hdiutil/diskutil metadata; build a direct loader for that exact identity. Commands hdiutil create -size 12g -type SPARSE -fs MS-DOS-FAT32 -layout GPTSPUD -volname J413SETUP ; wimlib-imagex verify /Volumes/WININSTALL/sources/install.wim ; stage same-volume boot/EFI/source files and split the greater-than-4GB install.wim into FAT-sized SWM pieces. New artifact hashes/manifests will be mandatory before any native launch. Current candidate SHA817b006fb1f5c9c23140dba3410ca2a6caa01fa0b3c73bb590324682289cc4ed and its manifested recovery remain unchanged. Target is a newly created local image, not the physical USB or internal disk. No partition resize, installed ESP write, bootstrap enrollment or reboot. Expected checkpoint: complete and hash-verified same-volume media, fixed GUID selection and software build; no native USB/Windows/driver success inferred.


## EXP-20261105-J413-045 — build fixed-partition Setup candidate

Before software build 2026-11-05T13:13:36.633349+00:00: source IDs/diffs and local target analysis/2026-11-05-direct-build-state.json. Root master 015b78fdfd58b5f5884ae260fd6e2f96c11c8da7; same pinned dirty submodules. Source plan analysis/2026-11-05-direct-setup-driver-plan.md. The operator delegates target choice; choose a same-volume internal-style FAT bundle to remove USB storage from the intended installer path, but prepare it only as the new local disk image now. Target partition UUID 9E7B3C33-1721-4EBF-8C9C-A5D4A798B224 is the mounted image, not an internal installation. Command scripts/build-j413-boot-experiment.sh > investigation/analysis/2026-11-05-direct-build.log 2>&1 . Full Mu/two-stage build, physical/off/debug qualification. Changed functional software contracts are explicit early NVMe root binding plus fixed GPT selection; no causal attribution between them without separate future hardware checkpoints. No reset/PHY/DMA/IRQ/Windows-driver runtime change. Prior candidate SHA817b006fb1f5c9c23140dba3410ca2a6caa01fa0b3c73bb590324682289cc4ed and manifest preserved in .local/recovery-20261105-before-direct-setup. New hashes mandatory after build; no native install or launch. Expected checkpoint: matching firmware/target/source/nested manifests and complete local Setup volume, not native Windows success.

After first software build 2026-11-05T13:18:42.239751+00:00, EXP-20261105-J413-045: Mu compilation rejected unused J413NextEfiOption under warnings-as-errors after direct selection replaced its caller. No new boot.bin was published and no launch occurred. Verdict rejected for that build. Correct direct-only preprocessing to exclude the obsolete generic queue/scanner instead of suppressing the compiler warning; add strict actual-header compilation regression before retry. Previous manifested recovery remains intact.


## EXP-20261105-J413-046 — direct-only compiler correction and build retry

Before software rebuild 2026-11-05T13:19:26.095815+00:00: source/diff identity analysis/2026-11-05-direct-build-retry-state.json, root f8724ceafc09293db6a22b5631901c674979fa8b. Relative to failed EXP045 only direct-only compilation/bookkeeping is corrected; no additional hardware or launch behavior changed. Command scripts/build-j413-boot-experiment.sh > investigation/analysis/2026-11-05-direct-build-retry.log 2>&1 . Same local disk-image target UUID9E7B3C33-1721-4EBF-8C9C-A5D4A798B224, physical/off/debug qualification, new SHA pending build. Prior manifested candidate/recovery .local/recovery-20261105-before-direct-setup untouched. Expected build/manifest/source/nested success; no physical install/launch/reboot.


## EXP-20261105T132915Z-DIRECT-SETUP-cd38e02a — same-volume Setup staging

Before 2026-11-05T13:29:15.222806+00:00: target /Volumes/J413SETUP PARTUUID 9E7B3C33-1721-4EBF-8C9C-A5D4A798B224; firmware SHA256 bcfedfbfe7695014503fdc64c871f9a490f91be6cef927002ec2f3dcbcbef1d6; manifest $PROJECT_ROOT/dist/j413/boot-experiment/MANIFEST.json; command ['tools/j413_setup_bundle.py', '--source', '/Volumes/WININSTALL', '--volume', '/Volumes/J413SETUP', '--partition-uuid', '9E7B3C33-1721-4EBF-8C9C-A5D4A798B224', '--apply']. Existing different files are rejected before copy; original source and internal partition layout are preserved. Expected checkpoint complete hashed ARM64 FAT32 Setup plus firmware on one volume; no launch.

After 2026-11-05T13:32:49.522785+00:00, EXP-20261105T132915Z-DIRECT-SETUP-cd38e02a: staged and hash/WIM verified; MEDIA.json /Volumes/J413SETUP/J413Setup/MEDIA.json; verdict implemented; no native boot phases, stop code, CPU/IRQ/timer/input/storage/network liveness or reboot.

Publication privacy correction 2026-11-05T13:38:57.887132+00:00: before the user-authorized HackWinDos source publication, fixed machine-specific console/vUART endpoint strings were replaced with placeholders in historical public documentation and with explicit environment inputs in launchers. This is privacy/portability redaction only; no prior verdict, stop code, artifact hash, hardware result or elapsed-time assertion was changed. Original exact file bytes and SHA256 are preserved under .local/github-publish/private-source/SHA256.json and local Git history. Source histories are unrelated to current GitHub main; publish a reviewed source snapshot as a child of its existing head without force. User explicitly requests main only; remote branch inventory contains only main, recorded in .local/github-publish/REMOTE-BRANCHES.before.txt.

After software verification 2026-11-05T13:46:21.724146+00:00, EXP-20261105-J413-046: full Mu and two-stage rebuild succeeded. boot.bin size 2541000 SHA256 bcfedfbfe7695014503fdc64c871f9a490f91be6cef927002ec2f3dcbcbef1d6; J413_EFI.fd SHA256 234421d3d1abb053cf0e9b17901edd88adf31e2a86afa5bbf35486f066d42d58; overlay c2d388806b05840e6dbafe7ee4636ff2a82803420baaa49c8dae941592842e60. Exact image/nested CRC/profile/current source checks and installer --verify-only passed. Focused tests at this checkpoint: 92 J413 tests, 91 pass/one skip. Log analysis/2026-11-05-direct-build-retry.log. No physical install/launch, boot phases, elapsed guest time, stop code/parameters, CPU/IRQ/timer or display/USB/storage/SSH/RDP liveness was measured. Verdict implemented; native causality inconclusive. This artifact is preserved before the next single-variable Aurora DART admission build.

After software preparation 2026-11-05T13:46:21.724146+00:00, EXP-20261105-J413-043 and EXP-20261105-J413-044: direct GUID-only selection and single-volume staging implemented, not hardware-qualified. New local 12GiB sparse image .local/direct-setup/J413SETUP.sparseimage PARTUUID 9E7B3C33-1721-4EBF-8C9C-A5D4A798B224 mounted as /Volumes/J413SETUP; no physical partition change. Actual stage EXP-20261105T132915Z-DIRECT-SETUP-cd38e02a copied/hash-verified 964 files and two split install WIM parts. Full original install.wim and staged boot/split WIM integrity verified; all 3 installation images and both PE/Setup images declare ARM64. Physical USB source remains unchanged. DockChannel software logic fixed; native Windows SYS/driver/hardware qualification still missing. No runtime observations; verdict implemented and native boot inconclusive.


## EXP-20261105-J413-047 — Aurora DART readback admission build

Before software build 2026-11-05T13:48:20.976179+00:00: source identities analysis/2026-11-05-aurora-build-state.json; branch main root 2877f7e320acbcbebcb0ab23493a5a5eb144b0b6. Hypothesis: verifying every TCR prevents false readiness when a requested bypass value fails to latch. Single behavior variable: actual DART readback admission; no initialization write/reset/power/IRQ/DMA/address change. Plan/source/license review analysis/2026-11-05-aurora-integration-plan.md. Build command scripts/build-j413-boot-experiment.sh > investigation/analysis/2026-11-05-aurora-build.log 2>&1 . Target remains local-image PARTUUID 9E7B3C33-1721-4EBF-8C9C-A5D4A798B224, debug qualification/physical/off/both no-proxy stages. Prior image SHA256 bcfedfbfe7695014503fdc64c871f9a490f91be6cef927002ec2f3dcbcbef1d6 and manifest preserved .local/recovery-20261105-before-aurora-dart/boot-experiment plus SHA256.json. Expected checkpoint build and exact nested/profile/source manifests; smallest future physical check both DART banks read back bypass then nonzero UsbIo. Failure exact bank/SID/TCR or build error. No install/launch/reboot; recovery macOS and preserved previous bytes.

After software build 2026-11-05T13:52:42.582846+00:00, EXP-20261105-J413-047: full Mu plus both ARM64 m1n1 stages succeeded; boot.bin 2541252 bytes SHA256 42fe5acbd493cd66e765a64df91f5b49b62042512748242b1276643de58203e8; J413_EFI.fd SHA256 27a8a1968a9c2605a40ba0b87f96a846036152555e698ea28d7f5d3b48e8b8d4; manifest dist/j413/boot-experiment/MANIFEST.json, overlay 2bcca8cff187f8d3f11b9ad2f53b876b46a76cf0088fb7084be7c6d8ef1b7841. Nested CRC/profile and exact artifact validation passed; build log analysis/2026-11-05-aurora-build.log. Prior direct image preserved as recorded. No physical install/launch/reboot and no boot phases, stop code/parameters, CPU/IRQ/timer or display/USB input/storage/SSH/RDP liveness measured. Verdict implemented; hypothesis of false software admission confirmed by regression, physical causal hypothesis inconclusive. Next smallest physical checkpoint both DART banks accepted then USB enumeration, independently of direct NVMe volume selection.


## EXP-20261105-J413-048 — update only firmware in verified local Setup image

Before 2026-11-05T13:53:19.021035+00:00: local virtual FAT volume /Volumes/J413SETUP PARTUUID 9E7B3C33-1721-4EBF-8C9C-A5D4A798B224; new firmware SHA256 42fe5acbd493cd66e765a64df91f5b49b62042512748242b1276643de58203e8 manifest dist/j413/boot-experiment/MANIFEST.json, debug/physical/off; root 7ced3c088f750ac512c7e7df39e29efd2a73c531. Exact prior payload SHA256 bcfedfbfe7695014503fdc64c871f9a490f91be6cef927002ec2f3dcbcbef1d6 and four provenance files preserved under .local/recovery-20261105-before-aurora-media. Command python3 .local/task-tools/update_local_media.py. Single variable relative to verified EXP044 is firmware DART-readback admission; Microsoft installer bytes/WIMs unchanged. First recheck every recorded file/part hash against old manifest; only then atomically replace local firmware/metadata and verify new manifest. No physical partition/image install or launch. Failure criterion mismatched identity/hash or copy/verify error; recovery prior local files and source sparse image.

After 2026-11-05T13:53:40.370347+00:00, EXP-20261105-J413-048: previous full media hashes passed; new local firmware and provenance replaced and all hashes passed again. No Microsoft installer content changed; source/split WIM integrity from EXP044 preserved. Verdict implemented, native boot inconclusive; no CPU/IRQ/timer/stop/liveness or guest phase measurements. No reboot.

Final software verification 2026-11-05T13:53:58.031327+00:00: full root suite 1611 tests, 90 failures, 55 errors, 42 skips; compared with 1583-test prior run (91 failures/55 errors/42 skips) there are no newly failing test headers and the host-path hygiene failure is removed. Focused J413 suite 92 tests: 91 pass/one skip; 25 installation transaction tests and 9 artifact-manifest tests pass. Exact full-suite paths/delta: analysis/2026-11-05-final-tests-summary.json and local analysis/2026-11-05-final-full-suite.log. No all-project pass or native readiness is claimed. Colima started for builds is stopped after containers finished.


## EXP-20261105-J413-049 — first public DockChannel WDK build result

Late result entry 2026-11-05T14:05:38.441731+00:00: build triggered by source publication 634a6579323e8041cfb1ba6201cd59c6a1a8346f; workflow intent was recorded before publication in CHG-20261105-012. Run https://github.com/Liamsitbon/HackWinDos/actions/runs/42040693239 job 127290434000, Windows-2025-vs2026 ARM64 Debug WDK 10.0.28000.2526; command msbuild drivers\apple-dockchannel\windows\AppleDockChannel.vcxproj /m /t:Clean,Build /p:Configuration=Debug /p:Platform=ARM64 /p:RunCodeAnalysis=true . Restore succeeded; ClCompile failed with C2220/C4005/C4083 from user vcruntime vs WDK km/crt conflicts; 40 warnings/9 errors; no SYS artifact. Verdict rejected for that software build. No hardware launch or liveness/stop/IRQ/timer evidence. Next change only the compile-time kernel header boundary and required build inputs.


## EXP-20261105-J413-050 — DockChannel kernel-header build correction

Before software rebuild 2026-11-05T14:05:38.441891+00:00: root main 938d8ddd8a89afab273c69a2452cc3e051db0a51; m1n1/Mu pins unchanged as EXP047; only driver/build inputs changed, no firmware rebuild/physical launch. Source MSVC /kernel documentation confirms _KERNEL_MODE=1; existing AppleInput kernel aliases and WDK 28000 first-run diagnostics inspected. Ownership, register/IRQ/DMA/power contracts unchanged. Build command same as EXP049, triggered by publishing this correction to main. Profile ARM64 Debug, artifact SYS/INF/CAT hashes pending successful build. Recovery current 42fe5acb firmware and prior local image backups; no previous DockChannel SYS existed to replace. One actual ARM64 COFF compilation regression (seven cores) passes with user CRT headers forbidden; no broad suite run. Expected checkpoint a linked ARM64 native SYS and catalog/metadata; failure compile/link/package error. No install or runtime qualification.


## EXP-20261105T143017Z-J413-MEDIA-MOVE — relocate generated media before provisioning

Before 2026-11-05T14:30:17.662030+00:00: preserve the complete generated sparse image at /Volumes/WININSTALL/HackWinDos-Staging/J413SETUP.sparseimage before freeing its internal allocation; original Microsoft installer remains untouched. Firmware manifest dist/j413/boot-experiment/MANIFEST.json, SHA256 42fe5acbd493cd66e765a64df91f5b49b62042512748242b1276643de58203e8. No physical partition write or launch in this phase.

After 2026-11-05T15:03:41.798865+00:00, EXP-20261105T143017Z-J413-MEDIA-MOVE: entire generated image preserved and hash-verified SHA256 da50f8a9f4f5dcb424302a0bc99995d5299671aa32feddbffddec123ff6457db; original local path is now a symlink. No Windows source file or physical partition changed; no launch. Verdict implemented.


## EXP-20261105T173236Z-J413-PROVISION — fresh internal UEFI-only host installation

Before 2026-11-05T17:32:36.806497+00:00: plan .local/asahi-uefi/PLAN.json, SHA256 85060aa846904692e09793edb63b8fb80cec598920f5f446daa6cd22adfb4910; source state {"Mu": {"commit": "8b4dc4b4e3ff8606d0af36163acf9de79b7b4737", "diff_sha256": "eed245e86f681724681857b9ed9c3401d8b715ff2a38ea4683c1657294d07b22"}, "m1n1": {"commit": "9cd80ac652ac404e92ae279deeaec8c629d7d184", "diff_sha256": "c21fa5b54fdd085ed09614abdef38fc86697c9a5efc13949a420c9928b8ee6a8"}, "root": {"commit": "a0f7827c358a1c4de2bea01643daea0707c5cf19", "diff_sha256": "67e1bc6537078fd062e5cd9f1110c7e43aeec9d326bc4a1ef51e0b1380abf0ce"}}; official installer archive SHA256 484d999e53b4aef27d17c4478e49567e96842f8a6cb35c073a0df5bf0bbe8276, UEFI package SHA256 fd886f920807a4cd09b816b0b48ebfc83809cf07dc050ad43a677fb6d0663cb4. Current physical store disk0s2 UUID E46E1C83-9FCD-4138-8941-2A1F091A21A8; resize target 233000927232 bytes; new 2.5GB stub plus 9.5GB FAT ESP. Adapter policy reserves at least 32GB macOS free space and respects the live APFS preferred minimum; upstream default is 38GB. Recovery original macOS ISC/Recovery retained, preserved generated installer and manifested firmware backups. Expected host checkpoint fresh stub/ESP identities then same-volume Setup and explicit rebuild. Failure wrong identity/space or installer error; stop without automated repair. No shutdown/reboot or Windows launch.

After 2026-11-05T17:54:58.981655+00:00, EXP-20261105T173236Z-J413-PROVISION: official host installation complete; result .local/asahi-uefi/RESULT.json. New stub/ESP created and blessed through owner authentication. Recovery enrollment and Windows/USB/GPU/CPU/IRQ/timer/liveness unmeasured. Verdict installed on host, native boot inconclusive; no reboot.


## EXP-20261105T175459Z-J413-NATIVE-TARGET — bind the newly provisioned physical ESP

Before 2026-11-05T17:54:59.208266+00:00: target PARTUUID 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB; source state {"Mu": {"commit": "8b4dc4b4e3ff8606d0af36163acf9de79b7b4737", "diff_sha256": "eed245e86f681724681857b9ed9c3401d8b715ff2a38ea4683c1657294d07b22"}, "m1n1": {"commit": "9cd80ac652ac404e92ae279deeaec8c629d7d184", "diff_sha256": "c21fa5b54fdd085ed09614abdef38fc86697c9a5efc13949a420c9928b8ee6a8"}, "root": {"commit": "a0f7827c358a1c4de2bea01643daea0707c5cf19", "diff_sha256": "153647eb41c9db8fdf6632c2379b92845c370022e9aac1dc1176c93806dceb57"}}; command scripts/build-j413-boot-experiment.sh. Single firmware variable relative to EXP047 is the direct target UUID. Prior manifested image preserved .local/recovery-before-native-target. Expected build/manifest then atomic Setup staging/install; no guest launch; Recovery enrollment remains operator-owned.

Before install EXP-20261105T175459Z-J413-NATIVE-TARGET: manifest dist/j413/boot-experiment/MANIFEST.json, SHA256 e3919fd288efc0cb0577274a2b9bec0c7b553691c6a760ec1f7ef1be725404e6; debug/physical/off; exact native ESP 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB. Install command uses the pinned transactional installer, fresh verified bootstrap recovery and same-volume media hashes.


## EXP-20261105T181629Z-J413-ESP-3147fefc — install J413 payload

Before 2026-11-05T18:16:58.542311+00:00: target disk0s4, PARTUUID 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB; source $PROJECT_ROOT/dist/j413/boot-experiment/boot.bin; SHA256 e3919fd288efc0cb0577274a2b9bec0c7b553691c6a760ec1f7ef1be725404e6; source state {"Mu": {"branch": "", "commit": "8b4dc4b4e3ff8606d0af36163acf9de79b7b4737", "diff_sha256": "eed245e86f681724681857b9ed9c3401d8b715ff2a38ea4683c1657294d07b22"}, "m1n1": {"branch": "", "commit": "9cd80ac652ac404e92ae279deeaec8c629d7d184", "diff_sha256": "c21fa5b54fdd085ed09614abdef38fc86697c9a5efc13949a420c9928b8ee6a8"}, "root": {"branch": "main", "commit": "a0f7827c358a1c4de2bea01643daea0707c5cf19", "diff_sha256": "ad8065b0e9d6a24caf45b4316b6618d9895714f5916e00be420542d3d3bebc67"}}. Command $PROJECT_ROOT/scripts/install-j413-direct-setup.py --esp-uuid 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB --image-sha256 e3919fd288efc0cb0577274a2b9bec0c7b553691c6a760ec1f7ef1be725404e6 --setup-source /Volumes/WININSTALL. Recovery destination $PROJECT_ROOT/.local/direct-setup-installs/EXP-20261105T181629Z-J413-ESP-3147fefc/boot.bin.before. Expected checkpoint: verified atomic payload replacement only; no guest launch. Failure criterion: target, mount, backup, copy or hash verification fails. Evidence: this entry and backup directory; no format, repair, boot-policy change or reboot.

Before replacement EXP-20261105T181629Z-J413-ESP-3147fefc: recovery $PROJECT_ROOT/.local/direct-setup-installs/EXP-20261105T181629Z-J413-ESP-3147fefc/boot.bin.before, SHA256 f4ce681bdb07cc897eb997a37858712b1ffc48ae1b4770e4d05b982ecffb1f23; backup verified. Existing bootability is not newly qualified; macOS startup picker remains recovery.

After 2026-11-05T18:22:21.115497+00:00, EXP-20261105T181629Z-J413-ESP-3147fefc: installed /Volumes/EFI - HACKW/m1n1/boot.bin, SHA256 e3919fd288efc0cb0577274a2b9bec0c7b553691c6a760ec1f7ef1be725404e6; byte verification passed. Verdict: installed; boot/USB/Windows result inconclusive. No boot phases, Windows stop/parameters, CPU/IRQ/timer or display/input/storage/SSH/RDP liveness measured; no reboot or launch. Next checkpoint: operator records fixed-volume NVMe/ARM64 loader entry and the actual resulting Windows phase.

After 2026-11-05T18:22:21.160866+00:00, EXP-20261105T175459Z-J413-NATIVE-TARGET: physical ESP Setup/candidate installed through recorded transaction; SHA256 e3919fd288efc0cb0577274a2b9bec0c7b553691c6a760ec1f7ef1be725404e6. No reboot or native boot result; Recovery enrollment pending. Verdict installed, runtime inconclusive.

After Windows software build 2026-11-05T18:22:37.414364+00:00, EXP-20261105-J413-050: official WDK ARM64 Debug compilation/link/code analysis/packaging succeeded; run https://github.com/Liamsitbon/HackWinDos/actions/runs/42041739601 job 127294005231 source 178670b624e05a5e1d8b2f7e332b47537fa1f93e. Actual 35848-byte SYS SHA256 8c71e11349967c6162277f71eb4f90732407572f0956efe04aa0f3a122bbec33; INF/CAT/archive identities analysis/2026-11-05-dockchannel-wdk-result.json; archive digest matches GitHub. Packaged dist/j413-drivers-20261105-dockchannel with install-drivers.ps1 and manifest. Verdict implemented. Catalog trust, MTP helper/DART/GPIO/IRQ/HID adaptation and actual Windows input remain unqualified. No driver installation, hardware stop/CPU/IRQ/timer or liveness measurement. No broad suite rerun after the operator requested focusing on implementation.


## EXP-20261105-J413-051 — complete native bundle provenance

Before 2026-11-05T18:24:31.922182+00:00: bootstrap on internal ESP 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB independently reads SHA256 e3919fd288efc0cb0577274a2b9bec0c7b553691c6a760ec1f7ef1be725404e6. No bootstrap or firmware behavior change. Add the separately inspectable FD and Recovery guide to the now-installed bundle; exact manifest dist/j413/boot-experiment/MANIFEST.json. Preserve original MEDIA metadata under .local/asahi-uefi/MEDIA.before-provenance.json. No launch.

After 2026-11-05T18:24:32.222907+00:00, EXP-20261105-J413-051: FD copy verified and bootstrap identity unchanged; native media metadata now includes both installed firmware files and the Recovery guide. Verdict implemented; no native Windows run, stop/IRQ/timer/CPU or liveness result.

Planning-margin correction 2026-11-05T18:29:58.245316+00:00, referencing EXP-20261105T173236Z-J413-PROVISION: the actual post-build macOS free space was 27542269952 bytes, below the initial 32GB planning floor because later compiler/VM allocation was not reserved. Do not reinterpret the original plan as a post-build guarantee. Future provisioning now requires an additional 8GB build reserve and repeats the admission at the root boundary. The completed partition layout and installed firmware are unchanged. One bounded in-memory regression covers the margin; no broad suite or additional hardware experiment.


## EXP-20261105-J413-052 — first Recovery/native integration checkpoint

Before operator run 2026-11-05T18:29:58.245330+00:00: source state {"Mu": {"commit": "8b4dc4b4e3ff8606d0af36163acf9de79b7b4737", "diff_sha256": "eed245e86f681724681857b9ed9c3401d8b715ff2a38ea4683c1657294d07b22"}, "m1n1": {"commit": "9cd80ac652ac404e92ae279deeaec8c629d7d184", "diff_sha256": "c21fa5b54fdd085ed09614abdef38fc86697c9a5efc13949a420c9928b8ee6a8"}, "root": {"commit": "d8347ab29277513c47df4875645b21cb0f5afe9e", "diff_sha256": "9be51e79092812e3c2835b4ba8da0faef15c3055735719e9bccfd2eae2d8221b"}}; branch main; artifact dist/j413/boot-experiment/boot.bin SHA256 e3919fd288efc0cb0577274a2b9bec0c7b553691c6a760ec1f7ef1be725404e6; debug/physical/off and both no-proxy stages; manifest dist/j413/boot-experiment/MANIFEST.json. Independent read of the actual internal ESP bootstrap matches. Direct target 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB and full ARM64 Setup are on that ESP; media and split WIM identities analysis/2026-11-05-native-host-result.json. Official bootstrap recovery .local/direct-setup-installs/EXP-20261105T181629Z-J413-ESP-3147fefc/boot.bin.before SHA256 f4ce681bdb07cc897eb997a37858712b1ffc48ae1b4770e4d05b982ecffb1f23. Build/install commands and before/after outcomes are recorded in EXP-20261105T175459Z-J413-NATIVE-TARGET and EXP-20261105T181629Z-J413-ESP-3147fefc. Intended launch: operator saves work, fully shuts down, waits 25 seconds, holds power for Startup Options, selects HackWinDos UEFI and completes owner-authenticated paired Recovery. No agent shutdown/reboot. Expected first checkpoints boot option visible, Recovery enrollment then fixed-GUID NVMe loader selection and Windows Setup. Failure any absent option, error, reset, hang or Windows stop; capture last screen, elapsed phase and exact parameters. This establishes a new integration baseline with cumulative recorded software changes, not causal proof of one USB fix. Display, USB input/storage, SSH/RDP, all CPUs and IRQ/timer liveness remain unmeasured until the actual run. Verdict pending; no launch outcome yet.


After operator run 2026-11-05T20:50:30.753061+00:00, EXP-20261105-J413-052: IMG_6327.HEIC SHA256 89eebc334f6e56b83345a89138ca140bf464eb7b04abe4b1cea4452e5b3ac1fa; user reports several hours with stationary screen. Native Mu console and BDS priority boot reached, Setup protocol lookup Success and final line "UEFI NVMe: PCI root lookup Success; roots 1". No root connection-return marker, target-volume selection, EFI loader or Windows entry observed. Exact elapsed time unknown. Display last frame visible; USB input, storage BlockIo, SSH/RDP, CPUs, IRQ/timer liveness unmeasured. No Windows stop code/parameters shown. Pre-run independently verified bootstrap e3919fd288efc0cb0577274a2b9bec0c7b553691c6a760ec1f7ef1be725404e6; no post-run read yet. Verdict rejected for this integration trial: hang is inside recursive PCI-root ConnectController or descendants; individual driver and cause remain unknown. Native Mu proves progress past the owner enrollment launch boundary, without independent Recovery log verification. Evidence analysis/2026-11-05-nvme-stall-result.json. Next single behavior variable: replace recursive whole-tree binding with staged nonrecursive synthetic-NVMe/namespace binding and mount only the exact GPT target. Do not attribute the hang to missing EFI or Windows drivers.


## EXP-20261105-J413-053 — staged fixed-volume NVMe binding

Before software build 2026-11-05T20:53:50.302886+00:00: branch main; source state analysis/2026-11-05-nvme-scope-build-state.json; plan analysis/2026-11-05-nvme-scope-plan.md. Single firmware behavior variable relative to e3919fd2: nonrecursive protocol-layer connection and filesystem attachment limited to the configured GPT target. Normal USB/security/loader/IRQ/timer/DMA/backend behavior unchanged. Build command scripts/build-j413-boot-experiment.sh > .local/nvme-stall/build.log 2>&1 . Manifest dist/j413/boot-experiment/MANIFEST.json, debug/physical/off/both no-proxy stages; new artifact SHA pending build and required before installation. Recovery exact preceding manifested image .local/recovery-20261105-before-nvme-scope/boot-experiment/boot.bin SHA256 e3919fd288efc0cb0577274a2b9bec0c7b553691c6a760ec1f7ef1be725404e6 (observed Mu boundary), official Asahi bootstrap f4ce681b remains preserved. Expected software checkpoint actual C policy regression plus native build/profile/provenance; next hardware checkpoint root enumeration return then NVMe controller/namespace/target filesystem return and fixed ARM64 loader. Failure build/manifest mismatch or stationary per-level entry. No install/launch/reboot in this build; physical causal hypothesis unqualified.

After software build 2026-11-05T20:58:56.220572+00:00, EXP-20261105-J413-053: full Mu and two m1n1 stages compiled/linked; bootstrap 2542056 bytes SHA256 639d558d3e1abe42024df8edc298f12e283cc87906920851858a76e66db59cc9, FD SHA256 38b42f7bfb6cb3db52c90bf6fd9623ace740e8ac0e7f5ed0f52caa0c928781f4; exact nested/profile/source checks and new default installer --dry-run --firmware-only passed, resolving disk0s4 PARTUUID 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB. Four actual C policy/selector regressions pass (including ASan/UBSan); 28 installer transaction tests pass including no Windows recopy, companion rollback and corrupted-backup rejection. No broad suite rerun. A USB test-harness extraction initially retained an unmatched endif; harness corrected, targeted USB test passes. Native build log .local/nvme-stall/build.log, result analysis/2026-11-05-nvme-scope-build-result.json. Colima stopped after build. sudo -n reports a password is required: no install or launch took place; new files remain local. Verdict implemented; removal of broad recursive scope verified in software, hardware causal hypothesis inconclusive. No Windows stop code/parameters or CPU/IRQ/timer/USB/storage/input/SSH/RDP liveness measured. Prior e3919fd2 bundle and official f4ce681b bootstrap retained. Next physical checkpoint per-level connection entry/return and fixed-GUID loader.

Source timing clarification for EXP-20261105-J413-053: the pre-build state file was captured before committing the reviewed implementation; actual native compilation started at root a030dd58e093e8984c46a6a674c4bb573b0ff17d. The resulting artifact manifest records that build state. No hardware behavior or result is reinterpreted.


## EXP-20261105-J413-054 — operator checkpoint for staged storage binding

Before operator install/launch 2026-11-05T20:59:45.598681+00:00: branch main; source state {"Mu": {"commit": "8b4dc4b4e3ff8606d0af36163acf9de79b7b4737", "diff_sha256": "b98926afb8392b4054cca6eff02749497b5e71c253686f6f2947f966d7f5824b"}, "m1n1": {"commit": "9cd80ac652ac404e92ae279deeaec8c629d7d184", "diff_sha256": "c21fa5b54fdd085ed09614abdef38fc86697c9a5efc13949a420c9928b8ee6a8"}, "root": {"commit": "27e8f81f6e44514ce0a7e0676a7fda721f26a9a6", "diff_sha256": "4595e14e5267a4774f9ed822e17b7d760567ef529f0d9d2dbb1d31d6c4449077"}}. Exact candidate dist/j413/boot-experiment/boot.bin SHA256 639d558d3e1abe42024df8edc298f12e283cc87906920851858a76e66db59cc9, manifest dist/j413/boot-experiment/MANIFEST.json; debug qualification/physical/off/both no-proxy stages. Build command scripts/build-j413-boot-experiment.sh; build result EXP053. Intended install command sudo /usr/bin/python3 scripts/install-j413-direct-setup.py --firmware-only; target internal PARTUUID 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB. This installation has NOT occurred: sudo -n reported password required. The installer must first emit its own before/after transaction and installed hash; do not launch following an error. Recovery preserved manifested preceding e3919fd288efc0cb0577274a2b9bec0c7b553691c6a760ec1f7ef1be725404e6 in .local/recovery-20261105-before-nvme-scope and original official f4ce681b bootstrap backup; transactional firmware update creates additional bootstrap and FD/metadata recovery copies. Single firmware behavior variable is nonrecursive storage attachment scope, as EXP053. Intended physical launch after successful installation: operator fully shuts down, holds power and selects existing HackWinDos UEFI; no agent reboot. Expected checkpoint each root/controller/namespace/target-filesystem return then unique-GUID fixed ARM64 loader selection. Failure a stationary entry marker for about one minute, error/reset or Windows stop; this observation limit is not a driver cancellation timeout. Evidence requested final-screen photo/video with elapsed phases, exact stop code/parameters if present and display/USB input/storage/SSH/RDP/all CPUs/IRQ/timer liveness. None has been measured for this candidate. Verdict pending; no launch outcome yet.


## EXP-20261105T210449Z-J413-ESP-2ae55439 — install J413 payload

Before 2026-11-05T21:04:50.445914+00:00: target disk0s4, PARTUUID 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB; source $PROJECT_ROOT/dist/j413/boot-experiment/boot.bin; SHA256 639d558d3e1abe42024df8edc298f12e283cc87906920851858a76e66db59cc9; source state {"Mu": {"branch": "", "commit": "8b4dc4b4e3ff8606d0af36163acf9de79b7b4737", "diff_sha256": "b98926afb8392b4054cca6eff02749497b5e71c253686f6f2947f966d7f5824b"}, "m1n1": {"branch": "", "commit": "9cd80ac652ac404e92ae279deeaec8c629d7d184", "diff_sha256": "c21fa5b54fdd085ed09614abdef38fc86697c9a5efc13949a420c9928b8ee6a8"}, "root": {"branch": "main", "commit": "958e58c9d3c51f66d9d599a229f7af1e35bc9830", "diff_sha256": "ae9df3a12b54a257bdcbbca3f4d3e381d03f3a72553d3e80b63d54d7ce9b7948"}}. Command $PROJECT_ROOT/scripts/install-j413-direct-setup.py --firmware-only. Recovery destination $PROJECT_ROOT/.local/direct-setup-installs/EXP-20261105T210449Z-J413-ESP-2ae55439/boot.bin.before. Expected checkpoint: verified atomic payload replacement only; no guest launch. Failure criterion: target, mount, backup, copy or hash verification fails. Evidence: this entry and backup directory; no format, repair, boot-policy change or reboot.

Before replacement EXP-20261105T210449Z-J413-ESP-2ae55439: recovery $PROJECT_ROOT/.local/direct-setup-installs/EXP-20261105T210449Z-J413-ESP-2ae55439/boot.bin.before, SHA256 e3919fd288efc0cb0577274a2b9bec0c7b553691c6a760ec1f7ef1be725404e6; backup verified. Existing bootability is not newly qualified; macOS startup picker remains recovery.

Before companion replacement EXP-20261105T210449Z-J413-ESP-2ae55439: verified recovery hashes {"J413Setup/FIRMWARE-MANIFEST.json": {"backup_file": "companion-1.before", "sha256": "cda099aeaf7620b79dec77150b88481a7b0d7d7652545057adec82ba95004597"}, "J413Setup/MEDIA.json": {"backup_file": "companion-2.before", "sha256": "53e784d0582d9d5ad17c38f7977fa1bc64499e624c4f510cec8af25bdceb1630"}, "m1n1/J413_EFI.fd": {"backup_file": "companion-0.before", "sha256": "8d6066b1f1346bb7257700dbcd121200a77065de84ab1f6ce99573c4a31bad61"}}. Windows installer bytes are retained.

After 2026-11-05T21:04:59.901246+00:00, EXP-20261105T210449Z-J413-ESP-2ae55439: installed /Volumes/EFI - HACKW/m1n1/boot.bin, SHA256 639d558d3e1abe42024df8edc298f12e283cc87906920851858a76e66db59cc9; byte verification passed. Verdict: installed; boot/USB/Windows result inconclusive. No boot phases, Windows stop/parameters, CPU/IRQ/timer or display/input/storage/SSH/RDP liveness measured; no reboot or launch. Next checkpoint: operator records fixed-volume NVMe/ARM64 loader entry and the actual resulting Windows phase.


After operator run 2026-11-05T21:15:46.342308+00:00, EXP-20261105-J413-054: installed bootstrap identity is recorded by EXP-20261105T210449Z-J413-ESP-2ae55439 as 639d558d3e1abe42024df8edc298f12e283cc87906920851858a76e66db59cc9. IMG_6329 Windows logo/spinner, IMG_6330 Windows 11 Setup Please wait, IMG_6331 Install driver to show hardware and A media driver your computer needs is missing. Photo hashes {"IMG_6329.HEIC": "56c00ffbc3c541017ce241668db3705eeb1dd1590b5a124f7f63b2f58b484ac0", "IMG_6330.HEIC": "3c3b55b7b0b230733f6b64993e8760e7a0405a1e93fb4f376ca1435d6777c2f4", "IMG_6331.JPG": "966a8da6b3f124d9278fe8c9ba74297f2e5a5c85941c55c54d0598dc65081583"}. Exact elapsed phases unknown. Verdict: fixed-GUID/native Windows Setup checkpoint confirmed by photos; full installation and media/target-disk access are not confirmed. Built-in keyboard/trackpad unresponsive per operator. CORRECTION to the initial external-mouse report: the adapter was attached to the iPad rather than this MacBook; external USB input has NOT been tested and must not be recorded as a USB failure. Display rendered successive Windows phases. No Windows stop code or parameters; IRQ/timer state, all CPUs, storage, SSH/RDP and USB liveness unmeasured. No WinPE disk/PnP/Setup logs available. Next justified checkpoint: connect the external input device to the actual MacBook and capture WinPE storage/PnP state; do not guess a missing driver or replace the Mu-reaching/Setup-reaching baseline. Evidence analysis/2026-11-05-winpe-entry-result.json.


## EXP-20261105-J413-055 — hands-free WinPE media and input inventory

Before software build 2026-11-05T21:22:00.115091+00:00: source state analysis/2026-11-05-winpe-diagnostic-build-state.json; plan analysis/2026-11-05-winpe-media-plan.md. Single experiment variable: WinPE image 2 diagnostic startup files (background collector plus bounded ARM64 wait helper); original sources/setup.exe launch retained, no firmware/ACPI/backend/IRQ/DMA/power changes. Build command python3 tools/j413_winpe_diagnostics.py --source /Volumes/WININSTALL/sources/boot.wim > .local/winpe-diagnostics/build.log 2>&1 . Original WIM SHA256 dcf58a3d6be5d8747ba8b475f6bbc3782a53bc5dc14c7b11e73ff140deeab534; bootstrap SHA256 639d558d3e1abe42024df8edc298f12e283cc87906920851858a76e66db59cc9. Target remains internal PARTUUID 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB. Output dist/j413-winpe-diagnostics/MANIFEST.json profile winpe-diagnostic; new WIM/hash pending before any install or launch. Recovery original WIM on source USB and exact Setup-reaching firmware .local/recovery-20261105-first-winpe-entry, plus a verified WIM/media backup required by installer. Expected software checkpoint actual ARM64 helper PE, embedded startup bytes and WIM integrity; hardware checkpoint automatic Notepad disk/PnP summary about 30 seconds after WinPE startup and unique-marker log persistence if source volume is visible. Failure builder/identity mismatch, no diagnostic window, reported command error or Windows stop/hang. No driver load/device reset, disk format/partition write, automatic Windows installation, reboot or physical launch. Native diagnostic execution unqualified.

After software preparation, EXP-20261105-J413-055: build failed the actual source-WIM dependency check because findstr.exe is absent, before copying/updating a WIM. No diagnostic artifact was produced or installed. Correct the collector to use only actual available commands before retrying. No physical diagnostic run occurred.


## EXP-20261105-J413-056 — external mouse retry and existing UEFI log collection

Late operator result 2026-11-05T21:34:22.478005+00:00: user tried the adapter on the actual Mac, first the port nearest MagSafe then swapped with SanDisk. Mouse unresponsive and LEDs unlit; user clarifies no not-found error message was displayed. Exact phase/timing and cold-start versus hot-swap detail unknown. Prior iPad attachment was not a valid test; this new report supersedes only the untested external-input status. Known unchanged firmware 639d558d from EXP054; no new install. macOS now enumerates E-Signal Inde-mouse 04d9:a09f behind GenesysLogic USB2.1 Hub; this does not prove VBUS/USB in Windows or identify the failure layer. No stop code/CPU/IRQ/timer/storage/network state observed. First normal diskutil mount of the exact internal ESP failed; no repair. Before next read-only host diagnostic: mount readOnly the same measured PARTUUID 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB and collect existing m1n1/j413uefi.log if available, plus installed bootstrap hash. No firmware/WIM, filesystem repair, partition, security or power-state changes. Recovery Setup-reaching 639d558d bundle preserved. Expected checkpoint an existing log identifying pre-OS USB connection/readiness; failure absent mount/log. Evidence analysis/2026-11-05-external-mouse-result.json and private capture under .local/winpe-diagnostics.

Before corrected software retry 2026-11-05T21:35:27.768360+00:00, EXP-20261105-J413-055: remove the absent findstr dependency; preserve full PnP output and identify log destination by an exact GUID marker filename, with duplicate rejection. Native firmware remains 639d558d and unchanged. Same build command, original WIM identity and recovery; no install/launch.

After corrected software build 2026-11-05T21:41:24.817712+00:00, EXP-20261105-J413-055: ARM64 PE32+ console helper 2048 bytes SHA256 1b2914a5ebf98d72c68a2ef5ae4a5556b47b4934fe56b5281c3369ff6d7ff43d; boot.wim 635027475 bytes SHA256 965e81d96c8b3586dca213fdfe9cbf0dea7b16afd9ceb6186c6cd40f2e735dd0. Exact embedded startup files match extracted bytes; complete WIM integrity passes, both original images retain ARM64 metadata. Manifest dist/j413-winpe-diagnostics/MANIFEST.json, profile winpe-diagnostic, original WIM dcf58a3d retained. Four real file-transaction tests pass including failure rollback, complete restore, corrupt backup rejection and read-only collection; pinned installer dry-run resolves exact internal ESP. Native execution remains unqualified; sudo reports password required, so no diagnostic image installed or launched. No firmware change, driver load, power/IRQ/DMA/ACPI modification or broad test rerun. Result analysis/2026-11-05-winpe-diagnostic-build-result.json.

After read-only host diagnostic 2026-11-05T21:41:24.817712+00:00, EXP-20261105-J413-056: diskutil mount readOnly disk0s4 also failed; no mount point and no existing UEFI log read. Exact PARTUUID remains unchanged. No filesystem repair was attempted. Cause of mount failure is not distinguished between privilege and filesystem state; do not claim corruption. Owner-password collect-only script is prepared and has not been executed. Verdict for existing-log collection inconclusive; external input unavailable by operator report, but no VBUS, firmware USB or Windows PnP measurement yet.


## EXP-20261105-J413-057 — prepared owner collection and diagnostic launch

Before owner action 2026-11-05T21:41:24.817712+00:00: source main 958e58c9d3c51f66d9d599a229f7af1e35bc9830 with reviewed diagnostic sources; m1n1/Mu pins/diffs unchanged from EXP055. First command sudo /usr/bin/python3 scripts/install-j413-winpe-diagnostics.py --collect-only reads existing UEFI log on exact ESP 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB; no media replacement. If a separate WinPE inventory trial is needed, install command sudo /usr/bin/python3 scripts/install-j413-winpe-diagnostics.py validates the full original media, creates byte-verified WIM/metadata backups then installs diagnostic WIM SHA256 965e81d96c8b3586dca213fdfe9cbf0dea7b16afd9ceb6186c6cd40f2e735dd0 with manifest dist/j413-winpe-diagnostics/MANIFEST.json. Firmware remains Setup-reaching 639d558d3e1abe42024df8edc298f12e283cc87906920851858a76e66db59cc9, physical/off/no-proxy; single changed variable is WinPE diagnostic startup. Recovery original boot.wim dcf58a3d6be5d8747ba8b475f6bbc3782a53bc5dc14c7b11e73ff140deeab534 and the new transaction recovery record required before any WIM replacement. Nothing has been installed or launched. Expected next hardware checkpoint existing USB readiness log, or automatically opened Notepad disk/PnP summary after operator Startup Options launch of existing HackWinDos UEFI. Failure mount/hash/transaction error, no summary, Windows stop/hang; record elapsed phases and exact stop/CPU/IRQ/timer/input/storage/USB/network liveness. No forced repair, driver injection or agent reboot. Verdict pending; owner password boundary remains.

Publication privacy note: newly collected runtime project paths are represented as $PROJECT_ROOT; exact unredacted bytes and digest are retained privately under .local/winpe-diagnostics. No result, artifact identity or experiment verdict changed.


## EXP-20261105T214802Z-J413-WINPE-4c24cdc4 — collect WinPE diagnostic media

Before 2026-11-05T21:48:02.366001+00:00: target disk0s4 PARTUUID 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB; source state {"Mu": {"branch": "", "commit": "8b4dc4b4e3ff8606d0af36163acf9de79b7b4737", "diff_sha256": "b98926afb8392b4054cca6eff02749497b5e71c253686f6f2947f966d7f5824b"}, "m1n1": {"branch": "", "commit": "9cd80ac652ac404e92ae279deeaec8c629d7d184", "diff_sha256": "c21fa5b54fdd085ed09614abdef38fc86697c9a5efc13949a420c9928b8ee6a8"}, "root": {"branch": "main", "commit": "ba243a1bccb026f22b37dbb5ca8f3a053a84fadc", "diff_sha256": "ae9df3a12b54a257bdcbbca3f4d3e381d03f3a72553d3e80b63d54d7ce9b7948"}}; command $PROJECT_ROOT/scripts/install-j413-winpe-diagnostics.py --collect-only; unchanged firmware SHA256 639d558d3e1abe42024df8edc298f12e283cc87906920851858a76e66db59cc9; WIM/profile {}. Expected checkpoint existing log capture only; failure identity/mount/hash/copy error. Recovery destination $PROJECT_ROOT/.local/winpe-diagnostic-installs/EXP-20261105T214802Z-J413-WINPE-4c24cdc4. No firmware replacement, driver load, partition/format/repair, security change or reboot.

After 2026-11-05T21:48:03.450428+00:00, EXP-20261105T214802Z-J413-WINPE-4c24cdc4: FAILED "ESP did not mount. No repair or media replacement attempted; see $PROJECT_ROOT/.local/winpe-diagnostic-installs/EXP-20261105T214802Z-J413-WINPE-4c24cdc4/mount.txt"; no physical diagnostic result or reboot. Evidence $PROJECT_ROOT/.local/winpe-diagnostic-installs/EXP-20261105T214802Z-J413-WINPE-4c24cdc4.


## EXP-20261105-J413-058 — identify ESP access failure without repair

Before read-only host diagnostic 2026-11-05T21:54:08.563319+00:00: source state {"Mu": {"commit": "8b4dc4b4e3ff8606d0af36163acf9de79b7b4737", "diff_sha256": "b98926afb8392b4054cca6eff02749497b5e71c253686f6f2947f966d7f5824b"}, "m1n1": {"commit": "9cd80ac652ac404e92ae279deeaec8c629d7d184", "diff_sha256": "c21fa5b54fdd085ed09614abdef38fc86697c9a5efc13949a420c9928b8ee6a8"}, "root": {"commit": "ba243a1bccb026f22b37dbb5ca8f3a053a84fadc", "diff_sha256": "b93c21322759a26249540d5acecf099fae9893282e2d1b08612cfd56c33005e5"}}. Owner collect-only transaction EXP-20261105T214802Z-J413-WINPE-4c24cdc4 failed to mount the correct ESP even under sudo; no diagnostic WIM was installed. Current disk0s4 PARTUUID remains 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB and unmounted. Hypothesis unresolved between filesystem/mount policy, dirty-state handling or device access; no corruption asserted. Commands sudo -n cat the existing mount.txt and sudo -n /sbin/fsck_msdos -n /dev/rdisk0s4 if already authenticated. The -n mode is read-only; no automatic repair or writes. Artifact remains Setup-reaching bootstrap 639d558d3e1abe42024df8edc298f12e283cc87906920851858a76e66db59cc9 with existing manifest/recovery. Evidence .local/winpe-diagnostics/esp-access-check.txt. Expected checkpoint exact mount/checker failure; failure owner password unavailable or no diagnostic output. No agent reboot or guest run; CPU/IRQ/timer/input/storage/USB/network liveness unmeasured.

After 2026-11-05T21:59:26.868397+00:00, EXP-20261105-J413-058: both sudo -n commands stopped because an owner password is required. No existing root mount.txt read, no fsck command executed, no partition bytes read and no repair or data mutation. Confirmed measured partition metadata {"DeviceBlockSize": 4096, "DiskUUID": "6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB", "MountPoint": "", "TotalSize": 9500098560}. Implemented bounded read-only FAT32 extraction in the host collection layer; source/spec review analysis/2026-11-05-fat32-log-collection-plan.md. Six sparse-file parser regressions pass (fragmented data, 4KiB-aligned raw I/O, active FAT, mirror disagreement, duplicate identity, invalid/truncated/cyclic chains); five transaction/policy tests pass, including raw fallback only during collection and no raw install fallback. Actual device extraction remains pending owner rerun of sudo /usr/bin/python3 scripts/install-j413-winpe-diagnostics.py --collect-only. Existing diagnostic WIM, firmware 639d558d and recovery artifacts are unchanged; no rebuild, installation, reboot, native stop/CPU/IRQ/timer/input/storage/USB/network result. Result analysis/2026-11-05-fat32-log-collection-result.json.

Operator update 2026-11-05T22:00:14.980471+00:00, referencing EXP-20261105-J413-057: user reports booting and trying again; no new photo, precise resulting phase, elapsed time or input/USB observation was supplied in that statement. Record the boot attempt as inconclusive rather than inventing a new symptom. No new diagnostic WIM installation exists in the host transaction ledger. The separate owner collect-only failure is recorded above; corrected read-only extraction awaits another macOS owner invocation.


## EXP-20261106T064048Z-J413-WINPE-6f9a10a5 — collect WinPE diagnostic media

Before 2026-11-06T06:40:48.655801+00:00: target disk0s4 PARTUUID 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB; source state {"Mu": {"branch": "", "commit": "8b4dc4b4e3ff8606d0af36163acf9de79b7b4737", "diff_sha256": "b98926afb8392b4054cca6eff02749497b5e71c253686f6f2947f966d7f5824b"}, "m1n1": {"branch": "", "commit": "9cd80ac652ac404e92ae279deeaec8c629d7d184", "diff_sha256": "c21fa5b54fdd085ed09614abdef38fc86697c9a5efc13949a420c9928b8ee6a8"}, "root": {"branch": "main", "commit": "fb14bbf44defa8d5df0e517f2c474bff1d3cab6b", "diff_sha256": "ae9df3a12b54a257bdcbbca3f4d3e381d03f3a72553d3e80b63d54d7ce9b7948"}}; command $PROJECT_ROOT/scripts/install-j413-winpe-diagnostics.py --collect-only; unchanged firmware SHA256 639d558d3e1abe42024df8edc298f12e283cc87906920851858a76e66db59cc9; WIM/profile {}. Expected checkpoint existing log capture only; failure identity/mount/hash/copy error. Recovery destination $PROJECT_ROOT/.local/winpe-diagnostic-installs/EXP-20261106T064048Z-J413-WINPE-6f9a10a5. No firmware replacement, driver load, partition/format/repair, security change or reboot.

After 2026-11-06T06:40:49.825111+00:00, EXP-20261106T064048Z-J413-WINPE-6f9a10a5: existing UEFI log collected through bounded read-only FAT32 extraction; no mount, repair, media replacement or guest launch. Evidence $PROJECT_ROOT/.local/winpe-diagnostic-installs/EXP-20261106T064048Z-J413-WINPE-6f9a10a5.


## EXP-20261106T064510Z-J413-WINPE-b09fce74 — collect WinPE diagnostic media

Before 2026-11-06T06:45:10.287146+00:00: target disk0s4 PARTUUID 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB; source state {"Mu": {"branch": "", "commit": "8b4dc4b4e3ff8606d0af36163acf9de79b7b4737", "diff_sha256": "b98926afb8392b4054cca6eff02749497b5e71c253686f6f2947f966d7f5824b"}, "m1n1": {"branch": "", "commit": "9cd80ac652ac404e92ae279deeaec8c629d7d184", "diff_sha256": "c21fa5b54fdd085ed09614abdef38fc86697c9a5efc13949a420c9928b8ee6a8"}, "root": {"branch": "main", "commit": "fb14bbf44defa8d5df0e517f2c474bff1d3cab6b", "diff_sha256": "c8714476ecfa42cabddf2a5c9fb381a479a7bb8e42f6b2fce9261682fc71baf4"}}; command $PROJECT_ROOT/scripts/install-j413-winpe-diagnostics.py --collect-only; unchanged firmware SHA256 639d558d3e1abe42024df8edc298f12e283cc87906920851858a76e66db59cc9; WIM/profile {}. Expected checkpoint existing log capture only; failure identity/mount/hash/copy error. Recovery destination $PROJECT_ROOT/.local/winpe-diagnostic-installs/EXP-20261106T064510Z-J413-WINPE-b09fce74. No firmware replacement, driver load, partition/format/repair, security change or reboot.

After 2026-11-06T06:45:11.358147+00:00, EXP-20261106T064510Z-J413-WINPE-b09fce74: existing UEFI log collected through bounded read-only FAT32 extraction; no mount, repair, media replacement or guest launch. Evidence $PROJECT_ROOT/.local/winpe-diagnostic-installs/EXP-20261106T064510Z-J413-WINPE-b09fce74.

Evidence handoff update 2026-11-06T06:45:41.679060+00:00, referencing EXP-20261106T064048Z-J413-WINPE-6f9a10a5: the owner collection transaction succeeded through read-only FAT32 extraction, but its root-owned evidence could not be read by workspace tools without another password. Added a caller-owned private console capture launcher; simulated sudo success/failure handoff test passes. The actual UEFI log contents are not yet read by the agent; no USB or storage cause inferred. No hardware/profile change or new launch.

Agent evidence read 2026-11-06T06:49:15.648133+00:00, EXP-20261106T064510Z-J413-WINPE-b09fce74: caller-owned launcher output .local/usb-evidence/run.Dwr9sh/console.log SHA256 b52be1a3c226706a8dc0d0fbcf902edefefecd5c08c57e2d881a2c2360cb105b read successfully and matched LATEST metadata, collector exit 0. Raw FAT32 collection verified Setup-reaching bootstrap 639d558d. Phase log reports NVMe boot connection Success, USB DART readiness Success, mask 2, USB boot connection Success and fixed-volume ARM64 selection Success. This is a bounded UEFI phase log, not a kernel/UART/device trace; no mouse descriptor, child enumeration/count, VBUS measurement or Windows PnP/DMA/IRQ handoff state is present. Do not infer working USB input from ConnectController Success. No new installation, launch, repair or firmware change. Result analysis/2026-11-06-uefi-usb-phase-result.json.


## EXP-20261106-J413-060 — prepared Windows-side input/storage checkpoint

Before owner install 2026-11-06T06:55:06.615618+00:00: root 8803f30cf9223de3a0b0b4be82d627cfb3c0f6d3 main; m1n1/Mu pins and hardware profile unchanged. Current 639d558d firmware phase log confirms NVMe connection, USB DART readiness mask 2, USB connection and fixed-volume selection Success; no USB child or Windows PnP/IRQ/DMA state. Source interfaces inspected: local mount_msdos(8) and existing exact-GUID installer/transaction contract; no hardware or driver implementation changed. Install command bash scripts/collect-j413-usb.command --install-diagnostics, exact target PARTUUID 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB. Only if ordinary mount fails, explicitly enabled native FAT mount helper uses /sbin/mount_msdos -o rw,nobrowse,noexec on that same verified device in a private mount point; failure prints exact helper error and stops without repair. Manifest dist/j413-winpe-diagnostics/MANIFEST.json, WIM SHA256 965e81d96c8b3586dca213fdfe9cbf0dea7b16afd9ceb6186c6cd40f2e735dd0; source original WIM dcf58a3d6be5d8747ba8b475f6bbc3782a53bc5dc14c7b11e73ff140deeab534. Verified original WIM/media backups are required before replacement; Setup-reaching firmware and source USB remain recovery. Single runtime variable is diagnostic WinPE startup, existing Setup launch retained. Expected host checkpoint WIM installation and clean unmount; then operator cold boot of existing HackWinDos UEFI produces an automatic Notepad disk/PnP summary after roughly 30 seconds of WinPE shell startup. Failure mount/hash/backup/copy/unmount error, no summary, hang or stop. No native mount, install or new hardware launch has occurred yet; no driver load, partition, firmware, IRQ/DMA/power or security change; no automatic reboot. Capture exact error/stop/elapsed phases and input/storage/USB/CPU/IRQ/timer/network liveness. Software verification: six diagnostic transaction/policy tests and launcher regression pass; no broad suite rerun. Verdict pending physical checkpoint.


## EXP-20261106T065636Z-J413-WINPE-518bd56b — install WinPE diagnostic media

Before 2026-11-06T06:56:36.712745+00:00: target disk0s4 PARTUUID 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB; source state {"Mu": {"branch": "", "commit": "8b4dc4b4e3ff8606d0af36163acf9de79b7b4737", "diff_sha256": "b98926afb8392b4054cca6eff02749497b5e71c253686f6f2947f966d7f5824b"}, "m1n1": {"branch": "", "commit": "9cd80ac652ac404e92ae279deeaec8c629d7d184", "diff_sha256": "c21fa5b54fdd085ed09614abdef38fc86697c9a5efc13949a420c9928b8ee6a8"}, "root": {"branch": "main", "commit": "b2664fdf48af8a3a357d780d1021089a6e3562d3", "diff_sha256": "ae9df3a12b54a257bdcbbca3f4d3e381d03f3a72553d3e80b63d54d7ce9b7948"}}; command $PROJECT_ROOT/scripts/install-j413-winpe-diagnostics.py --native-mount; unchanged firmware SHA256 639d558d3e1abe42024df8edc298f12e283cc87906920851858a76e66db59cc9; WIM/profile {"artifacts": {"J413Collect.cmd": {"sha256": "32bcc1bc6b6254591ea0ac69ba227421f5090f47fb3798f1a030d81147ff730a", "size": 3064}, "J413Wait.exe": {"sha256": "1b2914a5ebf98d72c68a2ef5ae4a5556b47b4934fe56b5281c3369ff6d7ff43d", "size": 2048}, "boot.wim": {"sha256": "965e81d96c8b3586dca213fdfe9cbf0dea7b16afd9ceb6186c6cd40f2e735dd0", "size": 635027475}, "winpeshl.ini": {"sha256": "c317c1885262a309f6c16b645a207640f806d1cb9a79c0a0e4461e13844e2fcb", "size": 191}}, "behavior": "Background read-only inventory and existing log collection; original Setup launch retained", "created_utc": "2026-11-05T21:35:38.245048+00:00", "esp_uuid": "6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB", "firmware_sha256": "639d558d3e1abe42024df8edc298f12e283cc87906920851858a76e66db59cc9", "images": [{"architecture": "ARM64", "index": "1", "name": "Microsoft Windows PE (arm64)"}, {"architecture": "ARM64", "index": "2", "name": "Microsoft Windows Setup (arm64)"}], "native_execution_qualified": false, "platform": "j413", "profile": "winpe-diagnostic", "source_boot_wim_sha256": "dcf58a3d6be5d8747ba8b475f6bbc3782a53bc5dc14c7b11e73ff140deeab534", "source_sha256": {"tools/j413_winpe_diagnostics.py": "23a75086755b45c84a1149e4e79783ac70fec45204987620b4c7258593a364f4", "tools/winpe/J413Collect.cmd": "33758600b69cb0ac53b5a68fec1dd3cf457306906eb2e3f9306f0e0a23469dfd", "tools/winpe/j413-wait.c": "d9a85ef61de8d8d9bd54c4ef5b8405ce3c9cf682fa8db950a3aa9853836cbc9c"}}. Expected checkpoint existing log capture and verified WIM/media transaction; failure identity/mount/hash/copy error. Recovery destination $PROJECT_ROOT/.local/winpe-diagnostic-installs/EXP-20261106T065636Z-J413-WINPE-518bd56b. No firmware replacement, driver load, partition/format/repair, security change or reboot.

Before replacement EXP-20261106T065636Z-J413-WINPE-518bd56b: verified recovery hashes {"J413Setup/DIAGNOSTIC-TARGET-6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB.txt": {"absent": true}, "J413Setup/MEDIA.json": {"backup_file": "payload-1.before", "sha256": "07176b779caca83e3b2eb760517e1a842b956d1fb0cd600c4a803ec80c39e924"}, "J413Setup/WINPE-DIAGNOSTICS.json": {"absent": true}, "sources/boot.wim": {"backup_file": "payload-0.before", "sha256": "dcf58a3d6be5d8747ba8b475f6bbc3782a53bc5dc14c7b11e73ff140deeab534"}}.

After 2026-11-06T06:56:50.723768+00:00, EXP-20261106T065636Z-J413-WINPE-518bd56b: host transaction completed; firmware unchanged. Existing evidence $PROJECT_ROOT/.local/winpe-diagnostic-installs/EXP-20261106T065636Z-J413-WINPE-518bd56b. Native diagnostic execution, input/USB, disk/PnP state and Windows installation remain unqualified; no launch or reboot.

After owner install 2026-11-06T06:58:30.142000+00:00, EXP-20261106-J413-060: transaction EXP-20261106T065636Z-J413-WINPE-518bd56b completed; caller-readable console .local/usb-evidence/run.nxwn72/console.log SHA256 d9d259fd07364585e408c5287a2f52350bb04889552b155213c91a233a3cc8fa independently read, launcher exit 0, diagnostic WIM installed and verified, original WIM/media recovery record created. Firmware remains 639d558d and WIM identity 965e81d9 as planned. No agent reboot; no Windows-side diagnostic execution, stop/CPU/IRQ/timer/input/storage/USB/network state observed yet. Host installation confirmed; native causal hypothesis still pending. Result analysis/2026-11-06-winpe-diagnostic-install-result.json.

After native operator run 2026-11-06T07:15:37.308868+00:00, EXP-20261106-J413-060 (installed transaction EXP-20261106T065636Z-J413-WINPE-518bd56b): photos [{"file": "IMG_6341.HEIC", "sha256": "9d5c6383bb26e9a1f9fdd341a70894300ce29d182b438e4ae522518e96b937c0"}, {"file": "IMG_6343.HEIC", "sha256": "02f0cffff47d5ba929d17796e4422ee732d48a0f8347ea242e3e3f37e7dd5166"}, {"file": "IMG_6344.HEIC", "sha256": "2cd54838464cfeaf5e0b527f1cebbe4712c4657488066cc363b538f6f3fe7fd4"}]; automatic SUMMARY.txt in Notepad reached. DiskPart lists disk 0 Online 233 GB GPT with 100 MB free and volume 0 EFI - HACKW FAT32 8 GB Healthy Hidden without drive letter. Standard NVM Express Controller Started with stornvme.inf / stornvme. Exact target marker matches 0; media and visible installer paths blank. USB heading is at bottom and device lines outside photographed viewport. User reports hub plus flash drive on port they call usb0, installer reached without earlier missing-media prompt; external mouse, trackpad and keyboard unresponsive, unable to scroll. Photos show adapter LED, not USB enumeration or measured VBUS. Time, stop/parameters, all-CPU, IRQ/timer, SSH/RDP and Windows USB child state unmeasured. Verdict confirmed for diagnostic startup and storage enumeration only; input cause inconclusive. The collector requires a drive letter to find its marker and places verbose storage output before USB, making input evidence unreadable without working input. Next smallest checkpoint: automatically page compact USB, device problems and HID inventory without keyboard/mouse. No claim that changing USB port fixed media or that NVMe driver is missing. Result analysis/2026-11-06-winpe-native-summary-result.json.


## EXP-20261106-J413-061 — input-free USB report pages

Before software build 2026-11-06T07:18:57.053495+00:00: branch main; source state {"Mu": {"commit": "8b4dc4b4e3ff8606d0af36163acf9de79b7b4737", "diff_sha256": "b98926afb8392b4054cca6eff02749497b5e71c253686f6f2947f966d7f5824b"}, "m1n1": {"commit": "9cd80ac652ac404e92ae279deeaec8c629d7d184", "diff_sha256": "c21fa5b54fdd085ed09614abdef38fc86697c9a5efc13949a420c9928b8ee6a8"}, "root": {"commit": "8b4c3006ae24acc6e283aad01592be9b262c1b03", "diff_sha256": "dad7c193b2a031d1dc36f6ec41cee73425ae0684658d01f7cf23cf9d00c2d24b"}}; plan analysis/2026-11-06-input-free-report-plan.md. Single guest behavior change is inventory presentation; USB/problem/HID/disk pages rotate every 12 seconds without input. No firmware, ACPI, IRQ/DMA/power, driver or partition change. Command python3 tools/j413_winpe_diagnostics.py --source /Volumes/WININSTALL/sources/boot.wim > .local/winpe-diagnostics/exp061-build.log 2>&1. Output dist/j413-winpe-diagnostics/boot.wim with MANIFEST.json profile winpe-diagnostic; candidate SHA required after build before install. Photographed previous WIM 965e81d96c8b3586dca213fdfe9cbf0dea7b16afd9ceb6186c6cd40f2e735dd0 and manifest preserved at .local/winpe-diagnostics/recovery-exp060-965e81d9; unchanged firmware 639d558d with its existing manifest/recovery. Install after verification: bash scripts/collect-j413-usb.command --install-diagnostics; exact internal GUID remeasured by installer and complete transaction backup required. Owner launch existing HackWinDos UEFI after cold shutdown. Expected checkpoint actual automatically changing USB pages and problem codes; failure no viewer, pages clipped/frozen, Windows stop/reset/hang. Capture page photos and timing, storage/input/USB/SSH/RDP/CPU/IRQ state where observed. No install or native launch yet. Host C page regression under ASan/UBSan and eight installer transaction/identity tests passed.

After software build 2026-11-06T07:20:55.270740+00:00, EXP-20261106-J413-061: candidate WIM 3a85e0a54facf56fa08750b173dd3191da06bc54a396233b1b26aeff642e8500 (636628125 bytes), profile winpe-diagnostic, manifest dist/j413-winpe-diagnostics/MANIFEST.json. Original Setup launch retained; unchanged firmware 639d558d. Actual WIM integrity, exact embedded files, two ARM64 images and both ARM64 PE32+ console helpers verified. Independent PE import inspection confirms report helper imports only Kernel32 APIs. C layout sanitizer regression and eight installer transaction/identity cases passed; ledger schema passed; installer dry-run re-resolved disk0s4 exact target GUID without mount/write. Preserved previous 965e81d9 WIM/manifest at .local/winpe-diagnostics/recovery-exp060-965e81d9 and earlier owner recovery record. No installation, native launch, reset or reboot in this build. Verdict implemented; rotating display and USB/problem/HID contents await owner hardware checkpoint. No new stop/CPU/IRQ/timer/input/storage/network result. Build log .local/winpe-diagnostics/exp061-build.log; result analysis/2026-11-06-input-free-report-build-result.json.


## EXP-20261106T072814Z-J413-WINPE-8b9199de — install WinPE diagnostic media

Before 2026-11-06T07:28:14.608979+00:00: target disk0s4 PARTUUID 6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB; source state {"Mu": {"branch": "", "commit": "8b4dc4b4e3ff8606d0af36163acf9de79b7b4737", "diff_sha256": "b98926afb8392b4054cca6eff02749497b5e71c253686f6f2947f966d7f5824b"}, "m1n1": {"branch": "", "commit": "9cd80ac652ac404e92ae279deeaec8c629d7d184", "diff_sha256": "c21fa5b54fdd085ed09614abdef38fc86697c9a5efc13949a420c9928b8ee6a8"}, "root": {"branch": "main", "commit": "858b3895e4aa182d8f9a8ab16bebdc9b68d6094c", "diff_sha256": "ae9df3a12b54a257bdcbbca3f4d3e381d03f3a72553d3e80b63d54d7ce9b7948"}}; command $PROJECT_ROOT/scripts/install-j413-winpe-diagnostics.py --native-mount; unchanged firmware SHA256 639d558d3e1abe42024df8edc298f12e283cc87906920851858a76e66db59cc9; WIM/profile {"artifacts": {"J413Collect.cmd": {"sha256": "8d8c81415fb8feb42d04721ce404a886702ba971a587a88eb24dbcb8d9073cc1", "size": 3498}, "J413Report.exe": {"sha256": "1426829f46848fe097b62bafc9d197a24b4b32fd370099434ccd3c7ecc2acb17", "size": 6656}, "J413Wait.exe": {"sha256": "478d36438d19905810d84df88e2cd1304627351662d45e9e72aa83efe75b8b34", "size": 2048}, "boot.wim": {"sha256": "3a85e0a54facf56fa08750b173dd3191da06bc54a396233b1b26aeff642e8500", "size": 636628125}, "winpeshl.ini": {"sha256": "c317c1885262a309f6c16b645a207640f806d1cb9a79c0a0e4461e13844e2fcb", "size": 191}}, "behavior": "Read-only inventory with automatic USB/problem/HID/disk display pages; original Setup launch retained", "created_utc": "2026-11-06T07:19:11.836147+00:00", "esp_uuid": "6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB", "firmware_sha256": "639d558d3e1abe42024df8edc298f12e283cc87906920851858a76e66db59cc9", "images": [{"architecture": "ARM64", "index": "1", "name": "Microsoft Windows PE (arm64)"}, {"architecture": "ARM64", "index": "2", "name": "Microsoft Windows Setup (arm64)"}], "native_execution_qualified": false, "platform": "j413", "profile": "winpe-diagnostic", "source_boot_wim_sha256": "dcf58a3d6be5d8747ba8b475f6bbc3782a53bc5dc14c7b11e73ff140deeab534", "source_sha256": {"tools/j413_winpe_diagnostics.py": "12b74e79b4888a4f62e8a6aa7c7a0d886c68dc9268d7be313e1586568a57a200", "tools/winpe/J413Collect.cmd": "e366f69af1d8b63cde42e68f8ab17cee0b7e827a69c2c3d5390d62ee75fba2fa", "tools/winpe/j413-report.c": "6564408855fa9f15945f875b6729395e79da446ad013e8a55f04c8e825705593", "tools/winpe/j413-wait.c": "d9a85ef61de8d8d9bd54c4ef5b8405ce3c9cf682fa8db950a3aa9853836cbc9c", "tools/winpe/report-pages.h": "527fc9449992255b41d13f576cdd9779075c7e25bcddd368dd6361c70b701204"}}. Expected checkpoint existing log capture and verified WIM/media transaction; failure identity/mount/hash/copy error. Recovery destination $PROJECT_ROOT/.local/winpe-diagnostic-installs/EXP-20261106T072814Z-J413-WINPE-8b9199de. No firmware replacement, driver load, partition/format/repair, security change or reboot.

Before replacement EXP-20261106T072814Z-J413-WINPE-8b9199de: verified recovery hashes {"J413Setup/DIAGNOSTIC-TARGET-6E5BC1A2-9871-4E5A-8E60-BF68C8E785BB.txt": {"backup_file": "payload-3.before", "sha256": "75ef6740f08631becf0f0c7619f1f50473ba5e1f7bdab5b7df9cd80f56c245c5"}, "J413Setup/MEDIA.json": {"backup_file": "payload-1.before", "sha256": "41322c1abaa05b618dbfc64f829310d32d97d5f838be7196b7c0b623a259c800"}, "J413Setup/WINPE-DIAGNOSTICS.json": {"backup_file": "payload-2.before", "sha256": "3069fe36fb46fb8a06fc34edc9df6e924178a4bf42f6f6d206f92d1aff75c7dd"}, "sources/boot.wim": {"backup_file": "payload-0.before", "sha256": "965e81d96c8b3586dca213fdfe9cbf0dea7b16afd9ceb6186c6cd40f2e735dd0"}}.

After 2026-11-06T07:28:28.399190+00:00, EXP-20261106T072814Z-J413-WINPE-8b9199de: host transaction completed; firmware unchanged. Existing evidence $PROJECT_ROOT/.local/winpe-diagnostic-installs/EXP-20261106T072814Z-J413-WINPE-8b9199de. Native diagnostic execution, input/USB, disk/PnP state and Windows installation remain unqualified; no launch or reboot.

Owner result read 2026-11-06T07:37:04.131159+00:00, EXP-20261106-J413-061: transaction EXP-20261106T072814Z-J413-WINPE-8b9199de installed and verified the rotating-report WIM, caller console .local/usb-evidence/run.rS6dAW/console.log SHA256 217a0123de211b4ed99484248b28b9b67494a9138bf7fa4d0b9ea7a89c1cfb79, exit 0. Full previous diagnostic WIM/media recovery recorded before replacement; firmware unchanged. No native display/input/USB result from this update supplied yet. Do not reinstall it or infer USB success.


## EXP-20261106-J413-062 — source-first driver admission and lifetime review

Before read-only host resource inventory 2026-11-06T07:37:04.131159+00:00: command python3 tools/collect_j413.py --output investigation/analysis/2026-11-06-driver-review-live-resources.json. Remeasure current T8112 ADT resources and IRQs only; no MMIO access, firmware launch, install, mount, driver loading or reboot. Known physical baseline EXP060 storage enumerates and input unavailable; EXP061 presentation install succeeded, guest result pending. Existing firmware 639d558d and manifested rotating WIM 3a85e0a5 retained with exact recovery. Expected checkpoint current ADT matches J413; failure model/translation error. No changed hardware variable and no Windows stop/CPU/IRQ/timer/network measurement claimed.

After read-only inventory 2026-11-06T07:44:45.908385+00:00, EXP-20261106-J413-062: current Mac14,2/T8112 ADT translated successfully, recorded in analysis/2026-11-06-driver-review-live-resources.json. Current Aurora Linux and DTS sources reviewed at 0943983df73eb270720a7e6ba13b009ccfd14312 with file hashes/license in analysis/2026-11-06-driver-source-review.json. Complete Windows samples tree has no Apple-specific paths. Existing MTP0 ACPI/FIFO/IRQ/helper contract is incomplete; no incomplete package injected. Actual callback sanitizer regression reproduced missing StreamBuffer allocation on PrepareHardware before correction; all four Windows callback/stream tests now pass. No MMIO read/write, native Windows launch, firmware/media replacement or reboot. WDK compile pending and physical input/CPU/IRQ/timer/SSH/RDP state unchanged/unmeasured. Verdict software lifetime defect confirmed; actual USB cause still inconclusive.


## EXP-20261106-J413-063 — WDK compile of DockChannel lifecycle correction

Before CI build 2026-11-06T07:48:05.348573+00:00: main source state {"Mu": {"commit": "8b4dc4b4e3ff8606d0af36163acf9de79b7b4737", "diff_sha256": "b98926afb8392b4054cca6eff02749497b5e71c253686f6f2947f966d7f5824b"}, "m1n1": {"commit": "9cd80ac652ac404e92ae279deeaec8c629d7d184", "diff_sha256": "c21fa5b54fdd085ed09614abdef38fc86697c9a5efc13949a420c9928b8ee6a8"}, "root": {"commit": "b46e330931abd6ec280571850960b1e357a130e1", "diff_sha256": "cf58d3567586467487738c30192ede6af1ac85e805d2c726cd1673314289265f"}}; lifetime implementation 47e488462bcf81a2a08092a786658be51bf3839a; unchanged firmware 639d558d and installed diagnostic WIM 3a85e0a5 with existing manifests and recovery. Exact build: .github/workflows/apple-dockchannel-wdk.yml on Windows runner, nuget restore drivers/apple-dockchannel/windows/packages.config -PackagesDirectory packages; msbuild drivers\apple-dockchannel\windows\AppleDockChannel.vcxproj /m /t:Clean,Build /p:Configuration=Debug /p:Platform=ARM64 /p:RunCodeAnalysis=true. Trigger by publishing the exact reviewed tree to Liamsitbon/HackWinDos main; public snapshot mapping recorded separately. Single driver behavior variable is paired stream storage lifetime and teardown synchronization. Expected linked ARM64 native SYS, INF and CAT; failure WDK compilation/link/package/code-analysis error. Artifact/hash required after build and before any installation; output software-only driver archive. Recovery unchanged current diagnostic WIM and firmware; no driver install permitted against incomplete MTP ABI. Capture actual workflow/run/job/artifact IDs hashes and logs. No physical launch, PnP load, reboot or Windows stop/CPU/IRQ/timer/input/storage/network evidence expected from CI.
