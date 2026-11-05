/** @file Connect the J413 external Setup storage through normal UEFI driver binding.
  SPDX-License-Identifier: BSD-2-Clause-Patent
**/
#ifndef J413_CONNECT_TRACE_H
#define J413_CONNECT_TRACE_H
#include <Protocol/NonDiscoverableDevice.h>
#include <Guid/NonDiscoverableDevice.h>
#include <Protocol/PciRootBridgeIo.h>

STATIC EFI_STATUS J413ConnectBootNvme(VOID)
{
  EFI_HANDLE *Handles = NULL;
  UINTN Count = 0;
  EFI_STATUS Result = EFI_NOT_FOUND;
  EFI_STATUS Status = gBS->LocateHandleBuffer(ByProtocol,
      &gEfiPciRootBridgeIoProtocolGuid, NULL, &Count, &Handles);
  Print(L"UEFI NVMe: PCI root lookup %r; roots %u\r\n", Status, Count);
  if (!EFI_ERROR(Status) && Handles != NULL) {
    // J413 exposes its synthetic NVMe at the registered PCI root. The platform
    // connect list is empty; do not wait until Shell/global ConnectAll to bind it.
    for (UINTN Index = 0; Index < Count; Index++) {
      Status = gBS->ConnectController(Handles[Index], NULL, NULL, TRUE);
      Print(L"UEFI NVMe: root connection returned %r\r\n", Status);
      if (!EFI_ERROR(Status) || Result != EFI_SUCCESS) Result = Status;
    }
  } else if (EFI_ERROR(Status)) {
    Result = Status;
  }
  if (Handles != NULL) FreePool(Handles);
  return Result;
}

STATIC EFI_STATUS J413ConnectBootUsb(VOID)
{
  EFI_HANDLE *Handles = NULL;
  UINTN Count = 0;
  UINTN Matched = 0;
  EFI_STATUS Result = EFI_NOT_FOUND;
  EFI_STATUS Status = gBS->LocateHandleBuffer(ByProtocol,
      &gEdkiiNonDiscoverableDeviceProtocolGuid, NULL, &Count, &Handles);
  Print(L"UEFI USB: registered controller lookup: %r; handles %u\r\n", Status, Count);
  if (EFI_ERROR(Status)) {
    if (Handles != NULL) FreePool(Handles);
    return Status;
  }
  for (UINTN Index = 0; Index < Count; Index++) {
    NON_DISCOVERABLE_DEVICE *Device = NULL;
    Status = gBS->HandleProtocol(Handles[Index], &gEdkiiNonDiscoverableDeviceProtocolGuid,
                                (VOID **)&Device);
    if (EFI_ERROR(Status) || Device == NULL || Device->Type == NULL ||
        !CompareGuid(Device->Type, &gEdkiiNonDiscoverableXhciDeviceGuid)) continue;
    Matched++;
    // The J413 platform registers only USB1, after checked core/DART initialization.
    // Recursive binding includes its PCI-I/O bridge, host, USB bus and storage children.
    EFI_DEVICE_PATH_PROTOCOL *Path = DevicePathFromHandle(Handles[Index]);
    CHAR16 *Text = Path == NULL ? NULL : ConvertDevicePathToText(Path, FALSE, FALSE);
    Print(L"UEFI CONNECT: boot USB controller %p entered\r\n", Handles[Index]);
    if (Text != NULL) { Print(L"UEFI CONNECT: path %s\r\n", Text); FreePool(Text); }
    Status = gBS->ConnectController(Handles[Index], NULL, NULL, TRUE);
    Print(L"UEFI CONNECT: boot USB controller returned %r\r\n", Status);
    if (!EFI_ERROR(Status) || Result != EFI_SUCCESS) Result = Status;
  }
  if (Handles != NULL) FreePool(Handles);
  Print(L"UEFI USB: matching boot controllers: %u; connection result: %r\r\n", Matched, Result);
  return Result;
}
#endif
