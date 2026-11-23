/* Original five-by-seven ASCII bitmaps; scaled to 10x14 logical pixels.
 * The Limine framebuffer is direct-mapped, not a browser-side overlay.
 */
#include "console_fb.h"
#include <stdint.h>

enum { FONT_W = 5, FONT_H = 7, FONT_SCALE = 2,
       CELL_W = 12, CELL_H = 18, MARGIN_X = 24, BODY_Y = 84 };

struct glyph {
    uint8_t code;
    uint8_t rows[FONT_H];
};

static const struct glyph font[] = {
    {48, {0x0e, 0x13, 0x15, 0x15, 0x19, 0x11, 0x0e}},
    {49, {0x04, 0x0c, 0x04, 0x04, 0x04, 0x04, 0x0e}},
    {50, {0x0e, 0x11, 0x01, 0x06, 0x08, 0x10, 0x1f}},
    {51, {0x1e, 0x01, 0x01, 0x0e, 0x01, 0x01, 0x1e}},
    {52, {0x02, 0x06, 0x0a, 0x12, 0x1f, 0x02, 0x02}},
    {53, {0x1f, 0x10, 0x10, 0x1e, 0x01, 0x01, 0x1e}},
    {54, {0x0f, 0x10, 0x10, 0x1e, 0x11, 0x11, 0x0e}},
    {55, {0x1f, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08}},
    {56, {0x0e, 0x11, 0x11, 0x0e, 0x11, 0x11, 0x0e}},
    {57, {0x0e, 0x11, 0x11, 0x0f, 0x01, 0x01, 0x1e}},
    {32, {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00}},
    {65, {0x0e, 0x11, 0x11, 0x1f, 0x11, 0x11, 0x11}},
    {66, {0x1e, 0x11, 0x11, 0x1e, 0x11, 0x11, 0x1e}},
    {67, {0x0f, 0x10, 0x10, 0x10, 0x10, 0x10, 0x0f}},
    {68, {0x1e, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1e}},
    {69, {0x1f, 0x10, 0x10, 0x1e, 0x10, 0x10, 0x1f}},
    {70, {0x1f, 0x10, 0x10, 0x1e, 0x10, 0x10, 0x10}},
    {71, {0x0f, 0x10, 0x10, 0x17, 0x11, 0x11, 0x0f}},
    {72, {0x11, 0x11, 0x11, 0x1f, 0x11, 0x11, 0x11}},
    {73, {0x1f, 0x04, 0x04, 0x04, 0x04, 0x04, 0x1f}},
    {74, {0x07, 0x02, 0x02, 0x02, 0x12, 0x12, 0x0c}},
    {75, {0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11}},
    {76, {0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1f}},
    {77, {0x11, 0x1b, 0x15, 0x15, 0x11, 0x11, 0x11}},
    {78, {0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11}},
    {79, {0x0e, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0e}},
    {80, {0x1e, 0x11, 0x11, 0x1e, 0x10, 0x10, 0x10}},
    {81, {0x0e, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0d}},
    {82, {0x1e, 0x11, 0x11, 0x1e, 0x14, 0x12, 0x11}},
    {83, {0x0f, 0x10, 0x10, 0x0e, 0x01, 0x01, 0x1e}},
    {84, {0x1f, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04}},
    {85, {0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0e}},
    {86, {0x11, 0x11, 0x11, 0x11, 0x11, 0x0a, 0x04}},
    {87, {0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0a}},
    {88, {0x11, 0x11, 0x0a, 0x04, 0x0a, 0x11, 0x11}},
    {89, {0x11, 0x11, 0x0a, 0x04, 0x04, 0x04, 0x04}},
    {90, {0x1f, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1f}},
    {33, {0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04}},
    {63, {0x0e, 0x11, 0x01, 0x02, 0x04, 0x00, 0x04}},
    {46, {0x00, 0x00, 0x00, 0x00, 0x00, 0x06, 0x06}},
    {44, {0x00, 0x00, 0x00, 0x00, 0x06, 0x06, 0x04}},
    {58, {0x00, 0x04, 0x04, 0x00, 0x04, 0x04, 0x00}},
    {59, {0x00, 0x04, 0x04, 0x00, 0x04, 0x04, 0x08}},
    {45, {0x00, 0x00, 0x00, 0x1f, 0x00, 0x00, 0x00}},
    {95, {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1f}},
    {47, {0x01, 0x01, 0x02, 0x04, 0x08, 0x10, 0x10}},
    {92, {0x10, 0x10, 0x08, 0x04, 0x02, 0x01, 0x01}},
    {43, {0x00, 0x04, 0x04, 0x1f, 0x04, 0x04, 0x00}},
    {61, {0x00, 0x1f, 0x00, 0x1f, 0x00, 0x00, 0x00}},
    {40, {0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02}},
    {41, {0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08}},
    {91, {0x0e, 0x08, 0x08, 0x08, 0x08, 0x08, 0x0e}},
    {93, {0x0e, 0x02, 0x02, 0x02, 0x02, 0x02, 0x0e}},
    {60, {0x02, 0x04, 0x08, 0x10, 0x08, 0x04, 0x02}},
    {62, {0x08, 0x04, 0x02, 0x01, 0x02, 0x04, 0x08}},
    {42, {0x00, 0x15, 0x0e, 0x1f, 0x0e, 0x15, 0x00}},
    {35, {0x0a, 0x0a, 0x1f, 0x0a, 0x1f, 0x0a, 0x0a}},
    {37, {0x19, 0x1a, 0x02, 0x04, 0x08, 0x0b, 0x13}},
    {38, {0x0c, 0x12, 0x12, 0x0c, 0x15, 0x12, 0x0d}},
    {64, {0x0e, 0x11, 0x17, 0x15, 0x17, 0x10, 0x0f}},
    {39, {0x04, 0x04, 0x02, 0x00, 0x00, 0x00, 0x00}},
    {34, {0x0a, 0x0a, 0x00, 0x00, 0x00, 0x00, 0x00}},
    {124, {0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04}},
};
static const struct glyph fallback = {63, {14, 17, 1, 2, 4, 0, 4}};

