/* SPDX-License-Identifier: MIT
 * Device initialization, hardware prepare/release, and interrupt handlers for DockChannel.
 */
#include "dockchannel_windows.h"

static uint32_t DcRead32(void *context, uint32_t offset)
{
    PDC_DEVICE_CONTEXT dc = (PDC_DEVICE_CONTEXT)context;
    if (!dc || !dc->BaseAddress || offset + sizeof(uint32_t) > dc->MemoryLength)
        return 0;
    return READ_REGISTER_NOFENCE_ULONG((PULONG)(dc->BaseAddress + offset));
}

static void DcWrite32(void *context, uint32_t offset, uint32_t value)
{
    PDC_DEVICE_CONTEXT dc = (PDC_DEVICE_CONTEXT)context;
    if (!dc || !dc->BaseAddress || offset + sizeof(uint32_t) > dc->MemoryLength)
        return;
    WRITE_REGISTER_NOFENCE_ULONG((PULONG)(dc->BaseAddress + offset), value);
}

static void DcWrite8(void *context, uint32_t offset, uint8_t value)
{
    PDC_DEVICE_CONTEXT dc = (PDC_DEVICE_CONTEXT)context;
    if (!dc || !dc->BaseAddress || offset + sizeof(uint8_t) > dc->MemoryLength)
        return;
    WRITE_REGISTER_NOFENCE_UCHAR((PUCHAR)(dc->BaseAddress + offset), value);
}

NTSTATUS DcEvtDeviceAdd(
    _In_ WDFDRIVER Driver,
    _Inout_ PWDFDEVICE_INIT DeviceInit)
{
    WDF_OBJECT_ATTRIBUTES deviceAttributes;
    WDF_PNPPOWER_EVENT_CALLBACKS pnpPowerCallbacks;
    WDF_INTERRUPT_CONFIG interruptConfig;
    WDF_WORKITEM_CONFIG workItemConfig;
    WDF_OBJECT_ATTRIBUTES workItemAttributes;
    WDFDEVICE device;
    PDC_DEVICE_CONTEXT context;
    NTSTATUS status;

    UNREFERENCED_PARAMETER(Driver);

    WDF_PNPPOWER_EVENT_CALLBACKS_INIT(&pnpPowerCallbacks);
    pnpPowerCallbacks.EvtDevicePrepareHardware = DcEvtDevicePrepareHardware;
    pnpPowerCallbacks.EvtDeviceReleaseHardware = DcEvtDeviceReleaseHardware;
    pnpPowerCallbacks.EvtDeviceD0Entry = DcEvtDeviceD0Entry;
    pnpPowerCallbacks.EvtDeviceD0Exit = DcEvtDeviceD0Exit;
    WdfDeviceInitSetPnpPowerEventCallbacks(DeviceInit, &pnpPowerCallbacks);

    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(&deviceAttributes, DC_DEVICE_CONTEXT);

    status = WdfDeviceCreate(&DeviceInit, &deviceAttributes, &device);
    if (!NT_SUCCESS(status))
        return status;

    context = DcGetDeviceContext(device);
    RtlZeroMemory(context, sizeof(*context));
    context->Device = device;

    status = WdfSpinLockCreate(WDF_NO_OBJECT_ATTRIBUTES, &context->Lock);
    if (!NT_SUCCESS(status))
        return status;

    WDF_INTERRUPT_CONFIG_INIT(&interruptConfig, DcEvtInterruptIsr, DcEvtInterruptDpc);
    status = WdfInterruptCreate(device, &interruptConfig, WDF_NO_OBJECT_ATTRIBUTES, &context->Interrupt);
    if (!NT_SUCCESS(status))
        return status;

    WDF_WORKITEM_CONFIG_INIT(&workItemConfig, DcEvtWorkItem);
    WDF_OBJECT_ATTRIBUTES_INIT(&workItemAttributes);
    workItemAttributes.ParentObject = device;
    status = WdfWorkItemCreate(&workItemConfig, &workItemAttributes, &context->WorkItem);
    if (!NT_SUCCESS(status))
        return status;

    context->StreamBuffer = (PUCHAR)ExAllocatePool2(POOL_FLAG_NON_PAGED, DC_STREAM_BUF_SIZE, DC_WIN_POOL_TAG);
    if (!context->StreamBuffer)
        return STATUS_INSUFFICIENT_RESOURCES;

    dchid_stream_reset(&context->Stream, context->StreamBuffer, DC_STREAM_BUF_SIZE);

    context->Io.context = context;
    context->Io.read32 = DcRead32;
    context->Io.write32 = DcWrite32;
    context->Io.write8 = DcWrite8;
    context->Io.fifo_size = DC_FIFO_SIZE;

    return STATUS_SUCCESS;
}

