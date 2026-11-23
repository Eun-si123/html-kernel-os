#include "task_model.h"
void htmlk_task_model_init(struct htmlk_task_model *model) {
    if (model == 0) return;
    for (unsigned i = 0; i < HTMLK_M4_MAX_TASKS; ++i)
        model->state[i] = HTMLK_TASK_EMPTY;
}
bool htmlk_task_create(struct htmlk_task_model *model, unsigned id) {
    if (model == 0 || id >= HTMLK_M4_MAX_TASKS ||
        model->state[id] != HTMLK_TASK_EMPTY) return false;
    model->state[id] = HTMLK_TASK_READY;
    return true;
}
int htmlk_task_next(const struct htmlk_task_model *model, unsigned last) {
    if (model == 0 || last >= HTMLK_M4_MAX_TASKS) return -1;
    for (unsigned step = 1; step <= HTMLK_M4_MAX_TASKS; ++step) {
        unsigned id = (last + step) % HTMLK_M4_MAX_TASKS;
        if (model->state[id] == HTMLK_TASK_READY) return (int)id;
    }
    return -1;
}
bool htmlk_task_run(struct htmlk_task_model *model, unsigned id) {
    if (model == 0 || id >= HTMLK_M4_MAX_TASKS ||
        model->state[id] != HTMLK_TASK_READY) return false;
    model->state[id] = HTMLK_TASK_RUNNING;
    return true;
}
bool htmlk_task_yield_state(struct htmlk_task_model *model, unsigned id) {
    if (model == 0 || id >= HTMLK_M4_MAX_TASKS ||
        model->state[id] != HTMLK_TASK_RUNNING) return false;
    model->state[id] = HTMLK_TASK_READY;
    return true;
}
bool htmlk_task_complete(struct htmlk_task_model *model, unsigned id) {
    if (model == 0 || id >= HTMLK_M4_MAX_TASKS ||
        model->state[id] != HTMLK_TASK_RUNNING) return false;
    model->state[id] = HTMLK_TASK_DONE;
    return true;
}
bool htmlk_task_all_done(const struct htmlk_task_model *model) {
    if (model == 0) return false;
    for (unsigned i = 0; i < HTMLK_M4_MAX_TASKS; ++i)
        if (model->state[i] != HTMLK_TASK_DONE) return false;
    return true;
}
