#!/usr/bin/env python3
"""Read actual QEMU VGA screenshot pixels, not guest serial/text assertions.

Build an opt-in framebuffer ISO without the QEMU debug-exit mechanism so the
emulator remains alive for a host-driven HMP 'screendump' and pixel analysis.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import socket
import struct
import subprocess
import sys
import tempfile
import time
import zlib

from test_boot import ROOT

EXPECTED_SERIAL = ("HTML KERNEL ON-SCREEN\n"
                   "THE DISPLAY IS DRAWN BY THE BOOTED CPU\n"
                   "42\nVIDEO PASS\n")


def build(source: Path, iso: Path, cache: Path, work: Path) -> None:
    done = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_boot.py"),
         "--source", str(source), "--out", str(iso),
         "--cache-dir", str(cache), "--work-dir", str(work),
         "--video-console"],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    if done.returncode:
        raise AssertionError(f"standalone screenshot source rejected: {done.stdout} {done.stderr}")


def pixel(image: bytes, x: int, y: int) -> bytes:
    head = re.match(rb"P6\s+(\d+)\s+(\d+)\s+255\s", image)
    if not head:
        raise AssertionError("QEMU screendump is not a PPM/P6 image")
    width, height = int(head[1]), int(head[2])
    if width < 320 or height < 200:
        raise AssertionError(f"unexpected QEMU VGA size: {width}x{height}")
    expected_size = head.end() + width * height * 3
    if len(image) != expected_size:
        raise AssertionError(f"truncated/unexpected VGA PPM: {len(image)} != {expected_size}")
    if x >= width or y >= height:
        raise AssertionError("screenshot bounds")
    return image[head.end() + (y * width + x) * 3:
                 head.end() + (y * width + x) * 3 + 3]


def check_display(image: bytes) -> None:
    expected = {
        "green hardware header": (0, 0, b"\x79\xed\xb5"),
        "dark background": (0, 84, b"\x0c\x14\x14"),
        "first actual HTML glyph": (24, 84, b"\xe0\xf0\xe4"),
    }
    for name, (x, y, color) in expected.items():
        actual = pixel(image, x, y)
        if actual != color:
            raise AssertionError(
                f"{name}: QEMU monitor captured {actual.hex()}, expected {color.hex()}"
            )


def png_from_ppm(image: bytes) -> bytes:
    """Lossless 8-bit RGB PNG, pure stdlib; no extra CI image dependency."""
    head = re.match(rb"P6\s+(\d+)\s+(\d+)\s+255\s", image)
    if not head:
        raise AssertionError("not a raw PPM screenshot")
    width, height = int(head[1]), int(head[2])
    raw = image[head.end():]
    stride = width * 3
    if len(raw) != stride * height:
        raise AssertionError("PPM image data length mismatch")

    def chunk(name: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + name + data +
                struct.pack(">I", zlib.crc32(name + data) & 0xffffffff))

    scanlines = b"".join(
        b"\x00" + raw[y * stride:(y + 1) * stride]
        for y in range(height)
    )
    result = (b"\x89PNG\r\n\x1a\n" +
              chunk(b"IHDR", struct.pack(">IIBBBBB", width, height,
                                          8, 2, 0, 0, 0)) +
              chunk(b"IDAT", zlib.compress(scanlines, 9)) +
              chunk(b"IEND", b""))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "build/.cache")
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build")
    opt = parser.parse_args()
    opt.work_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="htmlk-vga-screenshot-",
                                     dir=opt.work_dir) as name:
        work = Path(name)
        iso = work / "video.iso"
        output = work / "serial.log"
        monitor = work / "hmp.sock"
        screenshot = work / "actual-vga.ppm"
        build(ROOT / "examples/framebuffer-kernel.html", iso,
              opt.cache_dir, opt.work_dir)
        args = [
            "qemu-system-x86_64", "-M", "q35", "-m", "256M",
            "-cdrom", str(iso), "-boot", "d",
            "-display", "none", "-serial", "none",
            "-monitor", f"unix:{monitor},server,nowait",
            "-net", "none", "-debugcon", f"file:{output}",
            "-global", "isa-debugcon.iobase=0xe9",
            "-no-reboot",
        ]
        proc = subprocess.Popen(
            args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        try:
            deadline = time.monotonic() + 18
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise AssertionError(
                        f"QEMU unexpectedly exited before screenshot: {proc.returncode}")
                text = output.read_text(errors="replace") if output.exists() else ""
                if text == EXPECTED_SERIAL:
                    break
                if len(text) >= len(EXPECTED_SERIAL) and text != EXPECTED_SERIAL:
                    raise AssertionError(f"wrong serial output before screenshot: {text!r}")
                time.sleep(.05)
            else:
                raise AssertionError(f"QEMU HTML program not seen: {text!r}")
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(2)
                sock.connect(str(monitor))
                sock.sendall(f"screendump {screenshot}\n".encode("ascii"))
                # Poll file instead of relying on QEMU HMP's optional prompt.
                deadline = time.monotonic() + 5
                while not screenshot.exists() and time.monotonic() < deadline:
                    time.sleep(.05)
                if not screenshot.exists():
                    response = sock.recv(4096).decode("utf-8", errors="replace")
                    raise AssertionError(f"QEMU HMP did not write screenshot: {response!r}")
            image = screenshot.read_bytes()
            check_display(image)
            png = opt.work_dir / "html-kernel-video-visible-screen.png"
            png.write_bytes(png_from_ppm(image))
            if not png.read_bytes().startswith(b"\x89PNG"):
                raise AssertionError("visual evidence PNG was corrupted")
            print(f"M3 QEMU VGA screenshot evidence PNG: {png}")
            print("M3 HOST VGA SCREENSHOT: REAL KERNEL TEXT PIXELS PASS")
        finally:
            proc.terminate()
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=5)


if __name__ == "__main__":
    main()
