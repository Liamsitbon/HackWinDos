/* SPDX-License-Identifier: MIT */
#ifndef APPLE_DOCKCHANNEL_CORE_H
#define APPLE_DOCKCHANNEL_CORE_H

#include "dc_types.h"

/* Callbacks address offsets in the already mapped data bank. The adapter owns
 * register ordering, power, cancellation and serialization. No polling here. */
struct dc_io {
    void *context;
    uint32_t (*read32)(void *context, uint32_t offset);
    void (*write32)(void *context, uint32_t offset, uint32_t value);
    void (*write8)(void *context, uint32_t offset, uint8_t value);
    uint32_t fifo_size;
};

enum dc_status { DC_COMPLETE, DC_PARTIAL, DC_WOULD_BLOCK, DC_INVALID, DC_BAD_CAPACITY };
struct dc_result { enum dc_status status; size_t transferred; };

struct dc_result dc_try_send(const struct dc_io *io, const uint8_t *buffer,
                             size_t count, size_t budget);
struct dc_result dc_try_receive(const struct dc_io *io, uint8_t *buffer,
                                size_t count, size_t budget);
#endif
