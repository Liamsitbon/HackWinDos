/* SPDX-License-Identifier: MIT
 * The actual Setup image has no timeout/ping. No CRT or driver dependency. */
__declspec(dllimport) void __stdcall Sleep(unsigned long milliseconds);
__declspec(dllimport) __declspec(noreturn) void __stdcall ExitProcess(unsigned int code);

void Entry(void)
{
    Sleep(30000);
    ExitProcess(0);
}
