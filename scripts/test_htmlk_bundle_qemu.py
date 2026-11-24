"""Verify library source changes reach native kernel and Ring3 machine code."""
import os
from pathlib import Path
import tempfile
from test_boot import ROOT, assert_boot, build as build_kernel
from test_m5_interactive_run import build, exercise, HTML
import sys
sys.path.insert(0, str(ROOT))
from htmlk_bundle import bundle

def main():
    cache=Path(os.environ.get("HTMLK_CACHE_DIR",str(ROOT/"build/.cache")))
    app=(ROOT/"examples/libraries-app.html").read_text()
    library=(ROOT/"examples/libraries/math.html").read_text()
    with tempfile.TemporaryDirectory(prefix="htmlk-bundle-qemu-") as td:
        work=Path(td)
        for offset, expected in [(0,25),(1,27)]:
            lib=library.replace('value="x * x"',f'value="x * x + {offset}"')
            user=work/f"user-{offset}.html"
            user.write_text(bundle(app,[lib],target="user"))
            kernel=work/f"kernel-{offset}.html"
            kernel.write_text(bundle(app.replace("<program>","<kernel>").replace("</program>","</kernel>").replace("<main>","<onboot>").replace("</main>","</onboot>"),[lib],target="kernel"))
            kernel_iso=work/f"kernel-{offset}.iso"
            result=build_kernel(kernel,kernel_iso,cache,work)
            assert result.returncode==0,result.stdout
            assert_boot(kernel_iso,f"{expected}\n")
            iso=work/f"user-{offset}.iso"
            build(ROOT/"examples/kernel.html",iso,work,cache,extra=["--user-app-html",str(user),"--user-fault-recover"])
            trace,uart=exercise(iso,[(b"run /apps/hello.hke\r",b"M5_RUN_DONE\n"),(b"run /apps/hello.hke\r",b"M5_RUN_DONE\n"),(b"exit\r",b"M5_CONSOLE_EXIT\n"+HTML)],HTML)
            for data in (trace,uart):
                assert data.count(f"M5_C_USER_VALUE={expected}\n".encode())==2,data
                assert data.count(b"M5_C_USER_FRAMES_RECLAIMED\n")==2,data
            print(f"bundle library mutation: kernel and Ring3 x2 output {expected}, reclaim PASS",flush=True)

if __name__=="__main__":
    main()
