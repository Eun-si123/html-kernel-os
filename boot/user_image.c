#include "user_image.h"

uint32_t htmlk_hke_fnv1a(const uint8_t *bytes, size_t length) {
    if (bytes == 0 && length != 0) return 0;
    uint32_t hash = UINT32_C(2166136261);
    for (size_t i = 0; i < length; ++i) {
        hash ^= bytes[i];
        hash *= UINT32_C(16777619);
    }
    return hash;
}

static uint32_t read_le32(const uint8_t *bytes) {
    return (uint32_t)bytes[0] | ((uint32_t)bytes[1] << 8) |
           ((uint32_t)bytes[2] << 16) | ((uint32_t)bytes[3] << 24);
}

bool htmlk_hke_validate(const uint8_t *image, size_t length,
                        struct htmlk_hke_program *result) {
    if (result != 0) {
        result->code_length = 0;
        result->entry_offset = 0;
    }
    if (image == 0 || result == 0 || length < HTMLK_HKE_HEADER_BYTES ||
        length > 4096 || image[0] != 'H' || image[1] != 'K' ||
        image[2] != 'E' || image[3] != 'X' ||
        image[4] != 1 || image[5] != HTMLK_HKE_HEADER_BYTES ||
        image[6] != 0 || image[7] != 0) return false;
    const uint32_t entry = read_le32(image + 8);
    const uint32_t code_bytes = read_le32(image + 12);
    const uint32_t checksum = read_le32(image + 16);
    for (size_t i = 20; i < HTMLK_HKE_HEADER_BYTES; ++i)
        if (image[i] != 0) return false;
    if (entry != 0 || code_bytes < 1U ||
        code_bytes > HTMLK_HKE_MAX_CODE_BYTES ||
        code_bytes != length - HTMLK_HKE_HEADER_BYTES ||
        checksum != htmlk_hke_fnv1a(image + HTMLK_HKE_HEADER_BYTES,
                                   code_bytes)) return false;
    result->code_length = code_bytes;
    result->entry_offset = entry;
    return true;
}
