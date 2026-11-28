# M5-E3-O — legacy SSE state and floating-point fault containment

The single-active-app M5 loader upgrades the legacy FNSAVE path to
aligned 512-byte FXSAVE64/FXRSTOR64 when CPUID advertises FXSR and SSE
and CR0.EM/TS are clear. It enables CR4.OSFXSR during the app lifetime, clears OSXMMEXCPT
and OSXSAVE for the legacy-only app ABI, and restores
the saved CR4 after restoring the supervisor's legacy FPU state.
The immutable initial image contains default FCW 0x037f, MXCSR 0x1f80,
empty x87 tags, zero x87 data and all sixteen zero XMM registers.
Ordinary syscalls/IRQs do not clear a running app's live state.
The existing non-FXSR/SSE path retains the earlier x87 implementation.
No AVX/XSAVE ABI, language float type, multithreaded scheduler, or
physical CPU compatibility is claimed.

Intel architectural reference:
https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-2a-manual.pdf
(FXSAVE/FXRSTOR, OSFXSR requirements and 64-bit layout).

Actual #MF/#XM recovery remains open. Experimental QEMU TCG payloads
designed to trigger these exceptions reached the trailing UD2 instead;
no actual #MF/#XM delivery was verified. Those experimental exception
handlers were excluded from this patch. With OSXMMEXCPT clear, the
architectural SIMD exception route is #UD rather than #XM.
KVM device access is not available to the current account.
Kernel handlers remain general-register only.

## Verification

```sh
python3 scripts/test_m5_user_sse_context.py
python3 scripts/test_m5_user_x87_context.py
python3 -m unittest tests.test_user_fault_policy -v
```

The new QEMU regression checks all 256 XMM bytes and MXCSR after
normal exit, real UD2, and hardware timeout; live XMM15 and MXCSR survive
a nonterminal syscall. The same image runs a legacy x87 checker on
a CPU advertising no FXSR/SSE, with unsupported SSE contained as #UD.
Existing x87, CPU owner guards, timeout and hardware validation remain
independent gates. Browser compatibility is not established.
