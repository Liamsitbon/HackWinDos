"""Execute failure capture with bounded PCI reads and guarded ADT PHY reads."""
from pathlib import Path
import re
import unittest
import test_j413_efi_discovery as discovery

ROOT = Path(__file__).resolve().parents[1]


class UsbProbeTests(unittest.TestCase):
    run_c = discovery.EfiDiscoveryTests.run_c

    def test_read_only_capture_bounds_missing_resources_and_cleanup(self):
        header = (ROOT/'platforms/j413/mu/Silicon/Apple/AppleSiliconPkg/Drivers/WindowsAutoBootDxe/J413UsbProbe.h').read_text()
        # Use the owner's actual struct offsets, not a second invented register map.
        dwc = (ROOT/'mu/Silicon/Apple/AppleSiliconPkg/Include/Drivers/AppleUsbTypeCBringupDxe.h').read_text()
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#define STATIC static
#define VOID void
#define CONST const
#define TRUE 1
#define FALSE 0
#define EFI_ERROR(s) ((s)!=0)
#define ByProtocol 0
#define MAX_UINT32 UINT32_MAX
#define MAX_UINT64 UINT64_MAX
#define OFFSET_OF(t,m) offsetof(t,m)
#define ACPI_ADDRESS_SPACE_DESCRIPTOR 0x8a
#define ACPI_ADDRESS_SPACE_TYPE_MEM 0
#define EfiPciIoWidthUint32 2
typedef uint8_t UINT8;typedef uint16_t UINT16;typedef uint32_t UINT32;typedef uint64_t UINT64;
typedef size_t UINTN;typedef int BOOLEAN,EFI_STATUS;typedef char CHAR8;typedef wchar_t CHAR16;
typedef void *EFI_HANDLE;
typedef struct {UINT32 a;UINT16 b,c;UINT8 d[8];} EFI_GUID;
typedef struct {UINT8 Desc;UINT16 Len;UINT8 ResType;UINT64 AddrRangeMin,AddrLen;} EFI_ACPI_ADDRESS_SPACE_DESCRIPTOR;
typedef struct {unsigned ControllerMask;} J413_USB_DART_READY;
typedef struct {} dt_node_t;
typedef struct PCI EFI_PCI_IO_PROTOCOL;
struct PCI {struct {EFI_STATUS (*Read)(EFI_PCI_IO_PROTOCOL*,int,int,UINT64,UINTN,VOID*);} Mem;EFI_STATUS (*GetBarAttributes)(EFI_PCI_IO_PROTOCOL*,int,UINT64*,VOID**);};
static int allocations,reads,phy_reads,mode,phy_mode,cleared,paused,inventories,checkpoints;
static UINT64 bar_len=0x11800;
static int gEfiUsb2HcProtocolGuid,gEfiPciIoProtocolGuid,gJ413UsbDartReadyProtocolGuid;
static void *AllocatePool(size_t n){void *p=malloc(n);assert(p);allocations++;return p;}
static void FreePool(void *p){assert(p);allocations--;free(p);}
static int Print(const CHAR16 *s,...){assert(s);return 0;}
static int AsciiSPrint(CHAR8 *s,UINTN size,const CHAR8 *fmt,...){assert(size>2&&fmt);s[0]='x';s[1]=0;return 1;}
static void J413LogCount(const CHAR8 *s,UINTN n){assert(s&&*s);(void)n;}
static void J413LogStatus(const CHAR8 *s,EFI_STATUS n){assert(s&&*s);(void)n;}
static void J413Checkpoint(const CHAR8 *s,EFI_STATUS n){assert(s&&n);checkpoints++;}
static void J413UsbInventory(void){inventories++;}
static void J413PauseFailureScreen(void){paused++;}
static void clear_screen(void *self){assert(self);cleared++;}
static struct CONSOLE {void (*ClearScreen)(void*);} con={clear_screen};
static struct {struct CONSOLE *ConOut;} table={&con};
#define gST (&table)
static dt_node_t node;
static dt_node_t *dt_get(const char *name){assert(!strcmp(name,"atc-phy1"));return phy_mode==1?NULL:&node;}
static int dt_node_reg(dt_node_t *n,UINT32 i,uint64_t *base,uint64_t *size){assert(n==&node&&!i);*base=phy_mode==4?UINT64_MAX-3:0x502a90000ULL;*size=phy_mode==3?0x1c:0x4000;return phy_mode==2;}
static UINT32 MmioRead32(UINTN addr){assert(addr==0x502a90000ULL||addr==0x502a90004ULL||addr==0x502a90008ULL||addr==0x502a9001cULL);phy_reads++;return 0x1c1700f;}
static EFI_STATUS read_mem(EFI_PCI_IO_PROTOCOL *p,int width,int bar,UINT64 off,UINTN count,VOID *out){
 assert(p&&width==2&&!bar&&count==1&&!(off&3)&&off<=bar_len-4);reads++;
 *(UINT32*)out=off==0?(mode==6?UINT32_MAX:0x40):off==4?2U<<24:0x203;
 return mode==5?7:0;
}
static EFI_STATUS get_bar(EFI_PCI_IO_PROTOCOL *p,int bar,UINT64 *supports,VOID **out){assert(p&&!bar&&!supports);EFI_ACPI_ADDRESS_SPACE_DESCRIPTOR *d=AllocatePool(sizeof(*d));memset(d,0,sizeof(*d));d->Desc=0x8a;d->Len=sizeof(*d)-3;d->ResType=mode==3?1:0;d->AddrLen=bar_len;d->AddrRangeMin=0x502280000ULL;*out=d;return 0;}
static EFI_PCI_IO_PROTOCOL pci={{read_mem},get_bar};
static EFI_STATUS locate(int by,int *guid,VOID *reg,UINTN *count,EFI_HANDLE **out){assert(!by&&guid==&gEfiUsb2HcProtocolGuid&&!reg);*out=NULL;*count=0;if(mode==1)return 14;*count=1;*out=AllocatePool(sizeof(EFI_HANDLE));**out=(void*)1;return 0;}
static EFI_STATUS protocol(EFI_HANDLE h,VOID *guid,VOID **out){assert(h==(void*)1);*out=NULL;if(guid==&gEfiPciIoProtocolGuid){if(mode==2)return 14;*out=&pci;return 0;}assert(((EFI_GUID*)guid)->a==0x240612b7);*out=(void*)2;return 0;}
static J413_USB_DART_READY ready={2};
static EFI_STATUS locate_protocol(int *guid,VOID *reg,VOID **out){assert(guid==&gJ413UsbDartReadyProtocolGuid&&!reg);*out=phy_mode==5?NULL:&ready;return phy_mode==5?14:0;}
static struct {EFI_STATUS (*LocateHandleBuffer)(int,int*,VOID*,UINTN*,EFI_HANDLE**);EFI_STATUS (*HandleProtocol)(EFI_HANDLE,VOID*,VOID**);EFI_STATUS (*LocateProtocol)(int*,VOID*,VOID**);} services={locate,protocol,locate_protocol};
#define gBS (&services)
'''
        code += re.sub(r'^#include[^\n]*$', '', dwc, flags=re.M)
        code += re.sub(r'^#include[^\n]*$', '', header, flags=re.M)
        code += r'''
