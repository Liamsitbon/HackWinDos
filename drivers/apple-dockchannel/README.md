# DockChannel transport components

`core/dockchannel.c` provides bounded FIFO transfers behind register callbacks.
`core/hid_packet.c` ports command framing and packet validation from official
Asahi [dockchannel-hid.c at 77cb8f24](https://github.com/AsahiLinux/linux/blob/77cb8f24c2381a8abb7272d7bbdec548d6426a8a/drivers/hid/dockchannel-hid/dockchannel-hid.c).
The latter offers GPL-2.0 OR MIT. This adaptation selects MIT, retains Asahi
attribution and uses the [included license](../apple-rtkit/ASAHI-MIT-LICENSE.txt).

The packet core reads little-endian fields without unaligned typed loads. It
validates the eight-byte header, interface range 0–15, recognized channel,
aligned body size, complete packet, additive checksum and subheader payload
bounds before returning a borrowed view. Unknown channels are rejected rather
than treated as reports. Extra input can contain another frame; `consumed`
describes only the validated first frame. Invalid input produces no payload view.

Command encoding follows Asahi's eight-byte outer header, eight-byte subheader,
four-byte payload padding and trailing checksum whose complete word sum is
`0xffffffff`. Payloads over 65524 bytes are rejected before the 16-bit padded
body length can overflow. The encoder does not transmit or advance the sequence.
Buffers and output views must be disjoint as documented in the header.

`core/hid_stream.c` now assembles a frame across partial FIFO reads in caller-owned storage. It stops exactly at one complete frame, preserves extra input for the caller, and latches malformed-header/checksum/capacity failures until explicit transport recovery and reset. A complete view lives until reset; calls must be serialized. The adapter still owns timeouts/removal. Transport framing is not a HID descriptor parser or report delivery driver.
`core/hid_command.c` matches ACK channel, interface, sequence, flags and report ID against one serialized outstanding command. It returns the remote status and exact response length, advances sequence on completion/cancellation, rejects mismatched or late replies, and never silently truncates a response. Live firmware transfer,
helper-coprocessor startup, GPIO resets and Windows HID enumeration remain absent.
No input device, IRQ, DART mapping or physical register was exercised.

The portable cores and the KMDF wrapper now build into an ARM64 native
`AppleDockChannel.sys` with the official WDK. [Build 42041739601](https://github.com/Liamsitbon/HackWinDos/actions/runs/42041739601)
produced SYS/INF/CAT artifacts from source `178670b624e05a5e1d8b2f7e332b47537fa1f93e`.
The 35848-byte SYS SHA256 is `8c71e11349967c6162277f71eb4f90732407572f0956efe04aa0f3a122bbec33`.
Catalog trust and runtime hardware support remain unqualified. See [RTKit adapter ownership](../apple-rtkit/README.md)
and [kext evidence](../../documentation/reverse-engineering/DOCKCHANNEL.md).

## Interface discovery

`core/hid_discovery.c` parses one `EVENT_INIT` payload using the same pinned
Asahi structure definitions and MIT license selection. It returns bounded
interface/name, HID descriptor, GPIO request and product-name views. Fixed-width
names are copied with an added terminator. GPIO data must fit its own block,
not just the enclosing packet. Zero-length product/descriptor blocks, duplicate
known blocks, truncated lengths and invalid interface IDs are rejected without
exposing partial output. Unknown blocks are skipped; a terminator stops parsing
as in upstream. No buffer is allocated and no GPIO is driven.

Discovery can span multiple events (`more_packets`); accumulating descriptors
and atomically publishing an interface remain adapter responsibilities. These
cores still lack the complete MTP/helper/DART/GPIO/IRQ resource adapter and
discovery-driven HID publication in the Windows wrapper. Consequently
they do not make built-in input usable at Windows Boot Manager Recovery.

`tests/test_dockchannel_discovery.py` exercises every two-part frame split,
concatenated frames, sticky transport errors, untrusted initialization lengths,
fixed-width names and GPIO block boundaries under ASan/UBSan, and compiles both
new cores as Windows ARM64 COFF.

## Commands and firmware preparation

The command core follows the pinned Asahi `dchid_cmd`/`dchid_handle_ack`
transaction fields. Initialize state while transport is quiescent, serialize
TX/RX/cancel, then begin before transmitting. On send failure or timeout, cancel
and recover partial FIFO transmission before issuing another frame. The core
does not retry automatically. Sequence numbers wrap after 256 commands; matching
is not replay protection across reset or arbitrarily delayed full wraps. Insufficient
response storage leaves the command pending and writes no bytes. A nonzero remote
return code completes the command without delivering its response as valid HID data.

`core/hid_firmware.c` validates the HIDF v1 header and declared data/patch bounds,
copies data to caller-owned storage and patches a nonzero interface offset as in
Asahi `dchid_get_firmware`. Short headers, overflowing lengths, unsupported version,
invalid interface and insufficient destination capacity leave output untouched.
This is format validation, not signature or hardware compatibility verification.
No Apple firmware is distributed. No DMA allocation, mapping or transfer occurs.

The command/firmware tests exercise wrong-channel/interface/sequence/flags/report
ACKs, cancellation, sequence wrap, remote errors, every flags byte, insufficient
response capacity, short/oversized firmware fields, immutable input and randomized
archives under ASan/UBSan; both cores compile as Windows ARM64 COFF. These components
still need an actual transport/power/IRQ/DART adapter and Windows HID publication.
