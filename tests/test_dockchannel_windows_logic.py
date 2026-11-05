"""Execute the Windows adapter's actual error/stream logic without touching MMIO."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT/'drivers/apple-dockchannel/windows/src'
CORE = ROOT/'drivers/apple-dockchannel/core'


def function(source, name):
    match = re.search(r'\b'+name+r'\s*\([^;]*?\)\s*\{', source, re.S)
    assert match
    end, depth = match.end(), 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end]


class DockChannelWindowsLogicTests(unittest.TestCase):
    def run_c(self, source, libraries=()):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path/'test.c').write_text(source)
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                '-Wno-unused-function', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                '-I', str(CORE), str(path/'test.c'),
                *(str(CORE/(name+'.c')) for name in libraries), '-o', str(path/'test')], check=True)
            subprocess.run([str(path/'test')], check=True, timeout=10)

    def test_each_vhf_create_or_start_failure_unwinds_and_propagates(self):
        bridge = re.sub(r'^#include[^\n]*$', '', (DRIVER/'vhf_bridge.c').read_text(), flags=re.M)
        self.run_c(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "hid_packet.h"
#define TRUE 1
#define FALSE 0
#define STATUS_SUCCESS 0
#define STATUS_INVALID_PARAMETER -1
#define NT_SUCCESS(s) ((s)>=0)
#define RtlZeroMemory(p,n) memset(p,0,n)
typedef int NTSTATUS;typedef unsigned char UCHAR,*PUCHAR;typedef unsigned long ULONG;
typedef void VOID;typedef void *VHFHANDLE;
typedef struct {void *Device;VHFHANDLE KeyboardVhf,TrackpadVhf;int VhfStarted;} CONTEXT,*PDC_DEVICE_CONTEXT;
typedef struct {void *VhfClientContext;} VHF_CONFIG;
typedef struct {PUCHAR reportBuffer;ULONG reportBufferLen;UCHAR reportId;} HID_XFER_PACKET;
#define VHF_CONFIG_INIT(c,d,n,p) do{assert(d&&n&&p);memset(c,0,sizeof(*(c)));}while(0)
static void *WdfDeviceWdmGetDeviceObject(void *p){return p;}
static int calls,fail_at,live,deletes;
static NTSTATUS VhfCreate(VHF_CONFIG *c,VHFHANDLE *h){assert(c->VhfClientContext);if(++calls==fail_at)return -20;*h=(void*)(uintptr_t)(calls+1);live++;return 0;}
static NTSTATUS VhfStart(VHFHANDLE h){assert(h);return ++calls==fail_at?-20:0;}
static void VhfDelete(VHFHANDLE h,int wait){assert(h&&wait);live--;deletes++;}
static NTSTATUS VhfReadReportSubmit(VHFHANDLE h,HID_XFER_PACKET *p){assert(h&&p);return 0;}
static void DcVhfTeardown(PDC_DEVICE_CONTEXT);
''' + bridge.replace('VOID DcVhfTeardown(', 'static VOID DcVhfTeardown(') + r'''
int main(void){CONTEXT c={0};assert(DcVhfInitialize(NULL)==-1&&DcVhfInitialize(&c)==-1);
 for(int failure=1;failure<=4;failure++){
  memset(&c,0,sizeof(c));c.Device=&c;calls=deletes=0;fail_at=failure;
  assert(DcVhfInitialize(&c)==-20&&!c.VhfStarted&&!c.KeyboardVhf&&!c.TrackpadVhf&&!live);
  fail_at=0;calls=0;assert(DcVhfInitialize(&c)==0&&c.VhfStarted&&live==2);
  int prior=calls;assert(DcVhfInitialize(&c)==0&&calls==prior);
  DcVhfTeardown(&c);assert(!live&&!c.VhfStarted&&!c.KeyboardVhf&&!c.TrackpadVhf);
 }
 return 0;}
''')

    def test_d0_entry_returns_the_actual_vhf_initialization_result(self):
        body = function((DRIVER/'device.c').read_text(), 'DcEvtDeviceD0Entry')
        self.run_c(r'''
#include <assert.h>
#define _In_
#define STATUS_SUCCESS 0
#define UNREFERENCED_PARAMETER(p) ((void)(p))
typedef int NTSTATUS,WDF_POWER_DEVICE_STATE;typedef void *WDFDEVICE,*PDC_DEVICE_CONTEXT;
static int next_status;
static PDC_DEVICE_CONTEXT DcGetDeviceContext(WDFDEVICE d){return d;}
static NTSTATUS DcVhfInitialize(PDC_DEVICE_CONTEXT c){assert(c);return next_status;}
NTSTATUS
''' + body + r'''
int main(void){int d;next_status=-20;assert(DcEvtDeviceD0Entry(&d,0)==-20);next_status=0;assert(DcEvtDeviceD0Entry(&d,0)==0);return 0;}
''')

    def test_worker_consumes_two_distinct_concatenated_frames(self):
        body = function((DRIVER/'device.c').read_text(), 'DcEvtWorkItem')
        self.run_c(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "dockchannel.h"
#include "hid_packet.h"
#include "hid_stream.h"
#define _In_
#define DC_STREAM_BUF_SIZE 65536
typedef void *WDFWORKITEM;
typedef struct {void *BaseAddress;struct dc_io Io;struct dchid_stream Stream;uint8_t *StreamBuffer;} CONTEXT,*PDC_DEVICE_CONTEXT;
static void *WdfWorkItemGetParentObject(void *p){return p;}
static PDC_DEVICE_CONTEXT DcGetDeviceContext(void *p){return p;}
static uint8_t wire[128];static size_t wire_size,position;static unsigned reports,sequences[4];
static int DcVhfDispatchReport(PDC_DEVICE_CONTEXT c,const struct dchid_packet *p){assert(c&&reports<4);sequences[reports++]=p->sequence;return 0;}
static uint32_t read32(void *c,uint32_t offset){(void)c;if(offset==0x2c)return (uint32_t)(wire_size-position);assert(offset==0x28&&position+4<=wire_size);uint32_t n=(uint32_t)wire[position]|(uint32_t)wire[position+1]<<8|(uint32_t)wire[position+2]<<16|(uint32_t)wire[position+3]<<24;position+=4;return n;}
void
''' + body + r'''
int main(void){uint8_t storage[DC_STREAM_BUF_SIZE],payload[]={1,2,3};size_t a,b;
 assert(dchid_encode_command(2,7,0x81,payload,3,wire,sizeof(wire),&a)==DCHID_OK);
 assert(dchid_encode_command(2,8,0x81,payload,3,wire+a,sizeof(wire)-a,&b)==DCHID_OK);wire_size=a+b;
 CONTEXT c={0};c.BaseAddress=&c;c.StreamBuffer=storage;c.Io=(struct dc_io){.read32=read32,.fifo_size=4096};
 assert(dchid_stream_reset(&c.Stream,storage,sizeof(storage))==DCHID_OK);
 DcEvtWorkItem(&c);assert(reports==2&&sequences[0]==7&&sequences[1]==8&&position==wire_size&&c.Stream.used==0);
 return 0;}
''', ('dockchannel', 'hid_packet', 'hid_stream'))
