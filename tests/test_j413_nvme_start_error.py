"""Execute the actual NVMe Start error-unwind code with injected failures."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'mu/MU_BASECORE/MdeModulePkg/Bus/Pci/NvmExpressDxe/NvmExpress.c'


class NvmeStartErrorTests(unittest.TestCase):
    def run_unwind(self, j413):
        text = SOURCE.read_text()
        start = text.index('NvmExpressDriverBindingStart (')
        begin = text.index('\nExit:', start)
        end = text.index('\n}\n', begin)+3
        actual_exit = text[begin:end]
        harness = r'''
#include <assert.h>
#include <stdlib.h>
#define DEBUG(x) ((void)0)
#define DEBUG_INFO 0
#define DEBUG_ERROR 0
#define EFI_ERROR(s) ((s)<0)
#define NULL_HANDLE ((void*)0)
typedef long EFI_STATUS;
typedef void *EFI_HANDLE;
typedef struct {void *ControllerData;void *TimerEvent;} NVME_CONTROLLER_PRIVATE_DATA;
typedef struct {void *DriverBindingHandle;} BINDING;
static int clean_calls, frees, close_events, close_protocols;
static EFI_STATUS cleanup_result;
static int gEfiPciIoProtocolGuid,gEfiDevicePathProtocolGuid,token;
static EFI_STATUS NvmExpressDriverCleanUpQueues(NVME_CONTROLLER_PRIVATE_DATA *p){
 ++clean_calls;return p?cleanup_result:-2;
}
static void FreePool(void *p){assert(p);++frees;free(p);}
static EFI_STATUS close_event(void *p){assert(p==&token);++close_events;return 0;}
static EFI_STATUS close_protocol(void *c,int *g,void *a,void *p){
 assert(c==&token&&p==c&&a==&token&&(g==&gEfiPciIoProtocolGuid||g==&gEfiDevicePathProtocolGuid));
 ++close_protocols;return 0;
}
static struct {EFI_STATUS (*CloseEvent)(void*);EFI_STATUS (*CloseProtocol)(void*,int*,void*,void*);}
services={close_event,close_protocol};
#define gBS (&services)
static EFI_STATUS actual_unwind(EFI_STATUS Status,NVME_CONTROLLER_PRIVATE_DATA *Private){
 BINDING binding={&token}; BINDING *This=&binding; EFI_HANDLE Controller=&token;
 EFI_STATUS SavedStartStatus=0; (void)SavedStartStatus;
''' + actual_exit + r'''
int main(void){
 const long original_errors[]={-14,-18,-9};
 const long cleanup_errors[]={0,-7,-2};
 for(int i=0;i<3;++i){
  NVME_CONTROLLER_PRIVATE_DATA *p=NULL;
  clean_calls=frees=close_events=close_protocols=0;cleanup_result=cleanup_errors[i];
  if(i<2){p=calloc(1,sizeof(*p));assert(p);p->ControllerData=malloc(16);assert(p->ControllerData);p->TimerEvent=&token;}
  long result=actual_unwind(original_errors[i],p);
#ifdef J413_BOOT_CONTRACT
  assert(result==original_errors[i]);
#else
  /* Other platforms retain the preceding upstream behavior in this patch. */
  assert(result==cleanup_errors[i]);
#endif
  assert(clean_calls==1&&close_protocols==2);
  assert(frees==(i<2?2:0)&&close_events==(i<2?1:0));
 }
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'error.c'; binary = Path(tmp)/'error'
            source.write_text(harness)
            flags = ['-DJ413_BOOT_CONTRACT'] if j413 else []
            subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-Wno-unused-label', '-fsanitize=address,undefined',
                            *flags, str(source), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_original_start_error_survives_successful_or_failed_cleanup(self):
        self.run_unwind(True)

    def test_other_platform_behavior_is_unchanged(self):
        self.run_unwind(False)
