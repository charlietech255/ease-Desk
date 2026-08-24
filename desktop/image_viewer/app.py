"""CLI entrypoint for ease-Desk Image Viewer."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from file_manager.viewer import ImageViewerWindow
from shared.ui import load_global_theme


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    path = args[0] if args else None

    load_global_theme()
    win = ImageViewerWindow(path=path)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
