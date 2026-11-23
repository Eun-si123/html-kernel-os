/* M5-B: real guest CPU 16550 UART RX; no host-simulated command delivery. */
#include "serial_command.h"
#include "romfs.h"
#ifdef HTMLK_M5_INTERACTIVE_RUN
#include "user_image.h"
#include "user_probe.h"
#endif
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
#ifdef HTMLK_M5_INTERACTIVE_RUN
/* Kernel syscall diagnostics route to COM1 as well as debugcon. */
void htmlk_m5_console_byte(uint8_t byte) { send(byte); }
#endif
static void send_text(const char *text) {
    while (*text) send((uint8_t)*text++);
}
#if defined(HTMLK_M5_INTERACTIVE_RUN) && defined(HTMLK_M5_USER_EXIT_STATUS)
static void send_exit_status(uint8_t status) {
    if (status == 0U) { send_text("M5_RUN_DONE\n"); return; }
    send_text("M5_RUN_EXIT_CODE=");
    uint8_t digits[3];
    unsigned length=0U;
    do {
        digits[length++] = (uint8_t)('0'+status%10U);
        status = (uint8_t)(status/10U);
    } while (status != 0U);
    while (length != 0U) send(digits[--length]);
    send((uint8_t)10U);
}
#endif
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

#ifdef HTMLK_M5_INTERACTIVE_RUN
void htmlk_m5_serial_console(void);
static const struct limine_memmap_response *program_map;
static const struct limine_hhdm_response *program_hhdm;
static void run_program(const char *path) {
    uint8_t image[4096];
    size_t length = 0;
    if (!htmlk_romfs_read(&htmlk_romfs_image, path, 0,
                          image, sizeof(image), &length)) {
        send_text("M5_ERR_NOT_FOUND\n");
        return;
    }
    struct htmlk_hke_program metadata = {0};
    if (!htmlk_hke_validate(image, length, &metadata)) {
        send_text("M5_ERR_BAD_EXEC\n");
        return;
    }
    send_text("M5_RUN_START "); send_text(path); send_text("\n");
    htmlk_m5_user_run(path, program_map, program_hhdm);
#ifdef HTMLK_M5_USER_FAULT_RECOVER
#ifdef HTMLK_M5_USER_TIMEOUT
    if (htmlk_m5_user_last_timed_out())
        send_text("M5_ERR_USER_TIMEOUT\n");
    else
#endif
    if (htmlk_m5_user_last_faulted())
        send_text("M5_ERR_USER_FAULT\n");
    else if (htmlk_m5_user_last_bad_syscall())
        send_text("M5_ERR_USER_SYSCALL\n");
    else
#endif
#ifdef HTMLK_M5_USER_EXIT_STATUS
        send_exit_status(htmlk_m5_user_last_exit_status());
#else
        send_text("M5_RUN_DONE\n");
#endif
}
void htmlk_m5_serial_console_run(const struct limine_memmap_response *map,
                                  const struct limine_hhdm_response *hhdm) {
    program_map = map;
    program_hhdm = hhdm;
    htmlk_m5_serial_console();
}
#endif
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
#ifdef HTMLK_M5_INTERACTIVE_RUN
                    send_text("M5_HELP help ls cat /path run /path exit\n");
#else
                    send_text("M5_HELP help ls cat /path exit\n");
#endif
                    break;
                case HTMLK_CONSOLE_LS:
                    for (size_t i = 0; i < htmlk_romfs_image.count; ++i) {
                        send_text("M5_FILE ");
                        send_text(htmlk_romfs_image.files[i].path);
                        send_text("\n");
                    }
                    break;
                case HTMLK_CONSOLE_CAT: cat(command.path); break;
#ifdef HTMLK_M5_INTERACTIVE_RUN
                case HTMLK_CONSOLE_RUN: run_program(command.path); break;
#endif
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
