"""M5-B manual runner only launches safe read-only QEMU configuration."""
from pathlib import Path
import contextlib
import io
from unittest.mock import patch
import unittest

from scripts.run_m5_console import build_command, qemu_command, main, ROOT


class ConsoleRunnerTests(unittest.TestCase):
    def test_uses_real_qemu_serial_and_no_host_storage_or_network(self):
        cmd = qemu_command(Path("test.iso"), Path("log.txt"))
        self.assertEqual(cmd[0], "qemu-system-x86_64")
        self.assertEqual(cmd[cmd.index("-serial") + 1], "stdio")
        self.assertEqual(cmd[cmd.index("-net") + 1], "none")
        self.assertEqual(cmd[cmd.index("-display") + 1], "none")
        self.assertEqual(cmd[cmd.index("-monitor") + 1], "none")
        self.assertEqual(cmd[cmd.index("-cdrom") + 1], "test.iso")
        for unsafe in ("-drive", "-hda", "-usb", "-nic", "-netdev", "-snapshot"):
            self.assertNotIn(unsafe, cmd)
        self.assertIn("isa-debug-exit,iobase=0xf4,iosize=0x04", cmd)

    def test_builder_does_not_use_default_kernel_or_other_probes(self):
        cmd = build_command(Path("x.iso"), ROOT / "examples/romfs")
        self.assertIn("--romfs-console", cmd)
        self.assertIn("--test-exit", cmd)
        self.assertNotIn("--romfs-probe", cmd)
        self.assertNotIn("--user-preempt-probe", cmd)

    def test_separate_user_run_mode_does_not_activate_legacy_probes(self):
        cmd = build_command(Path("run.iso"), ROOT / "examples/romfs",
                            with_user_program=True)
        self.assertIn("--romfs-run-console", cmd)
        self.assertIn("--exception-idt", cmd)
        self.assertIn("--tss-ist", cmd)
        for forbidden in ("--romfs-console", "--romfs-probe", "--user-loader-probe",
                          "--user-preempt-probe"):
            self.assertNotIn(forbidden, cmd)

    def test_requires_interactive_tty_without_building(self):
        with patch("sys.stdin.isatty", return_value=False):
            with patch("subprocess.run") as proc:
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as context:
                        main([])
                self.assertEqual(context.exception.code, 2)
                proc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
