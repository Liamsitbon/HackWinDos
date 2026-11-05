/** @file Connect J413 Setup storage through normal UEFI driver binding.
  SPDX-License-Identifier: BSD-2-Clause-Patent
**/
#ifndef J413_CONNECT_TRACE_H
#define J413_CONNECT_TRACE_H
#include <Protocol/NonDiscoverableDevice.h>
#include <Guid/NonDiscoverableDevice.h>
#include <Protocol/PciRootBridgeIo.h>
#include <Protocol/PciIo.h>
#include "J413SetupPartition.h"

STATIC EFI_STATUS J413ConnectStorageLevel(EFI_HANDLE Handle, CONST CHAR16 *Stage)
{
  EFI_DEVICE_PATH_PROTOCOL *Path = DevicePathFromHandle(Handle);
  CHAR16 *Text = Path == NULL ? NULL : ConvertDevicePathToText(Path, FALSE, FALSE);
  EFI_STATUS Status;
  Print(L"UEFI NVMe: %s entered; handle %p\r\n", Stage, Handle);
  if (Text != NULL) { Print(L"UEFI NVMe: path %s\r\n", Text); FreePool(Text); }
  // A synchronous driver cannot be preempted by a timer around this call.
  // Expand one level so no unrelated partition/filesystem is connected recursively.
  Status = gBS->ConnectController(Handle, NULL, NULL, FALSE);
  Print(L"UEFI NVMe: %s returned %r\r\n", Stage, Status);
  return Status;
}

STATIC BOOLEAN J413StorageChild(EFI_HANDLE Child, EFI_HANDLE Parent)
{
  EFI_DEVICE_PATH_PROTOCOL *ChildPath = DevicePathFromHandle(Child);
  EFI_DEVICE_PATH_PROTOCOL *ParentPath = DevicePathFromHandle(Parent);
  UINTN ParentSize = ParentPath == NULL ? 0 : GetDevicePathSize(ParentPath);
  UINTN ChildSize = ChildPath == NULL ? 0 : GetDevicePathSize(ChildPath);
  return ParentSize > END_DEVICE_PATH_LENGTH && ChildSize > ParentSize &&
    CompareMem(ChildPath, ParentPath, ParentSize - END_DEVICE_PATH_LENGTH) == 0;
}

STATIC EFI_STATUS J413ConnectSetupFilesystem(EFI_HANDLE Selected)
{
  EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *Fs = NULL;
  EFI_STATUS Status = gBS->HandleProtocol(Selected, &gEfiSimpleFileSystemProtocolGuid, (VOID **)&Fs);
  if (!EFI_ERROR(Status) && Fs != NULL) {
    Print(L"UEFI NVMe: target filesystem already ready\r\n");
    return EFI_SUCCESS;
  }
  Status = J413ConnectStorageLevel(Selected, L"target filesystem");
  if (EFI_ERROR(Status) && Status != EFI_NOT_FOUND && Status != EFI_ALREADY_STARTED) return Status;
  Fs = NULL;
  Status = gBS->HandleProtocol(Selected, &gEfiSimpleFileSystemProtocolGuid, (VOID **)&Fs);
  Print(L"UEFI NVMe: target filesystem protocol %r\r\n", Status);
  return !EFI_ERROR(Status) && Fs != NULL ? EFI_SUCCESS : EFI_NOT_FOUND;
}

