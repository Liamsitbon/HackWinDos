"""Exercise the staged BDS selector and the real exact-path scanner together."""
import unittest
import test_j413_efi_discovery as discovery


class BdsSelectorTests(unittest.TestCase):
    run_c = discovery.EfiDiscoveryTests.run_c

    def test_usb_candidates_precede_nvme_and_internal_setup_is_tried_once(self):
        src = (discovery.ROOT / 'mu/Silicon/Apple/AppleSiliconPkg/Drivers/WindowsAutoBootDxe/WindowsAutoBootDxe.c').read_text()
        start = src.index('STATIC EFI_STATUS EFIAPI GetJ413SetupOption(')
        end = src.index('STATIC J413_WINDOWS_SETUP mSetup', start)
        prelude = discovery.PRELUDE.replace(
            '*out=&filesystems[(uintptr_t)h-1];',
            'filesystem_opens[(uintptr_t)h-1]++;*out=&filesystems[(uintptr_t)h-1];',
        ).replace(
            'static struct {EFI_STATUS (*LocateHandleBuffer)',
            'static struct {EFI_STATUS (*LocateProtocol)(int*,void*,void**);'
            'EFI_STATUS (*LocateDevicePath)(int*,EFI_DEVICE_PATH_PROTOCOL**,EFI_HANDLE*);EFI_STATUS (*LocateHandleBuffer)',
        ).replace('services={locate,protocol}', 'services={locate_protocol,locate_device_path,locate,protocol}')
        mock = r'''
static EFI_STATUS locate_protocol(int*,void*,void**);
static int filesystem_opens[2], usb_media;
static int gEfiUsbIoProtocolGuid;
static EFI_DEVICE_PATH_PROTOCOL paths[]={{(void*)1,L""},{(void*)2,L""}};
static EFI_DEVICE_PATH_PROTOCOL *DevicePathFromHandle(EFI_HANDLE h){return &paths[(uintptr_t)h-1];}
static EFI_STATUS locate_device_path(int *guid,EFI_DEVICE_PATH_PROTOCOL **path,EFI_HANDLE *ancestor){
 assert(guid==&gEfiUsbIoProtocolGuid&&path&&*path);
 if((*path)->Handle==(void*)2&&usb_media){*ancestor=(void*)3;return EFI_SUCCESS;}
 return EFI_NOT_FOUND;
}
'''
        prelude = prelude.replace('static EFI_STATUS locate(int', mock + 'static EFI_STATUS locate(int')
        self.run_c(prelude + '#define J413_USB_BOOT_ONLY\n' + discovery.HEADER.read_text() + r'''
#define EFIAPI
#define OUT
#define EFI_INVALID_PARAMETER 4
static BOOLEAN mUsbStarted, mInternalTried;
static int connects, inventories, nvme_connections, internal_picks, nvme_status, waits, failure_screens;
static int mJ413DirectSetupGuid;
static EFI_STATUS J413ConnectBootNvme(const int *target){
 assert(target==&mJ413DirectSetupGuid&&connects==1&&waits==1);
 nvme_connections++;return nvme_status;
}
static void J413UsbInventory(void){assert(connects==1);inventories++;}
static EFI_STATUS J413ConnectBootUsb(void){assert(!nvme_connections);connects++;return EFI_SUCCESS;}
static EFI_STATUS J413NextDirectSetupOption(EFI_BOOT_MANAGER_LOAD_OPTION *o){
 assert(nvme_connections==1);internal_picks++;
 o->Handle=(void*)1;return nvme_status;
}
static void J413LogStatus(const char *s,int v){(void)s;(void)v;}
static void J413LogCount(const char *s,size_t v){(void)s;(void)v;}
static void J413Checkpoint(const char *s,int v){(void)s;(void)v;}
static EFI_STATUS J413WaitForBootOption(EFI_BOOT_MANAGER_LOAD_OPTION *o){
 assert(!nvme_connections);waits++;return J413NextEfiOption(o);
}
static void J413ShowUsbFailure(EFI_STATUS s){assert(EFI_ERROR(s));failure_screens++;}
static struct {void *ConOut;} table={(void*)1};
#define gST (&table)
static int gJ413UsbDartReadyProtocolGuid;
typedef struct {unsigned ControllerMask;} J413_USB_DART_READY;
static EFI_STATUS locate_protocol(int *guid,void *key,void **out){assert(guid==&gJ413UsbDartReadyProtocolGuid&&!key);*out=NULL;return EFI_NOT_FOUND;}
'''+src[start:end]+r'''
static void reset(void){
 assert(!allocations&&opens==closes);
 mUsbStarted=mInternalTried=mEfiScanned=FALSE;
 mEfiCount=0;mEfiHead=mEfiTail=NULL;
 scans=connects=inventories=waits=nvme_connections=internal_picks=failure_screens=nvme_status=0;
 filesystem_opens[0]=filesystem_opens[1]=0;usb_media=1;boot[0].kind=0;
 roots[1].children=first;roots[1].count=roots[0].count;
}
int main(void){
 EFI_BOOT_MANAGER_LOAD_OPTION option;
 reset();assert(GetJ413SetupOption(NULL)==EFI_INVALID_PARAMETER&&!connects);
 assert(GetJ413SetupOption(&option)==EFI_SUCCESS&&option.Handle==(void*)2);
 assert(!nvme_connections&&!internal_picks&&filesystem_opens[0]==0&&filesystem_opens[1]==1);
 assert(GetJ413SetupOption(&option)==EFI_SUCCESS&&option.Handle==(void*)1);
 assert(GetJ413SetupOption(&option)==EFI_NOT_FOUND&&GetJ413SetupOption(&option)==EFI_NOT_FOUND);
 assert(connects==1&&waits==1&&scans==1&&nvme_connections==1&&internal_picks==1&&!failure_screens);
 reset();usb_media=0;
 assert(GetJ413SetupOption(&option)==EFI_SUCCESS&&option.Handle==(void*)1);
 assert(!filesystem_opens[0]&&!filesystem_opens[1]&&nvme_connections==1&&internal_picks==1);
 reset();boot[0].kind=1;nvme_status=EFI_NOT_FOUND;
 assert(GetJ413SetupOption(&option)==EFI_NOT_FOUND&&failure_screens==1&&nvme_connections==1);
 assert(GetJ413SetupOption(&option)==EFI_NOT_FOUND&&failure_screens==1&&nvme_connections==1);
 assert(!filesystem_opens[0]&&!other_opens&&!allocations&&opens==closes);
 return 0;
}
''')
