# Input-free WinPE report checkpoint

Observation: EXP-20261106-J413-060 and `2026-11-06-winpe-native-summary-result.json`.
The actual machine reached Notepad, enumerated the internal GPT disk and a healthy
hidden FAT32 ESP, and started the standard NVMe driver. Its USB output was below
the visible viewport. Input did not work. No Windows USB problem code or device
descriptor is yet visible. Port labels are the operator's, not a new ADT measurement.

Sources inspected: `tools/winpe/J413Collect.cmd`, `tools/winpe/j413-wait.c`,
`tools/j413_winpe_diagnostics.py`, exact-GUID host installer and current manifest;
Microsoft Console `GetConsoleScreenBufferInfo`, `WriteConsoleOutputW`, console
screen buffer documentation, and PnPUtil command syntax. The collector confirms a
Windows USB/input question but does not establish a firmware defect. This changes
only report presentation, not platform, driver, power, IRQ, DMA or ACPI behavior.
Earlier Asahi/m1n1/Mu contracts and the Setup-reaching 639d558d launch remain
unchanged; no new hardware protocol or register values are introduced or inferred.

The owning layer is the WinPE collector. It owns inventory, RAM log files and its
console only. Firmware still owns pre-OS initialization; the inherited runtime
platform and Windows drivers retain hardware, interrupts, DMA and power ownership.
No attempt to emulate a mouse or inject an unrelated DockChannel driver is made.
The hidden partition has no drive letter: the existing letter-only marker search
cannot persist evidence there. This update deliberately leaves that mount policy
unchanged so the next observation changes only visibility of existing evidence.

Implementation: preserve full original reports, add compact USB/HID copies, and
launch an ARM64 Kernel32-only console viewer. Display USB, problem devices, HID,
then DiskPart in bounded pages every 12 seconds; repeat without input. Wrap long
instance IDs without dropping characters or introducing a blank line after a
full-width CRLF line. Use actual visible console dimensions. Never read keyboard
or mouse, issue PnP reset/rescan, mount volumes or change partition attributes.
Unreadable/oversized files receive explicit notices. Fall back to existing Notepad
if the viewer cannot be started. Native display remains unqualified until observed.

The installed original diagnostic 965e81d9 is an explicitly pinned upgrade source;
accept it only when the on-volume profile, ESP/firmware/source identities, WIM hash
and duplicate media manifest agree. Preserve complete WIM and manifest rollback
before replacing it. Reject unknown diagnostic WIMs rather than requiring an
unnecessary restore to the original WIM and a second write transaction.

Smallest hardware checkpoint: automatically visible first USB page, followed by
its remaining pages and problem/HID inventory without input. Photograph pages;
controller status/problem code and root-hub/child presence determine the next
source-first investigation. Recovery: prior photographed diagnostic and unchanged
Setup-reaching firmware, plus transactional WIM/metadata backup. A successful
viewer run does not qualify USB input, installer media reads or a full install.

Official sources:
- https://learn.microsoft.com/en-us/windows/console/getconsolescreenbufferinfo
- https://learn.microsoft.com/en-us/windows/console/writeconsoleoutput
- https://learn.microsoft.com/en-us/windows/console/console-screen-buffers
- https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/pnputil-command-syntax
