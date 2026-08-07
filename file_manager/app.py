"""Charlie File Manager — GTK3 entry point.

Usage:
    python3 -m file_manager.app [directory]
"""

from __future__ import annotations

import os
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from file_manager.gui import FileManagerWindow  # noqa: E402
from shared.utilities import animate  # noqa: E402


def _load_css() -> None:
    css = b"""
    window, .app-window { background-color: #161b27; color: #dce3f0; }
    toolbar {
        background-color: #111520;
        border-bottom: 1px solid rgba(255,255,255,0.08);
        padding: 4px 8px;
    }
    toolbar button {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 6px;
        padding: 4px 10px;
        color: #cbd5e1;
        font-weight: 600;
    }
    toolbar button:hover {
        background-color: rgba(122, 162, 247, 0.2);
        color: #93c5fd;
        border-color: #7aa2f7;
    }
    toolbar button:active {
        background-color: rgba(122, 162, 247, 0.35);
    }
    entry {
        background-color: #0d1017;
        border-radius: 6px;
        border: 1px solid rgba(255,255,255,0.12);
        color: #f1f5f9;
        padding: 4px 10px;
    }
    entry:focus {
        border-color: #7aa2f7;
    }
    .action-bar {
        background-color: #141822;
        border-bottom: 1px solid rgba(255,255,255,0.06);
        padding: 5px 10px;
    }
    .action-btn {
        background: rgba(255,255,255,0.05);
        color: #cbd5e1;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 6px;
        font-weight: 600;
        padding: 3px 10px;
    }
    .action-btn:hover {
        background-color: rgba(255,255,255,0.12);
        color: #ffffff;
        border-color: rgba(255,255,255,0.2);
    }
    .statusbar {
        background-color: #111520;
        color: #8a97ad;
        padding: 5px 12px;
        font-size: 12px;
        border-top: 1px solid rgba(255,255,255,0.06);
    }
    .iconview {
        background-color: #161b27;
    }
    .iconview:selected {
        background-color: #2b364c;
        border-radius: 6px;
    }
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css)
    screen = Gdk.Screen.get_default()
    if screen is not None:
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    _load_css()

    start = argv[0] if argv else os.path.expanduser("~")
    if not os.path.isdir(start):
        start = os.path.expanduser("~")

    window = FileManagerWindow(start)
    window.show_all()
    animate.fade_in(window, duration_ms=220)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
