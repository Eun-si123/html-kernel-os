"""Document link validator behavior; avoid false PASS on broken paths."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_docs import local_links, validate_file


class DocumentationTests(unittest.TestCase):
    def test_links_in_code_blocks_are_not_links(self):
        content = "[ok](docs/a.md)\n```bash\n[bad](never.md)\n```\n"
        self.assertEqual(local_links(content), ["docs/a.md"])

    def test_missing_and_path_escape_report_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "[bad](missing.md) [escape](../../etc/hosts)\n")
            errors = validate_file(root, "README.md")
            self.assertEqual(len(errors), 2)

    def test_existing_directory_and_remote_links_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "STATUS.md").write_text("ok\n")
            (root / "README.md").write_text(
                "[local](docs/STATUS.md) [dir](docs/) "
                "[remote](https://example.org)\n")
            self.assertEqual(validate_file(root, "README.md"), [])


if __name__ == "__main__":
    unittest.main()