NTSTATUS DcEvtDevicePrepareHardware(
    _In_ WDFDEVICE Device,
    _In_ WDFCMRESLIST ResourcesRaw,
    _In_ WDFCMRESLIST ResourcesTranslated)
{
    PDC_DEVICE_CONTEXT context = DcGetDeviceContext(Device);
    ULONG count = WdfCmResourceListGetCount(ResourcesTranslated);
    ULONG index;

    UNREFERENCED_PARAMETER(ResourcesRaw);

    for (index = 0; index < count; ++index) {
        PCM_PARTIAL_RESOURCE_DESCRIPTOR desc = WdfCmResourceListGetDescriptor(ResourcesTranslated, index);
        if (!desc)
            continue;
        if (desc->Type == CmResourceTypeMemory && context->BaseAddress == NULL) {
            context->BaseAddress = (PUCHAR)MmMapIoSpace(desc->u.Memory.Start, desc->u.Memory.Length, MmNonCached);
            context->MemoryLength = desc->u.Memory.Length;
        }
    }

    if (context->BaseAddress == NULL)
        return STATUS_DEVICE_CONFIGURATION_ERROR;

    return STATUS_SUCCESS;
}

NTSTATUS DcEvtDeviceReleaseHardware(
    _In_ WDFDEVICE Device,
    _In_ WDFCMRESLIST ResourcesTranslated)
{
    PDC_DEVICE_CONTEXT context = DcGetDeviceContext(Device);

    UNREFERENCED_PARAMETER(ResourcesTranslated);

    DcVhfTeardown(context);

    if (context->BaseAddress != NULL) {
        MmUnmapIoSpace(context->BaseAddress, context->MemoryLength);
        context->BaseAddress = NULL;
    }

    if (context->StreamBuffer != NULL) {
        ExFreePoolWithTag(context->StreamBuffer, DC_WIN_POOL_TAG);
        context->StreamBuffer = NULL;
    }

    return STATUS_SUCCESS;
}

NTSTATUS DcEvtDeviceD0Entry(
    _In_ WDFDEVICE Device,
    _In_ WDF_POWER_DEVICE_STATE PreviousState)
{
    PDC_DEVICE_CONTEXT context = DcGetDeviceContext(Device);
    UNREFERENCED_PARAMETER(PreviousState);

    // Initialize Virtual HID Framework interfaces
    return DcVhfInitialize(context);
}

NTSTATUS DcEvtDeviceD0Exit(
    _In_ WDFDEVICE Device,
    _In_ WDF_POWER_DEVICE_STATE TargetState)
{
    PDC_DEVICE_CONTEXT context = DcGetDeviceContext(Device);
    UNREFERENCED_PARAMETER(TargetState);

    DcVhfTeardown(context);
    return STATUS_SUCCESS;
}

BOOLEAN DcEvtInterruptIsr(
    _In_ WDFINTERRUPT Interrupt,
    _In_ ULONG MessageID)
{
    PDC_DEVICE_CONTEXT context = DcGetDeviceContext(WdfInterruptGetDevice(Interrupt));
    UNREFERENCED_PARAMETER(MessageID);

    WdfInterruptQueueDpcForIsr(Interrupt);
    return TRUE;
}

VOID DcEvtInterruptDpc(
    _In_ WDFINTERRUPT Interrupt,
    _In_ WDFOBJECT AssociatedObject)
{
    PDC_DEVICE_CONTEXT context = DcGetDeviceContext(WdfInterruptGetDevice(Interrupt));
    UNREFERENCED_PARAMETER(AssociatedObject);

    WdfWorkItemEnqueue(context->WorkItem);
}

VOID DcEvtWorkItem(
    _In_ WDFWORKITEM WorkItem)
{
    PDC_DEVICE_CONTEXT context = DcGetDeviceContext(WdfWorkItemGetParentObject(WorkItem));
    uint8_t temp[512];
    struct dc_result result;

    if (!context || !context->BaseAddress)
        return;

    // Drain FIFO
    do {
        result = dc_try_receive(&context->Io, temp, sizeof(temp), sizeof(temp));
        if (result.status == DC_COMPLETE || result.status == DC_PARTIAL) {
            size_t offset = 0;
            while (offset < result.transferred) {
                size_t consumed = 0;
                struct dchid_packet packet;
                enum dchid_status s = dchid_stream_feed(
                    &context->Stream,
                    temp + offset,
                    result.transferred - offset,
                    &consumed,
                    &packet);

                if (s == DCHID_OK && packet.consumed > 0) {
                    (void)DcVhfDispatchReport(context, &packet);
                    // The borrowed packet view has been consumed. The stream
                    // intentionally retains a complete frame until reset.
                    // Reset only this successful frame, never a latched error.
                    (void)dchid_stream_reset(&context->Stream,
                        context->StreamBuffer, DC_STREAM_BUF_SIZE);
                }

                if (consumed == 0)
                    break;
                offset += consumed;
            }
        }
    } while (result.status == DC_COMPLETE && result.transferred > 0);
}
