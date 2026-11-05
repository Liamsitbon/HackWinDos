/** @file Direct Windows Setup on one configured GPT partition, at application TPL.
    SPDX-License-Identifier: BSD-2-Clause-Patent **/
#ifndef J413_DIRECT_SETUP_H
#define J413_DIRECT_SETUP_H
#include <Protocol/PartitionInfo.h>

STATIC EFI_STATUS J413DirectSetupOption(EFI_BOOT_MANAGER_LOAD_OPTION *Option, CONST EFI_GUID *Target)
{
  EFI_HANDLE *Handles = NULL;
  EFI_HANDLE Selected = NULL;
  EFI_GUID Empty = {0};
  UINTN Count = 0, Matches = 0;
  EFI_STATUS Status;
  EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *Fs = NULL;
  EFI_FILE_PROTOCOL *Root = NULL;
  EFI_DEVICE_PATH_PROTOCOL *Path = NULL;
  CHAR16 Loader[J413_EFI_MAX_PATH] = L"\\EFI\\BOOT\\BOOTAA64.EFI";
  if (Option == NULL || Target == NULL) return EFI_INVALID_PARAMETER;
  if (CompareGuid(Target, &Empty)) {
    Print(L"UEFI DIRECT: target partition UUID is not configured\r\n");
    return EFI_NOT_READY;
  }
  if (mEfiScanned) return EFI_NOT_FOUND;
  mEfiScanned = TRUE;
  Status = gBS->LocateHandleBuffer(ByProtocol, &gEfiPartitionInfoProtocolGuid, NULL, &Count, &Handles);
  if (EFI_ERROR(Status)) { if (Handles != NULL) FreePool(Handles); return Status; }
  // Resolve identity only. Never open a filesystem until the unique match is known.
  for (UINTN Index = 0; Index < Count; Index++) {
    EFI_PARTITION_INFO_PROTOCOL *Info = NULL;
    EFI_GUID Identity;
    Status = gBS->HandleProtocol(Handles[Index], &gEfiPartitionInfoProtocolGuid, (VOID **)&Info);
    if (EFI_ERROR(Status) || Info == NULL || Info->Revision < EFI_PARTITION_INFO_PROTOCOL_REVISION ||
        Info->Type != PARTITION_TYPE_GPT) continue;
    CopyMem(&Identity, &Info->Info.Gpt.UniquePartitionGUID, sizeof(Identity));
    if (CompareGuid(&Identity, Target)) { Selected = Handles[Index]; Matches++; }
  }
  if (Handles != NULL) FreePool(Handles);
  Print(L"UEFI DIRECT: partition %g matches %u\r\n", Target, Matches);
  if (Matches == 0) return EFI_NOT_FOUND;
  if (Matches != 1) {
    Print(L"UEFI DIRECT: duplicate partition identity; refusing ambiguous target\r\n");
    return EFI_ACCESS_DENIED;
  }
  Status = gBS->HandleProtocol(Selected, &gEfiSimpleFileSystemProtocolGuid, (VOID **)&Fs);
  if (EFI_ERROR(Status) || Fs == NULL) return EFI_NOT_FOUND;
  Status = Fs->OpenVolume(Fs, &Root);
  if (EFI_ERROR(Status) || Root == NULL) return EFI_NOT_FOUND;
  if (!J413EfiApplication(Root, Loader)) {
    Root->Close(Root);
    Print(L"UEFI DIRECT: target has no valid ARM64 EFI application at the fixed path\r\n");
    return EFI_NOT_FOUND;
  }
  Root->Close(Root);
  Path = FileDevicePath(Selected, Loader);
  Status = Path == NULL ? EFI_OUT_OF_RESOURCES :
    EfiBootManagerInitializeLoadOption(Option, LoadOptionNumberUnassigned,
      LoadOptionTypeBoot, LOAD_OPTION_ACTIVE, L"Windows Setup (same volume)", Path, NULL, 0);
  if (Path != NULL) FreePool(Path);
  if (!EFI_ERROR(Status)) Print(L"UEFI DIRECT: selected %s on partition %g\r\n", Loader, Target);
  return Status;
}
#endif
