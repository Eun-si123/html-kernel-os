#ifndef HTMLK_M5_USER_TEXT_POLICY_H
#define HTMLK_M5_USER_TEXT_POLICY_H
#include <stdbool.h>
#include <stdint.h>
/* Pure, host-testable check; caller also verifies active CPL3 frame/CR3/owner.
 * Accept only the exact read-only user executable page; no arbitrary copyin.
 */
enum { HTMLK_M5_USER_TEXT_MAX = 96 };
bool htmlk_m5_user_text_range(uint64_t start, uint64_t length,
                               uint64_t code_length);
#endif
