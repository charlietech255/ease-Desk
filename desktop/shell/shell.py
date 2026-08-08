"""ease-Desk Shell — Next-Gen Modern Desktop Environment Shell.

Features:
- Translucent Glassmorphism Topbar & Floating Island Dock.
- Pinned Applications with Active Process Glow Indicators.
- Dynamic Running Applications Taskbar with Window/Process Focus.
- Live System Status Tray (Real-time CPU % and RAM % Gauges).
- Crisp Digital Clock & Date Widget with Interactive Calendar & Uptime Flyout.
- Signature Wallpaper Engine & Custom Theme Manager.
- High-definition Desktop Glass Cards with Grid Layout & Context Menus.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk  # noqa: E402

from shared.utilities import animate, sysinfo, wallpaper  # noqa: E402
from shared.utilities.icons import get_icon_pixbuf  # noqa: E402
from shared.utilities.wallpaper import (  # noqa: E402
    CONFIG_DIR,
    CONFIG_FILE,
    DEFAULT_WALLPAPER,
    IMAGE_EXTENSIONS,
    SOLID_COLOR_PRESETS,
    WALLPAPER_MODES,
    WALLPAPER_PRESETS,
    cycle_next_wallpaper,
    get_thumbnail_pixbuf,
    get_wallpaper_config,
    hex_to_rgb,
    set_wallpaper,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ICON_PRESETS = [
    ("🖥️", "This PC"),
    ("📁", "Folder"),
    ("🗄️", "Drive / Storage"),
    ("⚡", "Quick Launch"),
    ("🌐", "Web (/var/www)"),
    ("📄", "Logs (/var/log)"),
    ("⚙️", "Config (/etc)"),
    ("💻", "Terminal"),
    ("💾", "Backup"),
    ("📦", "Packages"),
]

PINNED_APPS_CONFIG = [
    {
        "id": "browser",
        "name": "Web Browser",
        "icon_key": "browser",
        "target": "app://browser",
        "tooltip": "Fast Web Browser (Google Chrome / Epiphany)",
    },
    {
        "id": "this_pc",
        "name": "This PC",
        "icon_key": "computer",
        "target": "thispc://",
        "tooltip": "Files, Storage & Drives",
    },
    {
        "id": "terminal",
        "name": "Terminal",
        "icon_key": "terminal",
        "target": "app://terminal",
        "tooltip": "Embedded Terminal Console",
    },
    {
        "id": "task_manager",
        "name": "Task Manager",
        "icon_key": "task_manager",
        "target": "app://task_manager",
        "tooltip": "Process & Resource Monitor",
    },
    {
        "id": "settings",
        "name": "Themes & Wallpaper",
        "icon_key": "settings",
        "target": "app://wallpaper",
        "tooltip": "Personalize Desktop & Wallpapers",
    },
]

_CSS = b"""
/* ease-Desk Next-Gen Modern Glass Theme */
window.shell {
    background-color: #080b11;
}

/* Glass Topbar / Island Dock */
.topbar {
    background: rgba(13, 17, 23, 0.88);
    border-bottom: 1px solid rgba(255, 255, 255, 0.12);
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.45);
    padding: 0 12px;
}

.brand-pill {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 8px;
    padding: 3px 8px;
}
.brand-name {
    color: #f8fafc;
    font-weight: 800;
    font-size: 13px;
    letter-spacing: 0.5px;
}

/* Start Button */
.start-btn {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 8px;
    padding: 5px 14px;
    color: #ffffff;
    font-weight: 700;
    font-size: 12px;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.35);
    transition: all 150ms ease-in-out;
}
.start-btn:hover {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    box-shadow: 0 4px 14px rgba(59, 130, 246, 0.55);
}

/* Pinned Dock Icons */
.dock-item-box {
    padding: 0 2px;
}
.dock-btn {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 4px 8px;
    min-width: 38px;
    min-height: 34px;
    transition: all 140ms ease-in-out;
}
.dock-btn:hover {
    background-color: rgba(56, 189, 248, 0.18);
    border-color: rgba(56, 189, 248, 0.50);
    box-shadow: 0 2px 10px rgba(56, 189, 248, 0.25);
}
.dock-indicator {
    background: transparent;
    min-height: 3px;
    min-width: 14px;
    border-radius: 2px;
    margin-top: 1px;
    margin-bottom: 2px;
}
.dock-indicator.active {
    background: #38bdf8;
    box-shadow: 0 0 8px #38bdf8;
}

/* Running Tasks Section */
.running-task-btn {
    background: rgba(30, 41, 59, 0.65);
    border: 1px solid rgba(56, 189, 248, 0.35);
    border-radius: 8px;
    padding: 3px 10px;
    color: #e2e8f0;
    font-size: 11px;
    font-weight: 600;
    transition: all 120ms ease-in-out;
}
.running-task-btn:hover {
    background: rgba(56, 189, 248, 0.25);
    border-color: #38bdf8;
    color: #ffffff;
}

