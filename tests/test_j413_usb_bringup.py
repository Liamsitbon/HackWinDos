"""Execute the patched owning Mu functions with mocked firmware/MMIO services."""
from pathlib import Path
import re
import json
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MU = ROOT / 'mu/Silicon/Apple/AppleSiliconPkg'
PRELUDE = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdarg.h>
#include <stdio.h>
#define STATIC static
#define VOID void
#define IN
#define EFIAPI
#define TRUE 1
#define FALSE 0
#define DEBUG(x) do {} while(0)
#define ASSERT(x) assert(x)
#define BIT(n) (1u<<(n))
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define MAX_UINT64 UINT64_MAX
#define OFFSET_OF(t,m) offsetof(t,m)
#define SIZE_4GB UINT64_C(0x100000000)
#define SIZE_16KB 16384
#define EFI_SUCCESS 0
#define EFI_DEVICE_ERROR UINT64_C(0x8000000000000007)
#define EFI_NOT_FOUND UINT64_C(0x800000000000000e)
#define EFI_TIMEOUT UINT64_C(0x8000000000000012)
#define EFI_ERROR(s) (((s)>>63)!=0)
#define PcdAppleNumDwc3Controllers 0
#define FixedPcdGet32(x) 2
#define PcdGet32(x) 2
#define EFI_NATIVE_INTERFACE 0
#define J413_BOOT_CONTRACT 1
#define AsciiSPrint snprintf
#define AsciiStrCmp strcmp
#define AsciiStrnCmp strncmp
#define MemoryFence() do{}while(0)
#define __asm__(x) do{}while(0)
typedef uint64_t UINT64, UINTN, EFI_STATUS, PHYSICAL_ADDRESS;
typedef uint32_t UINT32; typedef int32_t INT32;
typedef int BOOLEAN; typedef char CHAR8;
typedef void *EFI_HANDLE, *EFI_EVENT, *EFI_SYSTEM_TABLE;
typedef struct {int n;} dt_node_t;
static dt_node_t node;
static int missing, reg_fail, short_reg, overflow_reg, read_count, write_count, busy, delayed, closed, installed;
static UINT32 midr=0x61000000, streams=16;
static char *compatible="dart,t8110"; static size_t compatible_size=11;
static UINT64 resource_base=0x502f00000, resource_size=0x100000;
static UINT64 last_write_address; static UINT32 last_write_value;
static UINTN suppressed_tcr, writes_address[4096]; static UINT32 writes_value[4096];
static dt_node_t *dt_get(const char *n) { return missing || n[strlen(n)-1]=='0' ? NULL : &node; }
static int dt_node_reg(dt_node_t *n,UINT32 index,UINT64 *base,UINT64 *size) {
 assert(n==&node); if(reg_fail)return 1;
 *base=overflow_reg ? UINT64_MAX-1 : resource_base+index*0x80000;
 if(size)*size=short_reg ? 8 : resource_size; return 0;
}
static void *dt_node_prop(dt_node_t *n,const char *prop,size_t *size) { assert(n==&node);(void)prop;*size=compatible_size;return compatible; }
static UINT32 ArmReadMidr(void){return midr;}
static UINT32 MmioRead32(UINTN address) {read_count++;switch(address&0x7ffff) {case 0xc:return streams; case 4:return 1; case 0x80:return busy ? BIT(31):0;case 0x20:return busy ? BIT(2):0;default:for(int i=write_count-1;i>=0;i--)if(writes_address[i]==address)return writes_value[i];return 0;}}
static void MmioWrite32(UINTN address,UINT32 value) {assert(write_count<4096);writes_address[write_count]=address;writes_value[write_count]=(address==suppressed_tcr)?0:value;write_count++;last_write_address=address;last_write_value=value;}
static void MicroSecondDelay(UINTN n){delayed+=(int)n;}
static EFI_STATUS install(EFI_HANDLE *h,void *g,int mode,void *p){(void)h;(void)g;(void)mode;(void)p;installed++;return 0;}
static void close_event(EFI_EVENT e){(void)e;closed++;}
static int gJ413UsbDartReadyProtocolGuid;
typedef struct {UINT32 ControllerMask;} J413_USB_DART_READY;
static J413_USB_DART_READY ready={2}; static int no_ready;
static EFI_STATUS locate(void *guid,void *registration,void **out){(void)guid;(void)registration;*out=no_ready?NULL:&ready;return no_ready?EFI_NOT_FOUND:0;}
static struct { EFI_STATUS (*LocateProtocol)(void*,void*,void**); void (*CloseEvent)(EFI_EVENT); EFI_STATUS (*InstallProtocolInterface)(EFI_HANDLE*,void*,int,void*); } services={locate,close_event,install},*gBS=&services;

