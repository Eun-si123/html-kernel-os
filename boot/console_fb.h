/* Freestanding RGB framebuffer text console, no libc/heap/unsafe public pointer API. */
#ifndef HTMLK_FB_CONSOLE_H
#define HTMLK_FB_CONSOLE_H

#include <stdbool.h>
#include <stdint.h>

struct htmlk_fb_mode {
    volatile uint8_t *address;  /* trusted Limine-mapped pixel base */
    uint64_t width;
    uint64_t height;
    uint64_t pitch;
    uint16_t bpp;
    uint8_t memory_model;
    uint8_t red_size, red_shift;
    uint8_t green_size, green_shift;
    uint8_t blue_size, blue_shift;
};

/* Return false and disable output for missing/malformed/unsupported mode.
 * This never accesses a pixel if validation fails. An existing frame buffer
 * must remain valid for the lifetime of the console, as Limine guarantees. */
bool htmlk_fb_init(const struct htmlk_fb_mode *mode);
bool htmlk_fb_active(void);
void htmlk_fb_putchar(uint8_t ch);

/* Only compiled/used in the explicit QEMU framebuffer test build.
 * Writes an evidence marker to debugcon and signals a non-success QEMU exit
 * on absent framebuffer or mismatched on-device pixel readback. */
#ifdef HTMLK_FB_TEST
void htmlk_fb_verify_probe(void);
#endif

#endif
