#ifndef HTMLK_TASK_MODEL_H
#define HTMLK_TASK_MODEL_H
#include <stdbool.h>
/* M4-A: bounded cooperative kernel tasks; neither user-mode nor preemption. */
#define HTMLK_M4_MAX_TASKS 2U
enum htmlk_task_state { HTMLK_TASK_EMPTY, HTMLK_TASK_READY,
                        HTMLK_TASK_RUNNING, HTMLK_TASK_DONE };
struct htmlk_task_model {
    enum htmlk_task_state state[HTMLK_M4_MAX_TASKS];
};
void htmlk_task_model_init(struct htmlk_task_model *model);
bool htmlk_task_create(struct htmlk_task_model *model, unsigned id);
int htmlk_task_next(const struct htmlk_task_model *model, unsigned last);
bool htmlk_task_run(struct htmlk_task_model *model, unsigned id);
bool htmlk_task_yield_state(struct htmlk_task_model *model, unsigned id);
bool htmlk_task_complete(struct htmlk_task_model *model, unsigned id);
bool htmlk_task_all_done(const struct htmlk_task_model *model);
#endif
