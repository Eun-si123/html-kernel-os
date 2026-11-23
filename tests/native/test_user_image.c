#include "user_image.h"
#include <assert.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static void write_le32(uint8_t *out, uint32_t value) {
    for (unsigned i = 0; i < 4; ++i) out[i] = (uint8_t)(value >> (i*8U));
}

int main(void) {
    const uint8_t code[8] = {0x31,0xc0,0xcd,0x80,0x0f,0x0b,0x90,0x90};
    uint8_t image[HTMLK_HKE_HEADER_BYTES + sizeof(code)] = {0};
    memcpy(image,"HKEX",4);
    image[4] = 1; image[5] = HTMLK_HKE_HEADER_BYTES;
    write_le32(image+12, (uint32_t)sizeof(code));
    memcpy(image+HTMLK_HKE_HEADER_BYTES,code,sizeof(code));
    write_le32(image+16,htmlk_hke_fnv1a(code,sizeof(code)));
    struct htmlk_hke_program result = {999U,999U};
    assert(htmlk_hke_validate(image,sizeof(image),&result));
    assert(result.code_length == sizeof(code) && result.entry_offset == 0);
    assert(htmlk_hke_fnv1a(0, 0) == UINT32_C(2166136261));
    assert(htmlk_hke_fnv1a(0, 3) == 0);
    assert(!htmlk_hke_validate(0,sizeof(image),&result));
    assert(!htmlk_hke_validate(image,sizeof(image),0));
    assert(!htmlk_hke_validate(image,31U,&result));
    assert(!htmlk_hke_validate(image,sizeof(image)-1,&result));
    assert(!htmlk_hke_validate(image,sizeof(image)+1,&result));
    assert(result.code_length == 0 && result.entry_offset == 0);
    for (size_t i = 0; i < sizeof(image); ++i) {
        const uint8_t original=image[i];
        if (i >= 32U && i <= 39U) {
            image[i]^=0xffU;
            assert(!htmlk_hke_validate(image,sizeof(image),&result));
        } else if (i == 0U || i == 4U || i == 5U ||
                   (i>=6U && i<=7U) || (i>=8U && i<=19U) ||
                   (i>=20U && i<=31U)) {
            image[i]^=0x01U;
            assert(!htmlk_hke_validate(image,sizeof(image),&result));
        }
        image[i]=original;
    }
    assert(htmlk_hke_validate(image,sizeof(image),&result));
    write_le32(image+12,HTMLK_HKE_MAX_CODE_BYTES+1U);
    assert(!htmlk_hke_validate(image,sizeof(image),&result));
    write_le32(image+12,0);
    assert(!htmlk_hke_validate(image,sizeof(image),&result));
    write_le32(image+12,sizeof(code));
    assert(htmlk_hke_validate(image,sizeof(image),&result));
    puts("M5 HKEX NATIVE HEADER/HASH/SIZE/NEGATIVES PASS");
    return 0;
}
