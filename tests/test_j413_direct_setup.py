"""Execute fixed-GPT selection: no unrelated filesystem or EFI is opened."""
from pathlib import Path
import re
import unittest
import test_j413_efi_discovery as discovery

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT/'platforms/j413/mu/Silicon/Apple/AppleSiliconPkg/Drivers/WindowsAutoBootDxe/J413DirectSetup.h'


class DirectSetupTests(unittest.TestCase):
    run_c = discovery.EfiDiscoveryTests.run_c

    def test_exact_partition_case_architecture_ambiguity_and_error_cleanup(self):
        self.run_c(discovery.PRELUDE + r'''
#define J413_DIRECT_SETUP_ONLY
#if defined(__clang__)
#pragma clang diagnostic error "-Wunused-function"
#elif defined(__GNUC__)
#pragma GCC diagnostic error "-Wunused-function"
#endif
''' + discovery.HEADER.read_text() + r'''
#define EFI_INVALID_PARAMETER 4
#define EFI_NOT_READY 5
#define EFI_ACCESS_DENIED 6
#define EFI_PARTITION_INFO_PROTOCOL_REVISION 0x1000
#define PARTITION_TYPE_GPT 2
typedef struct {UINT32 Data1;UINT16 Data2,Data3;UINT8 Data4[8];} EFI_GUID;
typedef struct {UINT32 Revision,Type;struct {struct {EFI_GUID UniquePartitionGUID;} Gpt;} Info;} EFI_PARTITION_INFO_PROTOCOL;
static EFI_GUID target={1,0,0,{0}};
static int gEfiPartitionInfoProtocolGuid, mode, fs_accesses, identities;
static int CompareGuid(const EFI_GUID *a,const EFI_GUID *b){return !memcmp(a,b,sizeof(*a));}
static EFI_PARTITION_INFO_PROTOCOL partitions[3];
static EFI_STATUS partition_locate(int by,int *guid,VOID *reg,UINTN *count,EFI_HANDLE **out){
 assert(!by&&guid==&gEfiPartitionInfoProtocolGuid&&!reg);
 *count=3;*out=AllocatePool(3*sizeof(EFI_HANDLE));for(int i=0;i<3;i++)(*out)[i]=(void*)(uintptr_t)(i+1);return 0;
}
static EFI_STATUS partition_protocol(EFI_HANDLE handle,int *guid,VOID **out){
 if(guid==&gEfiPartitionInfoProtocolGuid){identities++;*out=&partitions[(uintptr_t)handle-1];return 0;}
 assert(guid==&gEfiSimpleFileSystemProtocolGuid&&handle==(void*)2);fs_accesses++;
 if(mode==1){*out=NULL;return EFI_NOT_FOUND;}*out=&filesystems[0];return 0;
}
static struct {EFI_STATUS (*LocateHandleBuffer)(int,int*,VOID*,UINTN*,EFI_HANDLE**);EFI_STATUS (*HandleProtocol)(EFI_HANDLE,int*,VOID**);} direct_services={partition_locate,partition_protocol};
#undef gBS
#define gBS (&direct_services)
''' + re.sub(r'^#include[^\n]*$', '', HEADER.read_text(), flags=re.M) + r'''
static void reset(void){assert(!allocations);mEfiScanned=mode=fs_accesses=identities=0;path_fail=init_fail=0;
 for(int i=0;i<3;i++){memset(&partitions[i],0,sizeof(partitions[i]));partitions[i].Revision=0x1000;partitions[i].Type=2;partitions[i].Info.Gpt.UniquePartitionGUID.Data1=(UINT32)(i+10);}
 partitions[1].Info.Gpt.UniquePartitionGUID=target;first[0].name=L"EFI";efi[0].name=L"BOOT";boot[0].name=L"BOOTAA64.EFI";boot[0].kind=0;}
int main(void){EFI_BOOT_MANAGER_LOAD_OPTION o;EFI_GUID zero={0};(void)services;
 reset();assert(J413DirectSetupOption(NULL,&target)==4&&J413DirectSetupOption(&o,NULL)==4);
 assert(J413DirectSetupOption(&o,&zero)==5&&!identities&&!fs_accesses);
 reset();assert(J413DirectSetupOption(&o,&target)==0&&o.Handle==(void*)2&&fs_accesses==1&&identities==3&&!allocations);
 assert(!wcscmp(o.Description,L"Windows Setup (same volume)"));
 assert(J413DirectSetupOption(&o,&target)==EFI_NOT_FOUND&&fs_accesses==1&&!allocations);
 reset();partitions[2].Info.Gpt.UniquePartitionGUID=target;assert(J413DirectSetupOption(&o,&target)==6&&!fs_accesses&&!allocations);
 reset();partitions[1].Info.Gpt.UniquePartitionGUID.Data1=99;assert(J413DirectSetupOption(&o,&target)==1&&!fs_accesses&&!allocations);
 reset();partitions[1].Type=1;assert(J413DirectSetupOption(&o,&target)==1&&!fs_accesses&&!allocations);
 reset();partitions[1].Revision=0;assert(J413DirectSetupOption(&o,&target)==1&&!fs_accesses&&!allocations);
 reset();mode=1;assert(J413DirectSetupOption(&o,&target)==1&&fs_accesses==1&&!allocations);
 reset();boot[0].kind=1;assert(J413DirectSetupOption(&o,&target)==1&&!allocations); // A valid file elsewhere is not tried.
 reset();first[0].name=L"eFi";efi[0].name=L"bOot";boot[0].name=L"bootAa64.eFi";
 assert(J413DirectSetupOption(&o,&target)==0&&o.Handle==(void*)2&&!allocations);
 reset();path_fail=1;assert(J413DirectSetupOption(&o,&target)==3&&!allocations);
 reset();init_fail=1;assert(J413DirectSetupOption(&o,&target)==3&&!allocations);
 assert(opens==closes&&!other_opens);
 return 0;}
''')
