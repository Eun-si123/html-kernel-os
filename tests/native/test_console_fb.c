/* Host test of the exact freestanding framebuffer renderer. */
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include "console_fb.h"

#define W 640
#define H 480
#define PIXELS ((W) * (H) * 4)
static union {
    uint32_t alignment;
    uint8_t bytes[PIXELS + 16];
} memory;

#define CHECK(x) do { \
    if (!(x)) { \
        (void)fprintf(stderr, "framebuffer test line %d failed: %s\\n", __LINE__, #x); \
        return 1; \
    } \
} while (0)

static uint32_t pixel(uint64_t x, uint64_t y) {
    const volatile uint32_t *p = (const volatile uint32_t *)(const void *)
        (memory.bytes + (y * W + x) * 4);
    return *p;
}

int main(void) {
    const struct htmlk_fb_mode valid = {
        .address = memory.bytes, .width = W, .height = H,
        .pitch = W * 4, .bpp = 32, .memory_model = 1,
        .red_size = 8, .red_shift = 16,
        .green_size = 8, .green_shift = 8,
        .blue_size = 8, .blue_shift = 0
    };
    for (uint64_t i = PIXELS; i < PIXELS + 16; ++i) memory.bytes[i] = 0xa5;
    CHECK(htmlk_fb_init(&valid));
    CHECK(htmlk_fb_active());
    CHECK(pixel(0, 0) == UINT32_C(0x79edb5)); /* native green header */
    CHECK(pixel(0, 84) == UINT32_C(0x0c1414));
    const uint32_t bg = pixel(24, 84);
    htmlk_fb_putchar('H');
    CHECK(pixel(24, 84) != bg);
    htmlk_fb_putchar('i'); /* lowercase handled as uppercase glyph */
    CHECK(pixel(36, 84) != bg);
    htmlk_fb_putchar('\n');
    htmlk_fb_putchar('1');
    CHECK(pixel(28, 102) != bg);
    htmlk_fb_putchar('\r');
    htmlk_fb_putchar(0xff); /* UTF-8 bytes render replacement glyph */
    for (uint64_t i = PIXELS; i < PIXELS + 16; ++i) CHECK(memory.bytes[i] == 0xa5);

    struct htmlk_fb_mode invalid = valid;
    invalid.pitch = W * 4 - 4;
    CHECK(!htmlk_fb_init(&invalid) && !htmlk_fb_active());
    htmlk_fb_putchar('X'); /* inactive must be a no-op */
    invalid = valid; invalid.bpp = 24;
    CHECK(!htmlk_fb_init(&invalid));
    invalid = valid; invalid.memory_model = 0;
    CHECK(!htmlk_fb_init(&invalid));
    invalid = valid; invalid.width = 4097;
    CHECK(!htmlk_fb_init(&invalid));
    invalid = valid; invalid.height = 0;
    CHECK(!htmlk_fb_init(&invalid));
    invalid = valid; invalid.red_shift = 8; /* masks overlap */
    CHECK(!htmlk_fb_init(&invalid));
    invalid = valid; invalid.address = memory.bytes + 1;
    CHECK(!htmlk_fb_init(&invalid));
    invalid = valid; invalid.address = 0;
    CHECK(!htmlk_fb_init(&invalid));
    CHECK(!htmlk_fb_init(0));
    for (uint64_t i = PIXELS; i < PIXELS + 16; ++i) CHECK(memory.bytes[i] == 0xa5);
    CHECK(htmlk_fb_init(&valid)); /* clean reinitialization restores output */
    CHECK(htmlk_fb_active());
    (void)puts("M3 NATIVE FRAMEBUFFER GLYPH AND BOUNDS PASS");
    return 0;
}
