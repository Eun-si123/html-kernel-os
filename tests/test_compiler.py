import unittest

from compiler.htmlk import CompileError, compile_html


def wrap(body):
    return '<kernel arch="x86_64"><onboot>' + body + '</onboot></kernel>'


class CompilerTests(unittest.TestCase):
    def test_print_generates_debug_port_output(self):
        out = compile_html(wrap("<print>Hello &amp; OS!</print><halt/>"))
        self.assertIn("0x48, 0x65, 0x6c", out)
        self.assertIn("0x26", out)
        self.assertIn("kernel_main", out)
        self.assertIn("outb", out)

    def test_utf8(self):
        out = compile_html(wrap("<print>안녕</print>"))
        self.assertIn("0xec, 0x95, 0x88", out)

    def test_rejects_unsupported_tags(self):
        with self.assertRaises(CompileError):
            compile_html(wrap("<script>alert(1)</script><print>x</print>"))

    def test_rejects_unknown_arch(self):
        with self.assertRaises(CompileError):
            compile_html('<kernel arch="arm64"><onboot><print>x</print></onboot></kernel>')

    def test_rejects_unclosed(self):
        with self.assertRaises(CompileError):
            compile_html("<kernel><onboot><print>x</print>")

    def test_rejects_print_after_halt(self):
        with self.assertRaises(CompileError):
            compile_html(wrap("<halt/><print>unreachable</print>"))

    def test_rejects_missing_print(self):
        with self.assertRaises(CompileError):
            compile_html(wrap("<halt/>"))


if __name__ == "__main__":
    unittest.main()
