#include "user_text_policy.h"
#include "user_pages.h"
#include "user_image.h"

bool htmlk_m5_user_text_range(uint64_t start, uint64_t length,
                               uint64_t code_length) {
    if (code_length == 0U || code_length > HTMLK_HKE_MAX_CODE_BYTES ||
        length == 0U || length > HTMLK_M5_USER_TEXT_MAX ||
        start < HTMLK_M4_USER_BASE) return false;
    const uint64_t displacement = start - HTMLK_M4_USER_BASE;
    if (displacement >= code_length) return false;
    /* Prevent addition overflow before any kernel dereference. */
    return length <= code_length - displacement;
}
