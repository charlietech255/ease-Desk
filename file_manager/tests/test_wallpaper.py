"""Unit tests for the shared wallpaper utility module."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from shared.utilities import wallpaper


class WallpaperUtilTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.tmp_dir.name, "desktop_config.json")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_hex_to_rgb(self):
        # #000000 -> (0, 0, 0)
        self.assertEqual(wallpaper.hex_to_rgb("#000000"), (0.0, 0.0, 0.0))
        # #ffffff -> (1, 1, 1)
        self.assertEqual(wallpaper.hex_to_rgb("#ffffff"), (1.0, 1.0, 1.0))
        # Shorthand #fff
        self.assertEqual(wallpaper.hex_to_rgb("#fff"), (1.0, 1.0, 1.0))
        # Invalid fallback
        self.assertEqual(wallpaper.hex_to_rgb("invalid"), (0.043, 0.055, 0.078))

    def test_get_wallpaper_config_defaults(self):
        conf = wallpaper.get_wallpaper_config(self.config_path)
        self.assertEqual(conf["wallpaper_mode"], "fill")
        self.assertEqual(conf["solid_color"], "#0b0e14")
        self.assertTrue(os.path.isabs(conf["wallpaper"]))

    def test_set_and_get_wallpaper_config(self):
        dummy_img = os.path.join(self.tmp_dir.name, "custom.png")
        with open(dummy_img, "w") as f:
            f.write("img data")

        # Set new wallpaper and mode
        ok = wallpaper.set_wallpaper(
            dummy_img,
            mode="fit",
            solid_color="#0f172a",
            config_path=self.config_path,
        )
        self.assertTrue(ok)

        # Verify saved config
        conf = wallpaper.get_wallpaper_config(self.config_path)
        self.assertEqual(conf["wallpaper"], os.path.abspath(dummy_img))
        self.assertEqual(conf["wallpaper_mode"], "fit")
        self.assertEqual(conf["solid_color"], "#0f172a")

    def test_set_wallpaper_preserves_other_keys(self):
        # Initial config with items
        initial_data = {
            "items": [{"id": "item1", "name": "Test Item"}],
            "wallpaper": "old.png",
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(initial_data, f)

        # Update wallpaper
        wallpaper.set_wallpaper("new.png", mode="stretch", config_path=self.config_path)

        with open(self.config_path, "r", encoding="utf-8") as f:
            saved = json.load(f)

        self.assertEqual(saved["items"], [{"id": "item1", "name": "Test Item"}])
        self.assertEqual(saved["wallpaper_mode"], "stretch")

    def test_is_image_file(self):
        valid_img = os.path.join(self.tmp_dir.name, "photo.jpg")
        with open(valid_img, "w") as f:
            f.write("data")
        self.assertTrue(wallpaper.is_image_file(valid_img))

        txt_file = os.path.join(self.tmp_dir.name, "notes.txt")
        with open(txt_file, "w") as f:
            f.write("data")
        self.assertFalse(wallpaper.is_image_file(txt_file))

        non_existent = os.path.join(self.tmp_dir.name, "none.png")
        self.assertFalse(wallpaper.is_image_file(non_existent))

    def test_cycle_next_wallpaper(self):
        presets = wallpaper.WALLPAPER_PRESETS
        # Run cycling multiple times to ensure wrap-around works seamlessly
        for _ in range(len(presets) + 2):
            name, path = wallpaper.cycle_next_wallpaper(self.config_path)
            self.assertTrue(bool(name))
            self.assertTrue(os.path.isabs(path))

    def test_solid_color_mode(self):
        wallpaper.set_wallpaper(
            wallpaper.DEFAULT_WALLPAPER,
            mode="solid",
            solid_color="#1e1e2e",
            config_path=self.config_path,
        )
        conf = wallpaper.get_wallpaper_config(self.config_path)
        self.assertEqual(conf["wallpaper_mode"], "solid")
        self.assertEqual(conf["solid_color"], "#1e1e2e")

    def test_get_thumbnail_pixbuf(self):
        # Non-existent file should safely return None
        self.assertIsNone(wallpaper.get_thumbnail_pixbuf("non_existent_file.png"))
        # Preset file should return a GdkPixbuf respecting max bounds
        if os.path.exists(wallpaper.DEFAULT_WALLPAPER):
            pix = wallpaper.get_thumbnail_pixbuf(wallpaper.DEFAULT_WALLPAPER, 100, 60)
            self.assertIsNotNone(pix)
            self.assertLessEqual(pix.get_width(), 100)
            self.assertLessEqual(pix.get_height(), 60)
            self.assertGreater(pix.get_width(), 0)
            self.assertGreater(pix.get_height(), 0)


if __name__ == "__main__":
    unittest.main()
