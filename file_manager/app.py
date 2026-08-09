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
    window, .app-window { background-color: #131722; color: #dce3f0; }
    toolbar {
        background-color: #0f131c;
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
        background-color: #0a0d14;
        border-radius: 6px;
        border: 1px solid rgba(255,255,255,0.12);
        color: #f1f5f9;
        padding: 4px 10px;
    }
    entry:focus {
        border-color: #7aa2f7;
    }
    headerbar {
        background-color: #181825;
        border-bottom: 1px solid rgba(205, 214, 244, 0.08);
        box-shadow: none;
    }
    headerbar label.title {
        font-weight: 700;
        font-size: 14px;
        color: #cdd6f4;
    }
    headerbar label.subtitle {
        font-size: 11px;
        color: #a6adc8;
    }
    
    .toolbar {
        background-color: #1e1e2e;
        border-bottom: 1px solid rgba(205, 214, 244, 0.05);
        padding: 8px 12px;
    }
    .tool-btn {
        background-color: rgba(49, 50, 68, 0.6);
        color: #cdd6f4;
        border: 1px solid rgba(205, 214, 244, 0.08);
        border-radius: 8px;
        font-weight: 600;
        padding: 6px 12px;
        transition: all 150ms ease;
    }
    .tool-btn:hover {
        background-color: rgba(49, 50, 68, 0.95);
        border-color: rgba(137, 180, 250, 0.35);
    }
    .tool-btn:active {
        background-color: rgba(137, 180, 250, 0.2);
    }
    .action-bar {
        background-color: #121620;
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
        background-color: #0f131c;
        color: #8a97ad;
        padding: 5px 14px;
        font-size: 12px;
        border-top: 1px solid rgba(255,255,255,0.06);
    }
    .iconview {
        background-color: #131722;
    }
    .iconview:selected {
        background-color: #26334d;
        border-radius: 6px;
    }

    /* --- THIS PC / PARTITION VIEW STYLING --- */
    .thispc-container {
        background-color: #11111b; /* Deepin Dark Background */
        padding: 20px 24px;
    }
    .thispc-banner {
        background-color: rgba(49, 50, 68, 0.4);
        border: 1px solid rgba(205, 214, 244, 0.08);
        border-radius: 12px;
        padding: 14px 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }
    .thispc-sec-title {
        color: #a6adc8;
        font-weight: 700;
        font-size: 14px;
        margin-top: 16px;
        margin-bottom: 12px;
    }

    /* Drive / Partition Card */
    .drive-card {
        background-color: rgba(49, 50, 68, 0.55);
        border: 1px solid rgba(205, 214, 244, 0.08);
        border-radius: 16px;
        padding: 14px 18px;
        min-width: 260px;
        min-height: 84px;
        transition: all 180ms ease-in-out;
        box-shadow: 0 4px 14px rgba(0,0,0,0.25);
    }
    .drive-card:hover {
        background-color: rgba(49, 50, 68, 0.85);
        border-color: rgba(137, 180, 250, 0.45);
        box-shadow: 0 8px 24px rgba(0,0,0,0.4);
    }
    .drive-card:active, .drive-card.selected {
        background-color: rgba(137, 180, 250, 0.25);
        border-color: #89b4fa;
    }
    .drive-title {
        color: #cdd6f4;
        font-weight: 700;
        font-size: 14px;
    }
    .drive-sub {
        color: #a6adc8;
        font-size: 12px;
    }
    .drive-meta {
        color: #6c7086;
        font-size: 11px;
    }

    /* Progress bar for storage partitions */
    progressbar {
        border-radius: 6px;
        background-color: rgba(24, 24, 37, 0.8);
        min-height: 10px;
        border: 1px solid rgba(205, 214, 244, 0.05);
    }
    progressbar progress {
        background-image: linear-gradient(to right, #89b4fa, #74c7ec);
        border-radius: 6px;
        min-height: 10px;
    }
    .drive-warn progress {
        background-image: linear-gradient(to right, #f9e2af, #f38ba8);
    }
    .drive-crit progress {
        background-image: linear-gradient(to right, #f38ba8, #eba0ac);
    }

    /* Quick folder card */
    .folder-card {
        background-color: rgba(49, 50, 68, 0.4);
        border: 1px solid rgba(205, 214, 244, 0.05);
        border-radius: 12px;
        padding: 10px 16px;
        min-width: 160px;
        transition: all 150ms ease-in-out;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
    .folder-card:hover {
        background-color: rgba(49, 50, 68, 0.8);
        border-color: rgba(137, 180, 250, 0.35);
    }
    .folder-card:active {
        background-color: rgba(137, 180, 250, 0.2);
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
        settings.set_property("gtk-application-prefer-dark-theme", True)
        
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
