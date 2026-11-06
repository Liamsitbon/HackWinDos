"""Exercise the actual input-free viewer layout with sanitizers, not a mirror."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReportPagesTests(unittest.TestCase):
    def test_exact_width_crlf_wrapping_and_repeated_pages(self):
        harness = r'''
#include <assert.h>
#include <string.h>
#include "report-pages.h"
static unsigned short text[256], cells[256];
static void set(const char *s) {
    unsigned n = 0;
    while (*s) text[n++] = (unsigned char)*s++;
    text[n] = 0;
    for (n = 0; n < 256; ++n) cells[n] = ' ';
}
int main(void) {
    set("1234\r\n5678\r\nZ");
    unsigned off = report_page(text, 13, 0, cells, 4, 2);
    assert(off == 12);
    for (unsigned i = 0; i < 8; ++i) assert(cells[i] == "12345678"[i]);
    for (unsigned i = 0; i < 256; ++i) cells[i] = ' ';
    assert(report_page(text, 13, off, cells, 4, 2) == 13);
    assert(cells[0] == 'Z');
    set("ABCDEFGHIJK");
    off = report_page(text, 11, 0, cells, 4, 2);
    assert(off == 8);
    for (unsigned i = 0; i < 8; ++i) assert(cells[i] == 'A' + i);
    assert(report_page(text, 11, off, cells, 4, 2) == 11);
    assert(cells[0] == 'I' && cells[1] == 'J' && cells[2] == 'K');
    set("\nA\tB\n\nC");
    off = report_page(text, 8, 0, cells, 4, 2);
    assert(off == 5);
    assert(cells[0] == ' ' && cells[4] == 'A' && cells[5] == ' ' && cells[6] == 'B');
    assert(report_page(text, 8, off, cells, 0, 2) == off);
    assert(report_page(text, 8, off, cells, 4, 0) == off);
    /* Unicode is preserved; the renderer must not drop status/error digits. */
    text[0] = 0x05d0; text[1] = '4'; text[2] = '3';
    assert(report_page(text, 3, 0, cells, 2, 1) == 2);
    assert(cells[0] == 0x05d0 && cells[1] == '4');
    assert(report_page(text, 3, 2, cells, 2, 1) == 3 && cells[0] == '3');
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'layout.c'; binary = Path(tmp)/'layout'
            source.write_text(harness)
            subprocess.run(['clang', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                            '-I', str(ROOT/'tools/winpe'), str(source), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
