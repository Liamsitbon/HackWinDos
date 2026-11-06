/* SPDX-License-Identifier: MIT
 * Input-free WinPE inventory viewer. No CRT, WDK, drivers or device changes.
 * Uses the documented Kernel32 console/file APIs; writes only its own console.
 */
#include "report-pages.h"
typedef unsigned long DWORD;
typedef unsigned short WCHAR;
typedef void *HANDLE;
typedef int BOOL;
typedef struct { short X, Y; } COORD;
typedef struct { short Left, Top, Right, Bottom; } SMALL_RECT;
typedef struct {
    COORD size, cursor; unsigned short attributes;
    SMALL_RECT window; COORD maximum;
} CONSOLE_SCREEN_BUFFER_INFO;
typedef struct { WCHAR character; unsigned short attributes; } CHAR_INFO;
#define API __declspec(dllimport)
API HANDLE __stdcall GetStdHandle(DWORD);
API BOOL __stdcall GetConsoleScreenBufferInfo(HANDLE, CONSOLE_SCREEN_BUFFER_INFO *);
API BOOL __stdcall WriteConsoleOutputW(HANDLE, const CHAR_INFO *, COORD, COORD, SMALL_RECT *);
API DWORD __stdcall GetEnvironmentVariableW(const WCHAR *, WCHAR *, DWORD);
API HANDLE __stdcall CreateFileW(const WCHAR *, DWORD, DWORD, void *, DWORD, DWORD, HANDLE);
API BOOL __stdcall ReadFile(HANDLE, void *, DWORD, DWORD *, void *);
API BOOL __stdcall CloseHandle(HANDLE);
API int __stdcall MultiByteToWideChar(unsigned int, DWORD, const char *, int, WCHAR *, int);
API void __stdcall Sleep(DWORD);
API __declspec(noreturn) void __stdcall ExitProcess(unsigned int);

static unsigned char bytes[65536];
static WCHAR text[65536], cells[120 * 40], path[512];
static CHAR_INFO screen[120 * 40];
static const WCHAR *files[] = {
    L"USB-COMPACT.txt", L"PROBLEM-COMPACT.txt", L"HID-COMPACT.txt", L"DISKS.txt"
};

static unsigned int append(WCHAR *out, unsigned int at, const WCHAR *value)
{
    while (*value) out[at++] = *value++;
    out[at] = 0;
    return at;
}

static void label(unsigned int row, unsigned int width, const WCHAR *value)
{
    unsigned int x = 0;
    while (*value && x < width) cells[row * width + x++] = *value++;
}

static unsigned int load(const WCHAR *name, int *truncated)
{
    DWORD size = GetEnvironmentVariableW(L"SystemDrive", path, 128), count = 0, extra = 0;
    HANDLE file;
    unsigned int n = 0;
    *truncated = 0;
    if (!size || size >= 128) return 0;
    size = append(path, size, L"\\J413Diagnostics\\");
    append(path, size, name);
    file = CreateFileW(path, 0x80000000UL, 3, 0, 3, 0x80, 0);
    if (file == (HANDLE)(long long)-1) return 0;
    if (!ReadFile(file, bytes, sizeof(bytes), &count, 0)) count = 0;
    /* Explicit truncation notice; the full original remains in the RAM log. */
    if (count == sizeof(bytes)) {
        unsigned char probe;
        if (!ReadFile(file, &probe, 1, &extra, 0)) extra = 1;
        *truncated = extra != 0;
    }
    CloseHandle(file);
    if (count >= 2 && bytes[0] == 0xff && bytes[1] == 0xfe) {
        for (DWORD i = 2; i + 1 < count; i += 2)
            text[n++] = (WCHAR)(bytes[i] | ((unsigned int)bytes[i + 1] << 8));
    } else if (count) {
        int converted = MultiByteToWideChar(1 /* CP_OEMCP */, 0, (const char *)bytes,
                                          (int)count, text, sizeof(text) / sizeof(text[0]));
        if (converted > 0) n = (unsigned int)converted;
    }
    return n;
}

void Entry(void)
{
    HANDLE console = GetStdHandle((DWORD)-11);
    CONSOLE_SCREEN_BUFFER_INFO info;
    unsigned int file_index = 0;
    for (;;) {
        unsigned int offset = 0, page = 1, length;
        int truncated;
        length = load(files[file_index], &truncated);
        if (!length) length = append(text, 0, L"File absent or unreadable. Other sections follow automatically.");
        do {
            unsigned int width, height, count, next, n;
            WCHAR number[12], reversed[12];
            COORD dimensions, origin = {0, 0};
            SMALL_RECT rectangle;
            if (!GetConsoleScreenBufferInfo(console, &info)) ExitProcess(2);
            width = (unsigned int)(info.window.Right - info.window.Left + 1);
            height = (unsigned int)(info.window.Bottom - info.window.Top + 1);
            if (width > 120) width = 120;
            if (height > 40) height = 40;
            if (width < 20 || height < 8) ExitProcess(3);
            count = width * height;
            for (n = 0; n < count; ++n) cells[n] = ' ';
            label(0, width, L"J413 INPUT REPORT - automatic pages every 12 seconds");
            label(1, width, files[file_index]);
            label(2, width, L"Page ");
            n = page;
            unsigned int digits = 0, out = 0;
            do { reversed[digits++] = (WCHAR)('0' + n % 10); n /= 10; } while (n);
            while (digits) number[out++] = reversed[--digits];
            number[out] = 0;
            for (n = 0; n < out && n + 5 < width; ++n) cells[2 * width + 5 + n] = number[n];
            next = report_page(text, length, offset, cells + 4 * width, width, height - 5);
            label(height - 1, width, truncated ? L"TRUNCATED at 64 KiB; full file remains in RAM. Pages repeat."
                                               : L"Photograph each page. No mouse or keyboard needed. Pages repeat.");
            for (n = 0; n < count; ++n) {
                screen[n].character = cells[n]; screen[n].attributes = 0x0f;
            }
            dimensions.X = (short)width; dimensions.Y = (short)height;
            rectangle = info.window;
            rectangle.Right = (short)(rectangle.Left + width - 1);
            rectangle.Bottom = (short)(rectangle.Top + height - 1);
            if (!WriteConsoleOutputW(console, screen, dimensions, origin, &rectangle)) ExitProcess(4);
            Sleep(12000);
            offset = next;
            ++page;
        } while (offset < length);
        file_index = (file_index + 1) % (sizeof(files) / sizeof(files[0]));
    }
}
