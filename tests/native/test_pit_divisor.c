#include "timer_irq.h"
#include <assert.h>
#include <stdio.h>
/* Pure arithmetic linked with a host variant compiled without privileged I/O. */
int main(void) {
    assert(htmlk_m4_pit_divisor(0) == 0);
    assert(htmlk_m4_pit_divisor(18) == 0);
    assert(htmlk_m4_pit_divisor(100) == 11931);
    assert(htmlk_m4_pit_divisor(1000) == 1193);
    assert(htmlk_m4_pit_divisor(1193183) == 0);
    puts("M4 PIT RATE VALIDATION PASS");
}
