#include "user_text_policy.h"
#include "user_pages.h"
#include <stdint.h>
#include <assert.h>
int main(void) {
    const uint64_t base = HTMLK_M4_USER_BASE;
    assert(htmlk_m5_user_text_range(base,1,1));
    assert(htmlk_m5_user_text_range(base+16,20,36));
    assert(htmlk_m5_user_text_range(base+40,96,136));
    assert(!htmlk_m5_user_text_range(base+1,1,1));
    assert(!htmlk_m5_user_text_range(base+16,21,36));
    assert(!htmlk_m5_user_text_range(base,0,36));
    assert(!htmlk_m5_user_text_range(base,97,100));
    assert(!htmlk_m5_user_text_range(base,1,0));
    assert(!htmlk_m5_user_text_range(base,1,4096));
    assert(!htmlk_m5_user_text_range(base-1,1,30));
    assert(!htmlk_m5_user_text_range(UINT64_MAX-1,10,4090));
    assert(!htmlk_m5_user_text_range(0,12,200));
    assert(!htmlk_m5_user_text_range(HTMLK_M4_USER_STACK-32,8,4090));
    return 0;
}