struct fb_state {
    volatile uint8_t *pixels;
    uint64_t width, height, pitch, x, y;
    uint32_t fore, muted, bg, accent;
    uint64_t glyphs;
    uint64_t probe_offset;
    uint32_t probe_value;
    bool probe_written;
    bool active;
};

static struct fb_state fb;
#ifdef HTMLK_FB_TEST
static void report(const char *message);
#endif

static void paint(uint64_t x, uint64_t y, uint32_t color) {
    volatile uint32_t *pixel = (volatile uint32_t *)(void *)
        (fb.pixels + y * fb.pitch + x * 4);
    *pixel = color;
}

static uint32_t rgb(uint8_t red, uint8_t green, uint8_t blue,
                    const struct htmlk_fb_mode *mode) {
    return ((uint32_t)red << mode->red_shift) |
           ((uint32_t)green << mode->green_shift) |
           ((uint32_t)blue << mode->blue_shift);
}

static const struct glyph *lookup(uint8_t ch) {
    if (ch >= 'a' && ch <= 'z') ch = (uint8_t)(ch - 'a' + 'A');
    for (uint64_t i = 0; i < sizeof(font) / sizeof(font[0]); ++i) {
        if (font[i].code == ch) return &font[i];
    }
    return &fallback;
}

static void draw(uint8_t ch, uint64_t x, uint64_t y,
                 uint32_t foreground, bool record) {
    const struct glyph *glyph = lookup(ch);
    for (uint64_t row = 0; row < FONT_H; ++row) {
        for (uint64_t col = 0; col < FONT_W; ++col) {
            if ((glyph->rows[row] & (uint8_t)(1U << (FONT_W - 1 - col))) == 0)
                continue;
            for (uint64_t dy = 0; dy < FONT_SCALE; ++dy) {
                for (uint64_t dx = 0; dx < FONT_SCALE; ++dx) {
                    uint64_t px = x + col * FONT_SCALE + dx;
                    uint64_t py = y + row * FONT_SCALE + dy;
                    if (px >= fb.width || py >= fb.height) continue;
                    paint(px, py, foreground);
                    if (record) {
                        fb.probe_offset = py * fb.pitch + px * 4;
                        fb.probe_value = foreground;
                        fb.probe_written = true;
                    }
                }
            }
        }
    }
}

static void label(const char *text, uint64_t x, uint64_t y, uint32_t color) {
    while (*text != 0 && x + CELL_W < fb.width - MARGIN_X) {
        draw((uint8_t)*text++, x, y, color, false);
        x += CELL_W;
    }
}

static void fill_body(void) {
    for (uint64_t y = BODY_Y; y < fb.height; ++y) {
        for (uint64_t x = 0; x < fb.width; ++x) {
            paint(x, y, fb.bg);
        }
    }
}

