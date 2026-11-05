"""Execute the real binding policy: recursive root attachment is forbidden."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEADERS = ROOT/'platforms/j413/mu/Silicon/Apple/AppleSiliconPkg/Drivers/WindowsAutoBootDxe'


class NvmeConnectTests(unittest.TestCase):
    def test_actual_staged_binding_mounts_only_unique_target_and_stops_on_errors(self):
        cc = shutil.which('cc')
        if not cc:
            self.skipTest('C compiler unavailable')
        partition = (HEADERS/'J413SetupPartition.h').read_text()
        connect = (HEADERS/'J413ConnectTrace.h').read_text()
        connect = connect[:connect.index('STATIC EFI_STATUS J413ConnectBootUsb')]
        # USB helper is tested independently, outside this storage policy.
        source = r'''
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#define STATIC static
#define CONST const
#define VOID void
#define BOOLEAN int
#define TRUE 1
#define FALSE 0
#define ByProtocol 1
#define EFI_SUCCESS 0
#define EFI_NOT_FOUND 1
#define EFI_ACCESS_DENIED 2
#define EFI_INVALID_PARAMETER 3
#define EFI_NOT_READY 4
#define EFI_ALREADY_STARTED 5
#define EFI_DEVICE_ERROR 6
#define EFI_ERROR(s) ((s)!=0)
#define EFI_PARTITION_INFO_PROTOCOL_REVISION 0x1000
#define PARTITION_TYPE_GPT 2
#define END_DEVICE_PATH_LENGTH 4
#define EfiPciIoWidthUint8 0
typedef unsigned char UINT8;
typedef size_t UINTN;
typedef int EFI_STATUS;
typedef void *EFI_HANDLE;
typedef wchar_t CHAR16;
typedef struct {uint32_t Data1;uint16_t Data2,Data3;UINT8 Data4[8];} EFI_GUID;
typedef struct {unsigned Revision,Type;struct {struct {EFI_GUID UniquePartitionGUID;} Gpt;} Info;} EFI_PARTITION_INFO_PROTOCOL;
typedef struct {int ready;} EFI_SIMPLE_FILE_SYSTEM_PROTOCOL;
typedef struct {int MediaPresent,LogicalPartition;} MEDIA;
typedef struct {MEDIA *Media;} EFI_BLOCK_IO_PROTOCOL;
typedef struct PCI EFI_PCI_IO_PROTOCOL;
struct PCI {struct {EFI_STATUS (*Read)(EFI_PCI_IO_PROTOCOL*,int,unsigned,UINTN,void*);} Pci;
 EFI_STATUS (*GetLocation)(EFI_PCI_IO_PROTOCOL*,UINTN*,UINTN*,UINTN*,UINTN*);int id;};
typedef struct {UINT8 bytes[24];UINTN size;} EFI_DEVICE_PATH_PROTOCOL;
static EFI_GUID gEfiPartitionInfoProtocolGuid={1},gEfiPciRootBridgeIoProtocolGuid={2},
 gEfiPciIoProtocolGuid={3},gEfiBlockIoProtocolGuid={4},gEfiSimpleFileSystemProtocolGuid={5},target={88};
enum { ROOT_HANDLE=1,PCI_HANDLE=2,NAMESPACE_HANDLE=3,TARGET_HANDLE=4,OTHER_PARTITION=5,
 OTHER_PCI=6,OTHER_BLOCK=7,SECOND_NAMESPACE=8 };
#define H(n) ((EFI_HANDLE)(uintptr_t)(n))
static EFI_PARTITION_INFO_PROTOCOL partitions[2];
static EFI_SIMPLE_FILE_SYSTEM_PROTOCOL fs;
static MEDIA whole={1,0},partition_media={1,1};
static EFI_BLOCK_IO_PROTOCOL blocks[4]={{&whole},{&partition_media},{&whole},{&whole}};
static EFI_DEVICE_PATH_PROTOCOL paths[9];
static EFI_PCI_IO_PROTOCOL pci[2];
static int step,existing,fs_ready,duplicate,extra_root,missing_pci,bad_class,pci_read_error,
 missing_namespace,extra_namespace,fail_level,enumeration_error,connections,allocations,
 entered,returned,fs_queries,unrelated_queries;
static void *alloc(UINTN size){void *p=calloc(1,size);assert(p);allocations++;return p;}
static void FreePool(void *p){assert(p);allocations--;free(p);}
static int CompareGuid(const EFI_GUID*a,const EFI_GUID*b){return !memcmp(a,b,sizeof(*a));}
#define CopyMem memcpy
#define CompareMem memcmp
static void Print(const wchar_t *fmt,...){
 if(wcsstr(fmt,L"%s entered"))entered++;
 if(wcsstr(fmt,L"%s returned"))returned++;
}
static EFI_DEVICE_PATH_PROTOCOL *DevicePathFromHandle(EFI_HANDLE h){return &paths[(uintptr_t)h];}
static UINTN GetDevicePathSize(EFI_DEVICE_PATH_PROTOCOL *p){return p->size;}
static CHAR16 *ConvertDevicePathToText(EFI_DEVICE_PATH_PROTOCOL*p,int display,int shortcut){
 assert(p&&!display&&!shortcut);return alloc(2*sizeof(CHAR16));
}
static EFI_STATUS locate(int by,EFI_GUID *guid,void *key,UINTN *count,EFI_HANDLE **out){
 assert(by==ByProtocol&&!key);*out=NULL;*count=0;
 if(enumeration_error)return EFI_DEVICE_ERROR;
 if(guid==&gEfiPartitionInfoProtocolGuid){
  if(!existing&&step<3)return EFI_NOT_FOUND;
  *count=2;*out=alloc(2*sizeof(EFI_HANDLE));(*out)[0]=H(TARGET_HANDLE);(*out)[1]=H(OTHER_PARTITION);return 0;
 }
 if(guid==&gEfiPciRootBridgeIoProtocolGuid){
  *count=extra_root?2:1;*out=alloc(*count*sizeof(EFI_HANDLE));(*out)[0]=H(ROOT_HANDLE);return 0;
 }
 if(guid==&gEfiPciIoProtocolGuid){
  *count=2;*out=alloc(2*sizeof(EFI_HANDLE));(*out)[0]=H(OTHER_PCI);(*out)[1]=H(PCI_HANDLE);return 0;
 }
 assert(guid==&gEfiBlockIoProtocolGuid);
 *count=extra_namespace?4:3;*out=alloc(*count*sizeof(EFI_HANDLE));
 (*out)[0]=H(OTHER_BLOCK);(*out)[1]=H(OTHER_PARTITION);
 (*out)[2]=H(NAMESPACE_HANDLE);if(extra_namespace)(*out)[3]=H(SECOND_NAMESPACE);return 0;
}
static EFI_STATUS protocol(EFI_HANDLE h,EFI_GUID *guid,void **out){
 *out=NULL;
 if(guid==&gEfiPartitionInfoProtocolGuid){assert(h==H(TARGET_HANDLE)||h==H(OTHER_PARTITION));
  *out=&partitions[h==H(TARGET_HANDLE)?0:1];return 0;}
 if(guid==&gEfiSimpleFileSystemProtocolGuid){assert(h==H(TARGET_HANDLE));fs_queries++;
  if(fs_ready){*out=&fs;return 0;}return EFI_NOT_FOUND;}
 if(guid==&gEfiPciIoProtocolGuid){assert(h==H(PCI_HANDLE)||h==H(OTHER_PCI));
  if(missing_pci&&h==H(PCI_HANDLE))return EFI_NOT_FOUND;
  *out=&pci[h==H(PCI_HANDLE)?0:1];return 0;}
 assert(guid==&gEfiBlockIoProtocolGuid);
 if(h==H(OTHER_BLOCK))unrelated_queries++;
 if(missing_namespace&&h==H(NAMESPACE_HANDLE))return EFI_NOT_FOUND;
 *out=&blocks[h==H(NAMESPACE_HANDLE)?0:h==H(OTHER_PARTITION)?1:h==H(SECOND_NAMESPACE)?3:2];return 0;
}
static EFI_STATUS location(EFI_PCI_IO_PROTOCOL*p,UINTN*s,UINTN*b,UINTN*d,UINTN*f){
 *s=*b=*f=0;*d=(UINTN)p->id;return 0;
}
static EFI_STATUS read_class(EFI_PCI_IO_PROTOCOL*p,int width,unsigned offset,UINTN count,void*out){
 assert(p==&pci[0]&&width==EfiPciIoWidthUint8&&offset==9&&count==3);
 if(pci_read_error)return EFI_DEVICE_ERROR;
 UINT8 c[]={2,8,1};if(bad_class)c[0]=0;memcpy(out,c,3);return 0;
}
static EFI_STATUS connect_controller(EFI_HANDLE h,void*drivers,void*remaining,int recursive){
 assert(!drivers&&!remaining&&!recursive); // Old recursive-root code fails here.
 assert(entered==returned+1);connections++;
 int level=h==H(ROOT_HANDLE)?1:h==H(PCI_HANDLE)?2:h==H(NAMESPACE_HANDLE)?3:h==H(TARGET_HANDLE)?4:0;
 assert(level);if(fail_level==level)return EFI_DEVICE_ERROR;
 if(level==4)fs_ready=1;else {assert(level==step+1);step=level;}
 return 0;
}
static struct {EFI_STATUS(*LocateHandleBuffer)(int,EFI_GUID*,void*,UINTN*,EFI_HANDLE**);
 EFI_STATUS(*HandleProtocol)(EFI_HANDLE,EFI_GUID*,void**);
 EFI_STATUS(*ConnectController)(EFI_HANDLE,void*,void*,int);} services={locate,protocol,connect_controller};
#define gBS (&services)
''' + re.sub(r'^#include[^\n]*$', '', partition+connect, flags=re.M) + r'''
#endif
static void reset(void){
 assert(!allocations);step=existing=fs_ready=duplicate=extra_root=missing_pci=bad_class=pci_read_error=
 missing_namespace=extra_namespace=fail_level=enumeration_error=connections=entered=returned=fs_queries=unrelated_queries=0;
 memset(partitions,0,sizeof(partitions));for(int i=0;i<2;i++){partitions[i].Revision=0x1000;partitions[i].Type=2;}
 partitions[0].Info.Gpt.UniquePartitionGUID=target;partitions[1].Info.Gpt.UniquePartitionGUID.Data1=99;
 pci[0]=(EFI_PCI_IO_PROTOCOL){{read_class},location,0};pci[1]=(EFI_PCI_IO_PROTOCOL){{read_class},location,1};
 memset(paths,0,sizeof(paths));for(int i=0;i<9;i++)paths[i].size=8;
 paths[PCI_HANDLE].bytes[0]=42;
 paths[NAMESPACE_HANDLE].bytes[0]=paths[OTHER_PARTITION].bytes[0]=paths[SECOND_NAMESPACE].bytes[0]=42;
 paths[NAMESPACE_HANDLE].size=paths[OTHER_PARTITION].size=paths[SECOND_NAMESPACE].size=12;
 paths[OTHER_BLOCK].bytes[0]=99;paths[OTHER_BLOCK].size=12;
}
int main(void){EFI_GUID zero={0};
 reset();assert(J413ConnectBootNvme(NULL)==EFI_INVALID_PARAMETER&&!connections);
 assert(J413ConnectBootNvme(&zero)==EFI_NOT_READY&&!connections);
 reset();assert(J413ConnectBootNvme(&target)==0&&connections==4&&entered==returned&&fs_ready&&!unrelated_queries&&!allocations);
 reset();existing=fs_ready=1;assert(J413ConnectBootNvme(&target)==0&&!connections&&!allocations);
 reset();existing=1;assert(J413ConnectBootNvme(&target)==0&&connections==1&&!step&&!allocations);
 reset();existing=1;partitions[1].Info.Gpt.UniquePartitionGUID=target;
 assert(J413ConnectBootNvme(&target)==EFI_ACCESS_DENIED&&!connections&&!fs_queries&&!allocations);
 reset();extra_root=1;assert(J413ConnectBootNvme(&target)==EFI_ACCESS_DENIED&&!connections&&!allocations);
 reset();missing_pci=1;assert(J413ConnectBootNvme(&target)==EFI_NOT_FOUND&&connections==1&&!allocations);
 reset();bad_class=1;assert(J413ConnectBootNvme(&target)==EFI_NOT_FOUND&&connections==1&&!allocations);
 reset();pci_read_error=1;assert(J413ConnectBootNvme(&target)==EFI_NOT_FOUND&&connections==1&&!allocations);
 reset();missing_namespace=1;assert(J413ConnectBootNvme(&target)==EFI_NOT_FOUND&&connections==2&&!allocations);
 reset();extra_namespace=1;assert(J413ConnectBootNvme(&target)==EFI_ACCESS_DENIED&&connections==2&&!allocations);
 for(int i=1;i<=4;i++){reset();fail_level=i;assert(J413ConnectBootNvme(&target)==EFI_DEVICE_ERROR&&connections==i&&entered==returned&&!allocations);}
 reset();enumeration_error=1;assert(J413ConnectBootNvme(&target)==EFI_DEVICE_ERROR&&!connections&&!allocations);
 return 0;}
'''
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p/'t.c').write_text(source)
            subprocess.run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-Wno-missing-field-initializers', '-fsanitize=address,undefined',
                            '-fno-sanitize-recover=all', str(p/'t.c'), '-o', str(p/'t')], check=True)
            subprocess.run([str(p/'t')], check=True)