'''

def function(source, name):
    # Extract production definitions while retaining bodies byte for byte.
    hit=re.search(r'(?:STATIC\s+)?(?:EFI_STATUS|VOID)\s+(?:EFIAPI\s+)?'+name+r'\s*\(',source)
    if not hit: raise AssertionError(name)
    start=source.index('{',hit.start()); depth=1; end=start+1
    while depth:
        depth += (source[end]=='{')-(source[end]=='}'); end+=1
    return source[hit.start():end]

class J413UsbBringupTests(unittest.TestCase):
    def execute(self, source):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);(path/'test.c').write_text(source)
            subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter','-Wno-misleading-indentation','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(path/'test.c'),'-o',str(path/'test')],check=True)
            subprocess.run([str(path/'test')],check=True,timeout=10)

    def test_dart_command_resource_validation_and_readiness(self):
        source=(MU/'Drivers/AppleDartIoMmuDxe/AppleDartIoMmuDxe.c').read_text()
        header=(MU/'Include/Drivers/AppleDartIoMmuDxe.h').read_text()
        header=re.sub(r'^#include.*$', '', header,flags=re.M)
        actual='\n'.join(function(source,name) for name in ('AppleDartT8020TlbFlush','AppleDartT8110TlbFlush','AppleDartIoMmuDxeInitialize'))
        main=r'''
static void reset(void){read_count=write_count=installed=delayed=0;reg_fail=short_reg=overflow_reg=missing=busy=0;midr=0x61000000;compatible="dart,t8110";compatible_size=11;streams=16;}
int main(void){
 APPLE_DART_INFO d={.BaseAddress=0x502f00000,.Nsid=16};
 assert(AppleDartT8110TlbFlush(&d)==0);
 assert(last_write_address==d.BaseAddress+0x80 && last_write_value==0);
 busy=1; assert(AppleDartT8110TlbFlush(&d)==EFI_TIMEOUT && delayed==100);
 reset(); assert(AppleDartT8020TlbFlush(&d)==0 && last_write_address==d.BaseAddress+0x20 && last_write_value==BIT(20));
 reset(); assert(AppleDartIoMmuDxeInitialize(NULL,NULL)==0 && installed==1 && write_count>0);
 reset(); midr=0x41000000; assert(AppleDartIoMmuDxeInitialize(NULL,NULL)==EFI_NOT_FOUND && !write_count);
 for(int scenario=0;scenario<7;scenario++){
  reset(); switch(scenario){case 0:reg_fail=1;break;case 1:short_reg=1;break;case 2:overflow_reg=1;break;case 3:compatible=NULL;compatible_size=0;break;case 4:compatible="dart,xxxxx";break;case 5:compatible="dart,t8110";compatible_size=10;break;case 6:missing=1;break;}
  assert(AppleDartIoMmuDxeInitialize(NULL,NULL)==EFI_DEVICE_ERROR && !write_count && !installed);
 }
 reset(); streams=0;assert(AppleDartIoMmuDxeInitialize(NULL,NULL)==EFI_DEVICE_ERROR && !write_count && !installed);
 reset(); streams=257;assert(AppleDartIoMmuDxeInitialize(NULL,NULL)==EFI_DEVICE_ERROR && !write_count && !installed);
 reset();busy=1;assert(AppleDartIoMmuDxeInitialize(NULL,NULL)==EFI_TIMEOUT && !installed && delayed==100);
 // A write request is not proof of bypass: first and last stream in each bank.
 for(int bank=0;bank<2;bank++)for(int sid=0;sid<16;sid+=15){
  reset(); suppressed_tcr=resource_base+(UINTN)bank*0x80000+0x1000+4*sid;
  assert(AppleDartIoMmuDxeInitialize(NULL,NULL)==EFI_DEVICE_ERROR && !installed);
 }
 suppressed_tcr=0; reset();assert(AppleDartIoMmuDxeInitialize(NULL,NULL)==0 && installed==1);
}
'''
        readback=MU/'Include/Library/J413UsbDartReadback.h'
        self.execute(PRELUDE+header+'\nAPPLE_DART_INFO DartInfo[4];\n'+(readback.read_text() if readback.exists() else '')+actual+main)

    def test_usb_never_registers_failed_initialization_as_callback(self):
        source=(MU/'Drivers/AppleUsbTypeCBringupDxe/AppleUsbTypeCBringupDxe.c').read_text()
        actual=function(source,'AppleUsbTypeCBringupDxeInitializeUsbController')+'\n'+function(source,'AppleUsbTypeCBringupDxeBringupCallback')
        support=r'''
