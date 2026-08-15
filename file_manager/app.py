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

from file_manager.gui import FileManagerWindow  # noqa: E402
from shared.utilities import animate  # noqa: E402


def _load_css() -> None:
    css = b"""
    window, .app-window { background-color: #ffffff; color: #333333; }
    toolbar {
        background-color: #f8f9fa;
        border-bottom: 1px solid rgba(0,0,0,0.05);
        padding: 4px 8px;
    }
    toolbar button {
        background: transparent;
        border: 1px solid transparent;
        border-radius: 6px;
        padding: 4px 10px;
        color: #555555;
        font-weight: 500;
    }
    toolbar button:hover {
        background-color: rgba(0, 0, 0, 0.05);
        color: #000000;
        border-color: rgba(0, 0, 0, 0.1);
    }
    toolbar button:active {
        background-color: rgba(0, 0, 0, 0.1);
    }
    entry {
        background-color: #ffffff;
        border-radius: 6px;
        border: 1px solid rgba(0,0,0,0.1);
        color: #333333;
        padding: 4px 10px;
    }
    entry:focus {
        border-color: #007aff;
    }
    headerbar {
        background-color: #ffffff;
        border-bottom: 1px solid rgba(0,0,0,0.05);
        box-shadow: none;
    }
    headerbar label.title {
        font-weight: 600;
        font-size: 14px;
        color: #333333;
    }
    headerbar label.subtitle {
        font-size: 11px;
        color: #888888;
    }
    
    .toolbar {
        background-color: #f8f9fa;
        border-bottom: 1px solid rgba(0,0,0,0.05);
        padding: 8px 12px;
    }
    .tool-btn {
        background-color: transparent;
        color: #555555;
        border: 1px solid transparent;
        border-radius: 8px;
        font-weight: 500;
        padding: 6px 12px;
        transition: all 150ms ease;
    }
    .tool-btn:hover {
        background-color: rgba(0,0,0,0.05);
        border-color: rgba(0,0,0,0.1);
    }
    .tool-btn:active {
        background-color: rgba(0,0,0,0.1);
    }
    .action-bar {
        background-color: #f8f9fa;
        border-bottom: 1px solid rgba(0,0,0,0.05);
        padding: 5px 10px;
    }
    .action-btn {
        background: transparent;
        color: #555555;
        border: 1px solid transparent;
        border-radius: 6px;
        font-weight: 500;
        padding: 3px 10px;
    }
    .action-btn:hover {
        background-color: rgba(0,0,0,0.05);
        color: #000000;
        border-color: rgba(0,0,0,0.1);
    }
    .statusbar {
        background-color: #f8f9fa;
        color: #888888;
        padding: 5px 14px;
        font-size: 12px;
        border-top: 1px solid rgba(0,0,0,0.05);
    }
    .iconview {
        background-color: #ffffff;
    }
    .iconview:selected {
        background-color: rgba(0, 122, 255, 0.1);
        border: 1px solid rgba(0, 122, 255, 0.2);
        border-radius: 6px;
    }
    
    /* --- MENUS --- */
    menu, .menu, popover {
        background-color: #ffffff;
        border: 1px solid rgba(0,0,0,0.1);
        border-radius: 8px;
        padding: 4px;
        color: #333333;
    }
    menuitem {
        color: #333333;
        padding: 6px 12px;
        border-radius: 6px;
        transition: background 100ms ease;
    }
    menuitem:hover {
        background-color: rgba(0, 0, 0, 0.05);
    }

    /* --- SIDEBAR --- */
    .sidebar {
        background-color: #f8f9fa;
        border-right: 1px solid rgba(0,0,0,0.05);
    }
    .sidebar-row {
        padding: 8px 12px;
        color: #555555;
        font-weight: 500;
        border-radius: 6px;
        margin: 2px 8px;
    }
    .sidebar-row:hover {
        background-color: rgba(0, 0, 0, 0.05);
        color: #333333;
    }
    .sidebar-row:selected {
        background-color: rgba(0, 122, 255, 0.1);
        color: #007aff;
    }

    /* --- THIS PC / PARTITION VIEW STYLING --- */
    .thispc-container {
        background-color: #ffffff;
        padding: 20px 24px;
    }
    .thispc-banner {
        background-color: #f8f9fa;
        border: 1px solid rgba(0,0,0,0.05);
        border-radius: 12px;
        padding: 14px 20px;
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }
    .thispc-sec-title {
        color: #888888;
        font-weight: 600;
        font-size: 14px;
        margin-top: 16px;
        margin-bottom: 12px;
    }

    /* Drive / Partition Card */
    .drive-card {
        background-color: #ffffff;
        border: 1px solid rgba(0,0,0,0.1);
        border-radius: 16px;
        padding: 14px 18px;
        min-width: 260px;
        min-height: 84px;
        transition: all 180ms ease-in-out;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .drive-card:hover {
        background-color: #f8f9fa;
        border-color: rgba(0,0,0,0.15);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .drive-card:active, .drive-card.selected {
        background-color: rgba(0, 122, 255, 0.05);
        border-color: #007aff;
    }
    .drive-title {
        color: #333333;
        font-weight: 600;
        font-size: 14px;
    }
    .drive-sub {
        color: #888888;
        font-size: 12px;
    }
    .drive-meta {
        color: #aaaaaa;
        font-size: 11px;
    }

    /* Progress bar for storage partitions */
    progressbar {
        border-radius: 6px;
        background-color: rgba(0,0,0,0.05);
        min-height: 10px;
        border: 1px solid rgba(0,0,0,0.05);
    }
    progressbar progress {
        background-image: linear-gradient(to right, #007aff, #00c6ff);
        border-radius: 6px;
        min-height: 10px;
    }
    .drive-warn progress {
        background-image: linear-gradient(to right, #ffcc00, #ff9500);
    }
    .drive-crit progress {
        background-image: linear-gradient(to right, #ff3b30, #ff2d55);
    }

    /* Quick folder card */
    .folder-card {
        background-color: #ffffff;
        border: 1px solid rgba(0,0,0,0.1);
        border-radius: 12px;
        padding: 10px 16px;
        min-width: 160px;
        transition: all 150ms ease-in-out;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .folder-card:hover {
        background-color: #f8f9fa;
        border-color: rgba(0,0,0,0.15);
    }
    .folder-card:active {
        background-color: rgba(0, 122, 255, 0.05);
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
    
    # Enforce global dark mode for file manager to fix white title bar
    settings = Gtk.Settings.get_default()
    if settings:
        settings.set_property("gtk-application-prefer-dark-theme", False)
        
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
    window.show_all()
    animate.fade_in(window, duration_ms=220)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
