/* SPDX-License-Identifier: MIT
 * Windows KMDF Driver for Apple Silicon M2 DockChannel Input Transport.
 */
#ifndef APPLE_DOCKCHANNEL_WINDOWS_H
#define APPLE_DOCKCHANNEL_WINDOWS_H

#include <ntddk.h>
#include <wdf.h>
#include <hidport.h>
#include <vhf.h>

#include "dockchannel.h"
#include "hid_packet.h"
#include "hid_stream.h"
#include "hid_discovery.h"
#include "hid_command.h"

#define DC_WIN_POOL_TAG 'CDpA' // ApDC

#define DC_REG_STATUS_OFFSET   0x00u
#define DC_REG_DATA_OFFSET     0x04u
#define DC_REG_CONFIG_OFFSET   0x08u
#define DC_FIFO_SIZE           0x1000u

#define DC_STREAM_BUF_SIZE     0x10000u // 64 KB

typedef struct _DC_DEVICE_CONTEXT {
    WDFDEVICE Device;
    WDFINTERRUPT Interrupt;
    WDFSPINLOCK Lock;

    // MMIO Registers
    PUCHAR BaseAddress;
    ULONG MemoryLength;

    // FIFO IO descriptor
    struct dc_io Io;
    struct dchid_stream Stream;
    PUCHAR StreamBuffer;

    // VHF handles for Windows input subsystem
    VHFHANDLE KeyboardVhf;
    VHFHANDLE TrackpadVhf;
    BOOLEAN VhfStarted;

    // Interfaces mapped from EVENT_INIT
    UINT8 KeyboardInterfaceId;
    UINT8 TrackpadInterfaceId;
    BOOLEAN InterfacesDiscovered;

    // Work item for deferred report submission
    WDFWORKITEM WorkItem;
} DC_DEVICE_CONTEXT, *PDC_DEVICE_CONTEXT;

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(DC_DEVICE_CONTEXT, DcGetDeviceContext)

// Prototypes
EVT_WDF_DRIVER_DEVICE_ADD DcEvtDeviceAdd;
EVT_WDF_DEVICE_PREPARE_HARDWARE DcEvtDevicePrepareHardware;
EVT_WDF_DEVICE_RELEASE_HARDWARE DcEvtDeviceReleaseHardware;
EVT_WDF_DEVICE_D0_ENTRY DcEvtDeviceD0Entry;
EVT_WDF_DEVICE_D0_EXIT DcEvtDeviceD0Exit;
EVT_WDF_INTERRUPT_ISR DcEvtInterruptIsr;
EVT_WDF_INTERRUPT_DPC DcEvtInterruptDpc;
EVT_WDF_WORKITEM DcEvtWorkItem;

NTSTATUS DcVhfInitialize(PDC_DEVICE_CONTEXT Context);
VOID DcVhfTeardown(PDC_DEVICE_CONTEXT Context);
NTSTATUS DcVhfDispatchReport(PDC_DEVICE_CONTEXT Context, const struct dchid_packet *Packet);

#endif /* APPLE_DOCKCHANNEL_WINDOWS_H */
