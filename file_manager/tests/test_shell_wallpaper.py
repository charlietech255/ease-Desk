"""Unit tests for DesktopShell wallpaper engine, modes, caching, and config sync."""

from __future__ import annotations

import os
import tempfile
import unittest

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gtk  # noqa: E402

from desktop.shell.shell import DesktopShell  # noqa: E402
from shared.utilities import wallpaper  # noqa: E402


class ShellWallpaperEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.tmp_dir.name, "desktop_config.json")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_shell_init_wallpaper_state(self):
        shell = DesktopShell.__new__(DesktopShell)
        shell.wallpaper_path = wallpaper.DEFAULT_WALLPAPER
        shell.wallpaper_mode = "fill"
        shell.solid_color = "#0b0e14"
        shell.wallpaper_pixbuf = None
        shell._cached_scaled_pixbuf = None
        shell._cached_draw_params = None
        shell._cached_offsets = (0, 0)
        shell._cached_bg_rgb = (0.043, 0.055, 0.078)
        shell._config_mtime = 0.0

        # Load dummy pixbuf (100x100 RGB)
        pix = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 100, 100)
        shell.wallpaper_pixbuf = pix

        # Test 'fill' mode scaling
        shell.wallpaper_mode = "fill"
        shell._compute_scaled_wallpaper(1920, 1080)
        self.assertIsNotNone(shell._cached_scaled_pixbuf)
        self.assertGreaterEqual(shell._cached_scaled_pixbuf.get_width(), 1920)
        self.assertGreaterEqual(shell._cached_scaled_pixbuf.get_height(), 1080)

        # Test 'fit' mode scaling
        shell.wallpaper_mode = "fit"
        shell.solid_color = "#112233"
        shell._compute_scaled_wallpaper(1920, 1080)
        self.assertIsNotNone(shell._cached_scaled_pixbuf)
        self.assertLessEqual(shell._cached_scaled_pixbuf.get_width(), 1920)
        self.assertLessEqual(shell._cached_scaled_pixbuf.get_height(), 1080)
        self.assertEqual(shell._cached_bg_rgb, wallpaper.hex_to_rgb("#112233"))

        # Test 'stretch' mode scaling
        shell.wallpaper_mode = "stretch"
        shell._compute_scaled_wallpaper(1280, 720)
        self.assertEqual(shell._cached_scaled_pixbuf.get_width(), 1280)
        self.assertEqual(shell._cached_scaled_pixbuf.get_height(), 720)
        self.assertEqual(shell._cached_offsets, (0, 0))

        # Test 'center' mode scaling
        shell.wallpaper_mode = "center"
        shell._compute_scaled_wallpaper(1280, 720)
        self.assertEqual(shell._cached_scaled_pixbuf.get_width(), 100)
        self.assertEqual(shell._cached_scaled_pixbuf.get_height(), 100)
        self.assertEqual(shell._cached_offsets, ((1280 - 100) // 2, (720 - 100) // 2))

        # Test 'solid' mode
        shell.wallpaper_mode = "solid"
        shell.solid_color = "#ff5500"
        shell._compute_scaled_wallpaper(1280, 720)
        self.assertIsNone(shell._cached_scaled_pixbuf)
        self.assertEqual(shell._cached_bg_rgb, wallpaper.hex_to_rgb("#ff5500"))


if __name__ == "__main__":
    unittest.main()
