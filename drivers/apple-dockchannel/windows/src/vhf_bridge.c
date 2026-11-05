/* SPDX-License-Identifier: MIT
 * Experimental VHF bridge. Hardware discovery/report translation and the full
 * Windows Precision Touchpad contract still require a qualified J413 adapter.
 */
#include "dockchannel_windows.h"

// Standard USB HID Boot Keyboard Descriptor
static const UCHAR g_KeyboardHidDescriptor[] = {
    0x05, 0x01,                    // USAGE_PAGE (Generic Desktop)
    0x09, 0x06,                    // USAGE (Keyboard)
    0xa1, 0x01,                    // COLLECTION (Application)
    0x05, 0x07,                    //   USAGE_PAGE (Keyboard)
    0x19, 0xe0,                    //   USAGE_MINIMUM (Keyboard LeftControl)
    0x29, 0xe7,                    //   USAGE_MAXIMUM (Keyboard Right GUI)
    0x15, 0x00,                    //   LOGICAL_MINIMUM (0)
    0x25, 0x01,                    //   LOGICAL_MAXIMUM (1)
    0x75, 0x01,                    //   REPORT_SIZE (1)
    0x95, 0x08,                    //   REPORT_COUNT (8)
    0x81, 0x02,                    //   INPUT (Data,Var,Abs)
    0x95, 0x01,                    //   REPORT_COUNT (1)
    0x75, 0x08,                    //   REPORT_SIZE (8)
    0x81, 0x03,                    //   INPUT (Cnst,Var,Abs)
    0x95, 0x05,                    //   REPORT_COUNT (5)
    0x75, 0x01,                    //   REPORT_SIZE (1)
    0x05, 0x08,                    //   USAGE_PAGE (LEDs)
    0x19, 0x01,                    //   USAGE_MINIMUM (Num Lock)
    0x29, 0x05,                    //   USAGE_MAXIMUM (Kana)
    0x91, 0x02,                    //   OUTPUT (Data,Var,Abs)
    0x95, 0x01,                    //   REPORT_COUNT (1)
    0x75, 0x03,                    //   REPORT_SIZE (3)
    0x91, 0x03,                    //   OUTPUT (Cnst,Var,Abs)
    0x95, 0x06,                    //   REPORT_COUNT (6)
    0x75, 0x08,                    //   REPORT_SIZE (8)
    0x15, 0x00,                    //   LOGICAL_MINIMUM (0)
    0x25, 0x65,                    //   LOGICAL_MAXIMUM (101)
    0x05, 0x07,                    //   USAGE_PAGE (Keyboard)
    0x19, 0x00,                    //   USAGE_MINIMUM (Reserved)
    0x29, 0x65,                    //   USAGE_MAXIMUM (Keyboard Application)
    0x81, 0x00,                    //   INPUT (Data,Ary,Abs)
    0xc0                           // END_COLLECTION
};

// Experimental touch descriptor; not a complete Windows Precision Touchpad.
static const UCHAR g_TrackpadHidDescriptor[] = {
    0x05, 0x0d,                    // USAGE_PAGE (Digitizers)
    0x09, 0x05,                    // USAGE (Touch Pad)
    0xa1, 0x01,                    // COLLECTION (Application)
    0x85, 0x01,                    //   REPORT_ID (1)
    0x05, 0x0d,                    //   USAGE_PAGE (Digitizers)
    0x09, 0x22,                    //   USAGE (Finger)
    0xa1, 0x02,                    //   COLLECTION (Logical)
    0x09, 0x42,                    //     USAGE (Tip Switch)
    0x15, 0x00,                    //     LOGICAL_MINIMUM (0)
    0x25, 0x01,                    //     LOGICAL_MAXIMUM (1)
    0x75, 0x01,                    //     REPORT_SIZE (1)
    0x95, 0x01,                    //     REPORT_COUNT (1)
    0x81, 0x02,                    //     INPUT (Data,Var,Abs)
    0x09, 0x32,                    //     USAGE (In Range)
    0x81, 0x02,                    //     INPUT (Data,Var,Abs)
    0x95, 0x06,                    //     REPORT_COUNT (6)
    0x81, 0x03,                    //     INPUT (Cnst,Var,Abs)
    0x05, 0x01,                    //     USAGE_PAGE (Generic Desktop)
    0x09, 0x30,                    //     USAGE (X)
    0x26, 0x00, 0x10,              //     LOGICAL_MAXIMUM (4096)
    0x75, 0x10,                    //     REPORT_SIZE (16)
    0x95, 0x01,                    //     REPORT_COUNT (1)
    0x81, 0x02,                    //     INPUT (Data,Var,Abs)
    0x09, 0x31,                    //     USAGE (Y)
    0x26, 0x00, 0x10,              //     LOGICAL_MAXIMUM (4096)
    0x81, 0x02,                    //     INPUT (Data,Var,Abs)
    0xc0,                          //   END_COLLECTION
    0x05, 0x0d,                    //   USAGE_PAGE (Digitizers)
    0x09, 0x54,                    //   USAGE (Contact Count)
    0x15, 0x00,                    //   LOGICAL_MINIMUM (0)
    0x25, 0x05,                    //   LOGICAL_MAXIMUM (5)
    0x75, 0x08,                    //   REPORT_SIZE (8)
    0x95, 0x01,                    //   REPORT_COUNT (1)
    0x81, 0x02,                    //   INPUT (Data,Var,Abs)
    0x05, 0x09,                    //   USAGE_PAGE (Button)
    0x09, 0x01,                    //   USAGE (Button 1)
    0x15, 0x00,                    //   LOGICAL_MINIMUM (0)
    0x25, 0x01,                    //   LOGICAL_MAXIMUM (1)
    0x75, 0x01,                    //   REPORT_SIZE (1)
    0x95, 0x01,                    //   REPORT_COUNT (1)
    0x81, 0x02,                    //   INPUT (Data,Var,Abs)
    0x75, 0x07,                    //   REPORT_SIZE (7)
    0x81, 0x03,                    //   INPUT (Cnst,Var,Abs)
    0xc0                           // END_COLLECTION
};

