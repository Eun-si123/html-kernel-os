/* M5-B: real guest CPU 16550 UART RX; no host-simulated command delivery. */
#include "serial_command.h"
#include "romfs.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum { UART_BASE = 0x3f8, UART_LSR = UART_BASE + 5,
       UART_DATA_READY = 1, UART_TX_READY = 0x20 };

static uint8_t in_byte(uint16_t port) {
    uint8_t value;
    __asm__ volatile ("inb %1, %0" : "=a"(value) : "Nd"(port));
    return value;
}
static void out_byte(uint16_t port, uint8_t value) {
    __asm__ volatile ("outb %0, %1" : : "a"(value), "Nd"(port));
}

__attribute__((noreturn)) static void serial_fatal(void) {
    const char *message = "M5_CONSOLE_FATAL\n";
    while (*message) out_byte(0xe9, (uint8_t)*message++);
#ifdef HTMLK_QEMU_TEST_EXIT
    out_byte(0xf4, 0x1d); /* expected non-success 59 */
#endif
    for (;;) __asm__ volatile ("cli; hlt");
}

static void send(uint8_t byte) {
    out_byte(0xe9, byte);
    for (unsigned int attempts = 0; attempts < 1000000U; ++attempts) {
        if ((in_byte(UART_LSR) & UART_TX_READY) != 0U) {
            out_byte(UART_BASE, byte);
            return;
        }
    }
    serial_fatal();
}
static void send_text(const char *text) {
    while (*text) send((uint8_t)*text++);
}
static void send_uart_echo(uint8_t byte) {
    for (unsigned int attempts = 0; attempts < 1000000U; ++attempts) {
        if ((in_byte(UART_LSR) & UART_TX_READY) != 0U) {
            out_byte(UART_BASE, byte);
            return;
        }
    }
    serial_fatal();
}
static void init_uart(void) {
    if (in_byte(UART_LSR) == 0xffU) serial_fatal();
    out_byte(UART_BASE + 1, 0U);    /* disable UART interrupts */
    out_byte(UART_BASE + 3, 0x80U); /* DLAB */
    out_byte(UART_BASE + 0, 1U);    /* 115200 baud divisor */
    out_byte(UART_BASE + 1, 0U);
    out_byte(UART_BASE + 3, 3U);    /* 8 data, no parity, 1 stop */
    out_byte(UART_BASE + 2, 0xc7U); /* enable FIFO and clear stale RX */
    out_byte(UART_BASE + 4, 3U);    /* DTR / RTS */
}

static void cat(const char *path) {
    size_t offset = 0, got = 0;
    uint8_t chunk[17];
    if (!htmlk_romfs_read(&htmlk_romfs_image, path, 0, chunk,
                          sizeof(chunk), &got)) {
        send_text("M5_ERR_NOT_FOUND\n");
        return;
    }
    send_text("M5_CAT_BEGIN "); send_text(path); send_text("\n");
    for (;;) {
        if (!htmlk_romfs_read(&htmlk_romfs_image, path, offset,
                              chunk, sizeof(chunk), &got)) serial_fatal();
        if (got == 0) break;
        for (size_t i = 0; i < got; ++i) {
            if (chunk[i] != '\n' && (chunk[i] < 32U || chunk[i] > 126U)) {
                send_text("\nM5_ERR_BINARY_UNSUPPORTED\n");
                return;
            }
            send(chunk[i]);
        }
        offset += got;
    }
    send_text("M5_CAT_END\n");
}

void htmlk_m5_serial_console(void) {
    if (!htmlk_romfs_validate(&htmlk_romfs_image)) serial_fatal();
    init_uart();
    send_text("M5_CONSOLE_READY\nM5_PROMPT> ");
    struct htmlk_console_line line;
    htmlk_console_line_clear(&line);
    for (;;) {
        const uint8_t status = in_byte(UART_LSR);
        if ((status & UART_DATA_READY) == 0) {
            __asm__ volatile ("pause");
            continue;
        }
        if ((status & 0x1eU) != 0U) {
            (void)in_byte(UART_BASE); /* consume corrupt UART byte */
            line.invalid = true;
            continue;
        }
        uint8_t byte = in_byte(UART_BASE);
        enum htmlk_console_line_event event = htmlk_console_line_feed(&line, byte);
        if (byte == '\n' || byte == '\r') send_uart_echo('\n');
        else if (byte == 8 || byte == 127) {
            send_uart_echo(8); send_uart_echo(' '); send_uart_echo(8);
        } else if (byte >= 32 && byte <= 126 && !line.invalid) send_uart_echo(byte);
        if (event == HTMLK_CONSOLE_WAIT) continue;
        if (event == HTMLK_CONSOLE_INVALID) {
            send_text("M5_ERR_INVALID_LINE\n");
        } else {
            const struct htmlk_console_command command = htmlk_console_parse(line.bytes);
            switch (command.kind) {
                case HTMLK_CONSOLE_HELP:
                    send_text("M5_HELP help ls cat /path exit\n"); break;
                case HTMLK_CONSOLE_LS:
                    for (size_t i = 0; i < htmlk_romfs_image.count; ++i) {
                        send_text("M5_FILE ");
                        send_text(htmlk_romfs_image.files[i].path);
                        send_text("\n");
                    }
                    break;
                case HTMLK_CONSOLE_CAT: cat(command.path); break;
                case HTMLK_CONSOLE_BAD_PATH:
                    send_text("M5_ERR_INVALID_PATH\n"); break;
                case HTMLK_CONSOLE_UNKNOWN:
                    send_text("M5_ERR_UNKNOWN_COMMAND\n"); break;
                case HTMLK_CONSOLE_EXIT:
                    send_text("M5_CONSOLE_EXIT\n"); return;
                default: serial_fatal();
            }
        }
        htmlk_console_line_clear(&line);
        send_text("M5_PROMPT> ");
    }
}