/* Live System Badges */
.status-pill {
    background: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 8px;
    padding: 4px 10px;
}
.status-lbl {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.2px;
}
.status-ok { color: #34d399; }
.status-warn { color: #fbbf24; }
.status-crit { color: #f87171; }

/* Clock & Date Widget */
.clock-widget-box {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    padding: 2px 10px;
    transition: all 120ms ease-in-out;
}
.clock-widget-box:hover {
    background: rgba(56, 189, 248, 0.15);
    border-color: rgba(56, 189, 248, 0.40);
}
.clock-time {
    color: #f8fafc;
    font-size: 13px;
    font-weight: 800;
}
.clock-date {
    color: #94a3b8;
    font-size: 10px;
    font-weight: 600;
}

/* Quick Menu & Power */
.quick-btn {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 8px;
    padding: 4px 10px;
    color: #cbd5e1;
    font-size: 12px;
    font-weight: 600;
}
.quick-btn:hover {
    background: rgba(56, 189, 248, 0.20);
    border-color: #38bdf8;
    color: #f8fafc;
}
.power-btn {
    background: rgba(239, 68, 68, 0.12);
    border: 1px solid rgba(239, 68, 68, 0.30);
    border-radius: 8px;
    padding: 4px 10px;
    color: #fca5a5;
    font-size: 11px;
    font-weight: 700;
}
.power-btn:hover {
    background: rgba(239, 68, 68, 0.35);
    border-color: #ef4444;
    color: #ffffff;
    box-shadow: 0 2px 10px rgba(239, 68, 68, 0.4);
}

/* Desktop icon button - Modern Glass Card */
.icon-btn {
    background: rgba(15, 23, 42, 0.50);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 10px 8px;
    min-width: 96px;
    min-height: 96px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.30);
    transition: all 140ms ease-in-out;
}
.icon-btn:hover {
    background-color: rgba(30, 41, 59, 0.85);
    border-color: rgba(56, 189, 248, 0.60);
    box-shadow: 0 8px 24px rgba(56, 189, 248, 0.25);
}
.icon-btn:active, .icon-btn.selected {
    background-color: rgba(56, 189, 248, 0.25);
    border-color: #38bdf8;
    box-shadow: 0 0 16px rgba(56, 189, 248, 0.40);
}
.icon-name {
    color: #f1f5f9;
    font-weight: 600;
    font-size: 12px;
    text-shadow: 0 2px 8px rgba(0,0,0,0.95);
    margin-top: 4px;
}

/* Floating Server Status Panel */
.vps-frame {
    background-color: rgba(13, 17, 23, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.50);
}
.vps-title { color: #38bdf8; font-weight: 800; font-size: 12px; letter-spacing: 0.5px; }
.vps-key { color: #64748b; font-size: 11px; font-weight: 700; }
.vps-val { color: #cbd5e1; font-size: 11px; font-weight: 500; }
.hint { color: #64748b; font-size: 11px; text-shadow: 0 1px 3px rgba(0,0,0,0.8); }

/* Calendar & Health Flyout */
.cal-window {
    background-color: #0d1117;
    border: 1px solid rgba(56, 189, 248, 0.40);
    border-radius: 14px;
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.80);
}
.cal-title {
    color: #38bdf8;
    font-weight: 800;
    font-size: 14px;
}
.cal-stat-key { color: #64748b; font-size: 11px; font-weight: 600; }
.cal-stat-val { color: #e2e8f0; font-size: 11px; font-weight: 700; }

/* Wallpaper Dialog Styles */
.wp-section-lbl {
    color: #38bdf8;
    font-weight: 800;
    font-size: 12px;
    letter-spacing: 0.5px;
}
.wp-card {
    background: rgba(15, 23, 42, 0.65);
    border: 2px solid rgba(255, 255, 255, 0.10);
    border-radius: 10px;
    padding: 6px;
    transition: all 120ms ease-in-out;
}
.wp-card:hover {
    background-color: rgba(30, 41, 59, 0.85);
    border-color: rgba(56, 189, 248, 0.50);
}
.wp-card.active {
    background-color: rgba(56, 189, 248, 0.25);
    border-color: #38bdf8;
    box-shadow: 0 0 14px rgba(56, 189, 248, 0.35);
}
.wp-card-name {
    color: #e2e8f0;
    font-size: 11px;
    font-weight: 600;
    margin-top: 4px;
}
.color-btn {
    border-radius: 8px;
    border: 2px solid rgba(255, 255, 255, 0.15);
    min-width: 48px;
    min-height: 38px;
    padding: 2px;
}
.color-btn:hover {
    border-color: #38bdf8;
}
.color-btn.active {
    border-color: #ffffff;
    box-shadow: 0 0 10px rgba(255, 255, 255, 0.6);
}
.wallpaper-btn {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    padding: 8px 14px;
    color: #f1f5f9;
    font-weight: 600;
}
.wallpaper-btn:hover {
    background-color: rgba(56, 189, 248, 0.25);
    border-color: #38bdf8;
    color: #ffffff;
}
"""


class DesktopShell:
    def __init__(self) -> None:
        self.children: list[int] = []
        self.tracked_processes: dict[int, dict] = {}
        self.desktop_items: list[dict] = []
        self.icon_buttons: dict[str, Gtk.Button] = {}
        self.pinned_buttons: dict[str, Gtk.Button] = {}
        self.pinned_indicators: dict[str, Gtk.Widget] = {}
        self.selected_id: str | None = None
        self.wallpaper_path: str = DEFAULT_WALLPAPER
        self.wallpaper_mode: str = "fill"
        self.solid_color: str = "#080b11"
        self.wallpaper_pixbuf: GdkPixbuf.Pixbuf | None = None
        self._cached_scaled_pixbuf: GdkPixbuf.Pixbuf | None = None
        self._cached_draw_params: tuple[int, int, str, str, str] | None = None
        self._cached_offsets: tuple[int, int] = (0, 0)
        self._cached_bg_rgb: tuple[float, float, float] = (0.031, 0.043, 0.067)
        self._config_mtime: float = 0.0
        self._cal_window: Gtk.Window | None = None

        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.window.set_app_paintable(True)
        self.window.get_style_context().add_class("shell")
        self.window.set_title("ease-Desk")
        self.window.set_decorated(False)
        self.window.set_default_size(1280, 800)
        self.window.fullscreen()

        self.window.connect("draw", self._on_draw_background)
        self.window.connect("delete-event", self._on_delete_event)
        self.window.connect("key-press-event", self._on_key_press)

        self._load_config()
        self._load_wallpaper()
        self._load_css()
        self._build_ui()
        self._tick_clock_and_stats()
        self._refresh_info()

        self.window.show_all()
        GLib.timeout_add_seconds(1, self._tick_clock_and_stats)
        GLib.timeout_add_seconds(5, self._refresh_info)
        animate.fade_in(self.window, duration_ms=300)

    # --------------------------------------------------------------- WALLPAPER
    def _load_wallpaper(self) -> None:
        wp_conf = get_wallpaper_config(CONFIG_FILE)
        self.wallpaper_path = wp_conf.get("wallpaper", DEFAULT_WALLPAPER)
        self.wallpaper_mode = wp_conf.get("wallpaper_mode", "fill")
        self.solid_color = wp_conf.get("solid_color", "#080b11")

        if self.wallpaper_mode == "solid":
            self.wallpaper_pixbuf = None
        elif self.wallpaper_path and os.path.exists(self.wallpaper_path):
            try:
                self.wallpaper_pixbuf = GdkPixbuf.Pixbuf.new_from_file(self.wallpaper_path)
            except Exception:
                self.wallpaper_pixbuf = None
        else:
            self.wallpaper_pixbuf = None

        self._cached_draw_params = None
        if os.path.exists(CONFIG_FILE):
            try:
                self._config_mtime = os.path.getmtime(CONFIG_FILE)
            except Exception:
                pass
        self.window.queue_draw()

    def _compute_scaled_wallpaper(self, w: int, h: int) -> None:
        if self.wallpaper_mode == "solid" or self.wallpaper_pixbuf is None:
            self._cached_scaled_pixbuf = None
            self._cached_offsets = (0, 0)
            self._cached_bg_rgb = hex_to_rgb(self.solid_color)
            return

        pw = max(1, self.wallpaper_pixbuf.get_width())
        ph = max(1, self.wallpaper_pixbuf.get_height())

        if self.wallpaper_mode == "fill":
            scale = max(w / pw, h / ph)
            dw = max(1, int(pw * scale))
            dh = max(1, int(ph * scale))
            dx = (w - dw) // 2
            dy = (h - dh) // 2
            self._cached_scaled_pixbuf = self.wallpaper_pixbuf.scale_simple(
                dw, dh, GdkPixbuf.InterpType.BILINEAR
            )
            self._cached_offsets = (dx, dy)
            self._cached_bg_rgb = (0.031, 0.043, 0.067)
        elif self.wallpaper_mode == "fit":
            scale = min(w / pw, h / ph)
            dw = max(1, int(pw * scale))
            dh = max(1, int(ph * scale))
            dx = (w - dw) // 2
            dy = (h - dh) // 2
            self._cached_scaled_pixbuf = self.wallpaper_pixbuf.scale_simple(
                dw, dh, GdkPixbuf.InterpType.BILINEAR
            )
            self._cached_offsets = (dx, dy)
            self._cached_bg_rgb = hex_to_rgb(self.solid_color)
        elif self.wallpaper_mode == "stretch":
            self._cached_scaled_pixbuf = self.wallpaper_pixbuf.scale_simple(
                w, h, GdkPixbuf.InterpType.BILINEAR
            )
            self._cached_offsets = (0, 0)
            self._cached_bg_rgb = (0.0, 0.0, 0.0)
        elif self.wallpaper_mode == "center":
            dx = (w - pw) // 2
            dy = (h - ph) // 2
            self._cached_scaled_pixbuf = self.wallpaper_pixbuf
            self._cached_offsets = (dx, dy)
            self._cached_bg_rgb = hex_to_rgb(self.solid_color)
        else:
            self._cached_scaled_pixbuf = None
            self._cached_offsets = (0, 0)
            self._cached_bg_rgb = (0.031, 0.043, 0.067)

    def _on_draw_background(self, widget: Gtk.Widget, cr) -> bool:
        alloc = widget.get_allocation()
        w, h = max(1, alloc.width), max(1, alloc.height)
        draw_key = (w, h, self.wallpaper_path, self.wallpaper_mode, self.solid_color)

        if self._cached_draw_params != draw_key:
            self._compute_scaled_wallpaper(w, h)
            self._cached_draw_params = draw_key

        bg_r, bg_g, bg_b = self._cached_bg_rgb
        cr.set_source_rgb(bg_r, bg_g, bg_b)
        cr.paint()

        if self._cached_scaled_pixbuf is not None:
            dx, dy = self._cached_offsets
            Gdk.cairo_set_source_pixbuf(cr, self._cached_scaled_pixbuf, dx, dy)
            cr.paint()
            # Subtle modern dark vignette for deep contrast
            if self.wallpaper_mode in ("fill", "stretch"):
                cr.set_source_rgba(0, 0, 0, 0.10)
                cr.paint()

        return False

    # --------------------------------------------------------------- CONFIG
    def _load_config(self) -> None:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        default_items = [
            {
                "id": "this_pc",
                "name": "This PC",
                "icon": "🖥️",
                "path": "thispc://",
                "icon_key": "computer",
            },
            {
                "id": "browser",
                "name": "Web Browser",
                "icon": "🌐",
                "path": "app://browser",
                "icon_key": "browser",
            },
            {
                "id": "terminal",
                "name": "Terminal",
                "icon": "💻",
                "path": "app://terminal",
                "icon_key": "terminal",
            },
            {
                "id": "task_manager",
                "name": "Task Manager",
                "icon": "📊",
                "path": "app://task_manager",
                "icon_key": "task_manager",
            },
            {
                "id": "web_root",
                "name": "Web Root",
                "icon": "📁",
                "path": "/var/www",
                "icon_key": "webroot",
            },
        ]
        self.wallpaper_path = DEFAULT_WALLPAPER
        self.wallpaper_mode = "fill"
        self.solid_color = "#080b11"

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    items = data.get("items", default_items)
                    for it in items:
                        it.pop("x", None)
                        it.pop("y", None)
                        if it.get("id") in ("file_manager", "fm") or it.get("name") in ("File Manager", "Files"):
                            it["name"] = "This PC"
                            it["icon"] = "🖥️"
                            it["path"] = "thispc://"
                    existing_ids = {it.get("id") for it in items}
                    for default_it in default_items:
                        if default_it["id"] not in existing_ids and default_it["id"] in ("browser", "terminal", "task_manager"):
                            items.append(default_it)

                    self.desktop_items = items
                    self.wallpaper_path = data.get("wallpaper", DEFAULT_WALLPAPER)
                    self.wallpaper_mode = data.get("wallpaper_mode", "fill")
                    self.solid_color = data.get("solid_color", "#080b11")
                    return
            except Exception:
                pass
        self.desktop_items = default_items

    def _save_config(self) -> None:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "items": self.desktop_items,
                    "wallpaper": self.wallpaper_path,
                    "wallpaper_mode": self.wallpaper_mode,
                    "solid_color": self.solid_color,
                }, f, indent=2)
            self._config_mtime = os.path.getmtime(CONFIG_FILE)
        except Exception:
            pass

    # ------------------------------------------------------------------ CSS
    def _load_css(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_data(_CSS)
        screen = Gdk.Screen.get_default()
        if screen is not None:
            Gtk.StyleContext.add_provider_for_screen(
                screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.pack_start(self._build_topbar(), False, False, 0)

        # Content row
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        outer.pack_start(content, True, True, 0)

        # Left column: desktop shortcuts
        left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        left_col.set_margin_top(16)
        left_col.set_margin_start(18)
        left_col.set_margin_end(8)
        content.pack_start(left_col, False, False, 0)
        self.icons_col = left_col

        self._build_icon_column()

        # Right side: spacer + bottom info overlay
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.pack_start(right, True, True, 0)

        desk_event = Gtk.EventBox()
        desk_event.set_visible_window(False)
        desk_event.set_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        desk_event.connect("button-press-event", self._on_desktop_click)
        right.pack_start(desk_event, True, True, 0)

        # Bottom hint
        self.hint_label = Gtk.Label(
            label="Double-click icon to open  ·  Right-click desktop for options"
        )
        self.hint_label.get_style_context().add_class("hint")
        self.hint_label.set_halign(Gtk.Align.CENTER)
        self.hint_label.set_margin_bottom(10)
        self.hint_label.set_margin_top(4)

        self.window.add(outer)

        # Floating Server Status widget positioned at bottom-right
        self.info_panel = self._build_info_panel()
        self.info_panel.set_halign(Gtk.Align.END)
        self.info_panel.set_valign(Gtk.Align.END)
        self.info_panel.set_margin_end(24)
        self.info_panel.set_margin_bottom(40)

    # ---------------------------------------------------------- TOPBAR & DOCK
    def _build_topbar(self) -> Gtk.Widget:
        bar = Gtk.Box(spacing=8)
        bar.get_style_context().add_class("topbar")
        bar.set_size_request(-1, 48)

        # 1. Start Menu Button
        self.start_btn = Gtk.Button.new_with_label("✦ Start")
        self.start_btn.get_style_context().add_class("start-btn")
        self.start_btn.connect("clicked", lambda *_: self._popup_start_menu())
        bar.pack_start(self.start_btn, False, False, 0)

        # Brand pill
        brand_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        brand_box.get_style_context().add_class("brand-pill")
        brand_lbl = Gtk.Label(label="ease-Desk")
        brand_lbl.get_style_context().add_class("brand-name")
        brand_box.pack_start(brand_lbl, False, False, 2)
        bar.pack_start(brand_box, False, False, 2)

        bar.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 2)

        # 2. Pinned Apps Bar
        self.pinned_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for app in PINNED_APPS_CONFIG:
            item_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            item_box.get_style_context().add_class("dock-item-box")

            btn = Gtk.Button()
            btn.get_style_context().add_class("dock-btn")
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.set_tooltip_text(app["tooltip"])

            img = Gtk.Image.new_from_pixbuf(get_icon_pixbuf(app["icon_key"], size=22))
            btn.add(img)
            btn.connect("clicked", lambda *_, p=app["target"]: self._launch_path(p))

            indicator = Gtk.Box()
            indicator.get_style_context().add_class("dock-indicator")
            indicator.set_halign(Gtk.Align.CENTER)

            item_box.pack_start(btn, False, False, 0)
            item_box.pack_start(indicator, False, False, 0)

            self.pinned_buttons[app["id"]] = btn
            self.pinned_indicators[app["id"]] = indicator
            self.pinned_box.pack_start(item_box, False, False, 0)

        bar.pack_start(self.pinned_box, False, False, 2)

        bar.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 4)

        # 3. Dynamic Running Applications Box (Center)
        self.running_tasks_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bar.pack_start(self.running_tasks_box, True, True, 4)

        # 4. Right Controls: Live Stats, Clock & Quick Power
        # Server Label
        self.server_label = Gtk.Label()
        self.server_label.get_style_context().add_class("server")
        bar.pack_end(self.server_label, False, False, 0)

        # Power / Exit Desktop
        exit_btn = Gtk.Button.new_with_label("🚪 Exit")
        exit_btn.get_style_context().add_class("power-btn")
        exit_btn.set_tooltip_text("Exit Cloud Desktop Session")
        exit_btn.connect("clicked", lambda *_: self._exit())
        bar.pack_end(exit_btn, False, False, 2)

        # Clock & Date Widget
        clock_event = Gtk.EventBox()
        clock_event.set_visible_window(False)
        clock_event.connect("button-press-event", lambda *_: self._toggle_calendar())
        clock_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        clock_box.get_style_context().add_class("clock-widget-box")
        clock_box.set_valign(Gtk.Align.CENTER)

        self.clock_time_label = Gtk.Label(label="00:00")
        self.clock_time_label.get_style_context().add_class("clock-time")
        self.clock_date_label = Gtk.Label(label="Today")
        self.clock_date_label.get_style_context().add_class("clock-date")

        clock_box.pack_start(self.clock_time_label, False, False, 0)
        clock_box.pack_start(self.clock_date_label, False, False, 0)
        clock_event.add(clock_box)
        bar.pack_end(clock_event, False, False, 4)

        # Live System Badges (RAM & CPU)
        self.ram_pill = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.ram_pill.get_style_context().add_class("status-pill")
        self.ram_lbl = Gtk.Label(label="RAM --%")
        self.ram_lbl.get_style_context().add_class("status-lbl")
        self.ram_pill.pack_start(self.ram_lbl, False, False, 0)
        bar.pack_end(self.ram_pill, False, False, 2)

        self.cpu_pill = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.cpu_pill.get_style_context().add_class("status-pill")
        self.cpu_lbl = Gtk.Label(label="CPU --%")
        self.cpu_lbl.get_style_context().add_class("status-lbl")
        self.cpu_pill.pack_start(self.cpu_lbl, False, False, 0)
        bar.pack_end(self.cpu_pill, False, False, 2)

        return bar

    # ---------------------------------------------------- START MENU
    def _popup_start_menu(self) -> None:
        menu = Gtk.Menu()

        items = [
            ("🖥️  This PC (Storage & Drives)", lambda: self._launch_path("thispc://")),
            ("🌐  Web Browser (Lightweight / Chrome)", lambda: self._launch_path("app://browser")),
            ("📁  User Files (~/)", lambda: self._launch_path(os.path.expanduser("~"))),
            ("💻  Terminal Console", lambda: self._launch_path("app://terminal")),
            ("📊  Task Manager", lambda: self._launch_path("app://task_manager")),
            (None, None),
            ("🌐  Web Root Directory (/var/www)", lambda: self._launch_path("/var/www")),
            ("⚙️  System Configuration (/etc)", lambda: self._launch_path("/etc")),
            ("📋  System Logs (/var/log)", lambda: self._launch_path("/var/log")),
            (None, None),
            ("🎨  Personalize Wallpaper & Theme…", lambda: self._dialog_change_wallpaper()),
            ("➕  Add Desktop Shortcut…", lambda: self._dialog_add_shortcut()),
            ("📸  Take Desktop Screenshot", lambda: self._take_screenshot()),
            (None, None),
            ("🚪  Exit Desktop Session", lambda: self._exit()),
        ]

        for label, callback in items:
            if label is None:
                menu.append(Gtk.SeparatorMenuItem())
            else:
                mi = Gtk.MenuItem.new_with_label(label)
                mi.connect("activate", lambda *_, cb=callback: cb())
                menu.append(mi)

        menu.show_all()
        menu.popup_at_widget(self.start_btn, Gdk.Gravity.SOUTH_WEST, Gdk.Gravity.NORTH_WEST, None)

    # ---------------------------------------------------- CALENDAR FLYOUT
    def _toggle_calendar(self) -> None:
        if self._cal_window is not None:
            self._cal_window.destroy()
            self._cal_window = None
            return

        win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        win.set_transient_for(self.window)
        win.set_decorated(False)
        win.set_skip_taskbar_hint(True)
        win.set_skip_pager_hint(True)
        win.get_style_context().add_class("cal-window")

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_start(16)
        vbox.set_margin_end(16)
        vbox.set_margin_top(14)
        vbox.set_margin_bottom(14)

        # Header with today's date
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title = Gtk.Label(label=f"📅 {time.strftime('%A, %B %d, %Y')}")
        title.get_style_context().add_class("cal-title")
        header.pack_start(title, True, True, 0)
        vbox.pack_start(header, False, False, 0)

        # Calendar Widget
        cal = Gtk.Calendar()
        cal.get_style_context().add_class("cal-widget")
        vbox.pack_start(cal, True, True, 0)

        # Server Specs / Uptime Summary
        stats_grid = Gtk.Grid(column_spacing=12, row_spacing=4)
        info = sysinfo.summary()
        stats = [
            ("Host:", info.get("hostname", "vps")),
            ("Platform:", info.get("os", "Linux")),
            ("CPU Cores:", f"{info.get('cpu', 1)} cores"),
            ("Disk Usage:", f"{info.get('disk_used', '')} / {info.get('disk_total', '')}"),
        ]
        for idx, (k_text, v_text) in enumerate(stats):
            kl = Gtk.Label(label=k_text, xalign=0)
            kl.get_style_context().add_class("cal-stat-key")
            vl = Gtk.Label(label=v_text, xalign=0)
            vl.get_style_context().add_class("cal-stat-val")
            stats_grid.attach(kl, 0, idx, 1, 1)
            stats_grid.attach(vl, 1, idx, 1, 1)

        vbox.pack_start(stats_grid, False, False, 4)

        # Quick Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        wp_btn = Gtk.Button.new_with_label("🎨 Wallpaper")
        wp_btn.get_style_context().add_class("quick-btn")
        wp_btn.connect("clicked", lambda *_: (win.destroy(), self._dialog_change_wallpaper()))

        shot_btn = Gtk.Button.new_with_label("📸 Screenshot")
        shot_btn.get_style_context().add_class("quick-btn")
        shot_btn.connect("clicked", lambda *_: (win.destroy(), self._take_screenshot()))

        btn_box.pack_start(wp_btn, True, True, 0)
        btn_box.pack_start(shot_btn, True, True, 0)
        vbox.pack_start(btn_box, False, False, 2)

        win.add(vbox)

        # Position top-right near clock
        screen_w = self.window.get_allocation().width or 1280
        win.set_default_size(290, 360)
        win.move(max(10, screen_w - 320), 54)

        win.connect("focus-out-event", lambda *_: (win.destroy(), setattr(self, "_cal_window", None)))
        win.show_all()
        self._cal_window = win

    def _take_screenshot(self) -> None:
        out_path = os.path.expanduser(f"~/Desktop/screenshot_{int(time.time())}.png")
        if shutil.which("scrot"):
            subprocess.Popen(["scrot", out_path])
        elif shutil.which("import"):
            subprocess.Popen(["import", "-window", "root", out_path])

    # ---------------------------------------------------- ICON COLUMN
    def _build_icon_column(self) -> None:
        for child in self.icons_col.get_children():
            self.icons_col.remove(child)
        self.icon_buttons.clear()

        for item in self.desktop_items:
            btn = self._create_icon_button(item)
            self.icon_buttons[item["id"]] = btn
            self.icons_col.pack_start(btn, False, False, 6)

        self.icons_col.show_all()

    def _create_icon_button(self, item: dict) -> Gtk.Button:
        btn = Gtk.Button()
        btn.get_style_context().add_class("icon-btn")
        btn.set_relief(Gtk.ReliefStyle.NONE)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_halign(Gtk.Align.CENTER)

        item_id = item.get("id", "").lower()
        item_name = item.get("name", "").lower()
        if "pc" in item_id or "this pc" in item_name or "computer" in item_name:
            icon_key = "computer"
        elif "terminal" in item_id or "terminal" in item_name or "console" in item_name or "bash" in item_name:
            icon_key = "terminal"
        elif "task" in item_id or "task manager" in item_name or "activity" in item_name or "monitor" in item_name:
            icon_key = "task_manager"
        elif "browser" in item_id or "web" in item_id or "www" in item_name or "web root" in item_name:
            icon_key = "browser" if "browser" in item_id or "browser" in item_name else "webroot"
        elif "trash" in item_id or "trash" in item_name:
            icon_key = "trash"
        else:
            icon_key = item.get("icon_key", "folder")

        img = Gtk.Image.new_from_pixbuf(get_icon_pixbuf(icon_key, size=48))
        box.pack_start(img, False, False, 2)

        name_lbl = Gtk.Label(label=item.get("name", "Item"))
        name_lbl.get_style_context().add_class("icon-name")
        name_lbl.set_line_wrap(True)
        name_lbl.set_max_width_chars(12)
        name_lbl.set_justify(Gtk.Justification.CENTER)
        box.pack_start(name_lbl, False, False, 0)

        btn.add(box)
        btn.connect("button-press-event", lambda w, ev, it=item: self._on_icon_click(w, ev, it))
        return btn

    # ------------------------------------------------------------ EVENTS
    def _on_icon_click(self, widget: Gtk.Widget, event: Gdk.EventButton, item: dict) -> bool:
        item_id = item["id"]

        if event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 1:
            self._launch_path(item.get("path", os.path.expanduser("~")))
            return True

        if event.button == 1:
            self._select_icon(item_id)
            return True

        if event.button == 3:
            self._select_icon(item_id)
            self._show_icon_menu(event, item)
            return True

        return False

    def _on_desktop_click(self, widget: Gtk.Widget, event: Gdk.EventButton) -> bool:
        if event.button == 1:
            self._deselect_all()
            return False
        if event.button == 3:
            self._deselect_all()
            self._show_desktop_menu(event)
            return True
        return False

    def _select_icon(self, item_id: str) -> None:
        self._deselect_all()
        self.selected_id = item_id
        btn = self.icon_buttons.get(item_id)
        if btn:
            btn.get_style_context().add_class("selected")

    def _deselect_all(self) -> None:
        self.selected_id = None
        for btn in self.icon_buttons.values():
            btn.get_style_context().remove_class("selected")

    # ----------------------------------------------------- CONTEXT MENUS
    def _show_icon_menu(self, event: Gdk.EventButton, item: dict) -> None:
        menu = Gtk.Menu()

        open_mi = Gtk.MenuItem.new_with_label(f"Open '{item.get('name')}'")
        open_mi.connect("activate", lambda *_: self._launch_path(item.get("path", "~")))
        menu.append(open_mi)

        menu.append(Gtk.SeparatorMenuItem())

        ch_icon = Gtk.MenuItem.new_with_label("Change Icon / Symbol…")
        ch_icon.connect("activate", lambda *_: self._dialog_change_icon(item))
        menu.append(ch_icon)

        rename = Gtk.MenuItem.new_with_label("Rename Shortcut…")
        rename.connect("activate", lambda *_: self._dialog_rename(item))
        menu.append(rename)

        if item.get("id") not in ("file_manager", "this_pc"):
            menu.append(Gtk.SeparatorMenuItem())
            rem = Gtk.MenuItem.new_with_label("Remove Shortcut")
            rem.connect("activate", lambda *_: self._remove_shortcut(item))
            menu.append(rem)

        menu.show_all()
        menu.popup(None, None, None, None, event.button, event.time)

    def _show_desktop_menu(self, event: Gdk.EventButton) -> None:
        menu = Gtk.Menu()

        fm_mi = Gtk.MenuItem.new_with_label("🖥️  Open This PC")
        fm_mi.connect("activate", lambda *_: self._launch_path("thispc://"))
        menu.append(fm_mi)

        br_mi = Gtk.MenuItem.new_with_label("🌐  Open Web Browser")
        br_mi.connect("activate", lambda *_: self._launch_path("app://browser"))
        menu.append(br_mi)

        tm_mi = Gtk.MenuItem.new_with_label("💻  Open Terminal")
        tm_mi.connect("activate", lambda *_: self._launch_path("app://terminal"))
        menu.append(tm_mi)

        menu.append(Gtk.SeparatorMenuItem())

        add_mi = Gtk.MenuItem.new_with_label("➕  Add Desktop Shortcut…")
        add_mi.connect("activate", lambda *_: self._dialog_add_shortcut())
        menu.append(add_mi)

        wp_mi = Gtk.MenuItem.new_with_label("🎨  Personalize Wallpaper & Themes…")
        wp_mi.connect("activate", lambda *_: self._dialog_change_wallpaper())
        menu.append(wp_mi)

        next_wp = Gtk.MenuItem.new_with_label("🔀  Cycle Next Wallpaper")
        next_wp.connect("activate", lambda *_: self._cycle_wallpaper())
        menu.append(next_wp)

        menu.append(Gtk.SeparatorMenuItem())

        ref_mi = Gtk.MenuItem.new_with_label("🔄  Refresh System Probes")
        ref_mi.connect("activate", lambda *_: self._refresh_info())
        menu.append(ref_mi)

        menu.show_all()
        menu.popup(None, None, None, None, event.button, event.time)

    def _cycle_wallpaper(self) -> None:
        cycle_next_wallpaper(CONFIG_FILE)
        self._load_wallpaper()

    # ----------------------------------------------------------- DIALOGS
    def _dialog_change_wallpaper(self) -> None:
        dialog = Gtk.Dialog(
            title="Desktop Wallpaper & Themes",
            transient_for=self.window,
            modal=True,
            destroy_with_parent=True,
        )
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(580, 520)
        dialog.get_style_context().add_class("wp-dialog")

        content = dialog.get_content_area()
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(12)

        # 1. Preset Wallpapers Section
        wp_lbl = Gtk.Label(label="SIGNATURE WALLPAPER PRESETS", xalign=0)
        wp_lbl.get_style_context().add_class("wp-section-lbl")
        main_box.pack_start(wp_lbl, False, False, 0)

        card_grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        card_buttons: dict[str, Gtk.Button] = {}

        def update_active_card() -> None:
            for p_path, btn in card_buttons.items():
                if self.wallpaper_mode != "solid" and os.path.abspath(self.wallpaper_path) == os.path.abspath(p_path):
                    btn.get_style_context().add_class("active")
                else:
                    btn.get_style_context().remove_class("active")

        for idx, (name, path) in enumerate(WALLPAPER_PRESETS):
            if not os.path.exists(path):
                continue
            card_btn = Gtk.Button()
            card_btn.get_style_context().add_class("wp-card")
            card_btn.set_relief(Gtk.ReliefStyle.NONE)

            card_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            card_vbox.set_size_request(150, 115)

            thumb_pixbuf = get_thumbnail_pixbuf(path, 140, 85)
            if thumb_pixbuf:
                img = Gtk.Image.new_from_pixbuf(thumb_pixbuf)
            else:
                img = Gtk.Image.new_from_icon_name("image-x-generic", Gtk.IconSize.DIALOG)
            card_vbox.pack_start(img, True, True, 0)

            title_lbl = Gtk.Label(label=name)
            title_lbl.get_style_context().add_class("wp-card-name")
            title_lbl.set_ellipsize(3)
            card_vbox.pack_start(title_lbl, False, False, 0)

            card_btn.add(card_vbox)
            card_btn.connect("clicked", lambda *_, p=path: (
                self._set_wallpaper(p, mode=self.wallpaper_mode if self.wallpaper_mode != "solid" else "fill"),
                update_active_card()
            ))

            card_buttons[path] = card_btn
            card_grid.attach(card_btn, idx % 3, idx // 3, 1, 1)

        update_active_card()
        main_box.pack_start(card_grid, False, False, 0)

        # 2. Solid Colors Section
        color_lbl = Gtk.Label(label="SOLID COLOR MINIMAL THEMES", xalign=0)
        color_lbl.get_style_context().add_class("wp-section-lbl")
        main_box.pack_start(color_lbl, False, False, 2)

        color_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        color_buttons: dict[str, Gtk.Button] = {}

        def update_active_color() -> None:
            for hex_col, btn in color_buttons.items():
                if self.wallpaper_mode == "solid" and self.solid_color.lower() == hex_col.lower():
                    btn.get_style_context().add_class("active")
                else:
                    btn.get_style_context().remove_class("active")

        for col_name, hex_code in SOLID_COLOR_PRESETS:
            c_btn = Gtk.Button()
            c_btn.get_style_context().add_class("color-btn")
            c_btn.set_tooltip_text(f"{col_name} ({hex_code})")
            c_btn.set_size_request(56, 36)

            c_label = Gtk.Label(label=f"<span foreground='{hex_code}'>████</span>")
            c_label.set_use_markup(True)
            c_btn.add(c_label)

            c_btn.connect("clicked", lambda *_, col=hex_code: (
                self._set_solid_color(col),
                update_active_color(),
                update_active_card()
            ))
            color_buttons[hex_code] = c_btn
            color_box.pack_start(c_btn, False, False, 0)

        update_active_color()
        main_box.pack_start(color_box, False, False, 0)

        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 4)

        # 3. Display Mode & Custom Wallpaper Row
        ctrl_grid = Gtk.Grid(column_spacing=12, row_spacing=8)

        ctrl_grid.attach(Gtk.Label(label="Display Mode:", xalign=0), 0, 0, 1, 1)
        mode_combo = Gtk.ComboBoxText()
        for mode_key, mode_title in WALLPAPER_MODES:
            mode_combo.append(mode_key, mode_title)
        mode_combo.set_active_id(self.wallpaper_mode)

        def on_mode_changed(combo: Gtk.ComboBoxText) -> None:
            new_mode = combo.get_active_id() or "fill"
            if new_mode == "solid":
                self._set_solid_color(self.solid_color)
            else:
                self._set_wallpaper(self.wallpaper_path, mode=new_mode)
            update_active_color()
            update_active_card()

        mode_combo.connect("changed", on_mode_changed)
        ctrl_grid.attach(mode_combo, 1, 0, 1, 1)

        custom_btn = Gtk.Button.new_with_label("📁  Choose Custom Image…")
        custom_btn.get_style_context().add_class("wallpaper-btn")
        custom_btn.connect("clicked", lambda *_: (
            self._dialog_browse_wallpaper(dialog),
            update_active_card(),
            update_active_color()
        ))
        ctrl_grid.attach(custom_btn, 2, 0, 1, 1)

        main_box.pack_start(ctrl_grid, False, False, 4)

        content.add(main_box)
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def _set_wallpaper(self, path: str, mode: str = "fill") -> None:
        if os.path.exists(path):
            self.wallpaper_path = path
            self.wallpaper_mode = mode
            set_wallpaper(path, mode=mode, solid_color=self.solid_color, config_path=CONFIG_FILE)
            self._load_wallpaper()

    def _set_solid_color(self, color_hex: str) -> None:
        self.solid_color = color_hex
        self.wallpaper_mode = "solid"
        set_wallpaper(self.wallpaper_path, mode="solid", solid_color=color_hex, config_path=CONFIG_FILE)
        self._load_wallpaper()

    def _dialog_browse_wallpaper(self, parent_dialog: Gtk.Dialog) -> None:
        chooser = Gtk.FileChooserDialog(
            title="Select Wallpaper Image",
            transient_for=parent_dialog,
            action=Gtk.FileChooserAction.OPEN,
        )
        chooser.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL, "Set Wallpaper", Gtk.ResponseType.OK
        )

        filter_img = Gtk.FileFilter()
        filter_img.set_name("Images (*.png, *.jpg, *.jpeg, *.webp)")
        for ext in IMAGE_EXTENSIONS:
            filter_img.add_pattern(f"*{ext}")
            filter_img.add_pattern(f"*{ext.upper()}")
        chooser.add_filter(filter_img)

        preview_img = Gtk.Image()
        chooser.set_preview_widget(preview_img)

        def update_preview(c) -> None:
            filename = c.get_preview_filename()
            if filename and wallpaper.is_image_file(filename):
                thumb = get_thumbnail_pixbuf(filename, 160, 100)
                if thumb:
                    preview_img.set_from_pixbuf(thumb)
                    c.set_preview_widget_active(True)
                    return
            c.set_preview_widget_active(False)

        chooser.connect("update-preview", update_preview)

        if chooser.run() == Gtk.ResponseType.OK:
            selected = chooser.get_filename()
            if selected and os.path.exists(selected):
                mode = self.wallpaper_mode if self.wallpaper_mode != "solid" else "fill"
                self._set_wallpaper(selected, mode=mode)
        chooser.destroy()

    def _dialog_change_icon(self, item: dict) -> None:
        dialog = Gtk.Dialog(
            title=f"Icon for '{item.get('name')}'",
            transient_for=self.window,
            modal=True,
            destroy_with_parent=True,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Apply", Gtk.ResponseType.OK)
        dialog.set_default_size(360, 240)

        content = dialog.get_content_area()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_start(16)
        vbox.set_margin_end(16)
        vbox.set_margin_top(14)
        vbox.set_margin_bottom(14)

        vbox.pack_start(Gtk.Label(label="Choose an icon / symbol:"), False, False, 0)

        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        grid.set_halign(Gtk.Align.CENTER)
        selected = [item.get("icon", "📁")]

        for i, (sym, label) in enumerate(ICON_PRESETS):
            btn = Gtk.Button.new_with_label(sym)
            btn.set_tooltip_text(label)
            btn.set_size_request(44, 44)
            btn.connect("clicked", lambda *_, s=sym: selected.__setitem__(0, s))
            grid.attach(btn, i % 5, i // 5, 1, 1)

        vbox.pack_start(grid, False, False, 0)

        vbox.pack_start(Gtk.Label(label="Or custom emoji / text:"), False, False, 0)
        custom = Gtk.Entry()
        custom.set_text(item.get("icon", "📁"))
        vbox.pack_start(custom, False, False, 0)
        content.add(vbox)
        dialog.show_all()

        if dialog.run() == Gtk.ResponseType.OK:
            item["icon"] = custom.get_text().strip() or selected[0]
            self._save_config()
            self._build_icon_column()
        dialog.destroy()

    def _dialog_rename(self, item: dict) -> None:
        dialog = Gtk.Dialog(
            title="Rename Shortcut",
            transient_for=self.window,
            modal=True,
            destroy_with_parent=True,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Save", Gtk.ResponseType.OK)
        dialog.set_default_size(320, 130)

        content = dialog.get_content_area()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_start(16)
        vbox.set_margin_end(16)
        vbox.set_margin_top(14)
        vbox.set_margin_bottom(14)
        vbox.pack_start(Gtk.Label(label="New name:"), False, False, 0)
        entry = Gtk.Entry()
        entry.set_text(item.get("name", ""))
        entry.set_activates_default(True)
        vbox.pack_start(entry, False, False, 0)
        content.add(vbox)
        dialog.show_all()

        if dialog.run() == Gtk.ResponseType.OK:
            new_name = entry.get_text().strip()
            if new_name:
                item["name"] = new_name
                self._save_config()
                self._build_icon_column()
        dialog.destroy()

    def _dialog_add_shortcut(self) -> None:
        dialog = Gtk.Dialog(
            title="Add Desktop Shortcut",
            transient_for=self.window,
            modal=True,
            destroy_with_parent=True,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Add", Gtk.ResponseType.OK)
        dialog.set_default_size(380, 210)

        content = dialog.get_content_area()
        grid = Gtk.Grid(column_spacing=10, row_spacing=10)
        grid.set_margin_start(16)
        grid.set_margin_end(16)
        grid.set_margin_top(14)
        grid.set_margin_bottom(14)

        grid.attach(Gtk.Label(label="Name:"), 0, 0, 1, 1)
        name_e = Gtk.Entry()
        name_e.set_placeholder_text("e.g. Web Root")
        grid.attach(name_e, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label="Path:"), 0, 1, 1, 1)
        path_e = Gtk.Entry()
        path_e.set_placeholder_text("e.g. /var/www")
        grid.attach(path_e, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label="Icon:"), 0, 2, 1, 1)
        icon_e = Gtk.Entry()
        icon_e.set_text("🌐")
        grid.attach(icon_e, 1, 2, 1, 1)

        content.add(grid)
        dialog.show_all()

        if dialog.run() == Gtk.ResponseType.OK:
            import uuid
            self.desktop_items.append({
                "id": str(uuid.uuid4())[:8],
                "name": name_e.get_text().strip() or "Shortcut",
                "icon": icon_e.get_text().strip() or "📁",
                "path": path_e.get_text().strip() or os.path.expanduser("~"),
            })
            self._save_config()
            self._build_icon_column()
        dialog.destroy()

    def _remove_shortcut(self, item: dict) -> None:
        self.desktop_items = [i for i in self.desktop_items if i.get("id") != item.get("id")]
        self._save_config()
        self._build_icon_column()

    # ------------------------------------------------------ STATUS PANEL
    def _build_info_panel(self) -> Gtk.Widget:
        frame = Gtk.Frame()
        frame.get_style_context().add_class("vps-frame")
        g = Gtk.Grid(column_spacing=16, row_spacing=5)
        g.set_margin_start(16)
        g.set_margin_end(16)
        g.set_margin_top(12)
        g.set_margin_bottom(12)

        title = Gtk.Label(label="Server Cloud Status")
        title.get_style_context().add_class("vps-title")
        title.set_halign(Gtk.Align.START)
        g.attach(title, 0, 0, 2, 1)

        self.vps_rows: list[tuple[Gtk.Label, Gtk.Label]] = []
        for i, key in enumerate(("Server", "OS", "CPU", "RAM", "Disk")):
            k = Gtk.Label(label=key)
            k.get_style_context().add_class("vps-key")
            k.set_halign(Gtk.Align.START)
            v = Gtk.Label()
            v.get_style_context().add_class("vps-val")
            v.set_halign(Gtk.Align.START)
            v.set_selectable(True)
            g.attach(k, 0, i + 1, 1, 1)
            g.attach(v, 1, i + 1, 1, 1)
            self.vps_rows.append((k, v))

        frame.add(g)
        return frame

    # ---------------------------------------------------------- PROCESS TRACKING & RUNNERS
    def _launch_path(self, target_path: str) -> None:
        app_id = "files"
        title = "Files"
        icon_key = "computer"

        if target_path in ("app://terminal", "terminal"):
            cmd = [sys.executable, "-m", "desktop.terminal.app", os.path.expanduser("~")]
            app_id = "terminal"
            title = "Terminal"
            icon_key = "terminal"
        elif target_path in ("app://task_manager", "task_manager"):
            cmd = [sys.executable, "-m", "desktop.task_manager.app"]
            app_id = "task_manager"
            title = "Task Manager"
            icon_key = "task_manager"
        elif target_path in ("app://wallpaper", "wallpaper", "settings"):
            self._dialog_change_wallpaper()
            return
        elif target_path in ("app://browser", "browser"):
            app_id = "browser"
            title = "Web Browser"
            icon_key = "browser"
            browser_bin = None
            for b in ("epiphany-browser", "epiphany", "midori", "min", "firefox-esr", "firefox", "chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "x-www-browser"):
                if shutil.which(b):
                    browser_bin = b
                    break
            if browser_bin:
                if "chromium" in browser_bin or "chrome" in browser_bin:
                    cmd = [
                        browser_bin,
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--password-store=basic",
                        "https://google.com",
                    ]
                else:
                    cmd = [browser_bin, "https://google.com"]
            else:
                cmd = [
                    sys.executable,
                    "-m",
                    "desktop.terminal.app",
                    os.path.expanduser("~"),
                ]
        elif target_path in ("app://editor", "editor"):
            cmd = [sys.executable, "-m", "file_manager.app", os.path.expanduser("~")]
            app_id = "editor"
            title = "Editor"
            icon_key = "editor"
        else:
            cmd = [sys.executable, "-m", "file_manager.app", target_path]
            app_id = "this_pc" if target_path == "thispc://" else "files"
            title = "This PC" if target_path == "thispc://" else os.path.basename(target_path) or "Files"
            icon_key = "computer"

        try:
            p = subprocess.Popen(
                cmd,
                cwd=ROOT,
                env=dict(os.environ, PYTHONPATH=ROOT + os.pathsep + os.environ.get("PYTHONPATH", "")),
            )
            self.children.append(p.pid)
            self.tracked_processes[p.pid] = {
                "pid": p.pid,
                "app_id": app_id,
                "title": title,
                "icon_key": icon_key,
                "popen": p,
            }
            self._update_running_tasks_ui()
        except OSError:
            pass

    def _poll_processes(self) -> None:
        dead_pids = []
        for pid, meta in self.tracked_processes.items():
            popen = meta.get("popen")
            if popen and popen.poll() is not None:
                dead_pids.append(pid)

        for pid in dead_pids:
            self.tracked_processes.pop(pid, None)

        if dead_pids:
            self._update_running_tasks_ui()

    def _update_running_tasks_ui(self) -> None:
        active_app_ids = {meta["app_id"] for meta in self.tracked_processes.values()}

        # Update indicators on pinned dock icons
        for app_id, indicator in self.pinned_indicators.items():
            if app_id in active_app_ids:
                indicator.get_style_context().add_class("active")
            else:
                indicator.get_style_context().remove_class("active")

        # Update center running tasks box
        for child in self.running_tasks_box.get_children():
            self.running_tasks_box.remove(child)

        for pid, meta in list(self.tracked_processes.items()):
            btn = Gtk.Button()
            btn.get_style_context().add_class("running-task-btn")

            h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            img = Gtk.Image.new_from_pixbuf(get_icon_pixbuf(meta["icon_key"], size=16))
            h.pack_start(img, False, False, 0)

            lbl = Gtk.Label(label=meta["title"])
            h.pack_start(lbl, False, False, 0)

            btn.add(h)
            btn.connect("clicked", lambda *_, p=pid: self._focus_or_signal_proc(p))
            self.running_tasks_box.pack_start(btn, False, False, 0)

        self.running_tasks_box.show_all()

    def _focus_or_signal_proc(self, pid: int) -> None:
        # If wmctrl or xdotool is present, activate window, otherwise pass
        if shutil.which("wmctrl"):
            subprocess.Popen(["wmctrl", "-a", self.tracked_processes.get(pid, {}).get("title", "")])

    # ---------------------------------------------------------- TICK & STATS
    def _tick_clock_and_stats(self) -> bool:
        # Clock & Date
        self.clock_time_label.set_text(time.strftime("%H:%M"))
        self.clock_date_label.set_text(time.strftime("%a, %b %d"))

        # Live CPU & RAM
        cpu = sysinfo.cpu_percent()
        ram = sysinfo.memory_percent()

        self.cpu_lbl.set_text(f"⚡ CPU {cpu:.0f}%")
        self.ram_lbl.set_text(f"🧠 RAM {ram:.0f}%")

        self.cpu_lbl.get_style_context().remove_class("status-ok")
        self.cpu_lbl.get_style_context().remove_class("status-warn")
        self.cpu_lbl.get_style_context().remove_class("status-crit")
        if cpu < 60:
            self.cpu_lbl.get_style_context().add_class("status-ok")
        elif cpu < 85:
            self.cpu_lbl.get_style_context().add_class("status-warn")
        else:
            self.cpu_lbl.get_style_context().add_class("status-crit")

        self.ram_lbl.get_style_context().remove_class("status-ok")
        self.ram_lbl.get_style_context().remove_class("status-warn")
        self.ram_lbl.get_style_context().remove_class("status-crit")
        if ram < 70:
            self.ram_lbl.get_style_context().add_class("status-ok")
        elif ram < 90:
            self.ram_lbl.get_style_context().add_class("status-warn")
        else:
            self.ram_lbl.get_style_context().add_class("status-crit")

        self._poll_processes()
        return True

    def _refresh_info(self) -> bool:
        if os.path.exists(CONFIG_FILE):
            try:
                mtime = os.path.getmtime(CONFIG_FILE)
                if mtime > self._config_mtime:
                    self._config_mtime = mtime
                    self._load_wallpaper()
            except Exception:
                pass

        info = sysinfo.summary()
        self.server_label.set_text(f"Server: {info['hostname']}")
        if hasattr(self, "vps_rows") and len(self.vps_rows) >= 5:
            self.vps_rows[0][1].set_text(info["hostname"])
            self.vps_rows[1][1].set_text(info["os"])
            self.vps_rows[2][1].set_text(f"{info['cpu']} cores")
            self.vps_rows[3][1].set_text(f"{info['mem_used']} / {info['mem_total']}")
            self.vps_rows[4][1].set_text(f"{info['disk_used']} / {info['disk_total']}")
        return True

    def _on_key_press(self, window: Gtk.Window, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Delete and self.selected_id:
            item = next((i for i in self.desktop_items if i.get("id") == self.selected_id), None)
            if item and item.get("id") not in ("file_manager", "this_pc"):
                self._remove_shortcut(item)
                return True
        return False

    def _on_delete_event(self, window, event) -> bool:
        self._exit()
        return True

    def _exit(self) -> None:
        for pid in self.children:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        animate.fade_out(self.window, duration_ms=250, on_done=Gtk.main_quit)


def main() -> int:
    if not os.environ.get("DISPLAY") or not os.environ["DISPLAY"].strip():
        from desktop.session.session import SessionManager
        print("No active $DISPLAY detected. Launching ease-Desk session manager...")
        return SessionManager().start()

    initialized = False
    for _ in range(25):
        try:
            res = Gtk.init_check()
            if isinstance(res, (tuple, list)) and res:
                if res[0]:
                    initialized = True
                    break
            elif bool(res):
                initialized = True
                break
        except Exception:
            pass
        time.sleep(0.2)

    if not initialized:
        print(f"Error: Unable to initialize GTK on display {os.environ.get('DISPLAY')}", file=sys.stderr)
        return 1

    DesktopShell()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
