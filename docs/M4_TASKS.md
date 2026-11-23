# M4 Phase A — cooperative kernel task contexts

**Status: experimental implementation; verify evidence in PR/CI before promoting.**

This bounded x86-64 slice introduces two distinct ring-0 task stacks and
SysV AMD64 callee-saved register context switching. A fixed-state task model
enforces EMPTY -> READY -> RUNNING -> READY or DONE. A round-robin dispatcher
runs two independent kernel tasks, three rounds each. The tasks preserve
stack-local tokens across actual stack switches, then both terminate. An
opt-in negative probe rejects duplicate creation, out-of-range task IDs,
restarting terminated tasks, and invalid state transitions.

Run:

    python3 scripts/test_m4_tasks.py
    python3 scripts/build_boot.py --task-probe --out build/html-kernel-m4-tasks.iso

The QEMU oracle must observe alternating M4_TASK_A_0/B_0/.../A_2/B_2,
followed by M4_TASKS_DONE and then the HTML-derived kernel output.
The test also changes the HTML source and builds a distinct ISO, rejects
stale output, and compiles the pure C state model with GCC UBSan -O0/-O3.
--task-negative-test requires --task-probe. Default images are unchanged.

**Not proven:** preemption, timer IRQs, ring 3, protected page tables,
syscalls, process exit policies, stack guards, FPU/FS/GS context, SMP, TSS.RSP0
for privilege return, general kernel heap, real hardware, or user-program
isolation. Both task stacks share the same privileged address space and
control CPU only at explicit yields. M4 milestone completion REQUIRES
independently running user tasks plus forbidden memory access rejection.

Next phases: B — proper interrupt timer/IRQ accounting and yield decisions;
C — ring-3 GDT/IDT syscall entry with TSS.RSP0, separate user mappings;
D — negative read/write privilege fault controls and safe task cleanup.
