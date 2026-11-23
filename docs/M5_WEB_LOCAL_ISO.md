# M5 Web-Live C — boot your own HTML-compiled native ISO in GitHub Pages

**Status:** experimental, source-owned opt-in extension to the existing
M5 Web Live page. Local QEMU and isolated Chromium browser evidence
must be checked separately; public deployment requires exact PR-head
GitHub Actions, Gitleaks and Pages verification.

## Why this is a genuine HTML-program workflow

GitHub Pages is a static site. It does NOT run Python/GCC or build ISO
files when visitors edit a web textbox. The supported path instead reuses
the repository's **real existing HTML-shaped compiler** on your PC to
compile a native Ring3 user program into a read-only ROMFS BIOS ISO,
then loads the **actual bytes of that generated ISO** into the pinned
WASM x86-64 CPU emulator from your own browser.

1. Download/clone the open-source repository, install its documented
   Python, GCC, binutils, xorriso and pinned Limine boot-tool prerequisites.
2. Copy `examples/user-programs/html-u64-report.html` and edit the
   custom HTML-shaped program. For example replace
   `<print value="18446744073709551615"/>` with
   `<print value="12345678901234567890"/>`, and
   `<halt code="7"/>` with `<halt code="9"/>`.
3. From the cloned repository root build **without installing any
   external service**:

   ```sh
   python3 scripts/build_live_site.py --source ./my-program.html --out-dir ./build/my-html-os
   ```

4. Open <https://eun-si123.github.io/html-kernel-os/live/>. Choose
   `build/my-html-os/html-kernel-live.iso` in **내 빌드 ISO** and
   choose the same `my-program.html` in **같은 원본 HTML**. The
   browser computes SHA-256 of the selected ISO and raw user HTML;
   it does not upload their contents to any server or invoke a backend.
   Clicking **실제 ISO 부팅** starts the actual guest CPU.
5. In the real UART shell run `cat /source.html` to read original
   user HTML bytes from the **booted guest's ROMFS**, and compare them
   byte-for-byte with the selected HTML file. Then
   `run /apps/hello.hke` executes the native Ring3 code built from
   that source. UART reports genuine numeric values, six-frame reclaim
   and the app's real exit code (e.g. `9`, not hardcoded `7`).

The browser file input is **not** an online compiler. New source bytes
cannot affect a previously compiled ISO just by selecting an HTML file.
If the user selects HTML without an ISO, the page blocks boot with an
explanation. If only the ISO is selected, it may boot, but **does not
claim source match** because no source was supplied. If both are supplied
but their kernel-read ROMFS bytes differ, the UI explicitly labels
the mismatch. An ISO9660 magic check and 64KiB–16MiB size bound are
simple sanity checks, **not image signing or malware security**.

## Native acceptance and adversarial tests

```sh
python3 scripts/test_local_live_iso.py
python3 -m unittest tests.test_live_pages
node --check site/live/live.js
```

The test invokes the actual `--source` CLI for a modified HTML,
builds a new BIOS bootable native ELF+HKEX+ROMFS ISO, checks its volume
descriptor and manifest SHA256, then runs it in actual x86 QEMU.
It sends `cat /source.html` and `run /apps/hello.hke` twice
over the *real* guest COM1, checks exactly the altered 64-bit number
`12345678901234567890` and changed status `9` twice, asserts the
original `18446744073709551615` is absent, confirms two actual
six-frame reclaims, and finally exits the HTML kernel. Over-4KiB
source is rejected **before** an ISO is built. Default public-asset
hash manifest and its tests remain unchanged.

The browser positive test uses a genuine **separately built modified
ISO**, served as an isolated fixture inside the container together with
the matching edited HTML. Chromium receives those bytes through the
standard File input `File`/`DataTransfer` change-handling path
(the OS-native file-picker dialog is not part of this automated test).
It actually boots the uploaded image with the already pinned v86 wasm,
receives a real `M5_PROMPT>`, gets byte-for-byte HTML from real ROMFS
`cat /source.html`, runs the program, and must output **new** 64-bit
value and status **9**; original value/code7 must be absent. The
frontend does **not** fabricate matching UART values or exit codes.

## Boundaries

- A caller-selected ISO image may contain malicious OS code. Run only
  images you built or trust; **do not treat this as an arbitrary-code
  security sandbox**. The emulator does not attach a virtual guest
  network or host disks; browser and emulator vulnerabilities remain
  outside the proof.
- HTML source is only read-only once selected; dynamic compilation
  within GitHub Pages is **not** implemented. A local toolchain is
  required to compile edited HTML into *real* native x86-64.
- The published machine intentionally has **no x2APIC user timer**
  (browser support not verified). A user program that never returns
  may hang the guest. Close/reload the page to recover; no host disk
  is exposed and no guest network device is attached.
- SHA-256 verifies source/image **consistency only**, not signatures,
  supply-chain integrity or authenticated origin. ROMFS equality
  establishes source bytes embedded in the image, not a mathematical
  proof that arbitrary ISO code corresponds to that source. Compiling
  with this repository's toolchain, differential QEMU testing and
  reproducible artifacts give the meaningful evidence.
- M6 bare hardware/UEFI, arbitrary ELF safety, SMP, FPU/FS-GS,
  calibrated timers and writable filesystems remain unverified.
