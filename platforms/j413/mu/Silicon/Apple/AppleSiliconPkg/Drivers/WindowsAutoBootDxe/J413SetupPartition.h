/** @file Resolve the direct Setup GPT identity without opening any filesystem.
    SPDX-License-Identifier: BSD-2-Clause-Patent **/
#ifndef J413_SETUP_PARTITION_H
#define J413_SETUP_PARTITION_H
#include <Protocol/PartitionInfo.h>

STATIC EFI_STATUS J413FindSetupPartition(CONST EFI_GUID *Target, EFI_HANDLE *Selected)
{
  EFI_HANDLE *Handles = NULL;
  EFI_GUID Empty = {0};
  UINTN Count = 0, Matches = 0;
  EFI_STATUS Status;
  if (Target == NULL || Selected == NULL) return EFI_INVALID_PARAMETER;
  *Selected = NULL;
  if (CompareGuid(Target, &Empty)) return EFI_NOT_READY;
  Status = gBS->LocateHandleBuffer(ByProtocol, &gEfiPartitionInfoProtocolGuid, NULL, &Count, &Handles);
  if (EFI_ERROR(Status)) { if (Handles != NULL) FreePool(Handles); return Status; }
  for (UINTN Index = 0; Handles != NULL && Index < Count; Index++) {
    EFI_PARTITION_INFO_PROTOCOL *Info = NULL;
    EFI_GUID Identity;
    Status = gBS->HandleProtocol(Handles[Index], &gEfiPartitionInfoProtocolGuid, (VOID **)&Info);
    if (EFI_ERROR(Status) || Info == NULL || Info->Revision < EFI_PARTITION_INFO_PROTOCOL_REVISION ||
        Info->Type != PARTITION_TYPE_GPT) continue;
    CopyMem(&Identity, &Info->Info.Gpt.UniquePartitionGUID, sizeof(Identity));
    if (CompareGuid(&Identity, Target)) { *Selected = Handles[Index]; Matches++; }
  }
  if (Handles != NULL) FreePool(Handles);
  Print(L"UEFI DIRECT: partition %g matches %u\r\n", Target, Matches);
  if (Matches == 1) return EFI_SUCCESS;
  *Selected = NULL;
  if (Matches == 0) return EFI_NOT_FOUND;
  Print(L"UEFI DIRECT: duplicate partition identity; refusing ambiguous target\r\n");
  return EFI_ACCESS_DENIED;
}
#endif
