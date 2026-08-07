"""Automated verification test suite for ease-Desk phase 2 features.
Tests:
1. Archive compression & extraction (zip, tar.gz)
2. Vector icon pixbuf rendering (terminal, task_manager, archive)
3. Terminal emulator initialization
4. Task manager process list & system info
5. Desktop shell start menu & shortcut launching dispatch
"""

import os
import shutil
import tempfile
import unittest

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk

from desktop.shell.shell import DesktopShell
from desktop.task_manager.task_manager import TaskManagerWindow, list_processes
from desktop.terminal.terminal import TerminalWindow
from file_manager.core import fs
from shared.utilities.icons import get_icon_pixbuf


class TestNewFeatures(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="easedesk_test_")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_icons_rendering(self):
        """Verify vector rendering of new and updated icons."""
        for icon_key in ["terminal", "task_manager", "archive", "computer", "webroot", "folder"]:
            pb = get_icon_pixbuf(icon_key, size=48)
            self.assertIsNotNone(pb, f"Icon {icon_key} should return a valid Pixbuf")
            self.assertEqual(pb.get_width(), 48)
            self.assertEqual(pb.get_height(), 48)

    def test_archive_zip_roundtrip(self):
        """Test ZIP archive creation and safe extraction."""
        f1 = os.path.join(self.temp_dir, "sample.txt")
        with open(f1, "w", encoding="utf-8") as f:
            f.write("Hello from ease-Desk by charlie!")

        zip_out = os.path.join(self.temp_dir, "test.zip")
        fs.compress_archive([f1], zip_out)
        self.assertTrue(os.path.exists(zip_out))
        self.assertTrue(fs.is_archive(zip_out))

        dest_dir = os.path.join(self.temp_dir, "zip_extracted")
        fs.extract_archive(zip_out, dest_dir)
        extracted_file = os.path.join(dest_dir, "sample.txt")
        self.assertTrue(os.path.exists(extracted_file))
        with open(extracted_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Hello from ease-Desk by charlie!")

    def test_archive_targz_roundtrip(self):
        """Test TAR.GZ archive creation and safe extraction."""
        sub = os.path.join(self.temp_dir, "subfolder")
        os.makedirs(sub, exist_ok=True)
        f1 = os.path.join(sub, "data.txt")
        with open(f1, "w", encoding="utf-8") as f:
            f.write("Tar.gz data test")

        tar_out = os.path.join(self.temp_dir, "test.tar.gz")
        fs.compress_archive([sub], tar_out)
        self.assertTrue(os.path.exists(tar_out))
        self.assertTrue(fs.is_archive(tar_out))

        dest_dir = os.path.join(self.temp_dir, "tar_extracted")
        fs.extract_archive(tar_out, dest_dir)
        extracted_file = os.path.join(dest_dir, "subfolder", "data.txt")
        self.assertTrue(os.path.exists(extracted_file))

    def test_task_manager_and_sysinfo(self):
        """Test Task Manager window and process listing."""
        procs = list_processes()
        self.assertIsInstance(procs, list)
        self.assertGreater(len(procs), 0)

        tm = TaskManagerWindow()
        self.assertIsNotNone(tm)
        self.assertIn("Task Manager", tm.get_title())
        tm.destroy()

    def test_terminal_emulator(self):
        """Test Terminal window initialization."""
        term = TerminalWindow()
        self.assertIsNotNone(term)
        self.assertIn("Terminal", term.get_title())
        term.destroy()

    def test_desktop_shell_integration(self):
        """Test DesktopShell start menu and item configuration."""
        shell = DesktopShell()
        self.assertIsNotNone(shell.start_btn)
        item_ids = [it["id"] for it in shell.desktop_items]
        self.assertIn("terminal", item_ids)
        self.assertIn("task_manager", item_ids)
        shell.window.destroy()


if __name__ == "__main__":
    unittest.main()
