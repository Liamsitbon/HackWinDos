from pathlib import Path
import unittest
import test_j413_efi_discovery as discovery
PRELUDE, HEADER, ROOT = discovery.PRELUDE, discovery.HEADER, discovery.ROOT

class BdsSelectorTests(unittest.TestCase):
 run_c=discovery.EfiDiscoveryTests.run_c
 def test_actual_selector_connects_usb_once_and_uses_only_fallback_loader(self):
  src=(ROOT/'mu/Silicon/Apple/AppleSiliconPkg/Drivers/WindowsAutoBootDxe/WindowsAutoBootDxe.c').read_text()
  a=src.index('STATIC EFI_STATUS EFIAPI GetJ413SetupOption(');b=src.index('STATIC J413_WINDOWS_SETUP mSetup',a)
  self.run_c(PRELUDE+HEADER.read_text()+r'''
#define EFIAPI
#define OUT
#define EFI_INVALID_PARAMETER 4
static BOOLEAN mSetupSelected;
static int connects, inventories, nvme_connections;
static int mJ413DirectSetupGuid;
static EFI_STATUS J413ConnectBootNvme(const int *target){assert(target==&mJ413DirectSetupGuid&&!connects);nvme_connections++;return EFI_SUCCESS;}
static void J413UsbInventory(void){assert(connects==1);inventories++;}
static EFI_STATUS J413ConnectBootUsb(void){assert(nvme_connections==1);connects++;return EFI_SUCCESS;}
static EFI_STATUS J413NextDirectSetupOption(EFI_BOOT_MANAGER_LOAD_OPTION *o){return J413NextEfiOption(o);}
static void J413LogStatus(const char *s,int v){(void)s;(void)v;}
static void J413LogCount(const char *s,size_t v){(void)s;(void)v;}
static void J413Checkpoint(const char *s,int v){(void)s;(void)v;}
static int discovery_waits, failure_screens;
static EFI_STATUS J413WaitForBootOption(EFI_BOOT_MANAGER_LOAD_OPTION *o){discovery_waits++;return J413NextEfiOption(o);}
static void J413ShowUsbFailure(EFI_STATUS s){assert(EFI_ERROR(s));failure_screens++;}
static struct {void *ConOut;} table={(void*)1};
#define gST (&table)
static int gJ413UsbDartReadyProtocolGuid;
typedef struct {unsigned ControllerMask;} J413_USB_DART_READY;
static EFI_STATUS locate_protocol(int *guid,void *key,void **out){assert(guid==&gJ413UsbDartReadyProtocolGuid&&!key);*out=NULL;return EFI_NOT_FOUND;}
static struct {EFI_STATUS (*LocateProtocol)(int*,void*,void**);} selector_services={locate_protocol};
#undef gBS
#define gBS (&selector_services)
'''+src[a:b]+r'''
int main(void){EFI_BOOT_MANAGER_LOAD_OPTION o;
 assert(GetJ413SetupOption(NULL)==EFI_INVALID_PARAMETER&&!connects);
 // No BCD, boot.wim, boot.sdi or BlockIo protocol exists in this harness.
 assert(GetJ413SetupOption(&o)==0&&o.Handle==(EFI_HANDLE)1&&connects==1);
 assert(GetJ413SetupOption(&o)==EFI_NOT_FOUND&&connects==1&&scans==1);
 assert(GetJ413SetupOption(&o)==EFI_NOT_FOUND&&connects==1&&scans==1);
 assert(!allocations&&opens==closes&&!other_opens&&inventories==1&&discovery_waits==1&&!failure_screens&&nvme_connections==1);return 0;}
''')
