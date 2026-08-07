import unittest
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

from shared.utilities.icons import THEME_ICON_MAP, get_icon_pixbuf


class TestIconsEngine(unittest.TestCase):
    def test_all_categories_generate_valid_pixbuf(self):
        for key in THEME_ICON_MAP:
            pb = get_icon_pixbuf(key, size=48)
            self.assertIsNotNone(pb)
            self.assertIsInstance(pb, GdkPixbuf.Pixbuf)
            self.assertEqual(pb.get_width(), 48)
            self.assertEqual(pb.get_height(), 48)

    def test_custom_sizes(self):
        for sz in (24, 32, 48, 64):
            pb = get_icon_pixbuf("folder", size=sz)
            self.assertEqual(pb.get_width(), sz)
            self.assertEqual(pb.get_height(), sz)

    def test_unknown_key_graceful_fallback(self):
        pb = get_icon_pixbuf("some_unknown_weird_extension", size=48)
        self.assertIsNotNone(pb)
        self.assertEqual(pb.get_width(), 48)


if __name__ == "__main__":
    unittest.main()
