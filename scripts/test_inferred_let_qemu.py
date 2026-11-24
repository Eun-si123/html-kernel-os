#!/usr/bin/env python3
"""Real kernel and Ring3 execution of inferred locals, including changed source."""
import os
from pathlib import Path
import tempfile
from test_boot import ROOT, assert_boot, build as build_kernel
from test_m5_interactive_run import build, exercise, HTML

def main():
    cache = Path(os.environ.get("HTMLK_CACHE_DIR", str(ROOT / "build/.cache")))
    source = (ROOT / "examples/inferred-let.html").read_text()
    with tempfile.TemporaryDirectory(prefix="htmlk-inferred-let-") as td:
        work = Path(td)
        images = []
        for count in (3, 5):
            text = source.replace('name="count" value="3"', f'name="count" value="{count}"')
            app = work / f"app-{count}.html"
            app.write_text(text)
            kernel = work / f"kernel-{count}.html"
            kernel.write_text(text.replace("<program>", "<kernel>").replace("</program>", "</kernel>").replace("<main>", "<onboot>").replace("</main>", "</onboot>"))
            kernel_iso = work / f"kernel-{count}.iso"
            built = build_kernel(kernel, kernel_iso, cache, work)
            assert built.returncode == 0, built.stdout
            assert_boot(kernel_iso, f"{count*2}\n0\n")
            iso = work / f"app-{count}.iso"
            build(ROOT / "examples/kernel.html", iso, work, cache, extra=["--user-app-html", str(app), "--user-fault-recover"])
            trace, uart = exercise(iso, [
                (b"run /apps/hello.hke\r", b"M5_RUN_DONE\n"),
                (b"run /apps/hello.hke\r", b"M5_RUN_DONE\n"),
                (b"exit\r", b"M5_CONSOLE_EXIT\n" + HTML),
            ], HTML)
            for data in (trace, uart):
                assert data.count(f"M5_C_USER_VALUE={count*2}\n".encode()) == 2, data
                assert data.count(b"M5_C_USER_VALUE=0\n") == 2, data
                assert data.count(b"M5_C_USER_FRAMES_RECLAIMED\n") == 2, data
            images.append(iso)
            print(f"inferred locals: native kernel + Ring3 x2 output {count*2},0, reclaim PASS", flush=True)
        assert images[0].read_bytes() != images[1].read_bytes()

if __name__ == "__main__":
    main()
