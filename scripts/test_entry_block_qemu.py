#!/usr/bin/env python3
"""Independent kernel and Ring3 CPU execution of entrypoint scopes."""
import os
from pathlib import Path
import tempfile
from test_boot import ROOT, assert_boot, build as build_kernel
from test_m5_interactive_run import build, exercise, HTML

def main():
    cache=Path(os.environ.get("HTMLK_CACHE_DIR",str(ROOT/"build/.cache")))
    source=(ROOT/"examples/block-locals.html").read_text()
    with tempfile.TemporaryDirectory(prefix="htmlk-block-locals-") as td:
        work=Path(td)
        for n, expected in [(3,(26,9,12)),(5,(30,15,12))]:
            app=work/f"app-{n}.html"
            app.write_text(source.replace('name="loop_0" value="3"',f'name="loop_0" value="{n}"'))
            kernel=work/f"kernel-{n}.html"
            kernel.write_text(app.read_text().replace("<program>","<kernel>").replace("</program>","</kernel>").replace("<main>","<onboot>").replace("</main>","</onboot>"))
            kernel_iso=work/f"kernel-{n}.iso"
            result=build_kernel(kernel,kernel_iso,cache,work)
            assert result.returncode==0,result.stdout
            assert_boot(kernel_iso,"".join(f"{v}\n" for v in expected))
            iso=work/f"app-{n}.iso"
            build(ROOT/"examples/kernel.html",iso,work,cache,extra=["--user-app-html",str(app),"--user-fault-recover"])
            trace,uart=exercise(iso,[
                (b"run /apps/hello.hke\r",b"M5_RUN_DONE\n"),
                (b"run /apps/hello.hke\r",b"M5_RUN_DONE\n"),
                (b"exit\r",b"M5_CONSOLE_EXIT\n"+HTML),
            ],HTML)
            for data in (trace,uart):
                reports=[int(line.split(b"=")[1]) for line in data.splitlines() if line.startswith(b"M5_C_USER_VALUE=")]
                assert reports==list(expected)*2,(reports,expected,data)
                assert data.count(b"M5_C_USER_FRAMES_RECLAIMED\n")==2,data
            print(f"entry scopes kernel and Ring3 x2: {expected}; reclaim PASS",flush=True)

if __name__=="__main__":
    main()
