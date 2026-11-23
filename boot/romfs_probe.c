/* M5-A opt-in real QEMU proof: read bytes embedded in the kernel ELF. */
#include "romfs.h"
#include <stdint.h>

static void send_byte(uint8_t byte) {
    __asm__ volatile ("outb %0,%1" : : "a"(byte), "Nd"((uint16_t)0xe9));
    __asm__ volatile ("outb %0,%1" : : "a"(byte), "Nd"((uint16_t)0x3f8));
}
static void send_string(const char *text) {
    while (*text) send_byte((uint8_t)*text++);
}
__attribute__((noreturn)) static void fail(void) {
    send_string("M5_ROMFS_FATAL\n");
#ifdef HTMLK_QEMU_TEST_EXIT
    __asm__ volatile ("outb %0,%1" : : "a"((uint8_t)0x1c), "Nd"((uint16_t)0xf4));
#endif
    for (;;) __asm__ volatile ("cli; hlt");
}
static void dump_file(const char *path) {
    size_t offset = 0;
    uint8_t chunk[13];
    for (;;) {
        size_t got = 0;
        if (!htmlk_romfs_read(&htmlk_romfs_image, path, offset, chunk,
                              sizeof(chunk), &got)) fail();
        if (got == 0) break;
        for (size_t i = 0; i < got; ++i) {
            /* The minimal boot console is text-only; reject control sequences. */
            if (chunk[i] != '\n' && (chunk[i] < 32U || chunk[i] > 126U)) fail();
            send_byte(chunk[i]);
        }
        offset += got;
    }
}
void htmlk_m5_romfs_probe(void) {
    if (!htmlk_romfs_validate(&htmlk_romfs_image)) fail();
    size_t got = 42;
    uint8_t sentinel = 0xa5;
    if (htmlk_romfs_read(&htmlk_romfs_image, "/../welcome.txt", 0,
                         &sentinel, 1, &got) || got != 0 || sentinel != 0xa5)
        fail();
    got = 42;
    if (htmlk_romfs_read(&htmlk_romfs_image, "/missing.txt", 0,
                         &sentinel, 1, &got) || got != 0 || sentinel != 0xa5)
        fail();
    send_string("M5_ROMFS_VALID\nM5_ROMFS_WELCOME_BEGIN\n");
    dump_file("/welcome.txt");
    send_string("M5_ROMFS_WELCOME_END\nM5_ROMFS_CONFIG_BEGIN\n");
    dump_file("/config/build.txt");
    send_string("M5_ROMFS_CONFIG_END\n");
#ifdef HTMLK_M5_ROMFS_NEGATIVE
    send_string("M5_ROMFS_DENIED\n");
    fail(); /* negative ISO MUST NOT execute generated HTML */
#endif
    send_string("M5_ROMFS_PASS\n");
}
