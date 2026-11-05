/** @file Direct Windows Setup on one configured GPT partition, at application TPL.
    SPDX-License-Identifier: BSD-2-Clause-Patent **/
#ifndef J413_DIRECT_SETUP_H
#define J413_DIRECT_SETUP_H
#include "J413SetupPartition.h"

STATIC EFI_STATUS J413DirectSetupOption(EFI_BOOT_MANAGER_LOAD_OPTION *Option, CONST EFI_GUID *Target)
{
  EFI_HANDLE Selected = NULL;
  EFI_GUID Empty = {0};
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
  Status = J413FindSetupPartition(Target, &Selected);
  if (EFI_ERROR(Status)) return Status;
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
