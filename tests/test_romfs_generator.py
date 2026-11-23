"""M5-A deterministic ROMFS source rules and rejection tests."""
from pathlib import Path
import tempfile
import unittest
from scripts.gen_romfs import collect, generate, valid_path


class RomfsGeneratorTests(unittest.TestCase):
    def test_canonical_names(self):
        for path in ("/foo", "/config/build-1.txt", "/a_2/b.3"):
            self.assertTrue(valid_path(path))
        for path in ("foo", "/", "/a/../b", "/a//b", "/.hidden/./x",
                     "/with space", "/unicode-가", "/" + "x"*64):
            self.assertFalse(valid_path(path))

    def test_deterministic_and_sorted_and_empty_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/"root"
            root.mkdir()
            (root/"z").write_bytes(b"Z")
            (root/"a").write_bytes(b"")
            first = Path(temp)/"one.c"
            second = Path(temp)/"two.c"
            self.assertEqual(generate(root, first), generate(root, second))
            self.assertEqual(first.read_bytes(), second.read_bytes())
            contents = first.read_text()
            self.assertLess(contents.find('"/a"'), contents.find('"/z"'))
            self.assertIn('{"/a", 0, 0U}', contents)

    def test_reject_untrusted_entries(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/"root"
            root.mkdir()
            with self.assertRaisesRegex(ValueError, "empty"):
                collect(root)
            (root/"bad space").write_text("x")
            with self.assertRaisesRegex(ValueError, "noncanonical"):
                collect(root)
            (root/"bad space").unlink()
            (root/"large").write_bytes(b"A"*4097)
            with self.assertRaisesRegex(ValueError, "limit"):
                collect(root)
            (root/"large").unlink()
            (root/"link").symlink_to(root)
            with self.assertRaisesRegex(ValueError, "symlink"):
                collect(root)
            (root/"link").unlink()
            for i in range(17):
                (root/f"file{i}").write_bytes(b"x")
            with self.assertRaisesRegex(ValueError, "limit"):
                collect(root)

    def test_aggregate_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index in range(8):
                (root/f"f{index}").write_bytes(b"0"*4096)
            self.assertEqual(len(collect(root)), 8)
            (root/"f8").write_bytes(b"1")
            with self.assertRaisesRegex(ValueError, "limit"):
                collect(root)


if __name__ == "__main__":
    unittest.main()
