#include "task_model.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
    struct htmlk_task_model m;
    htmlk_task_model_init(&m);
    assert(!htmlk_task_all_done(&m));
    assert(htmlk_task_next(&m, 1) == -1);
    assert(!htmlk_task_create(NULL, 0));
    assert(!htmlk_task_create(&m, 2));
    assert(htmlk_task_create(&m, 0));
    assert(htmlk_task_create(&m, 1));
    assert(!htmlk_task_create(&m, 0));
    assert(!htmlk_task_run(&m, 2));
    assert(htmlk_task_next(&m, 1) == 0);
    assert(htmlk_task_run(&m, 0));
    assert(!htmlk_task_run(&m, 0));
    assert(!htmlk_task_complete(&m, 1));
    assert(htmlk_task_yield_state(&m, 0));
    assert(!htmlk_task_yield_state(&m, 0));
    assert(htmlk_task_next(&m, 0) == 1);
    assert(htmlk_task_run(&m, 1));
    assert(htmlk_task_complete(&m, 1));
    assert(!htmlk_task_run(&m, 1));
    assert(htmlk_task_next(&m, 1) == 0);
    assert(htmlk_task_run(&m, 0));
    assert(htmlk_task_complete(&m, 0));
    assert(htmlk_task_all_done(&m));
    assert(htmlk_task_next(&m, 0) == -1);
    assert(!htmlk_task_complete(&m, 0));
    assert(!htmlk_task_yield_state(&m, 0));
    assert(!htmlk_task_create(&m, 1));
    puts("M4 MODEL TRANSITIONS + INVALID STATES PASS");
}
