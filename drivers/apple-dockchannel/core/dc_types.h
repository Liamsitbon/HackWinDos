/* SPDX-License-Identifier: MIT */
#ifndef APPLE_DC_TYPES_H
#define APPLE_DC_TYPES_H

/* /kernel defines _KERNEL_MODE. Do not mix MSVC's user-mode vcruntime
 * headers with WDK km/crt definitions in the kernel translation units. */
#ifdef _KERNEL_MODE
#include <ntddk.h>
typedef UCHAR uint8_t;
typedef USHORT uint16_t;
typedef ULONG uint32_t;
typedef ULONGLONG uint64_t;
#ifndef UINT32_MAX
#define UINT32_MAX MAXULONG
#endif
#ifndef UINT32_C
#define UINT32_C(value) value##u
#endif
#else
#include <stddef.h>
#include <stdint.h>
#endif

#endif
