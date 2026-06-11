from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from madcli.project_files import list_project_tree, read_project_file


class ProjectFilesTests(unittest.TestCase):
    def test_list_project_tree_excludes_generated_and_dependency_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "madcli").mkdir()
            (root / "madcli" / "cli.py").write_text("print('ok')", encoding="utf-8")
            (root / ".git").mkdir()
            (root / ".git" / "config").write_text("private", encoding="utf-8")
            (root / ".madcli").mkdir()
            (root / ".madcli" / "metadata.json").write_text("{}", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "pkg.js").write_text("", encoding="utf-8")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "x.pyc").write_text("", encoding="utf-8")

            tree = list_project_tree(root)

            paths = {item["path"] for item in tree}
            self.assertIn("madcli", paths)
            self.assertIn("madcli/cli.py", paths)
            self.assertNotIn(".git", paths)
            self.assertNotIn(".madcli", paths)
            self.assertNotIn("node_modules", paths)
            self.assertNotIn("__pycache__", paths)

    def test_read_project_file_rejects_paths_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root.parent / "outside-secret.txt"
            outside.write_text("secret", encoding="utf-8")
            try:
                with self.assertRaisesRegex(ValueError, "outside project root"):
                    read_project_file(root, "../outside-secret.txt")
            finally:
                outside.unlink()

    def test_read_project_file_returns_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Project\n", encoding="utf-8")

            text = read_project_file(root, "README.md")

            self.assertEqual(text, "# Project\n")


if __name__ == "__main__":
    unittest.main()