#define NonDiscoverableDeviceTypeXhci 1
#define NonDiscoverableDeviceDmaTypeCoherent 1
static int init_count, register_count, fail_init;

static int setup_count;
static EFI_STATUS Dwc3XhciCoreInit(DWC3_CONTROLLER *c){assert((UINTN)c==resource_base+DWC3_REG_OFFSET);init_count++;return fail_init?EFI_DEVICE_ERROR:0;}
static void Dwc3AppleSetupCio(UINTN base){assert(base==resource_base);setup_count++;}
static void Dwc3SetMode(DWC3_CONTROLLER *c,UINT32 mode){(void)c;(void)mode;}
static void Dwc3SetFladj(DWC3_CONTROLLER *c,UINT32 value){(void)c;(void)value;}
static void Dwc3XhciSetBeatBurstLength(DWC3_CONTROLLER *c){(void)c;}
static EFI_STATUS RegisterNonDiscoverableMmioDevice(int type,int dma,EFI_STATUS (*cb)(void*),void *handle,UINTN count,...){assert(type==1 && dma==1 && cb==NULL && handle==NULL && count==1);va_list args;va_start(args,count);assert(va_arg(args,UINTN)==resource_base);assert(va_arg(args,UINTN)==resource_size);va_end(args);register_count++;return 0;}
'''
        main=r'''
