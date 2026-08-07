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
        background-color: #131722;
        padding: 16px 20px;
    }
    .thispc-banner {
        background-color: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 16px;
    }
    .thispc-sec-title {
        color: #94a3b8;
        font-weight: 700;
        font-size: 13px;
        margin-top: 12px;
        margin-bottom: 8px;
    }

    /* Drive / Partition Card */
    .drive-card {
        background-color: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 10px 14px;
        min-width: 250px;
        min-height: 76px;
        transition: all 150ms ease-in-out;
    }
    .drive-card:hover {
        background-color: rgba(255, 255, 255, 0.08);
        border-color: rgba(122, 162, 247, 0.45);
    }
    .drive-card:active, .drive-card.selected {
        background-color: rgba(122, 162, 247, 0.18);
        border-color: #7aa2f7;
    }
    .drive-title {
        color: #f1f5f9;
        font-weight: 700;
        font-size: 13px;
    }
    .drive-sub {
        color: #94a3b8;
        font-size: 11px;
    }
    .drive-meta {
        color: #64748b;
        font-size: 11px;
    }

    /* Progress bar for storage partitions */
    progressbar {
        border-radius: 4px;
        background-color: rgba(255, 255, 255, 0.08);
        min-height: 8px;
        border: none;
    }
    progressbar progress {
        background-image: linear-gradient(to right, #38bdf8, #2563eb);
        border-radius: 4px;
        min-height: 8px;
    }
    .drive-warn progress {
        background-image: linear-gradient(to right, #fbbf24, #f59e0b);
    }
    .drive-crit progress {
        background-image: linear-gradient(to right, #f87171, #ef4444);
    }

    /* Quick folder card */
    .folder-card {
        background-color: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 8px;
        padding: 8px 12px;
        min-width: 150px;
        transition: all 120ms ease-in-out;
    }
    .folder-card:hover {
        background-color: rgba(255, 255, 255, 0.08);
        border-color: rgba(122, 162, 247, 0.35);
    }
    .folder-card:active {
        background-color: rgba(122, 162, 247, 0.2);
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
