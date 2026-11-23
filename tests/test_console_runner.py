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

    def test_recover_faults_only_in_user_mode_and_no_host_drive(self):
        with self.assertRaisesRegex(ValueError,"interactive Ring3"):
            build_command(Path("bad.iso"),ROOT / "examples/romfs",
                          recover_user_faults=True)
        cmd=build_command(Path("recovery.iso"), ROOT / "examples/romfs",
                          with_user_program=True,recover_user_faults=True)
        self.assertIn("--romfs-run-console",cmd)
        self.assertIn("--user-fault-recover",cmd)
        self.assertIn("--exception-idt",cmd)
        self.assertIn("--tss-ist",cmd)
        for flag in ("--user-loader-probe","--romfs-console","--user-preempt-probe"):
            self.assertNotIn(flag,cmd)

    def test_real_x2apic_timeout_requires_fault_recovery_and_uses_safe_qemu(self):
        with self.assertRaisesRegex(ValueError,"fault recovery"):
            build_command(Path("unsafe.iso"),ROOT/"examples/romfs",user_timeout=True)
        cmd=build_command(Path("timeout.iso"),ROOT/"examples/romfs",
                          with_user_program=True,recover_user_faults=True,
                          user_timeout=True)
        for required in ("--user-timeout","--user-fault-recover",
                         "--romfs-run-console","--exception-idt","--tss-ist"):
            self.assertIn(required,cmd)
        qemu=qemu_command(Path("timeout.iso"),Path("debug.log"),user_timeout=True)
        self.assertEqual(qemu[qemu.index("-cpu")+1],"qemu64,+x2apic")
        self.assertEqual(qemu[qemu.index("-smp")+1],"1")
        self.assertEqual(qemu[qemu.index("-net")+1],"none")
        for blocked in ("-hda","-drive","-usb","-netdev"):
            self.assertNotIn(blocked,qemu)

    def test_timeout_manual_cli_fails_closed_without_recovery(self):
        with patch("sys.stdin.isatty",return_value=True), \
             patch("sys.stdout.isatty",return_value=True):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main(["--user-timeout","--with-user-program"])
                self.assertEqual(raised.exception.code,2)

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
