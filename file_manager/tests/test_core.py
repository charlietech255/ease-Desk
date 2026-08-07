"""Unit tests for the Charlie File Manager core (no GTK required)."""

from __future__ import annotations

import os
import tempfile
import unittest

from file_manager.core import fs, types
from shared.utilities.secure import SecurityError, safe_child


class SafeChildTests(unittest.TestCase):
    def test_rejects_traversal(self):
        for bad in ("..", "../etc", "a/b", "a\\b", "", ".", "a\x00b"):
            with self.assertRaises(SecurityError):
                safe_child("/tmp", bad)

    def test_accepts_plain_name(self):
        self.assertEqual(safe_child("/tmp", "index.html"), "/tmp/index.html")

    def test_rejects_protected_delete(self):
        from shared.utilities.secure import assert_destructible

        with self.assertRaises(SecurityError):
            assert_destructible("/")
        with self.assertRaises(SecurityError):
            assert_destructible(os.path.expanduser("~"))


class EntryListingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_sorted_and_typed(self):
        os.mkdir(os.path.join(self.root, "bdir"))
        with open(os.path.join(self.root, "afile.txt"), "w") as f:
            f.write("hi")
        entries = fs.list_dir(self.root)
        names = [e.name for e in entries]
        self.assertEqual(names, ["afile.txt", "bdir"])  # case-insensitive sort
        afile = entries[0]
        self.assertFalse(afile.is_dir)
        bdir = entries[1]
        self.assertTrue(bdir.is_dir)

    def test_list_missing_dir(self):
        with self.assertRaises(fs.FileOpError):
            fs.list_dir(os.path.join(self.root, "nope"))


class FileOperationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_mkdir_rename_delete_roundtrip(self):
        created = fs.make_directory(self.root, "New Folder")
        self.assertTrue(os.path.isdir(created))
        renamed = fs.rename(created, "Renamed")
        self.assertTrue(os.path.isdir(renamed))
        self.assertFalse(os.path.exists(created))
        fs.delete(renamed, recursive=True)
        self.assertFalse(os.path.exists(renamed))

    def test_copy_and_move_file(self):
        src = os.path.join(self.root, "a.txt")
        with open(src, "w") as f:
            f.write("data")
        dest = os.path.join(self.root, "b")
        os.mkdir(dest)
        copied = fs.copy(src, dest)
        self.assertTrue(os.path.exists(copied))
        moved = fs.move(src, dest)
        self.assertTrue(os.path.exists(moved))
        self.assertFalse(os.path.exists(src))

    def test_copy_directory_auto_names(self):
        src = os.path.join(self.root, "proj")
        os.mkdir(src)
        with open(os.path.join(src, "f"), "w") as f:
            f.write("x")
        dest = os.path.join(self.root, "out")
        os.mkdir(dest)
        first = fs.copy(src, dest)
        second = fs.copy(src, dest)
        self.assertNotEqual(first, second)
        self.assertTrue(os.path.isdir(first))
        self.assertTrue(os.path.isdir(second))

    def test_rename_duplicate_rejected(self):
        fs.make_directory(self.root, "one")
        fs.make_directory(self.root, "two")
        with self.assertRaises(fs.FileOpError):
            fs.rename(os.path.join(self.root, "one"), "two")

    def test_delete_guards_root(self):
        with self.assertRaises(SecurityError):
            fs.delete("/", recursive=True)

    def test_read_text_and_binary_rejection(self):
        txt = os.path.join(self.root, "x.txt")
        with open(txt, "w") as f:
            f.write("hello")
        content, truncated = fs.read_text(txt)
        self.assertEqual(content, "hello")
        self.assertFalse(truncated)

        binary = os.path.join(self.root, "blob")
        with open(binary, "wb") as f:
            f.write(b"\x00\x01\x02binary")
        with self.assertRaises(fs.FileOpError):
            fs.read_text(binary)

    def test_permissions_blocked(self):
        if os.geteuid() == 0:
            self.skipTest("running as root; permissions are not enforced")
        blocked = os.path.join(self.root, "blocked")
        os.mkdir(blocked)
        os.chmod(blocked, 0o000)
        try:
            with self.assertRaises(fs.PermissionDeniedError):
                fs.list_dir(blocked)
        finally:
            os.chmod(blocked, 0o755)

    def test_properties_shape(self):
        src = os.path.join(self.root, "prop.txt")
        with open(src, "w") as f:
            f.write("abc")
        props = fs.properties(src)
        self.assertEqual(props["name"], "prop.txt")
        self.assertEqual(props["size"], "3 B")
        self.assertIn("permissions", props)
        self.assertIn("owner", props)


class TypeCategorizeTests(unittest.TestCase):
    def test_folder(self):
        cat, desc, icon = types.categorize("html", True)
        self.assertEqual(cat, "folder")

    def test_known_types(self):
        cases = {
            "index.php": "php",
            "app.js": "javascript",
            "index.html": "html",
            "style.css": "css",
            "config.json": "json",
            "database.conf": "config",
            "archive.zip": "archive",
            "photo.png": "image",
            "README.md": "text",
            "server.log": "text",
        }
        for name, expected in cases.items():
            cat, _, _ = types.categorize(name, False)
            self.assertEqual(cat, expected, name)

    def test_unknown_is_other(self):
        cat, desc, icon = types.categorize("mystery.zzz", False)
        self.assertEqual(cat, "other")
        self.assertIn("zzz", desc)

    def test_link(self):
        cat, _, icon = types.categorize("whatever", False, is_link=True)
        self.assertEqual(cat, "link")


if __name__ == "__main__":
    unittest.main()
