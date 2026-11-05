"""Execute m1n1's PHY initializer at the power/MMIO boundary."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'm1n1_windows/src/usb.c'

PRELUDE = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;typedef uint64_t u64;
#define USB_IODEV_COUNT 2
#define FMT_ATC_PATH "/arm-io/atc-phy%u"
#define FMT_DART_PATH "/arm-io/dart-usb%u"
#define FMT_DRD_PATH "/arm-io/usb-drd%u"
#define PIPEHANDLER_MUX_CTRL 0x0c
#define PIPEHANDLER_MUX_CTRL_DUMMY 0x22
#define PIPEHANDLER_AON_GEN 0x1c
#define PIPEHANDLER_AON_GEN_DWC3_RESET_N 1
#define PIPEHANDLER_NONSELECTED_OVERRIDE 0x20
#define USB2PHY_SIG_HOST (7U << 12)
struct usb_drd_regs {uintptr_t drd_regs,drd_regs_unk3,atc;};
static int reg_fail,power_fail,power_calls,writes,reads,bad_readback;
static unsigned current_index;
static uintptr_t addresses[8];static u32 values[8];
static int usb_drd_get_regs(u32 idx,struct usb_drd_regs *r){
 assert(idx<2);current_index=idx;if(reg_fail)return -1;
 r->drd_regs=idx?UINT64_C(0x502280000):UINT64_C(0x382280000);
 r->drd_regs_unk3=idx?UINT64_C(0x502a84000):UINT64_C(0x382a84000);
 r->atc=idx?UINT64_C(0x502a90000):UINT64_C(0x382a90000);return 0;
}
static int pmgr_adt_power_enable(const char *p){
 char want[32];const char *fmt[]={FMT_ATC_PATH,FMT_DART_PATH,FMT_DRD_PATH};
 assert(power_calls<3);snprintf(want,sizeof(want),fmt[power_calls++],current_index);
 assert(!strcmp(p,want));return power_calls==power_fail?-1:0;
}
static void write32(uintptr_t a,u32 v){assert(power_calls==3&&writes<8);addresses[writes]=a;values[writes++]=v;}
static u32 read32(uintptr_t a){assert(a==(current_index?UINT64_C(0x502a90008):UINT64_C(0x382a90008)));reads++;return bad_readback?0:values[0];}
'''

class UsbPhyRoleTests(unittest.TestCase):
    def execute(self, flags):
        text = SOURCE.read_text()
        start = text.index('int usb_phy_bringup(u32 idx)')
        end = text.index('\ndwc3_dev_t *usb_iodev_bringup', start)
        main = r'''
static void reset(void){reg_fail=power_fail=power_calls=writes=reads=bad_readback=0;}
int main(void){
 for(unsigned idx=0;idx<2;idx++){
  reset();assert(usb_phy_bringup(idx)==0&&writes==8&&power_calls==3);
  uintptr_t atc=idx?UINT64_C(0x502a90000):UINT64_C(0x382a90000);
  uintptr_t pipe=idx?UINT64_C(0x502a84000):UINT64_C(0x382a84000);
  u32 sig=0x01c1000f;
#if defined(M1N1_J413) && defined(M1N1_NO_PROXY)
  if(idx==1)sig=0x01c1700f;
#endif
  // Host role must be established in the first write, before release from reset.
  assert(addresses[0]==atc+8&&values[0]==sig);
  assert(addresses[1]==atc+4&&values[1]==3);
  assert(addresses[2]==atc+4&&values[2]==0);
  assert(addresses[3]==atc+0x1c&&values[3]==0x008c0813);
  assert(addresses[4]==atc&&values[4]==2);
  assert(addresses[5]==pipe+0x0c&&values[5]==0x22);
  assert(addresses[6]==pipe+0x1c&&values[6]==1);
  assert(addresses[7]==pipe+0x20&&values[7]==0x9332);
 }
#if defined(M1N1_J413) && defined(M1N1_NO_PROXY)
 reset();bad_readback=1;assert(usb_phy_bringup(1)==-1&&reads==1);
#endif
 reset();assert(usb_phy_bringup(2)==-1&&!writes&&!power_calls);
 reset();reg_fail=1;assert(usb_phy_bringup(1)==-1&&!writes&&!power_calls);
 for(int i=1;i<=3;i++){reset();power_fail=i;assert(usb_phy_bringup(1)==-1&&!writes&&power_calls==i);}
 return 0;}
'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.c').write_text(PRELUDE+text[start:end]+main)
            subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-function',
                            '-fsanitize=address,undefined','-fno-sanitize-recover=all',
                            *flags,str(p/'test.c'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True,timeout=10)

    def test_quiet_j413_usb1_selects_host_phy_before_reset(self):
        self.execute(['-DM1N1_J413','-DM1N1_NO_PROXY'])

    def test_legacy_and_proxy_profiles_keep_prior_phy_state(self):
        for flags in ([],['-DM1N1_J413'],['-DM1N1_NO_PROXY']):
            with self.subTest(flags=flags):self.execute(flags)
