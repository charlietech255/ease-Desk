"""Simple viewers: text viewer and image preview for Charlie File Manager."""

from __future__ import annotations

import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkPixbuf, Gtk  # noqa: E402

from file_manager.core import fs  # noqa: E402


class TextViewerWindow(Gtk.Window):
    def __init__(self, path: str | None = None):
        super().__init__()
        self.set_default_size(720, 520)
        self.set_position(Gtk.WindowPosition.CENTER)
        
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("ease-Desk Text Editor")
        header.set_subtitle(os.path.basename(path) if path else "New Document")
        self.set_titlebar(header)

        if path:
            content, truncated = fs.read_text(path)
        else:
            content, truncated = "", False

        textview = Gtk.TextView()
        textview.set_editable(False)
        textview.set_cursor_visible(True)
        textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        textview.get_buffer().set_text(content)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(textview)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.pack_start(scrolled, True, True, 0)

        status = Gtk.Label()
        status.set_xalign(0)
        status.set_margin_top(4)
        status.set_margin_bottom(4)
        if path:
            total = len(content.encode("utf-8", "replace"))
            note = " (file truncated at 1 MiB)" if truncated else ""
            status.set_text(f"{os.path.basename(path)} — {fs.human_size(total)} read{note}")
        else:
            status.set_text("New Document")
        box.pack_start(status, False, False, 0)

        self.add(box)
        self.connect("delete-event", lambda *_: self._close())

    def _close(self) -> bool:
        self.destroy()
        return False


class ImageViewerWindow(Gtk.Window):
    def __init__(self, path: str | None = None):
        super().__init__()
        self.set_position(Gtk.WindowPosition.CENTER)

        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("ease-Desk Image Viewer")
        header.set_subtitle(os.path.basename(path) if path else "No Image")
        self.set_titlebar(header)
        
        pixbuf = None
        if path:
            try:
                info = GdkPixbuf.Pixbuf.get_file_info(path)[0]
                if info:
                    w, h = info.get_width(), info.get_height()
                    if w > 8192 or h > 8192:
                        raise fs.FileOpError(f"Image too large ({w}x{h}). Max supported is 8192x8192.")
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
            except Exception as exc:
                raise fs.FileOpError(f"Could not load image: {exc}") from exc

        if pixbuf:
            screen = Gdk.Screen.get_default()
            screen_w = min(screen.get_width(), 1100)
            scale = min(1.0, screen_w / pixbuf.get_width()) if pixbuf.get_width() else 1.0
            if scale < 1.0:
                pixbuf = pixbuf.scale_simple(
                    int(pixbuf.get_width() * scale),
                    int(pixbuf.get_height() * scale),
                    GdkPixbuf.InterpType.BILINEAR,
                )
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            self.set_default_size(min(1100, pixbuf.get_width() + 40), min(800, pixbuf.get_height() + 80))
            self.add(image)
        else:
            lbl = Gtk.Label(label="No image selected")
            self.set_default_size(600, 400)
            self.add(lbl)
            
        self.connect("delete-event", lambda *_: self._close())

    def _close(self) -> bool:
        self.destroy()
        return False