NTSTATUS DcVhfInitialize(PDC_DEVICE_CONTEXT Context)
{
    VHF_CONFIG config;
    NTSTATUS status;

    if (!Context || !Context->Device)
        return STATUS_INVALID_PARAMETER;
    if (Context->VhfStarted)
        return STATUS_SUCCESS;

    // Start Keyboard VHF
    VHF_CONFIG_INIT(
        &config,
        WdfDeviceWdmGetDeviceObject(Context->Device),
        sizeof(g_KeyboardHidDescriptor),
        (PUCHAR)g_KeyboardHidDescriptor);
    config.VhfClientContext = Context;

    status = VhfCreate(&config, &Context->KeyboardVhf);
    if (!NT_SUCCESS(status))
        goto fail;
    status = VhfStart(Context->KeyboardVhf);
    if (!NT_SUCCESS(status))
        goto fail;

    // Start Trackpad VHF
    VHF_CONFIG_INIT(
        &config,
        WdfDeviceWdmGetDeviceObject(Context->Device),
        sizeof(g_TrackpadHidDescriptor),
        (PUCHAR)g_TrackpadHidDescriptor);
    config.VhfClientContext = Context;

    status = VhfCreate(&config, &Context->TrackpadVhf);
    if (!NT_SUCCESS(status))
        goto fail;
    status = VhfStart(Context->TrackpadVhf);
    if (!NT_SUCCESS(status))
        goto fail;

    Context->VhfStarted = TRUE;
    return STATUS_SUCCESS;

fail:
    DcVhfTeardown(Context);
    return status;
}

VOID DcVhfTeardown(PDC_DEVICE_CONTEXT Context)
{
    if (!Context)
        return;

    if (Context->KeyboardVhf) {
        VhfDelete(Context->KeyboardVhf, TRUE);
        Context->KeyboardVhf = NULL;
    }

    if (Context->TrackpadVhf) {
        VhfDelete(Context->TrackpadVhf, TRUE);
        Context->TrackpadVhf = NULL;
    }

    Context->VhfStarted = FALSE;
}

NTSTATUS DcVhfDispatchReport(PDC_DEVICE_CONTEXT Context, const struct dchid_packet *Packet)
{
    HID_XFER_PACKET xfer;

    if (!Context || !Packet || !Packet->payload || Packet->payload_size == 0)
        return STATUS_INVALID_PARAMETER;

    // If packet is from report channel
    if (Packet->channel == DCHID_REPORT_CHANNEL) {
        RtlZeroMemory(&xfer, sizeof(xfer));
        xfer.reportBuffer = (PUCHAR)Packet->payload;
        xfer.reportBufferLen = (ULONG)Packet->payload_size;
        xfer.reportId = Packet->payload[0];

        // Route to keyboard if interface 1 or standard keyboard report size
        if (Packet->interface_id == 1 || Packet->payload_size == 8) {
            if (Context->KeyboardVhf)
                return VhfReadReportSubmit(Context->KeyboardVhf, &xfer);
        } else {
            // Route to precision touch pad
            if (Context->TrackpadVhf)
                return VhfReadReportSubmit(Context->TrackpadVhf, &xfer);
        }
    }

    return STATUS_SUCCESS;
}
