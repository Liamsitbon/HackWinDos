/* SPDX-License-Identifier: MIT
 * Adapted from Apple DockChannel HID transport:
 * Copyright The Asahi Linux Contributors
 */
#ifndef APPLE_DOCKCHANNEL_HID_PACKET_H
#define APPLE_DOCKCHANNEL_HID_PACKET_H
#include "dc_types.h"

#define DCHID_MAX_PAYLOAD 65524u
#define DCHID_COMMAND_CHANNEL 0x11u
#define DCHID_REPORT_CHANNEL 0x12u
enum dchid_status { DCHID_OK, DCHID_INVALID, DCHID_INCOMPLETE,
                    DCHID_BAD_HEADER, DCHID_BAD_CHECKSUM, DCHID_NO_SPACE };
struct dchid_packet {
    const uint8_t *payload;
    size_t payload_size, consumed;
    uint32_t return_code;
    uint8_t channel, sequence, interface_id, flags;
};

/* Borrowed view into an immutable caller-owned packet snapshot. Snapshot and
 * view must not overlap. Extra bytes may contain the next packet; consumed
 * gives the exact first packet size. No FIFO bytes are read or discarded. */
enum dchid_status dchid_parse_packet(const uint8_t *bytes, size_t available,
                                     struct dchid_packet *view);
/* Encode the command form sent by Asahi. Payload and output must be disjoint.
 * Does not advance sequence or send anything. Invalid/no-space calls write no
 * output bytes and set written to zero. */
enum dchid_status dchid_encode_command(uint8_t interface_id, uint8_t sequence,
                                       uint8_t flags, const uint8_t *payload,
                                       size_t payload_size, uint8_t *output,
                                       size_t capacity, size_t *written);
#endif
