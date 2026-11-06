/* SPDX-License-Identifier: MIT
 * Bounded UTF-16 page layout, shared with the host regression harness. */
static unsigned int report_page(const unsigned short *text, unsigned int length,
                               unsigned int offset, unsigned short *cells,
                               unsigned int columns, unsigned int rows)
{
    unsigned int row = 0, column = 0;
    if (!columns || !rows) return offset;
    while (offset < length && row < rows) {
        unsigned short ch = text[offset++];
        if (ch == '\r') continue;
        if (ch == '\n') { ++row; column = 0; continue; }
        /* Delay wrapping until the next printable character. Otherwise a
         * newline following an exactly full row introduces an extra blank row. */
        if (column == columns) {
            ++row; column = 0;
            if (row == rows) return offset - 1;
        }
        cells[row * columns + column++] = ch == '\t' ? ' ' : ch;
    }
    return offset;
}
