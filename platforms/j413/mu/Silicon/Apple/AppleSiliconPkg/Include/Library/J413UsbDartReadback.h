/** @file
  Verify the USB DART bypass contract before publishing J413 readiness.

  Adapted from UsbDartVerifyControllerBypass in aurora-silicon/mu at
  063c6b34da94801d1ee9085594e5ac71ae1793b9, AppleUsbTypeCBringupDxe.c.
  Copyright (c) 2026 Aurora Silicon
  Copyright (c) 2024 amarioguy (AppleWOA authors)
  Copyright (C) 2022 Mark Kettenis <kettenis@openbsd.org>
  Copyright (C) The Asahi Linux Contributors
  Copyright 2017, 2020 NXP
  SPDX-License-Identifier: (BSD-2-Clause-Patent OR MIT) AND GPL-2.0-only

  See third_party/aurora-usb/README.md for the compatibility review and terms.
**/
#ifndef J413_USB_DART_READBACK_H
#define J413_USB_DART_READBACK_H

STATIC EFI_STATUS
J413UsbDartVerifyBypass(IN APPLE_DART_INFO *Dart, IN UINT32 Bank)
{
  if (Dart->Nsid <= 0 || Dart->Nsid > 256) {
    return EFI_DEVICE_ERROR;
  }
  MemoryFence();
  for (INT32 Sid = 0; Sid < Dart->Nsid; Sid++) {
    UINT32 Tcr = MmioRead32(Dart->BaseAddress + DART_TCR(*Dart, Sid));
    if (Tcr == Dart->TcrBypass) {
      continue;
    }
    DEBUG((DEBUG_ERROR, "UEFI DART: bank %d SID %d TCR=0x%x expected bypass 0x%x; not ready\n",
           Bank, Sid, Tcr, Dart->TcrBypass));
    return EFI_DEVICE_ERROR;
  }
  return EFI_SUCCESS;
}
#endif
