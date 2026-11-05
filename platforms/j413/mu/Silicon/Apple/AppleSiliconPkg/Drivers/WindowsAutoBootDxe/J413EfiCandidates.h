/** @file Exact-path, filesystem-independent ARM64 fallback loader discovery.
    SPDX-License-Identifier: BSD-2-Clause-Patent **/
#ifndef J413_EFI_CANDIDATES_H
#define J413_EFI_CANDIDATES_H
#define J413_EFI_MAX_PATH 1024
#define J413_EFI_MAX_CANDIDATES 256

STATIC BOOLEAN mEfiScanned;
#ifndef J413_DIRECT_SETUP_ONLY
typedef struct J413_EFI_CANDIDATE {
  struct J413_EFI_CANDIDATE *Next;
  EFI_HANDLE Handle;
  CHAR16 Path[J413_EFI_MAX_PATH];
} J413_EFI_CANDIDATE;
STATIC J413_EFI_CANDIDATE *mEfiHead, *mEfiTail;
STATIC UINTN mEfiCount;
#endif

STATIC CHAR16 J413EfiFold(CHAR16 C) { return C >= L'A' && C <= L'Z' ? C + (L'a' - L'A') : C; }
STATIC BOOLEAN J413EfiSamePath(CONST CHAR16 *A, CONST CHAR16 *B) {
  while (*A && J413EfiFold(*A) == J413EfiFold(*B)) { A++; B++; }
  return J413EfiFold(*A) == J413EfiFold(*B);
}
STATIC UINT32 J413EfiLe32(CONST UINT8 *P) {
  return (UINT32)P[0] | ((UINT32)P[1] << 8) | ((UINT32)P[2] << 16) | ((UINT32)P[3] << 24);
}
STATIC UINT16 J413EfiLe16(CONST UINT8 *P) { return (UINT16)(P[0] | ((UINT16)P[1] << 8)); }

// Some third-party filesystems have case-sensitive Open(). Resolve only the
// three standard components there; never recurse or select another EFI name.
STATIC EFI_STATUS J413EfiFindName(EFI_FILE_PROTOCOL *Directory, CONST CHAR16 *Wanted,
                                BOOLEAN IsDirectory, CHAR16 *Name) {
  UINTN Capacity = 512;
  EFI_FILE_INFO *Info = AllocatePool(Capacity);
  EFI_STATUS Status;
  if (Info == NULL) return EFI_OUT_OF_RESOURCES;
  Status = Directory->SetPosition(Directory, 0);
  if (EFI_ERROR(Status)) { FreePool(Info); return Status; }
  Status = EFI_NOT_FOUND;
  for (UINTN Entry = 0; Entry < 8192; ) {
    UINTN Bytes = Capacity;
    Status = Directory->Read(Directory, &Bytes, Info);
    if (Status == EFI_BUFFER_TOO_SMALL) {
      EFI_FILE_INFO *Larger;
      if (Bytes <= Capacity || Bytes > 65536) { Status = EFI_VOLUME_CORRUPTED; break; }
      Larger = AllocatePool(Bytes);
      if (Larger == NULL) { Status = EFI_OUT_OF_RESOURCES; break; }
      FreePool(Info); Info = Larger; Capacity = Bytes;
      continue;
    }
    if (EFI_ERROR(Status)) break;
    if (Bytes == 0) { Status = EFI_NOT_FOUND; break; }
    Entry++;
    if (Bytes > Capacity || Bytes < OFFSET_OF(EFI_FILE_INFO, FileName) + sizeof(CHAR16) ||
        Info->Size > Bytes || Info->Size < OFFSET_OF(EFI_FILE_INFO, FileName) + sizeof(CHAR16)) {
      Status = EFI_VOLUME_CORRUPTED; break;
    }
    {
      UINTN Limit = (UINTN)(Info->Size - OFFSET_OF(EFI_FILE_INFO, FileName)) / sizeof(CHAR16);
      UINTN Length = 0;
      while (Length < Limit && Info->FileName[Length] != 0) Length++;
      if (Length == Limit) { Status = EFI_VOLUME_CORRUPTED; break; }
      if (Length == StrLen(Wanted) && J413EfiSamePath(Info->FileName, Wanted) &&
          ((Info->Attribute & EFI_FILE_DIRECTORY) != 0) == IsDirectory) {
        CopyMem(Name, Info->FileName, (Length + 1) * sizeof(CHAR16));
        Status = EFI_SUCCESS; break;
      }
    }
    Status = EFI_NOT_FOUND;
  }
  FreePool(Info);
  return Status;
}

