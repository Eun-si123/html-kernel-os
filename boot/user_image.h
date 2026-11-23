#ifndef HTMLK_USER_IMAGE_H
#define HTMLK_USER_IMAGE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* M5-C1 deliberately simple position-independent flat x86-64 image.
 * Format is not ELF. No relocations or arbitrary entry offsets are accepted.
 * This is a byte-integrity/shape check, not a security signature or sandbox.
 */
enum { HTMLK_HKE_HEADER_BYTES = 32, HTMLK_HKE_MAX_CODE_BYTES = 4096 - 32 };
struct htmlk_hke_program {
    uint32_t code_length;
    uint32_t entry_offset;
};
uint32_t htmlk_hke_fnv1a(const uint8_t *bytes, size_t length);
bool htmlk_hke_validate(const uint8_t *image, size_t image_length,
                        struct htmlk_hke_program *result);
#endif
