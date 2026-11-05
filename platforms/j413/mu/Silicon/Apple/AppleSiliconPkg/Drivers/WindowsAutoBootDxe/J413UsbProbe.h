/** @file Read-only failure snapshot, bounded by published BAR/live ADT resources.
    SPDX-License-Identifier: BSD-2-Clause-Patent **/
#ifndef J413_USB_PROBE_H
#define J413_USB_PROBE_H
#include <IndustryStandard/Acpi.h>
#include <Protocol/PciIo.h>
#include <Library/AppleDTLib.h>
#include <Library/IoLib.h>
#include <Drivers/AppleUsbTypeCBringupDxe.h>

STATIC BOOLEAN J413UsbRead32(EFI_PCI_IO_PROTOCOL *Pci, UINT64 Length, UINTN Offset,
                            CONST CHAR16 *Name, UINT32 *Value)
{
  EFI_STATUS Status;
  if ((Offset & 3) != 0 || Length < 4 || Offset > Length - 4) return FALSE;
  *Value = 0;
  Status = Pci->Mem.Read(Pci, EfiPciIoWidthUint32, 0, Offset, 1, Value);
  Print(L"USB probe: %s +0x%x = %08x (%r)\r\n", Name, (UINT32)Offset, *Value, Status);
  if (!EFI_ERROR(Status)) {
    CHAR8 Label[64];
    AsciiSPrint(Label, sizeof(Label), "USB MMIO +0x%x", (UINT32)Offset);
    J413LogCount(Label, *Value);
  } else {
    J413LogStatus("USB MMIO read failed", Status);
  }
  return !EFI_ERROR(Status);
}

STATIC VOID J413UsbPhySnapshot(VOID)
{
  J413_USB_DART_READY *Ready = NULL;
  dt_node_t *Node;
  uint64_t Base = 0, Length = 0;
  CONST UINTN Offsets[] = {0x00, 0x04, 0x08, 0x1c};
  CONST CHAR16 *Names[] = {L"USBCTL", L"CTL", L"SIG", L"MISCTUNE"};
  EFI_STATUS Status = gBS->LocateProtocol(&gJ413UsbDartReadyProtocolGuid, NULL, (VOID **)&Ready);
  if (EFI_ERROR(Status) || Ready == NULL || (Ready->ControllerMask & 2) == 0) {
    Print(L"USB probe: USB1 PHY not read: host readiness unavailable\r\n");
    return;
  }
  Node = dt_get("atc-phy1");
  // The same translated reg[0] and offsets used by m1n1's USB2 PHY owner.
  // No fixed physical address, power/reset change or unsafe speculative access.
  if (Node == NULL || dt_node_reg(Node, 0, &Base, &Length) != 0 || Base == 0 ||
      (Base & 3) != 0 || Length < 0x20 || Base > MAX_UINT64 - 0x1f) {
    Print(L"USB probe: USB1 PHY not read: invalid live ADT resource\r\n");
    return;
  }
  for (UINTN Index = 0; Index < 4; Index++) {
    UINT32 Value = MmioRead32((UINTN)(Base + Offsets[Index]));
    CHAR8 Label[64];
    Print(L"USB probe: USB1 PHY %s = %08x\r\n", Names[Index], Value);
    AsciiSPrint(Label, sizeof(Label), "USB1 PHY +0x%x", (UINT32)Offsets[Index]);
    J413LogCount(Label, Value);
  }
}