STATIC EFI_STATUS J413EfiResolveFallback(EFI_FILE_PROTOCOL *Root, CHAR16 *Path) {
  CONST CHAR16 *Names[] = {L"EFI", L"BOOT", L"BOOTAA64.EFI"};
  EFI_FILE_PROTOCOL *Directory = Root;
  EFI_STATUS Status = EFI_NOT_FOUND;
  Path[0] = 0;
  for (UINTN Index = 0; Index < 3; Index++) {
    CHAR16 Name[16]; // Each match has exactly the corresponding standard name's length.
    UINTN Length = StrLen(Path);
    Status = J413EfiFindName(Directory, Names[Index], Index < 2, Name);
    if (EFI_ERROR(Status)) break;
    Path[Length++] = L'\\';
    CopyMem(Path + Length, Name, (StrLen(Name) + 1) * sizeof(CHAR16));
    if (Index < 2) {
      EFI_FILE_PROTOCOL *Next = NULL;
      Status = Root->Open(Root, &Next, Path, EFI_FILE_MODE_READ, 0);
      if (EFI_ERROR(Status) || Next == NULL) { Status = EFI_NOT_FOUND; break; }
      if (Directory != Root) Directory->Close(Directory);
      Directory = Next;
    }
  }
  if (Directory != Root) Directory->Close(Directory);
  return Status;
}

// Header preflight only. Standard BDS LoadImage still owns complete validation/security.
STATIC BOOLEAN J413EfiApplication(EFI_FILE_PROTOCOL *Root, CHAR16 *Path) {
  EFI_FILE_PROTOCOL *File = NULL;
  UINT8 Dos[64], Pe[94];
  UINTN Size = sizeof(Dos);
  BOOLEAN Valid = FALSE;
  EFI_STATUS Status = Root->Open(Root, &File, Path, EFI_FILE_MODE_READ, 0);
  if (Status == EFI_NOT_FOUND && !EFI_ERROR(J413EfiResolveFallback(Root, Path))) {
    Status = Root->Open(Root, &File, Path, EFI_FILE_MODE_READ, 0);
  }
  if (EFI_ERROR(Status) || File == NULL) return FALSE;
  Status = File->Read(File, &Size, Dos);
  if (!EFI_ERROR(Status) && Size == sizeof(Dos) && Dos[0] == 'M' && Dos[1] == 'Z') {
    UINT32 Offset = J413EfiLe32(Dos + 60);
    if (Offset >= sizeof(Dos) && Offset <= 0x1000000) {
      Status = File->SetPosition(File, Offset);
      Size = sizeof(Pe);
      if (!EFI_ERROR(Status)) Status = File->Read(File, &Size, Pe);
      if (!EFI_ERROR(Status) && Size == sizeof(Pe)) {
        Valid = J413EfiLe32(Pe) == 0x4550 && J413EfiLe16(Pe + 4) == 0xaa64 &&
                J413EfiLe16(Pe + 20) >= 70 && J413EfiLe16(Pe + 24) == 0x20b &&
                J413EfiLe16(Pe + 92) == 10;
      }
    }
  }
  File->Close(File);
  return Valid;
}

