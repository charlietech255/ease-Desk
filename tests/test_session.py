"""Integration and lifecycle tests for ease-Desk session and utilities."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest

from desktop.session.session import SessionManager
from shared.utilities import secure, sysinfo


class SysinfoTests(unittest.TestCase):
    def test_summary_keys(self):
        info = sysinfo.summary()
        self.assertIn("hostname", info)
        self.assertIn("os", info)
        self.assertIn("cpu", info)
        self.assertIn("mem_used", info)
        self.assertIn("mem_total", info)
        self.assertIn("disk_used", info)
        self.assertIn("disk_total", info)

    def test_cpu_count_positive(self):
        self.assertGreater(sysinfo.cpu_count(), 0)

    def test_human_size_formatting(self):
        self.assertEqual(sysinfo.human_size(0), "0 B")
        self.assertEqual(sysinfo.human_size(1024), "1.0 KB")
        self.assertEqual(sysinfo.human_size(1048576), "1.0 MB")

    def test_partitions_returns_root(self):
        parts = sysinfo.partitions()
        self.assertIsInstance(parts, list)
        self.assertGreaterEqual(len(parts), 1)
        root = next((p for p in parts if p["mount"] == "/"), None)
        self.assertIsNotNone(root)
        self.assertIn("name", root)
        self.assertIn("total", root)
        self.assertIn("free_str", root)
        self.assertIn("percent", root)

    def test_quick_folders(self):
        folders = sysinfo.quick_folders()
        self.assertIsInstance(folders, list)
        self.assertGreaterEqual(len(folders), 1)
        for f in folders:
            self.assertIn("name", f)
            self.assertIn("path", f)
            self.assertIn("icon", f)


class SessionManagerTests(unittest.TestCase):
    def test_session_init(self):
        mgr = SessionManager(resolution="1024x768x24", vnc_port=5901, novnc_port=6081)
        self.assertEqual(mgr.resolution, "1024x768x24")
        self.assertEqual(mgr.vnc_port, 5901)
        self.assertEqual(mgr.novnc_port, 6081)

    def test_display_allocation(self):
        mgr = SessionManager()
        display = mgr._find_free_display()
        self.assertTrue(display.startswith(":"))

    def test_cli_help_flag(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = dict(os.environ)
        env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")

        proc = subprocess.run(
            [sys.executable, "-m", "desktop.session.session", "--help"],
            env=env,
            cwd=root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("ease-Desk Session Manager", proc.stdout)


if __name__ == "__main__":
    unittest.main()