STATIC EFI_STATUS J413ConnectBootNvme(CONST EFI_GUID *Target)
{
  EFI_HANDLE *Handles = NULL;
  EFI_HANDLE Selected = NULL, Controller = NULL, Namespace = NULL;
  UINTN Count = 0, Matches = 0;
  EFI_STATUS Status = J413FindSetupPartition(Target, &Selected);
  if (!EFI_ERROR(Status)) return J413ConnectSetupFilesystem(Selected);
  if (Status != EFI_NOT_FOUND) return Status;

  Status = gBS->LocateHandleBuffer(ByProtocol,
      &gEfiPciRootBridgeIoProtocolGuid, NULL, &Count, &Handles);
  Print(L"UEFI NVMe: PCI root lookup %r; roots %u\r\n", Status, Count);
  if (EFI_ERROR(Status)) { if (Handles != NULL) FreePool(Handles); return Status; }
  // hv_pci.c exposes one root and one function, segment 0, 00:00.0.
  if (Handles == NULL || Count != 1) {
    if (Handles != NULL) FreePool(Handles);
    return Count > 1 ? EFI_ACCESS_DENIED : EFI_NOT_FOUND;
  }
  Status = J413ConnectStorageLevel(Handles[0], L"root enumeration");
  FreePool(Handles);
  Handles = NULL;
  if (EFI_ERROR(Status) && Status != EFI_NOT_FOUND && Status != EFI_ALREADY_STARTED) return Status;

  Count = 0;
  Status = gBS->LocateHandleBuffer(ByProtocol, &gEfiPciIoProtocolGuid, NULL, &Count, &Handles);
  if (EFI_ERROR(Status)) { if (Handles != NULL) FreePool(Handles); return Status; }
  for (UINTN Index = 0; Handles != NULL && Index < Count; Index++) {
    EFI_PCI_IO_PROTOCOL *Pci = NULL;
    UINTN Segment, Bus, Device, Function;
    UINT8 Class[3];
    Status = gBS->HandleProtocol(Handles[Index], &gEfiPciIoProtocolGuid, (VOID **)&Pci);
    if (EFI_ERROR(Status) || Pci == NULL) continue;
    Status = Pci->GetLocation(Pci, &Segment, &Bus, &Device, &Function);
    if (EFI_ERROR(Status) || Segment != 0 || Bus != 0 || Device != 0 || Function != 0) continue;
    Status = Pci->Pci.Read(Pci, EfiPciIoWidthUint8, 0x09, sizeof(Class), Class);
    if (EFI_ERROR(Status) || Class[0] != 0x02 || Class[1] != 0x08 || Class[2] != 0x01) continue;
    Controller = Handles[Index];
    Matches++;
  }
  if (Handles != NULL) FreePool(Handles);
  Handles = NULL;
  Print(L"UEFI NVMe: synthetic PCI functions %u\r\n", Matches);
  if (Matches != 1) return Matches > 1 ? EFI_ACCESS_DENIED : EFI_NOT_FOUND;
  Status = J413ConnectStorageLevel(Controller, L"NVMe controller");
  if (EFI_ERROR(Status) && Status != EFI_NOT_FOUND && Status != EFI_ALREADY_STARTED) return Status;

  Count = Matches = 0;
  Status = gBS->LocateHandleBuffer(ByProtocol, &gEfiBlockIoProtocolGuid, NULL, &Count, &Handles);
  if (EFI_ERROR(Status)) { if (Handles != NULL) FreePool(Handles); return Status; }
  for (UINTN Index = 0; Handles != NULL && Index < Count; Index++) {
    EFI_BLOCK_IO_PROTOCOL *Block = NULL;
    if (!J413StorageChild(Handles[Index], Controller)) continue;
    Status = gBS->HandleProtocol(Handles[Index], &gEfiBlockIoProtocolGuid, (VOID **)&Block);
    if (EFI_ERROR(Status) || Block == NULL || Block->Media == NULL ||
        !Block->Media->MediaPresent || Block->Media->LogicalPartition) continue;
    Namespace = Handles[Index];
    Matches++;
  }
  if (Handles != NULL) FreePool(Handles);
  Print(L"UEFI NVMe: whole namespaces %u\r\n", Matches);
  if (Matches != 1) return Matches > 1 ? EFI_ACCESS_DENIED : EFI_NOT_FOUND;
  Status = J413ConnectStorageLevel(Namespace, L"namespace");
  if (EFI_ERROR(Status) && Status != EFI_NOT_FOUND && Status != EFI_ALREADY_STARTED) return Status;
  Status = J413FindSetupPartition(Target, &Selected);
  return EFI_ERROR(Status) ? Status : J413ConnectSetupFilesystem(Selected);
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
