"""Ensure the single HTML language produces target-appropriate native C."""
import unittest

from compiler.htmlk import compile_html, CompileError


PROGRAM = ('<kernel arch="x86_64"><onboot><print>hello</print>'
           '<let name="x" type="u64" value="3"/>'
           '<print value="x + 1"/><halt/></onboot></kernel>')


class TargetTests(unittest.TestCase):
    def test_linux_uses_userspace_stdio_and_main(self):
        generated = compile_html(PROGRAM, target="linux")
        self.assertIn('#include <stdio.h>', generated)
        self.assertIn('int main(void)', generated)
        self.assertIn('putchar((int)v)', generated)
        self.assertIn('fflush(stdout) == EOF', generated)
        self.assertNotIn('__asm__', generated)
        self.assertNotIn('io_outb(', generated)
        self.assertNotIn('kernel_main', generated)
        self.assertNotIn('serial_init', generated)

    def test_kernel_target_is_unchanged_and_privileged(self):
        generated = compile_html(PROGRAM)
        self.assertEqual(generated, compile_html(PROGRAM, target="kernel"))
        self.assertIn('void kernel_main(void)', generated)
        self.assertIn('serial_init();', generated)
        self.assertIn('io_outb(0xe9, v)', generated)
        self.assertIn('HTMLK_QEMU_TEST_EXIT', generated)
        self.assertNotIn('#include <stdio.h>', generated)

    def test_unknown_target_is_rejected(self):
        with self.assertRaisesRegex(CompileError, "unknown compiler target"):
            compile_html(PROGRAM, target="emulated-windows")

    def test_same_ast_semantics_under_both_targets(self):
        for target in ("linux", "kernel"):
            with self.subTest(target=target):
                generated = compile_html(PROGRAM, target=target)
                self.assertIn('uint64_t htmlk_x = UINT64_C(3);', generated)
                self.assertIn('htmlk_print_u64(((uint64_t)(htmlk_x + UINT64_C(1))));',
                              generated)


if __name__ == "__main__":
    unittest.main()
