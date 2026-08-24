"""ease-Desk This PC & File Manager — GTK3 entry point.

Usage:
    python3 -m file_manager [directory | thispc://]
"""

from __future__ import annotations

import os
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from file_manager.gui import FileManagerWindow
from shared.ui import load_global_theme  # noqa: E402
from shared.utilities import animate  # noqa: E402


def _load_css() -> None:
    css = b"""
    window, .app-window { background-color: #1e1e1e; color: #cccccc; }
    toolbar {
        background-color: #252526;
        border-bottom: 1px solid #333333;
        padding: 4px 8px;
    }
    toolbar button {
        background: transparent;
        border: 1px solid transparent;
        border-radius: 4px;
        padding: 4px 10px;
        color: #cccccc;
        font-weight: normal;
    }
    toolbar button:hover {
        background-color: #3e3e42;
        color: #ffffff;
        border-color: #3e3e42;
    }
    toolbar button:active {
        background-color: #007acc;
        color: #ffffff;
    }
    entry {
        background-color: #3c3c3c;
        border-radius: 4px;
        border: 1px solid #3c3c3c;
        color: #cccccc;
        padding: 4px 10px;
    }
    entry:focus {
        border-color: #007acc;
    }
    headerbar {
        background-color: #252526;
        border-bottom: 1px solid #333333;
        box-shadow: none;
    }
    headerbar label.title {
        font-weight: 600;
        font-size: 14px;
        color: #cccccc;
    }
    headerbar label.subtitle {
        font-size: 11px;
        color: #858585;
    }
    
    .toolbar {
        background-color: #252526;
        border-bottom: 1px solid #333333;
        padding: 8px 12px;
    }
    .tool-btn {
        background-color: transparent;
        color: #cccccc;
        border: 1px solid transparent;
        border-radius: 4px;
        font-weight: normal;
        padding: 6px 12px;
        transition: all 150ms ease;
    }
    .tool-btn:hover {
        background-color: #3e3e42;
        border-color: #3e3e42;
        color: #ffffff;
    }
    .tool-btn:active {
        background-color: #007acc;
        color: #ffffff;
    }
    .action-bar {
        background-color: #252526;
        border-bottom: 1px solid #333333;
        padding: 5px 10px;
    }
    .action-btn {
        background: transparent;
        color: #cccccc;
        border: 1px solid transparent;
        border-radius: 4px;
        font-weight: normal;
        padding: 3px 10px;
    }
    .action-btn:hover {
        background-color: #3e3e42;
        color: #ffffff;
        border-color: #3e3e42;
    }
    .statusbar {
        background-color: #007acc;
        color: #ffffff;
        padding: 2px 14px;
        font-size: 12px;
        border-top: none;
    }
    .iconview {
        background-color: #1e1e1e;
    }
    .iconview:selected {
        background-color: #04395e;
        border: 1px solid #007acc;
        border-radius: 4px;
    }
    
    /* --- MENUS --- */
    menu, .menu, popover {
        background-color: #252526;
        border: 1px solid #454545;
        border-radius: 4px;
        padding: 4px;
        color: #cccccc;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    menuitem {
        color: #cccccc;
        padding: 6px 12px;
        border-radius: 2px;
        transition: background 100ms ease;
    }
    menuitem:hover {
        background-color: #007acc;
        color: #ffffff;
    }

    /* --- SIDEBAR --- */
    .sidebar {
        background-color: #252526;
        border-right: 1px solid #333333;
    }
    .sidebar-row {
        padding: 6px 12px;
        color: #cccccc;
        font-weight: normal;
        border-radius: 4px;
        margin: 2px 8px;
    }
    .sidebar-row:hover {
        background-color: #2a2d2e;
        color: #ffffff;
    }
    .sidebar-row:selected {
        background-color: #37373d;
        color: #ffffff;
        border-left: 3px solid #007acc;
        border-radius: 0;
    }

    /* --- THIS PC / PARTITION VIEW STYLING --- */
    .thispc-container {
        background-color: #1e1e1e;
        padding: 20px 24px;
    }
    .thispc-banner {
        background-color: #252526;
        border: 1px solid #333333;
        border-radius: 4px;
        padding: 14px 20px;
        margin-bottom: 20px;
        box-shadow: none;
    }
    .thispc-sec-title {
        color: #cccccc;
        font-weight: 600;
        font-size: 14px;
        margin-top: 16px;
        margin-bottom: 12px;
    }

    /* Drive / Partition Card */
    .drive-card {
        background-color: #252526;
        border: 1px solid #333333;
        border-radius: 4px;
        padding: 14px 18px;
        min-width: 260px;
        min-height: 84px;
        transition: all 180ms ease-in-out;
        box-shadow: none;
    }
    .drive-card:hover {
        background-color: #2a2d2e;
        border-color: #454545;
    }
    .drive-card:active, .drive-card.selected {
        background-color: #37373d;
        border-color: #007acc;
    }
    .drive-title {
        color: #cccccc;
        font-weight: 600;
        font-size: 14px;
    }
    .drive-sub {
        color: #858585;
        font-size: 12px;
    }
    .drive-meta {
        color: #555555;
        font-size: 11px;
    }

    /* Progress bar for storage partitions */
    progressbar {
        border-radius: 2px;
        background-color: #3c3c3c;
        min-height: 8px;
        border: none;
    }
    progressbar progress {
        background-image: none;
        background-color: #007acc;
        border-radius: 2px;
        min-height: 8px;
    }
    .drive-warn progress {
        background-color: #d7ba7d;
    }
    .drive-crit progress {
        background-color: #f14c4c;
    }

    /* Quick folder card */
    .folder-card {
        background-color: #252526;
        border: 1px solid #333333;
        border-radius: 4px;
        padding: 10px 16px;
        min-width: 160px;
        transition: all 150ms ease-in-out;
        box-shadow: none;
    }
    .folder-card:hover {
        background-color: #2a2d2e;
        border-color: #454545;
    }
    .folder-card:active {
        background-color: #37373d;
        border-color: #007acc;
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
    
    # Enforce global premium app theme (includes dark mode)
    load_global_theme()
    _load_css()

    start = "thispc://"
    if argv:
        target = argv[0].strip()
        if target.lower() in ("thispc", "thispc://", "pc", "pc://", "mycomputer", "computer://"):
            start = "thispc://"
        elif os.path.exists(os.path.expanduser(target)):
            start = os.path.expanduser(target)
        else:
            start = "thispc://"

    window = FileManagerWindow(start)
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    animate.fade_in(window, duration_ms=220)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
