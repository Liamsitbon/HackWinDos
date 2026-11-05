from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT = Path(__file__).resolve().parents[1]
class ConnectTraceTests(unittest.TestCase):
    def test_actual_targeted_binding_ignores_unrelated_controllers_and_preserves_errors(self):
        cc=shutil.which('cc')
        if not cc:self.skipTest('C compiler unavailable')
        header=(ROOT/'platforms/j413/mu/Silicon/Apple/AppleSiliconPkg/Drivers/WindowsAutoBootDxe/J413ConnectTrace.h').read_text()
        header=header[header.index('STATIC EFI_STATUS J413ConnectBootUsb'):].rsplit('#endif', 1)[0]
        source=r'''
#include <assert.h>
#include <stdlib.h>
#include <stdint.h>
#include <wchar.h>
#define STATIC static
#define VOID void
#define TRUE 1
#define FALSE 0
#define ByProtocol 1
#define EFI_NOT_FOUND 2
#define EFI_SUCCESS 0
#define EFI_ERROR(x) ((x)!=0)
typedef int EFI_STATUS;typedef size_t UINTN;typedef void *EFI_HANDLE;typedef wchar_t CHAR16;typedef int EFI_GUID;
typedef struct {const EFI_GUID *Type;} NON_DISCOVERABLE_DEVICE;
typedef struct {int value;} EFI_DEVICE_PATH_PROTOCOL;
static EFI_GUID gEdkiiNonDiscoverableDeviceProtocolGuid=1,gEdkiiNonDiscoverableXhciDeviceGuid=2,other_guid=3,gEfiPciRootBridgeIoProtocolGuid=4;
static NON_DISCOVERABLE_DEVICE devices[4];
static int entered,returned,free_count,connect_count,enumeration_fail,protocol_fail,protocol_null,connect_fail,nvme_mode,empty;
static void Print(const wchar_t *s,...){if(wcsstr(s,L"controller %p entered"))entered++;if(wcsstr(s,L"controller returned"))returned++;}
static int CompareGuid(const EFI_GUID *a,const EFI_GUID *b){return *a==*b;}
static EFI_STATUS locate(int type,EFI_GUID *guid,void *key,UINTN *count,EFI_HANDLE **out){
 assert(type==ByProtocol&&!key);if(enumeration_fail)return 7;
 if(nvme_mode){assert(guid==&gEfiPciRootBridgeIoProtocolGuid);*count=empty?0:1;*out=empty?NULL:malloc(sizeof(EFI_HANDLE));if(!empty)(*out)[0]=(void*)3;return 0;}
 assert(guid==&gEdkiiNonDiscoverableDeviceProtocolGuid);
 *count=4;*out=malloc(4*sizeof(EFI_HANDLE));for(int i=0;i<4;i++)(*out)[i]=(void*)(uintptr_t)(i+1);return 0;}
static EFI_STATUS protocol(EFI_HANDLE h,EFI_GUID *guid,void **out){assert(guid==&gEdkiiNonDiscoverableDeviceProtocolGuid);if(protocol_fail)return 7;*out=protocol_null?NULL:&devices[(uintptr_t)h-1];return 0;}
static EFI_STATUS connect(EFI_HANDLE h,void *drivers,void *path,int recursive){assert(h==(void*)3&&!drivers&&!path&&recursive);if(!nvme_mode)assert(entered==returned+1);connect_count++;return connect_fail?7:0;}
static EFI_DEVICE_PATH_PROTOCOL path;
static EFI_DEVICE_PATH_PROTOCOL *DevicePathFromHandle(EFI_HANDLE h){assert(h==(void*)3);return &path;}
static CHAR16 *ConvertDevicePathToText(EFI_DEVICE_PATH_PROTOCOL *p,int display,int shortcuts){assert(p==&path&&!display&&!shortcuts);return calloc(2,sizeof(CHAR16));}
static void FreePool(void *p){assert(p);free_count++;free(p);}
static struct {EFI_STATUS (*LocateHandleBuffer)(int,EFI_GUID*,void*,UINTN*,EFI_HANDLE**);EFI_STATUS (*HandleProtocol)(EFI_HANDLE,EFI_GUID*,void**);EFI_STATUS (*ConnectController)(EFI_HANDLE,void*,void*,int);} bs={locate,protocol,connect};
#define gBS (&bs)
''' + header + r'''
static void reset(void){entered=returned=free_count=connect_count=enumeration_fail=protocol_fail=protocol_null=connect_fail=nvme_mode=empty=0;devices[0].Type=&other_guid;devices[1].Type=NULL;devices[2].Type=&gEdkiiNonDiscoverableXhciDeviceGuid;devices[3].Type=&other_guid;}
int main(void){reset();assert(J413ConnectBootUsb()==0&&entered==1&&returned==1&&connect_count==1&&free_count==2);
 reset();enumeration_fail=1;assert(J413ConnectBootUsb()==7&&!connect_count&&!free_count);
 reset();protocol_fail=1;assert(J413ConnectBootUsb()==EFI_NOT_FOUND&&!connect_count&&free_count==1);
 reset();protocol_null=1;assert(J413ConnectBootUsb()==EFI_NOT_FOUND&&!connect_count&&free_count==1);
 reset();devices[2].Type=&other_guid;assert(J413ConnectBootUsb()==EFI_NOT_FOUND&&!connect_count&&free_count==1);
 reset();connect_fail=1;assert(J413ConnectBootUsb()==7&&entered==1&&returned==1&&free_count==2);
 return 0;}
'''
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'t.c').write_text(source)
            subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(p/'t.c'),'-o',str(p/'t')],check=True)
            subprocess.run([str(p/'t')],check=True)
