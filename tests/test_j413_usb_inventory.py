"""Execute USB boundary reporting without hardware access or extra binding."""
from pathlib import Path
import unittest
import test_j413_efi_discovery as discovery
ROOT = Path(__file__).resolve().parents[1]
class UsbInventoryTests(unittest.TestCase):
    run_c = discovery.EfiDiscoveryTests.run_c

    def test_actual_inventory_reports_status_paths_and_cleans_all_allocations(self):
        header=(ROOT/'platforms/j413/mu/Silicon/Apple/AppleSiliconPkg/Drivers/WindowsAutoBootDxe/J413UsbInventory.h').read_text()
        header='\n'.join(line for line in header.splitlines() if not line.startswith('#include'))
        self.run_c(r'''
#include <assert.h>
#include <stdlib.h>
#include <stdarg.h>
#include <wchar.h>
#define STATIC static
#define VOID void
#define CONST const
#define FALSE 0
#define ByProtocol 1
#define EFI_ERROR(s) ((s)!=0)
typedef int EFI_STATUS,EFI_GUID;typedef size_t UINTN;typedef wchar_t CHAR16;typedef void *EFI_HANDLE;
typedef struct {int unused;} EFI_DEVICE_PATH_PROTOCOL;
static EFI_GUID gEfiUsb2HcProtocolGuid=0,gEfiUsbIoProtocolGuid=1,gEfiBlockIoProtocolGuid=2,gEfiSimpleFileSystemProtocolGuid=3;
static int calls,allocations,lookups,paths,mode;
static EFI_DEVICE_PATH_PROTOCOL path;
static void FreePool(void *p){assert(p);allocations--;free(p);}
static EFI_STATUS locate(int type,EFI_GUID *guid,void *key,UINTN *count,EFI_HANDLE **out){
 assert(type==ByProtocol&&!key&&*guid==calls++);*out=NULL;*count=0;
 if(mode==1)return 14;
 *out=malloc(sizeof(void*));allocations++;(*out)[0]=(void*)1;*count=1;
 return mode==2?7:0; // Even an error with an allocated buffer must free it.
}
static EFI_DEVICE_PATH_PROTOCOL *DevicePathFromHandle(EFI_HANDLE h){assert(h==(void*)1);return mode==3?NULL:&path;}
static CHAR16 *ConvertDevicePathToText(EFI_DEVICE_PATH_PROTOCOL *p,int display,int shortcuts){
 assert(p==&path&&!display&&!shortcuts);if(mode==4)return NULL;
 CHAR16 *s=calloc(4,sizeof(*s));allocations++;return s;
}
static void Print(const CHAR16 *s,...){
 if(wcsstr(s,L"lookup:"))lookups++;
 if(wcsstr(s,L"handle %p path"))paths++;
}
static struct {EFI_STATUS (*LocateHandleBuffer)(int,EFI_GUID*,void*,UINTN*,EFI_HANDLE**);} bs={locate};
#define gBS (&bs)
''' + header + r'''
int main(void){for(mode=0;mode<5;mode++){
 calls=lookups=paths=0;J413UsbInventory();assert(calls==4&&lookups==4&&!allocations);
 assert(paths==((mode==1||mode==2)?0:4));}return 0;}
''')
