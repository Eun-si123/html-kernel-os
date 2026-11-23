#!/usr/bin/env python3
"""HTML Kernel Language developer CLI: check, describe, run and build.

All builds use the real shared compiler. 'run' executes a *Linux userspace*
binary on the host; it NEVER boots or runs a kernel on the host.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from compiler.htmlk import compile_html  # noqa: E402
from compiler.diagnostics import diagnostic_from  # noqa: E402
from htmlk_check import read_source  # noqa: E402
from build_html_user_image import build as build_user_image  # noqa: E402

MAX_RUN_OUTPUT = 16384
BUILD_TIMEOUT = 30
RUN_TIMEOUT = 10


def gcc_linux(source: str, dest: Path) -> str:
    """Compile already checked HTMLK source using the single Linux codegen."""
    generated = compile_html(source, target="linux")
    c_path = dest.with_suffix(".c")
    c_path.write_text(generated, encoding="utf-8")
    result = subprocess.run(
        ["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
         str(c_path), "-o", str(dest)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=BUILD_TIMEOUT,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("Linux GCC compilation failed: " +
                           result.stderr.decode("utf-8", errors="replace")[:2000])
    return hashlib.sha256(generated.encode("utf-8")).hexdigest()


def native_artifact(source: str, *, target: str, tempdir: Path) -> tuple[Path, str]:
    """Produce only inside a temporary directory; publish after whole success."""
    snapshot = tempdir / "input.html"
    snapshot.write_text(source, encoding="utf-8")
    if target == "linux":
        artifact = tempdir / "program"
        digest = gcc_linux(source, artifact)
    elif target == "user":
        artifact = tempdir / "program.hke"
        generated = compile_html(source, target="user")
        digest = hashlib.sha256(generated.encode("utf-8")).hexdigest()
        build_user_image(snapshot, artifact)
    else:
        raise ValueError("only Linux executable and native Ring3 HKEX builds are supported")
    if not artifact.is_file() or not artifact.stat().st_size:
        raise RuntimeError("compiler did not produce an executable artifact")
    return artifact, digest


def result_error(error: Exception, *, target: str, json_mode: bool) -> int:
    diagnostic = diagnostic_from(error)
    if json_mode:
        print(json.dumps({
            "schema_version": 1, "ok": False, "target": target,
            "diagnostics": [vars(diagnostic)],
        }, ensure_ascii=False, sort_keys=True))
    else:
        print(f"error {diagnostic.code}: {diagnostic.message}", file=sys.stderr)
        if diagnostic.hint:
            print(f"hint: {diagnostic.hint}", file=sys.stderr)
    return 1


def atomic_copy(src: Path, dst: Path, *, overwrite: bool) -> None:
    """No partially written destination if the compiler or copy fails."""
    if dst.is_symlink() or (dst.exists() and not overwrite):
        raise FileExistsError("destination already exists (or is a symlink): " + str(dst))
    if not dst.parent.is_dir():
        raise FileNotFoundError("destination parent directory does not exist: " +
                                str(dst.parent))
    fd, staging = tempfile.mkstemp(prefix=".htmlk-", dir=dst.parent)
    os.close(fd)
    stage_path = Path(staging)
    try:
        shutil.copyfile(src, stage_path)
        os.chmod(stage_path, src.stat().st_mode & 0o777)
        if dst.is_symlink() or (dst.exists() and not overwrite):
            raise FileExistsError("destination changed during build: " + str(dst))
        os.replace(stage_path, dst)
    finally:
        stage_path.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    for cmd in ("check", "run", "build"):
        p = sub.add_parser(cmd)
        p.add_argument("source", help="UTF-8 HTML Kernel Language source file")
        p.add_argument("--json", action="store_true", help="Machine-readable result")
        if cmd in ("check", "build"):
            p.add_argument("--target", choices=("kernel", "linux", "user"),
                           default="linux" if cmd == "check" else "linux")
        if cmd == "build":
            p.add_argument("--out", required=True, type=Path, help="Output file")
            p.add_argument("--force", action="store_true", help="Overwrite existing output")
    desc = sub.add_parser("describe", help="Discover actual accepted grammar and limits")
    desc.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.command in ("check", "describe"):
        command = [sys.executable, str(ROOT / "scripts/htmlk_check.py")]
        if args.command == "describe":
            command.append("--describe")
        else:
            command.extend((args.source, "--target", args.target))
        if args.json:
            command.append("--json")
        return subprocess.run(command, check=False).returncode

    target = "linux" if args.command == "run" else args.target
    if target == "kernel":
        return result_error(ValueError(
            "kernel artifacts must be built as ISO using scripts/build_boot.py; "
            "never execute privileged kernels on the host"),
            target=target, json_mode=args.json)
    try:
        source = read_source(args.source)
        if args.command == "build":
            if args.out.is_symlink() or (args.out.exists() and not args.force):
                raise FileExistsError("refusing to overwrite existing destination " +
                                      str(args.out))
        with tempfile.TemporaryDirectory(prefix="htmlk-cli-") as root:
            executable, c_hash = native_artifact(source, target=target,
                                                  tempdir=Path(root))
            if args.command == "build":
                atomic_copy(executable, args.out, overwrite=args.force)
                report = {
                    "schema_version": 1, "ok": True, "target": target,
                    "artifact": str(args.out), "bytes": args.out.stat().st_size,
                    "sha256": hashlib.sha256(args.out.read_bytes()).hexdigest(),
                    "generated_c_sha256": c_hash,
                }
                if args.json:
                    print(json.dumps(report, sort_keys=True))
                else:
                    print(f"Built {args.out} ({target}, {report['bytes']} bytes)")
                return 0
            # Only vetted generated Linux userspace code runs here, not kernel
            # binaries or imported HKEX. This is NOT an OS-level sandbox.
            done = subprocess.run([str(executable)], cwd=root,
                                  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, timeout=RUN_TIMEOUT,
                                  check=False)
            if len(done.stdout) > MAX_RUN_OUTPUT or len(done.stderr) > MAX_RUN_OUTPUT:
                raise RuntimeError("Linux program output exceeded bounded 16 KiB result")
            if args.json:
                print(json.dumps({
                    "schema_version": 1, "ok": done.returncode == 0,
                    "target": "linux", "exit_code": done.returncode,
                    "stdout": done.stdout.decode("utf-8", errors="replace"),
                    "stderr": done.stderr.decode("utf-8", errors="replace"),
                    "generated_c_sha256": c_hash,
                }, ensure_ascii=False, sort_keys=True))
            else:
                sys.stdout.buffer.write(done.stdout)
                sys.stderr.buffer.write(done.stderr)
            return done.returncode if done.returncode >= 0 else 1
    except (OSError, UnicodeError, ValueError, RuntimeError,
            subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        return result_error(e, target=target, json_mode=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
