"""Run the actual event-driven deadline with delayed filesystem publication."""
from pathlib import Path
import unittest
import test_j413_efi_discovery as discovery
ROOT = Path(__file__).resolve().parents[1]
class BootWaitTests(unittest.TestCase):
    run_c = discovery.EfiDiscoveryTests.run_c

    def test_real_scanner_finds_filesystem_published_after_initial_empty_snapshot(self):
        prelude = discovery.PRELUDE.replace('scans++;*count=2;',
            'scans++;if(!published){*out=NULL;*count=0;return EFI_NOT_FOUND;}*count=2;')
        header=(ROOT/'platforms/j413/mu/Silicon/Apple/AppleSiliconPkg/Drivers/WindowsAutoBootDxe/J413BootWait.h').read_text()
        self.run_c('static int published;\n'+prelude+discovery.HEADER.read_text()+r'''
#define EVT_TIMER 1
#define TPL_CALLBACK 8
#define TimerRelative 0
#define TimerPeriodic 1
typedef void *EFI_EVENT;
static int created,closed,waits;
static EFI_STATUS create(int type,int tpl,void *fn,void *arg,EFI_EVENT *out){assert(type==1&&tpl==8&&!fn&&!arg);*out=(void*)(uintptr_t)(++created);return 0;}
static EFI_STATUS timer(EFI_EVENT e,int type,UINT64 ticks){(void)e;(void)type;(void)ticks;return 0;}
static EFI_STATUS wait_event(UINTN count,EFI_EVENT *events,UINTN *index){assert(count==2&&events[0]);waits++;if(waits==3)published=1;*index=1;return 0;}
static EFI_STATUS close_event(EFI_EVENT e){assert(e);closed++;return 0;}
static struct {EFI_STATUS (*CreateEvent)(int,int,void*,void*,EFI_EVENT*);EFI_STATUS (*SetTimer)(EFI_EVENT,int,UINT64);EFI_STATUS (*WaitForEvent)(UINTN,EFI_EVENT*,UINTN*);EFI_STATUS (*CloseEvent)(EFI_EVENT);} timers={create,timer,wait_event,close_event};
#undef gBS
#define gBS (&timers)
'''+header+r'''
int main(void){EFI_BOOT_MANAGER_LOAD_OPTION o;
 assert(J413WaitForBootOption(&o)==0&&waits==3&&scans==4&&created==closed);
 assert(o.Handle==(EFI_HANDLE)1&&!wcscmp(o.Description,L"\\EFI\\BOOT\\BOOTAA64.EFI"));
 assert(J413NextEfiOption(&o)==EFI_NOT_FOUND&&!allocations&&opens==closes&&!other_opens);
 return 0;}
''')

    def test_late_media_deadline_service_failures_cleanup_and_no_repeated_attempt(self):
        header=(ROOT/'platforms/j413/mu/Silicon/Apple/AppleSiliconPkg/Drivers/WindowsAutoBootDxe/J413BootWait.h').read_text()
        self.run_c(r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <wchar.h>
#define STATIC static
#define VOID void
#define FALSE 0
#define EFI_NOT_FOUND 14
#define EFI_ERROR(s) ((s)!=0)
#define EVT_TIMER 1
#define TPL_CALLBACK 8
#define TimerRelative 0
#define TimerPeriodic 1
typedef int EFI_STATUS;typedef size_t UINTN;typedef void *EFI_EVENT;
typedef struct {int ready;} EFI_BOOT_MANAGER_LOAD_OPTION;
static int mEfiScanned,mEfiCount;
static int scans,created,closed,waits,set_calls,mode,publication;
static int Print(const wchar_t *s,...){(void)s;return 0;}
static EFI_STATUS J413NextEfiOption(EFI_BOOT_MANAGER_LOAD_OPTION *o){
 assert(!mEfiScanned);mEfiScanned=1;scans++;
 if(waits>=publication){o->ready=1;return 0;}return EFI_NOT_FOUND;
}
static EFI_STATUS create(int type,int tpl,void *fn,void *arg,EFI_EVENT *out){
 assert(type==1&&tpl==8&&!fn&&!arg);if(mode==1&&created==1)return 7;
 *out=(void*)(uintptr_t)(++created);return 0;
}
static EFI_STATUS timer(EFI_EVENT event,int type,uint64_t ticks){
 set_calls++;if(mode==2)return 7;
 if(ticks==300000000ULL){assert(type==TimerRelative);return 0;}
 if(event==(void*)1)assert(type==TimerRelative&&ticks==100000000ULL);
 else assert(event==(void*)2&&type==TimerPeriodic&&ticks==2000000ULL);
 return 0;
}
static EFI_STATUS wait_event(UINTN count,EFI_EVENT *events,UINTN *index){
 assert(count==1||count==2);assert(events[0]==(void*)1);waits++;
 if(mode==3)return 7;
 *index= count==1||waits==50?0:1;return 0;
}
static EFI_STATUS close_event(EFI_EVENT event){assert(event);closed++;return 0;}
static struct {EFI_STATUS (*CreateEvent)(int,int,void*,void*,EFI_EVENT*);
 EFI_STATUS (*SetTimer)(EFI_EVENT,int,uint64_t);
 EFI_STATUS (*WaitForEvent)(UINTN,EFI_EVENT*,UINTN*);
 EFI_STATUS (*CloseEvent)(EFI_EVENT);} services={create,timer,wait_event,close_event};
#define gBS (&services)
''' + header + r'''
static void reset(void){mEfiScanned=mEfiCount=scans=created=closed=waits=set_calls=mode=0;publication=3;}
int main(void){EFI_BOOT_MANAGER_LOAD_OPTION o={0};
 reset();assert(J413WaitForBootOption(&o)==0&&o.ready&&scans==4&&waits==3&&created==2&&closed==2);
 reset();publication=0;assert(J413WaitForBootOption(&o)==0&&scans==1&&!created&&!waits);
 reset();publication=100;assert(J413WaitForBootOption(&o)==14&&scans==50&&waits==50&&closed==2);
 for(int fail=1;fail<=3;fail++){reset();mode=fail;assert(J413WaitForBootOption(&o)==14&&created==closed);}
 reset();J413PauseFailureScreen();assert(created==1&&closed==1&&waits==1&&set_calls==1);
 return 0;}
''')
