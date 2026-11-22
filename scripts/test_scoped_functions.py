#!/usr/bin/env python3
"""Real QEMU+Linux acceptance for scoped M2 function statements."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

from test_boot import ROOT, assert_boot, build
from test_linux import build_and_run

ORIGINAL = "Scoped functions in HTML Kernel!\n25\n10\nscoped function PASS\n"
MUTATED = "Scoped functions in HTML Kernel!\n22\n10\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "build/.cache")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build")
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    source = ROOT / "examples/scoped-functions-kernel.html"
    baseline = source.read_text(encoding="utf-8")
    condition = '<if test="sum &gt; 20">'
    if baseline.count(condition) != 1:
        raise AssertionError("scoped function fixture unexpectedly changed")
    with tempfile.TemporaryDirectory(dir=args.work_dir, prefix="htmlk-scoped-") as td:
        work = Path(td)
        original_iso = None
        for name, file, expected in [
            ("baseline", source, ORIGINAL),
            ("changed", work / "changed.html", MUTATED),
        ]:
            if name == "changed":
                file.write_text(baseline.replace(condition, '<if test="sum &gt; 30">'),
                                encoding="utf-8")
            build_and_run(file, work, expected)
            image = work / (name + ".iso")
            result = build(file, image, args.cache_dir, args.work_dir)
            if result.returncode:
                raise AssertionError(f"QEMU build failed: {result.stdout}")
            assert_boot(image, expected)
            if original_iso is None:
                original_iso = image.read_bytes()
            else:
                if original_iso == image.read_bytes():
                    raise AssertionError("modified HTML generated identical ISO")
                try:
                    assert_boot(image, ORIGINAL)
                except AssertionError:
                    print("SCOPED WRONG-OUTPUT NEGATIVE CONTROL PASS")
                else:
                    raise AssertionError("wrong output accepted after source edit")

        # Both targets must reject broken scopes and missing returns at compile time.
        invalid_cases = {
            "missing-return": baseline.replace(
                '    <return value="sum"/>\n  </function>', '  </function>'),
            "scope-leak": baseline.replace(
                '    <return value="sum"/>\n  </function>',
                '    <return value="step"/>\n  </function>'),
        }
        for name, invalid in invalid_cases.items():
            file = work / (name + ".html")
            file.write_text(invalid, encoding="utf-8")
            for target in ("linux", "kernel"):
                dest = work / f"{name}-{target}.c"
                result = subprocess.run(
                    [sys.executable, str(ROOT / "compiler/htmlk.py"), str(file),
                     "--target", target, "--out", str(dest)],
                    cwd=ROOT, capture_output=True, text=True, timeout=10)
                if result.returncode == 0 or dest.exists():
                    raise AssertionError(f"{name} accepted on {target}: {result}")
        print("SCOPED INVALID-RETURN/SCOPE REJECTION PASS")
    print("SCOPED FUNCTIONS REAL QEMU + LINUX PASS")


if __name__ == "__main__":
    main()