int main(void){
 resource_base=CAPTURED_USB_BASE;resource_size=CAPTURED_USB_SIZE;
 AppleUsbTypeCBringupDxeBringupCallback(NULL,NULL); assert(init_count==1 && register_count==1 && closed==1 && setup_count==1);
 init_count=register_count=setup_count=read_count=write_count=0;fail_init=1;AppleUsbTypeCBringupDxeBringupCallback(NULL,NULL);assert(init_count==1 && !register_count && !setup_count && !read_count && !write_count);
 fail_init=0;init_count=0;
 resource_size=APPLE_DWC3_CIO_LINK_TIMER+sizeof(UINT32)-1;AppleUsbTypeCBringupDxeBringupCallback(NULL,NULL);assert(!init_count && !register_count);
 resource_size=DWC3_REG_OFFSET+OFFSET_OF(DWC3_CONTROLLER,GFLAdj)+sizeof(UINT32)-1;AppleUsbTypeCBringupDxeBringupCallback(NULL,NULL);assert(!init_count && !register_count);
 resource_size=CAPTURED_USB_SIZE;resource_base=(UINT64_MAX-resource_size+8)&~UINT64_C(7);AppleUsbTypeCBringupDxeBringupCallback(NULL,NULL);assert(!init_count && !register_count);
 resource_base=CAPTURED_USB_BASE+1;AppleUsbTypeCBringupDxeBringupCallback(NULL,NULL);assert(!init_count && !register_count);
 resource_base=(UINT64_MAX-resource_size)&~UINT64_C(7);AppleUsbTypeCBringupDxeBringupCallback(NULL,NULL);assert(init_count==1 && register_count==1);
 init_count=register_count=setup_count=read_count=write_count=0;resource_base=CAPTURED_USB_BASE;
 reg_fail=1;AppleUsbTypeCBringupDxeBringupCallback(NULL,NULL);assert(!init_count && !register_count);
 reg_fail=0;short_reg=1;AppleUsbTypeCBringupDxeBringupCallback(NULL,NULL);assert(!init_count && !register_count);
 short_reg=0;overflow_reg=1;AppleUsbTypeCBringupDxeBringupCallback(NULL,NULL);assert(!init_count && !register_count);
 overflow_reg=0;no_ready=1;AppleUsbTypeCBringupDxeBringupCallback(NULL,NULL);assert(!init_count && !register_count);
 no_ready=0;ready.ControllerMask=0;AppleUsbTypeCBringupDxeBringupCallback(NULL,NULL);assert(!init_count && !register_count);
}
'''
        header=(MU/'Include/Drivers/AppleUsbTypeCBringupDxe.h').read_text()
        header=re.sub(r'^#include.*$', '', header,flags=re.M)
        captured=json.loads((ROOT/'investigation/j413-macos-resources.json').read_text())
        base,size=captured['nodes']['usb-drd1']['physical_reg_pairs'][0]
        fixture=f'\n#define CAPTURED_USB_BASE UINT64_C({base})\n#define CAPTURED_USB_SIZE UINT64_C({size})\n'
        self.execute(PRELUDE+header+fixture+support+actual+main)

    def test_actual_core_accepts_both_known_ids_without_cross_family_erratum(self):
        source=(MU/'Drivers/AppleUsbTypeCBringupDxe/AppleUsbTypeCBringupDxe.c').read_text()
        header=(MU/'Include/Drivers/AppleUsbTypeCBringupDxe.h').read_text()
        header='\n'.join(line for line in header.splitlines() if not line.startswith('#include'))
        prelude=r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#define STATIC static
#define IN
#define TRUE 1
#define FALSE 0
#define DEBUG(x) do{}while(0)
#define BIT0 1u
#define BIT3 8u
#define BIT7 128u
#define BIT11 2048u
#define BIT16 65536u
#define BIT31 0x80000000u
#define EFI_SUCCESS 0
#define EFI_NOT_FOUND 1
typedef uint32_t UINT32;typedef uint64_t UINT64;typedef uintptr_t UINTN;typedef int EFI_STATUS;typedef void VOID;
''' + header + r'''
static int resets,writes;
static void Dwc3ControllerSoftReset(DWC3_CONTROLLER *c){(void)c;resets++;}
static UINT32 MmioRead32(UINTN address){return *(UINT32*)address;}
static void MmioWrite32(UINTN address,UINT32 value){*(UINT32*)address=value;writes++;}
'''
        main=r'''
int main(void){DWC3_CONTROLLER c;
 const UINT32 identities[]={DWC3_SYNOPSYS_ID|0x180a,DWC3_SYNOPSYS_ID|0x290a,DWC3_SYNOPSYS_ALT_ID};
 for(int i=0;i<3;i++){memset(&c,0,sizeof(c));c.GSnpsId=identities[i];resets=writes=0;assert(Dwc3XhciCoreInit(&c)==EFI_SUCCESS&&resets==1&&writes==1);assert(((c.GCtl&DWC3_GCTL_U2RSTECN)!=0)==(i==0));}
 const UINT32 invalid[]={0,0xffffffffu,0x12340000};
 for(int i=0;i<3;i++){memset(&c,0,sizeof(c));c.GSnpsId=invalid[i];resets=writes=0;assert(Dwc3XhciCoreInit(&c)==EFI_NOT_FOUND&&!resets&&!writes);}
 return 0;}
'''
        self.execute(prelude+function(source,'Dwc3XhciCoreInit')+main)