#ifndef J413_DIRECT_SETUP_ONLY
STATIC VOID J413EfiQueue(EFI_HANDLE Handle, EFI_FILE_PROTOCOL *Root, CHAR16 *Path) {
  J413_EFI_CANDIDATE *Item;
  if (mEfiCount >= J413_EFI_MAX_CANDIDATES || StrLen(Path) >= J413_EFI_MAX_PATH) return;
  for (Item = mEfiHead; Item != NULL; Item = Item->Next) {
    if (Item->Handle == Handle && J413EfiSamePath(Item->Path, Path)) return;
  }
  if (!J413EfiApplication(Root, Path)) return;
  Item = AllocateZeroPool(sizeof(*Item));
  if (Item == NULL) { Print(L"UEFI EFI: candidate allocation failed\r\n"); return; }
  Item->Handle = Handle;
  CopyMem(Item->Path, Path, (StrLen(Path) + 1) * sizeof(CHAR16));
  if (mEfiTail != NULL) mEfiTail->Next = Item; else mEfiHead = Item;
  mEfiTail = Item;
  mEfiCount++;
  Print(L"UEFI EFI: found %s\r\n", Path);
}

STATIC EFI_STATUS J413NextEfiOption(EFI_BOOT_MANAGER_LOAD_OPTION *Option) {
  EFI_STATUS Status;
  if (!mEfiScanned) {
    EFI_HANDLE *Handles = NULL;
    UINTN Count = 0;
    mEfiScanned = TRUE;
    Status = gBS->LocateHandleBuffer(ByProtocol, &gEfiSimpleFileSystemProtocolGuid, NULL, &Count, &Handles);
    if (EFI_ERROR(Status)) { if (Handles != NULL) FreePool(Handles); return Status; }
    // Only the standard ARM64 fallback path, on every readable filesystem.
    // No Windows Setup dependency gate, BlockIo requirement or recursive scan.
    for (UINTN Index = 0; Index < Count; Index++) {
      EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *Fs = NULL;
      EFI_FILE_PROTOCOL *Root = NULL;
      CHAR16 Path[J413_EFI_MAX_PATH] = L"\\EFI\\BOOT\\BOOTAA64.EFI";
      Status = gBS->HandleProtocol(Handles[Index], &gEfiSimpleFileSystemProtocolGuid, (VOID **)&Fs);
      if (EFI_ERROR(Status) || Fs == NULL) continue;
      Status = Fs->OpenVolume(Fs, &Root);
      if (EFI_ERROR(Status) || Root == NULL) continue;
      J413EfiQueue(Handles[Index], Root, Path);
      Root->Close(Root);
    }
    if (Handles != NULL) FreePool(Handles);
    if (mEfiCount >= J413_EFI_MAX_CANDIDATES) Print(L"UEFI EFI: candidate limit reached\r\n");
    Print(L"UEFI EFI: discovered %u BOOTAA64.EFI candidates\r\n", mEfiCount);
  }
  while (mEfiHead != NULL) {
    J413_EFI_CANDIDATE *Item = mEfiHead;
    EFI_DEVICE_PATH_PROTOCOL *Path;
    mEfiHead = Item->Next;
    if (mEfiHead == NULL) mEfiTail = NULL;
    Path = FileDevicePath(Item->Handle, Item->Path);
    Status = Path == NULL ? EFI_OUT_OF_RESOURCES :
      EfiBootManagerInitializeLoadOption(Option, LoadOptionNumberUnassigned,
        LoadOptionTypeBoot, LOAD_OPTION_ACTIVE, Item->Path, Path, NULL, 0);
    if (Path != NULL) FreePool(Path);
    if (!EFI_ERROR(Status)) Print(L"UEFI EFI: selected %s\r\n", Item->Path);
    FreePool(Item);
    if (!EFI_ERROR(Status)) return Status;
    Print(L"UEFI EFI: option creation failed: %r\r\n", Status);
  }
  return EFI_NOT_FOUND;
}
#endif
#endif
