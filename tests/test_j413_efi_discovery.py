"""Execute exact-path loader discovery, candidate iterator and BDS retry loop."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
HEADER=ROOT/'platforms/j413/mu/Silicon/Apple/AppleSiliconPkg/Drivers/WindowsAutoBootDxe/J413EfiCandidates.h'
PRELUDE=r'''
#include <assert.h>
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <wchar.h>
#define STATIC static
#define CONST const
#define VOID void
#define TRUE 1
#define FALSE 0
#define EFI_SUCCESS 0
#define EFI_NOT_FOUND 1
#define EFI_BUFFER_TOO_SMALL 2
#define EFI_OUT_OF_RESOURCES 3
#define EFI_VOLUME_CORRUPTED 4
#define EFI_ERROR(s) ((s)!=0)
#define EFI_FILE_MODE_READ 1
#define EFI_FILE_DIRECTORY 16
#define ByProtocol 0
#define LoadOptionNumberUnassigned 0xffff
#define LoadOptionTypeBoot 0
#define LOAD_OPTION_ACTIVE 1
#define OFFSET_OF(t,m) offsetof(t,m)
#define StrLen wcslen
#define CopyMem memcpy
typedef uint8_t UINT8;typedef uint16_t UINT16;typedef uint32_t UINT32;typedef uint64_t UINT64;
typedef size_t UINTN;typedef wchar_t CHAR16;typedef int BOOLEAN,EFI_STATUS;typedef void *EFI_HANDLE;
typedef struct {UINT64 Size,FileSize,PhysicalSize;UINT8 times[48];UINT64 Attribute;CHAR16 FileName[1];} EFI_FILE_INFO;
typedef struct FILE EFI_FILE_PROTOCOL;
struct FILE {EFI_STATUS (*Open)(EFI_FILE_PROTOCOL*,EFI_FILE_PROTOCOL**,CHAR16*,UINT64,UINT64);EFI_STATUS (*Close)(EFI_FILE_PROTOCOL*);EFI_STATUS (*Read)(EFI_FILE_PROTOCOL*,UINTN*,VOID*);EFI_STATUS (*SetPosition)(EFI_FILE_PROTOCOL*,UINT64);};
typedef struct FS EFI_SIMPLE_FILE_SYSTEM_PROTOCOL;
struct FS {EFI_STATUS (*OpenVolume)(EFI_SIMPLE_FILE_SYSTEM_PROTOCOL*,EFI_FILE_PROTOCOL**);int index;};
typedef struct {EFI_HANDLE Handle;CHAR16 Name[1024];} EFI_DEVICE_PATH_PROTOCOL;
typedef struct {EFI_HANDLE Handle;CHAR16 Description[1024];int Status;} EFI_BOOT_MANAGER_LOAD_OPTION;
static int allocations,opens,closes,scans,prints,directory_reads,other_opens,init_fail,path_fail,malformed,grow,read_fail,unterminated,oversize,pe32,short_read;
static VOID *AllocatePool(UINTN n){void *p=malloc(n);assert(p);allocations++;return p;}
static VOID *AllocateZeroPool(UINTN n){void *p=AllocatePool(n);memset(p,0,n);return p;}
static VOID FreePool(VOID *p){assert(p);allocations--;free(p);}
static int Print(CONST CHAR16 *fmt,...){(void)fmt;prints++;return 0;}
static int gEfiSimpleFileSystemProtocolGuid;
static EFI_DEVICE_PATH_PROTOCOL *FileDevicePath(EFI_HANDLE h,CONST CHAR16 *path){if(path_fail)return NULL;EFI_DEVICE_PATH_PROTOCOL *p=AllocateZeroPool(sizeof(*p));p->Handle=h;wcscpy(p->Name,path);return p;}
static EFI_STATUS EfiBootManagerInitializeLoadOption(EFI_BOOT_MANAGER_LOAD_OPTION *o,int number,int type,int active,CONST CHAR16 *name,EFI_DEVICE_PATH_PROTOCOL *p,VOID *args,int size){assert(number==0xffff&&type==0&&active==1&&!args&&!size);if(init_fail)return 3;o->Handle=p->Handle;wcscpy(o->Description,name);return 0;}
struct Node {CONST CHAR16 *name;int directory,kind;struct Node *children;size_t count;};
static struct Node deep[]={ {L"Mixed.EfI",0,0,NULL,0}, {L"driver.efi",0,2,NULL,0}, {L"x64.efi",0,1,NULL,0}, {L"broken.efi",0,3,NULL,0} };
static struct Node boot[]={ {L"BOOTAA64.EFI",0,0,NULL,0} };
static struct Node efi[]={ {L"BOOT",1,0,boot,1} };
static struct Node first[]={ {L"EFI",1,0,efi,1}, {L"odd folder",1,0,deep,4}, {L"notes.txt",0,0,NULL,0}, {L".",1,0,NULL,0}, {L"..",1,0,NULL,0}, {L"bad/name.efi",0,0,NULL,0} };
static struct Node second[]={ {L"root.efi",0,0,NULL,0} };
static struct Node roots[]={ {L"",1,0,first,6}, {L"",1,0,second,1} };
struct MOCK {EFI_FILE_PROTOCOL File;struct Node *node,*root;size_t position,entry;};
static EFI_STATUS open_file(EFI_FILE_PROTOCOL*,EFI_FILE_PROTOCOL**,CHAR16*,UINT64,UINT64);
static EFI_STATUS close_file(EFI_FILE_PROTOCOL *p){closes++;FreePool(p);return 0;}
static EFI_STATUS seek_file(EFI_FILE_PROTOCOL *p,UINT64 off){((struct MOCK*)p)->position=off;if(!off)((struct MOCK*)p)->entry=0;return 0;}
static EFI_STATUS read_file(EFI_FILE_PROTOCOL *p,UINTN *size,VOID *data){
 struct MOCK *m=(struct MOCK*)p;
 if(read_fail)return EFI_NOT_FOUND;
 if(m->node->directory){directory_reads++;
  if(m->entry==m->node->count){*size=0;return 0;}
  if((grow && *size<8192)||oversize){*size=oversize?65537:8192;return EFI_BUFFER_TOO_SMALL;}
  struct Node *n=&m->node->children[m->entry];size_t bytes=offsetof(EFI_FILE_INFO,FileName)+(wcslen(n->name)+1)*sizeof(CHAR16);
  if(*size<bytes){*size=bytes;return EFI_BUFFER_TOO_SMALL;}
  EFI_FILE_INFO *info=data;memset(info,0,bytes);info->Size=bytes;info->Attribute=n->directory?16:0;wcscpy(info->FileName,n->name);
  if(malformed){info->Size=bytes+sizeof(CHAR16);malformed=0;}
  if(unterminated)info->FileName[wcslen(n->name)]=L'X';
  *size=bytes;m->entry++;return 0;
 }
 UINT8 image[256]={0};image[0]='M';image[1]='Z';image[60]=64;
 image[64]='P';image[65]='E';image[68]=m->node->kind==1?0x64:0x64;image[69]=m->node->kind==1?0x86:0xaa;
 image[84]=0xf0;image[88]=0x0b;image[89]=pe32?0x01:0x02;image[156]=m->node->kind==2?11:10;
 if(m->node->kind==3)image[0]=0;
 size_t avail=m->position<sizeof(image)?sizeof(image)-m->position:0; if(*size>avail)*size=avail;if(short_read&&*size)(*size)--;
 memcpy(data,image+m->position,*size);m->position+=*size;return 0;
}
static EFI_FILE_PROTOCOL *make_file(struct Node *node,struct Node *root){struct MOCK *p=AllocateZeroPool(sizeof(*p));p->node=node;p->root=root;p->File=(EFI_FILE_PROTOCOL){open_file,close_file,read_file,seek_file};opens++;return &p->File;}
static EFI_STATUS open_file(EFI_FILE_PROTOCOL *p,EFI_FILE_PROTOCOL **out,CHAR16 *path,UINT64 mode,UINT64 attr){
 assert(mode==1&&!attr);CHAR16 folded[1024];size_t k=0;for(;path[k];k++)folded[k]=path[k]>=L'A'&&path[k]<=L'Z'?path[k]+32:path[k];folded[k]=0;
 if(wcscmp(folded,L"\\efi")&&wcscmp(folded,L"\\efi\\boot")&&wcscmp(folded,L"\\efi\\boot\\bootaa64.efi"))other_opens++;
 struct Node *node=path[0]==L'\\'?((struct MOCK*)p)->root:((struct MOCK*)p)->node;*out=NULL;
 while(*path){while(*path==L'\\')path++;if(!*path)break;CHAR16 name[1024];size_t n=0;while(*path&&*path!=L'\\')name[n++]=*path++;name[n]=0;struct Node *found=NULL;
 for(size_t i=0;i<node->count;i++)if(!wcscmp(node->children[i].name,name)){found=&node->children[i];break;}
 if(!found)return 1;node=found;}
 *out=make_file(node,((struct MOCK*)p)->root);return 0;
}
static EFI_STATUS open_volume(EFI_SIMPLE_FILE_SYSTEM_PROTOCOL *fs,EFI_FILE_PROTOCOL **out){*out=make_file(&roots[fs->index],&roots[fs->index]);return 0;}
static EFI_SIMPLE_FILE_SYSTEM_PROTOCOL filesystems[]={ {open_volume,0},{open_volume,1} };
static EFI_STATUS locate(int type,int *guid,VOID *reg,UINTN *count,EFI_HANDLE **out){assert(type==0&&guid==&gEfiSimpleFileSystemProtocolGuid&&!reg);scans++;*count=2;*out=AllocatePool(2*sizeof(EFI_HANDLE));(*out)[0]=(EFI_HANDLE)1;(*out)[1]=(EFI_HANDLE)2;return 0;}
static EFI_STATUS protocol(EFI_HANDLE h,int *guid,VOID **out){assert(guid==&gEfiSimpleFileSystemProtocolGuid);*out=&filesystems[(uintptr_t)h-1];return 0;}
static struct {EFI_STATUS (*LocateHandleBuffer)(int,int*,VOID*,UINTN*,EFI_HANDLE**);EFI_STATUS (*HandleProtocol)(EFI_HANDLE,int*,VOID**);} services={locate,protocol};
#define gBS (&services)
'''

class EfiDiscoveryTests(unittest.TestCase):
 def run_c(self,code):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'t.c').write_text(code)
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-Wno-unused-function','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(p/'t.c'),'-o',str(p/'t')],check=True)
   subprocess.run([str(p/'t')],check=True,timeout=10)

 def test_exact_path_only_across_filesystems_types_and_cleanup(self):
  self.run_c(PRELUDE+HEADER.read_text()+r'''
static void reset(void){assert(!allocations);mEfiHead=mEfiTail=NULL;mEfiCount=0;mEfiScanned=0;init_fail=path_fail=malformed=grow=read_fail=0;opens=closes=scans=directory_reads=other_opens=0;roots[1].children=second;roots[1].count=1;boot[0].kind=0;}
int main(void){EFI_BOOT_MANAGER_LOAD_OPTION o;
 reset();assert(J413NextEfiOption(&o)==0&&!wcscmp(o.Description,L"\\EFI\\BOOT\\BOOTAA64.EFI"));
 assert(J413NextEfiOption(&o)==1&&J413NextEfiOption(&o)==1&&scans==1&&opens==closes&&!allocations);
 assert(!other_opens); // ACPIVIEW/other EFI applications are never opened.
 reset();roots[1].children=first;roots[1].count=1;
 assert(J413NextEfiOption(&o)==0&&o.Handle==(EFI_HANDLE)1);
 assert(J413NextEfiOption(&o)==0&&o.Handle==(EFI_HANDLE)2);
 assert(J413NextEfiOption(&o)==1&&scans==1&&opens==closes&&!allocations&&!other_opens);
 // An arbitrary ARM64 application alone is not a boot candidate.
 reset();boot[0].kind=3;assert(J413NextEfiOption(&o)==1&&opens==closes&&!allocations&&!other_opens);
 for(int kind=1;kind<=3;kind++){reset();boot[0].kind=kind;assert(J413NextEfiOption(&o)==1&&opens==closes&&!allocations);}
 reset();path_fail=1;assert(J413NextEfiOption(&o)==1&&opens==closes&&!allocations);
 reset();init_fail=1;assert(J413NextEfiOption(&o)==1&&opens==closes&&!allocations);
 reset();read_fail=1;assert(J413NextEfiOption(&o)==1&&opens==closes&&!allocations);
 reset();assert(J413EfiSamePath(L"\\EFI\\BOOT\\BOOTAA64.EFI",L"\\efi\\boot\\bootaa64.efi"));
 return 0;}
''')

 def test_case_insensitive_exact_components_with_bounds_and_arm64_filter(self):
  self.run_c(PRELUDE+HEADER.read_text()+r'''
static void reset(void){assert(!allocations);mEfiHead=mEfiTail=NULL;mEfiCount=0;mEfiScanned=0;malformed=grow=read_fail=unterminated=oversize=pe32=short_read=0;opens=closes=scans=directory_reads=other_opens=0;first[0].name=L"eFi";efi[0].name=L"bOoT";boot[0].name=L"bootAa64.eFi";boot[0].kind=0;}
int main(void){EFI_BOOT_MANAGER_LOAD_OPTION o;
 reset();assert(J413NextEfiOption(&o)==0&&!wcscmp(o.Description,L"\\eFi\\bOoT\\bootAa64.eFi"));
 assert(J413NextEfiOption(&o)==1&&directory_reads>=3&&opens==closes&&!allocations&&!other_opens);
 reset();grow=1;assert(J413NextEfiOption(&o)==0);assert(J413NextEfiOption(&o)==1&&opens==closes&&!allocations&&!other_opens);
 for(int kind=1;kind<=3;kind++){reset();boot[0].kind=kind;assert(J413NextEfiOption(&o)==1&&opens==closes&&!allocations&&!other_opens);}
 reset();pe32=1;assert(J413NextEfiOption(&o)==1&&opens==closes&&!allocations);
 reset();short_read=1;assert(J413NextEfiOption(&o)==1&&opens==closes&&!allocations);
 reset();malformed=1;assert(J413NextEfiOption(&o)==1&&opens==closes&&!allocations);
 reset();unterminated=1;assert(J413NextEfiOption(&o)==1&&opens==closes&&!allocations);
 reset();oversize=1;assert(J413NextEfiOption(&o)==1&&opens==closes&&!allocations);
 reset();boot[0].name=L"ACPIview.efi";assert(J413NextEfiOption(&o)==1&&opens==closes&&!allocations&&!other_opens);
 return 0;}
''')

 def test_actual_priority_loop_uses_standard_bds_and_advances_after_return(self):
  src=(ROOT/'mu/Silicon/Apple/AppleSiliconPkg/Library/DeviceBootManagerLib/DeviceBootManagerLib.c').read_text()
  a=src.index('      Status = Setup->GetOption(BootOption);');b=src.index('\n    }',a)
  self.run_c(r'''
#include <assert.h>
#include <stddef.h>
#include <wchar.h>
#define EFI_ERROR(s) ((s)!=0)
#define EFI_NOT_FOUND 1
typedef int EFI_STATUS;typedef struct {const wchar_t *Description;int Status;} EFI_BOOT_MANAGER_LOAD_OPTION;
static int attempts,free_count,next_count;
static int Print(const wchar_t *s,...){(void)s;return 0;}
static void EfiBootManagerBoot(EFI_BOOT_MANAGER_LOAD_OPTION *o){attempts++;o->Status=attempts==1?7:attempts==2?0:26;}
static void EfiBootManagerFreeLoadOption(EFI_BOOT_MANAGER_LOAD_OPTION *o){(void)o;free_count++;}
static int next(EFI_BOOT_MANAGER_LOAD_OPTION *o){next_count++;o->Description=L"\\unusual\\app.efi";return next_count<=3?0:1;}
int main(void){struct {int (*GetOption)(EFI_BOOT_MANAGER_LOAD_OPTION*);} protocol={next},*Setup=&protocol;EFI_BOOT_MANAGER_LOAD_OPTION option,*BootOption=&option;EFI_STATUS Status;
'''+src[a:b]+r'''
assert(Status==1&&attempts==3&&free_count==3&&next_count==4);return 0;}
''')
