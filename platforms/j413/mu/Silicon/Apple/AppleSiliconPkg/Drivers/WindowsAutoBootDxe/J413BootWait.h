/** @file Application-level discovery deadline; no hardware reset or busy stall.
    SPDX-License-Identifier: BSD-2-Clause-Patent **/
#ifndef J413_BOOT_WAIT_H
#define J413_BOOT_WAIT_H
#ifndef J413_BOOT_NEXT_OPTION
#define J413_BOOT_NEXT_OPTION J413NextEfiOption
#endif

STATIC EFI_STATUS J413WaitForBootOption(EFI_BOOT_MANAGER_LOAD_OPTION *Option)
{
  EFI_EVENT Events[2] = {NULL, NULL};
  EFI_STATUS Status = J413_BOOT_NEXT_OPTION(Option);
  EFI_STATUS Probe;
  UINTN Index;
  if (Status != EFI_NOT_FOUND) return Status;
  // Give the existing asynchronous USB bus timers a bounded discovery window.
  // The first event is the wall-clock deadline, so it wins over a pending retry.
  Probe = gBS->CreateEvent(EVT_TIMER, TPL_CALLBACK, NULL, NULL, &Events[0]);
  if (!EFI_ERROR(Probe)) Probe = gBS->CreateEvent(EVT_TIMER, TPL_CALLBACK, NULL, NULL, &Events[1]);
  if (!EFI_ERROR(Probe)) Probe = gBS->SetTimer(Events[0], TimerRelative, 100000000ULL);
  if (!EFI_ERROR(Probe)) Probe = gBS->SetTimer(Events[1], TimerPeriodic, 2000000ULL);
  if (EFI_ERROR(Probe)) {
    Print(L"UEFI USB: discovery timer unavailable: %r\r\n", Probe);
  } else {
    Print(L"UEFI USB: waiting up to 10 seconds for the exact ARM64 fallback loader\r\n");
    for (UINTN Attempt = 0; Attempt < 50; Attempt++) {
      Probe = gBS->WaitForEvent(2, Events, &Index);
      if (EFI_ERROR(Probe) || Index == 0) break;
      // The previous empty queue was consumed. Recheck newly published filesystems.
      mEfiScanned = FALSE;
#ifndef J413_DIRECT_SETUP_ONLY
      mEfiCount = 0;
#endif
      Status = J413_BOOT_NEXT_OPTION(Option);
      if (Status != EFI_NOT_FOUND) break;
    }
    if (EFI_ERROR(Probe)) Print(L"UEFI USB: discovery wait returned %r\r\n", Probe);
  }
  if (Events[1] != NULL) gBS->CloseEvent(Events[1]);
  if (Events[0] != NULL) gBS->CloseEvent(Events[0]);
  return Status;
}

STATIC VOID J413PauseFailureScreen(VOID)
{
  EFI_EVENT Event = NULL;
  UINTN Index;
  EFI_STATUS Status = gBS->CreateEvent(EVT_TIMER, TPL_CALLBACK, NULL, NULL, &Event);
  Print(L"UEFI USB: photograph this diagnostic screen; Shell continues in 30 seconds\r\n");
  if (!EFI_ERROR(Status)) {
    Status = gBS->SetTimer(Event, TimerRelative, 300000000ULL);
    if (!EFI_ERROR(Status)) gBS->WaitForEvent(1, &Event, &Index);
    gBS->CloseEvent(Event);
  }
}
#endif