static void reset(void){assert(!allocations);reads=phy_reads=mode=phy_mode=0;bar_len=0x11800;}
int main(void){UINT32 v;
 reset();J413UsbSnapshot();assert(reads==12&&phy_reads==4&&!allocations);
 assert(DWC3_REG_OFFSET+OFFSET_OF(DWC3_CONTROLLER,GCtl)==0xc110);
 assert(DWC3_REG_OFFSET+OFFSET_OF(DWC3_CONTROLLER,GUsb2PhyCfg)==0xc200);
 assert(DWC3_REG_OFFSET+OFFSET_OF(DWC3_CONTROLLER,GUsb3PipeCtl)==0xc2c0);
 for(int m=1;m<=3;m++){reset();mode=m;J413UsbSnapshot();assert(!reads&&!allocations);}
 reset();bar_len=0x24;J413UsbSnapshot();assert(reads==3&&!allocations);
 for(int m=5;m<=6;m++){reset();mode=m;J413UsbSnapshot();assert(reads==1&&!allocations);}
 for(int m=1;m<=5;m++){reset();phy_mode=m;J413UsbSnapshot();assert(!phy_reads&&!allocations);}
 reset();assert(!J413UsbRead32(&pci,2,0,L"short",&v)&&!reads);
 assert(!J413UsbRead32(&pci,0x100,3,L"unaligned",&v)&&!reads);
 assert(!J413UsbRead32(&pci,0x100,0x100,L"outside",&v)&&!reads);
 J413ShowUsbFailure(14);assert(cleared==1&&paused==1&&inventories==1&&checkpoints==1&&!allocations);
 return 0;}
'''
        self.run_c(code)