STATIC VOID J413UsbSnapshot(VOID)
{
  // Private marker published by the pinned UsbBusDxe on its host handle.
  // UsbBusDxe.inf FILE_GUID; probe its presence without dereferencing BusId.
  EFI_GUID UsbBusGuid = {0x240612b7, 0xa063, 0x11d4, {0x9a,0x3a,0x00,0x90,0x27,0x3f,0xc1,0x4d}};
  EFI_HANDLE *Handles = NULL;
  UINTN Count = 0;
  EFI_STATUS Status = gBS->LocateHandleBuffer(ByProtocol, &gEfiUsb2HcProtocolGuid, NULL, &Count, &Handles);
  Print(L"USB probe: host lookup %r, count %u\r\n", Status, Count);
  if (!EFI_ERROR(Status) && Handles != NULL) {
    for (UINTN Index = 0; Index < Count && Index < 8; Index++) {
      EFI_PCI_IO_PROTOCOL *Pci = NULL;
      EFI_ACPI_ADDRESS_SPACE_DESCRIPTOR *Bar = NULL;
      VOID *Bus = NULL;
      UINT32 Cap, Hcs, Value;
      UINTN Op, Ports;
      Status = gBS->HandleProtocol(Handles[Index], &UsbBusGuid, &Bus);
      Print(L"USB probe: host %u UsbBus binding: %r\r\n", Index, Status);
      J413LogStatus("USB bus binding", Status);
      Status = gBS->HandleProtocol(Handles[Index], &gEfiPciIoProtocolGuid, (VOID **)&Pci);
      if (EFI_ERROR(Status) || Pci == NULL) {
        Print(L"USB probe: PCI I/O unavailable: %r\r\n", Status); continue;
      }
      Status = Pci->GetBarAttributes(Pci, 0, NULL, (VOID **)&Bar);
      if (EFI_ERROR(Status) || Bar == NULL) {
        Print(L"USB probe: BAR0 unavailable: %r\r\n", Status);
        if (Bar != NULL) FreePool(Bar);
        continue;
      }
      if (Bar->Desc != ACPI_ADDRESS_SPACE_DESCRIPTOR || Bar->Len != sizeof(*Bar) - 3 ||
          Bar->ResType != ACPI_ADDRESS_SPACE_TYPE_MEM || Bar->AddrLen < 0x20) {
        Print(L"USB probe: invalid BAR0 resource; reads skipped\r\n"); FreePool(Bar); continue;
      }
      Print(L"USB probe: BAR0 base %Lx length %Lx\r\n", Bar->AddrRangeMin, Bar->AddrLen);
      if (!J413UsbRead32(Pci, Bar->AddrLen, 0x00, L"CAP", &Cap) || Cap == MAX_UINT32 ||
          (Cap & 0xff) < 0x20 || (Cap & 3) != 0) { FreePool(Bar); continue; }
      Op = Cap & 0xff;
      if (J413UsbRead32(Pci, Bar->AddrLen, 0x04, L"HCSPARAMS1", &Hcs)) {
        Ports = Hcs >> 24;
        for (UINTN Port = 0; Port < Ports && Port < 8; Port++) {
          // Read PORTSC directly. GetRootHubPortStatus acknowledges change bits
          // and can allocate slots in this xHCI driver, so is not a snapshot API.
          if (J413UsbRead32(Pci, Bar->AddrLen, Op + 0x400 + 0x10 * Port, L"PORTSC", &Value))
            Print(L"USB probe: port %u connected=%u enabled=%u speed=%u\r\n", Port + 1,
                  Value & 1, (Value >> 1) & 1, (Value >> 10) & 15);
        }
        if (Ports > 8) Print(L"USB probe: port snapshot limited to 8 of %u\r\n", Ports);
      }
      J413UsbRead32(Pci, Bar->AddrLen, 0x10, L"HCCPARAMS1", &Value);
      J413UsbRead32(Pci, Bar->AddrLen, Op + 0x00, L"USBCMD", &Value);
      J413UsbRead32(Pci, Bar->AddrLen, Op + 0x04, L"USBSTS", &Value);
      J413UsbRead32(Pci, Bar->AddrLen, Op + 0x18, L"CRCR low", &Value);
      J413UsbRead32(Pci, Bar->AddrLen, Op + 0x1c, L"CRCR high", &Value);
      J413UsbRead32(Pci, Bar->AddrLen, DWC3_REG_OFFSET + OFFSET_OF(DWC3_CONTROLLER, GCtl), L"DWC3 GCTL", &Value);
      J413UsbRead32(Pci, Bar->AddrLen, DWC3_REG_OFFSET + OFFSET_OF(DWC3_CONTROLLER, GUsb2PhyCfg), L"DWC3 USB2PHYCFG", &Value);
      J413UsbRead32(Pci, Bar->AddrLen, DWC3_REG_OFFSET + OFFSET_OF(DWC3_CONTROLLER, GUsb3PipeCtl), L"DWC3 USB3PIPECTL", &Value);
      FreePool(Bar);
    }
  }
  if (Handles != NULL) FreePool(Handles);
  J413UsbPhySnapshot();
}

STATIC VOID J413ShowUsbFailure(EFI_STATUS Status)
{
  gST->ConOut->ClearScreen(gST->ConOut);
  Print(L"J413: ARM64 fallback not selected (%r)\r\n", Status);
  J413UsbInventory();
  J413UsbSnapshot();
  J413Checkpoint("USB late failure snapshot", Status);
  Print(L"UEFI BOOT: exact \\EFI\\BOOT\\BOOTAA64.EFI, case-insensitive, ARM64 applications only.\r\n");
  J413PauseFailureScreen();
}
#endif