bool htmlk_fb_init(const struct htmlk_fb_mode *mode) {
#ifdef HTMLK_FB_TEST
    report("FB_DRIVER_ENTRY\n");
#endif
    fb.active = false;
    fb.pixels = 0;
    fb.glyphs = 0;
    fb.probe_written = false;
    if (mode == 0 || mode->address == 0 ||
        mode->memory_model != 1 || mode->bpp != 32 ||
        mode->width < 320 || mode->width > 4096 ||
        mode->height < 200 || mode->height > 2160 ||
        mode->width > UINT64_MAX / 4 ||
        mode->pitch < mode->width * 4 || mode->pitch > 32768 ||
        (mode->pitch & 3) != 0 ||
        ((uintptr_t)mode->address & 3) != 0 ||
        mode->red_size != 8 || mode->green_size != 8 || mode->blue_size != 8 ||
        mode->red_shift > 24 || mode->green_shift > 24 ||
        mode->blue_shift > 24) {
        return false;
    }
    const uint32_t r = UINT32_C(0xff) << mode->red_shift;
    const uint32_t g = UINT32_C(0xff) << mode->green_shift;
    const uint32_t b = UINT32_C(0xff) << mode->blue_shift;
    if ((r & g) || (g & b) || (b & r)) return false;
    if (mode->pitch > UINT64_MAX / mode->height ||
        mode->pitch * mode->height > 96 * UINT64_C(1024) * 1024) return false;
    const uintptr_t address = (uintptr_t)mode->address;
    if (mode->pitch * mode->height > UINTPTR_MAX - address) return false;

#ifdef HTMLK_FB_TEST
    report("FB_DRIVER_VALID_MODE\n");
#endif
    fb.pixels = mode->address;
    fb.width = mode->width;
    fb.height = mode->height;
    fb.pitch = mode->pitch;
    fb.bg = rgb(12, 20, 20, mode);
    fb.fore = rgb(224, 240, 228, mode);
    fb.muted = rgb(127, 171, 160, mode);
    fb.accent = rgb(121, 237, 181, mode);
    fb.x = MARGIN_X;
    fb.y = BODY_Y;
    fb.active = true;

#ifdef HTMLK_FB_TEST
    report("FB_DRIVER_CLEAR_START\n");
#endif
    for (uint64_t y = 0; y < fb.height; ++y) {
        for (uint64_t x = 0; x < fb.width; ++x) paint(x, y, fb.bg);
    }
#ifdef HTMLK_FB_TEST
    report("FB_DRIVER_CLEAR_DONE\n");
#endif
    for (uint64_t y = 0; y < 4; ++y) {
        for (uint64_t x = 0; x < fb.width; ++x) paint(x, y, fb.accent);
    }
    label("HTML KERNEL OS", MARGIN_X, 18, fb.fore);
    label("NATIVE FRAMEBUFFER / SOURCE DRIVEN", MARGIN_X, 45, fb.muted);
    for (uint64_t x = MARGIN_X; x + MARGIN_X < fb.width; ++x) {
        paint(x, 70, fb.muted);
    }
#ifdef HTMLK_FB_TEST
    report("FB_DRIVER_DRAW_DONE\n");
#endif
    return true;
}

bool htmlk_fb_active(void) { return fb.active; }

static void newline(void) {
    fb.x = MARGIN_X;
    fb.y += CELL_H;
    if (fb.y + FONT_H * FONT_SCALE >= fb.height - 12) {
        fill_body();
        fb.y = BODY_Y;
        fb.probe_written = false; /* old pixel was erased */
    }
}

void htmlk_fb_putchar(uint8_t ch) {
    if (!fb.active) return;
    if (ch == '\r') return;
    if (ch == '\n') {
        newline();
        return;
    }
    if (ch == '\t') ch = ' ';
    if (fb.x + CELL_W + MARGIN_X > fb.width) newline();
    if (ch >= 128 || ch < 32) ch = '?';
    draw(ch, fb.x, fb.y, fb.fore, true);
    fb.x += CELL_W;
    ++fb.glyphs;
}

#ifdef HTMLK_FB_TEST
static void report(const char *message) {
    while (*message) {
        const uint8_t b = (uint8_t)*message++;
        __asm__ volatile ("outb %0, %1" : :
                          "a"(b), "Nd"((unsigned short)0xe9));
    }
}

void htmlk_fb_verify_probe(void) {
    bool correct = fb.active && fb.glyphs != 0 && fb.probe_written;
    if (correct) {
        volatile uint32_t *actual = (volatile uint32_t *)(void *)
            (fb.pixels + fb.probe_offset);
        correct = *actual == fb.probe_value;
    }
    if (correct) {
        report("FB_PIXELS_OK\n");
    } else {
        report("FB_PIXELS_FAIL\n");
        __asm__ volatile ("outb %0, %1" : :
                          "a"((unsigned char)0x14), "Nd"((unsigned short)0xf4));
        __asm__ volatile ("cli");
        for (;;) __asm__ volatile ("hlt");
    }
}
#endif
