#ifndef HTMLK_M5_USER_TIMEOUT_H
#define HTMLK_M5_USER_TIMEOUT_H
#include "user_preempt_frame.h"
#include <stdbool.h>
#include <stdint.h>

/* Actual local x2APIC timer: active only while one Ring3 HKEX task runs. */
void htmlk_m5_timeout_start(void);
void htmlk_m5_timeout_stop(void);
struct htmlk_m4_d1_irq_frame *htmlk_m4_d1_on_irq(
    struct htmlk_m4_d1_irq_frame *frame);
#endif
