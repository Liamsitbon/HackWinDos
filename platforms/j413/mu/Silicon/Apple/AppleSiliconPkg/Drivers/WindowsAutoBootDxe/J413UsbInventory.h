/** @file Read-only protocol inventory after J413 boot USB binding.
    SPDX-License-Identifier: BSD-2-Clause-Patent **/
#ifndef J413_USB_INVENTORY_H
#define J413_USB_INVENTORY_H
#include <Protocol/Usb2HostController.h>
#include <Protocol/UsbIo.h>

STATIC VOID J413UsbInventory(VOID)
{
  EFI_GUID *Protocols[] = {
    &gEfiUsb2HcProtocolGuid, &gEfiUsbIoProtocolGuid,
    &gEfiBlockIoProtocolGuid, &gEfiSimpleFileSystemProtocolGuid
  };
  CONST CHAR16 *Names[] = { L"host controllers", L"USB interfaces", L"block devices (all buses)", L"filesystems (all buses)" };
  for (UINTN Kind = 0; Kind < sizeof(Protocols) / sizeof(Protocols[0]); Kind++) {
    EFI_HANDLE *Handles = NULL;
    UINTN Count = 0;
    EFI_STATUS Status = gBS->LocateHandleBuffer(ByProtocol, Protocols[Kind], NULL, &Count, &Handles);
    // Print status separately: an enumeration error is not proof of zero devices.
    Print(L"UEFI USB: %s lookup: %r; handles %u\r\n", Names[Kind], Status, Count);
    if (!EFI_ERROR(Status) && Handles != NULL) {
      for (UINTN Index = 0; Index < Count; Index++) {
        EFI_DEVICE_PATH_PROTOCOL *Path = DevicePathFromHandle(Handles[Index]);
        CHAR16 *Text = Path == NULL ? NULL : ConvertDevicePathToText(Path, FALSE, FALSE);
        Print(L"UEFI USB: %s handle %p path %s\r\n", Names[Kind], Handles[Index],
              Text == NULL ? L"<unavailable>" : Text);
        if (Text != NULL) FreePool(Text);
      }
    }
    if (Handles != NULL) FreePool(Handles);
  }
}
#endif
