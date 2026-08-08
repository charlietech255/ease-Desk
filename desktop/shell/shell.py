"""ease-Desk Shell — minimal desktop environment shell.

Renders custom wallpaper background, top bar (server name, clock, Exit Desktop),
desktop icons in a clean left-column grid, and a compact VPS status panel.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys

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

_CSS = b"""
window.shell {
    background-color: #0b0e14;
}
.topbar {
    background-color: rgba(10, 14, 23, 0.85);
    border-bottom: 1px solid rgba(255,255,255,0.08);
}
.brand { color: #dce3f0; font-weight: 700; font-size: 15px; }
.start-btn {
    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
    border: 1px solid rgba(255, 255, 255, 0.20);
    border-radius: 6px;
    padding: 4px 14px;
    color: #ffffff;
    font-weight: 700;
    font-size: 12px;
}
.start-btn:hover {
    background: linear-gradient(135deg, #60a5fa 0%, #2563eb 100%);
}
.topbar-tool-btn {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    padding: 4px 12px;
    color: #cbd5e1;
    font-size: 12px;
    font-weight: 500;
}
.topbar-tool-btn:hover {
    background-color: rgba(122, 162, 247, 0.25);
    border-color: #7aa2f7;
    color: #93c5fd;
}
.server { color: #8a97ad; font-size: 12px; }
.clock { color: #7aa2f7; font-size: 14px; font-weight: 700; margin-right: 18px; }
.exitbtn {
    background: rgba(255, 255, 255, 0.06); color: #cbd5e1;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 6px; font-weight: 600; padding: 4px 14px;
}
.exitbtn:hover { background-color: rgba(239, 68, 68, 0.25); color: #fca5a5; border-color: #ef4444; }

/* Desktop icon button */
.icon-btn {
    background: rgba(15, 23, 42, 0.45);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 10px 8px;
    min-width: 96px;
    min-height: 96px;
    transition: all 120ms ease-in-out;
}
.icon-btn:hover {
    background-color: rgba(30, 41, 59, 0.75);
    border-color: rgba(122, 162, 247, 0.50);
}
.icon-btn:active, .icon-btn.selected {
    background-color: rgba(122, 162, 247, 0.30);
    border-color: #7aa2f7;
}
.icon-name {
    color: #f1f5f9;
    font-weight: 600;
    font-size: 12px;
    text-shadow: 0 2px 6px rgba(0,0,0,0.95);
}
.vps-frame {
    background-color: rgba(10, 14, 23, 0.88);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 10px;
}
.vps-title { color: #7aa2f7; font-weight: 700; font-size: 12px; }
.vps-key { color: #64748b; font-size: 12px; font-weight: 600; }
.vps-val { color: #cbd5e1; font-size: 12px; }
.hint { color: #64748b; font-size: 11px; text-shadow: 0 1px 3px rgba(0,0,0,0.8); }

/* Wallpaper Dialog Styles */
.wp-section-lbl {
    color: #7aa2f7;
    font-weight: 700;
    font-size: 12px;
}
.wp-card {
    background: rgba(15, 23, 42, 0.65);
    border: 2px solid rgba(255, 255, 255, 0.10);
    border-radius: 8px;
    padding: 6px;
    transition: all 120ms ease-in-out;
}
.wp-card:hover {
    background-color: rgba(30, 41, 59, 0.85);
    border-color: rgba(122, 162, 247, 0.50);
}
.wp-card.active {
    background-color: rgba(122, 162, 247, 0.25);
    border-color: #7aa2f7;
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
    border-color: #7aa2f7;
}
.color-btn.active {
    border-color: #ffffff;
}
.wallpaper-btn {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    padding: 8px 14px;
    color: #f1f5f9;
    font-weight: 500;
}
.wallpaper-btn:hover {
    background-color: rgba(122, 162, 247, 0.25);
    border-color: #7aa2f7;
    color: #93c5fd;
}
"""


class DesktopShell:
    def __init__(self) -> None:
        self.children: list[int] = []
        self.desktop_items: list[dict] = []
        self.icon_buttons: dict[str, Gtk.Button] = {}
        self.selected_id: str | None = None
        self.wallpaper_path: str = DEFAULT_WALLPAPER
        self.wallpaper_mode: str = "fill"
        self.solid_color: str = "#0b0e14"
        self.wallpaper_pixbuf: GdkPixbuf.Pixbuf | None = None
        self._cached_scaled_pixbuf: GdkPixbuf.Pixbuf | None = None
        self._cached_draw_params: tuple[int, int, str, str, str] | None = None
        self._cached_offsets: tuple[int, int] = (0, 0)
        self._cached_bg_rgb: tuple[float, float, float] = (0.043, 0.055, 0.078)
        self._config_mtime: float = 0.0

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
        self._tick_clock()
        self._refresh_info()

        self.window.show_all()
        GLib.timeout_add_seconds(1, self._tick_clock)
        GLib.timeout_add_seconds(5, self._refresh_info)
        animate.fade_in(self.window, duration_ms=300)

    # --------------------------------------------------------------- WALLPAPER
    def _load_wallpaper(self) -> None:
        wp_conf = get_wallpaper_config(CONFIG_FILE)
        self.wallpaper_path = wp_conf.get("wallpaper", DEFAULT_WALLPAPER)
        self.wallpaper_mode = wp_conf.get("wallpaper_mode", "fill")
        self.solid_color = wp_conf.get("solid_color", "#0b0e14")

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
        """Compute and cache the scaled pixbuf and offsets for current window size."""
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
            self._cached_bg_rgb = (0.043, 0.055, 0.078)
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
            self._cached_bg_rgb = (0.043, 0.055, 0.078)

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
            # Subtle dark scrim so icons and panels stay readable
            if self.wallpaper_mode in ("fill", "stretch"):
                cr.set_source_rgba(0, 0, 0, 0.12)
                cr.paint()

        return False  # Allow children to render on top

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
        self.solid_color = "#0b0e14"

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
                    # Ensure essential shortcuts exist if upgrading from earlier version
                    existing_ids = {it.get("id") for it in items}
                    for default_it in default_items:
                        if default_it["id"] not in existing_ids and default_it["id"] in ("browser", "terminal", "task_manager"):
                            items.append(default_it)

                    self.desktop_items = items
                    self.wallpaper_path = data.get("wallpaper", DEFAULT_WALLPAPER)
                    self.wallpaper_mode = data.get("wallpaper_mode", "fill")
                    self.solid_color = data.get("solid_color", "#0b0e14")
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
        # Main vertical box: topbar + content row
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.pack_start(self._build_topbar(), False, False, 0)

        # Content row: left icon column + spacer + right info panel
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        outer.pack_start(content, True, True, 0)

        # Left column: desktop icons in a vertical flow
        left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        left_col.set_margin_top(16)
        left_col.set_margin_start(16)
        left_col.set_margin_end(8)
        content.pack_start(left_col, False, False, 0)
        self.icons_col = left_col

        # Populate icons
        self._build_icon_column()

        # Right side: spacer + bottom info overlay
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.pack_start(right, True, True, 0)

        # Click-anywhere on empty desktop: right-click context menu
        desk_event = Gtk.EventBox()
        desk_event.set_visible_window(False)
        desk_event.set_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        desk_event.connect("button-press-event", self._on_desktop_click)
        right.pack_start(desk_event, True, True, 0)

        # Bottom status + hint overlay
        overlay = Gtk.Overlay()
        right.pack_start(overlay, False, False, 0)

        # Hint text
        self.hint_label = Gtk.Label(
            label="Double-click icon to open  ·  Right-click desktop for options"
        )
        self.hint_label.get_style_context().add_class("hint")
        self.hint_label.set_halign(Gtk.Align.CENTER)
        self.hint_label.set_margin_bottom(8)
        self.hint_label.set_margin_top(4)

        self.window.add(outer)

        # Build the status info panel as a separate widget positioned at bottom-right
        self.info_panel = self._build_info_panel()
        self.info_panel.set_halign(Gtk.Align.END)
        self.info_panel.set_valign(Gtk.Align.END)
        self.info_panel.set_margin_end(24)
        self.info_panel.set_margin_bottom(60)

    def _build_topbar(self) -> Gtk.Widget:
        bar = Gtk.Box(spacing=10)
        bar.get_style_context().add_class("topbar")
        bar.set_margin_start(14)
        bar.set_margin_end(14)
        bar.set_size_request(-1, 48)

        # 1. Start Menu Button
        self.start_btn = Gtk.Button.new_with_label("Start")
        self.start_btn.get_style_context().add_class("start-btn")
        self.start_btn.connect("clicked", lambda *_: self._popup_start_menu())
        bar.pack_start(self.start_btn, False, False, 0)

        brand = Gtk.Label(label="ease-Desk")
        brand.get_style_context().add_class("brand")
        bar.pack_start(brand, False, False, 4)

        bar.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 2)

        # 2. Quick Action Buttons
        term_btn = Gtk.Button.new_with_label("Terminal")
        term_btn.get_style_context().add_class("topbar-tool-btn")
        term_btn.connect("clicked", lambda *_: self._launch_path("app://terminal"))
        bar.pack_start(term_btn, False, False, 0)

        task_btn = Gtk.Button.new_with_label("Task Manager")
        task_btn.get_style_context().add_class("topbar-tool-btn")
        task_btn.connect("clicked", lambda *_: self._launch_path("app://task_manager"))
        bar.pack_start(task_btn, False, False, 0)

        bar.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 2)

        self.server_label = Gtk.Label()
        self.server_label.get_style_context().add_class("server")
        bar.pack_start(self.server_label, False, False, 0)

        bar.pack_start(Gtk.Box(), True, True, 0)

        exit_btn = Gtk.Button.new_with_label("Exit Desktop")
        exit_btn.get_style_context().add_class("exitbtn")
        exit_btn.connect("clicked", lambda *_: self._exit())
        bar.pack_end(exit_btn, False, False, 0)

        self.clock_label = Gtk.Label()
        self.clock_label.get_style_context().add_class("clock")
        bar.pack_end(self.clock_label, False, False, 16)

        return bar

    def _popup_start_menu(self) -> None:
        menu = Gtk.Menu()

        items = [
            ("🖥️ This PC", lambda: self._launch_path("thispc://")),
            ("🌐 Web Browser", lambda: self._launch_path("app://browser")),
            ("📁 File Manager", lambda: self._launch_path(os.path.expanduser("~"))),
            ("💻 Terminal Console", lambda: self._launch_path("app://terminal")),
            ("📊 Task Manager", lambda: self._launch_path("app://task_manager")),
            (None, None),
            ("🌐 Web Root (/var/www)", lambda: self._launch_path("/var/www")),
            ("⚙️ System Config (/etc)", lambda: self._launch_path("/etc")),
            ("🏠 User Home", lambda: self._launch_path(os.path.expanduser("~"))),
            (None, None),
            ("🎨 Change Wallpaper & Theme…", lambda: self._dialog_change_wallpaper()),
            ("➕ Add Desktop Shortcut…", lambda: self._dialog_add_shortcut()),
            (None, None),
            ("🚪 Exit Desktop", lambda: self._exit()),
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

    # ---------------------------------------------------- ICON COLUMN
    def _build_icon_column(self) -> None:
        for child in self.icons_col.get_children():
            self.icons_col.remove(child)
        self.icon_buttons.clear()

        for item in self.desktop_items:
            btn = self._create_icon_button(item)
            self.icon_buttons[item["id"]] = btn
            self.icons_col.pack_start(btn, False, False, 4)

        self.icons_col.show_all()

    def _create_icon_button(self, item: dict) -> Gtk.Button:
        btn = Gtk.Button()
        btn.get_style_context().add_class("icon-btn")
        btn.set_relief(Gtk.ReliefStyle.NONE)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_halign(Gtk.Align.CENTER)

        # Detect appropriate icon key
        item_id = item.get("id", "").lower()
        item_name = item.get("name", "").lower()
        if "pc" in item_id or "this pc" in item_name or "computer" in item_name:
            icon_key = "computer"
        elif "terminal" in item_id or "terminal" in item_name or "console" in item_name or "bash" in item_name:
            icon_key = "terminal"
        elif "task" in item_id or "task manager" in item_name or "activity" in item_name or "monitor" in item_name:
            icon_key = "task_manager"
        elif "web" in item_id or "www" in item_name or "web root" in item_name:
            icon_key = "webroot"
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

        # Double click (left): Launch
        if event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 1:
            self._launch_path(item.get("path", os.path.expanduser("~")))
            return True

        # Single click (left): Select
        if event.button == 1:
            self._select_icon(item_id)
            return True

        # Right click: Context menu
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

        fm_mi = Gtk.MenuItem.new_with_label("Open This PC")
        fm_mi.connect("activate", lambda *_: self._launch_path("thispc://"))
        menu.append(fm_mi)

        menu.append(Gtk.SeparatorMenuItem())

        add_mi = Gtk.MenuItem.new_with_label("Add Desktop Shortcut…")
        add_mi.connect("activate", lambda *_: self._dialog_add_shortcut())
        menu.append(add_mi)

        wp_mi = Gtk.MenuItem.new_with_label("🎨 Change Wallpaper…")
        wp_mi.connect("activate", lambda *_: self._dialog_change_wallpaper())
        menu.append(wp_mi)

        next_wp = Gtk.MenuItem.new_with_label("🔀 Next Wallpaper")
        next_wp.connect("activate", lambda *_: self._cycle_wallpaper())
        menu.append(next_wp)

        menu.append(Gtk.SeparatorMenuItem())

        ref_mi = Gtk.MenuItem.new_with_label("Refresh Server Info")
        ref_mi.connect("activate", lambda *_: self._refresh_info())
        menu.append(ref_mi)

        menu.show_all()
        menu.popup(None, None, None, None, event.button, event.time)

    def _cycle_wallpaper(self) -> None:
        name, path = cycle_next_wallpaper(CONFIG_FILE)
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
        dialog.set_default_size(580, 500)
        dialog.get_style_context().add_class("wp-dialog")

        content = dialog.get_content_area()
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(12)

        # 1. Preset Wallpapers Section
        wp_lbl = Gtk.Label(label="WALLPAPER PRESETS", xalign=0)
        wp_lbl.get_style_context().add_class("wp-section-lbl")
        main_box.pack_start(wp_lbl, False, False, 0)

        # Scrolled grid of wallpaper cards
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

            # Thumbnail
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
        color_lbl = Gtk.Label(label="SOLID COLOR THEMES", xalign=0)
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

            # Custom draw color square
            r, g, b = hex_to_rgb(hex_code)
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

        # Image preview in file chooser
        preview_img = Gtk.Image()
        chooser.set_preview_widget(preview_img)

        def update_preview(c) -> None:
            filename = c.get_preview_filename()
            if filename and is_image_file(filename):
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

        title = Gtk.Label(label="Server Status")
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

    # ---------------------------------------------------------- RUNNERS
    def _launch_path(self, target_path: str) -> None:
        if target_path in ("app://terminal", "terminal"):
            cmd = [sys.executable, "-m", "desktop.terminal.app", os.path.expanduser("~")]
        elif target_path in ("app://task_manager", "task_manager"):
            cmd = [sys.executable, "-m", "desktop.task_manager.app"]
        elif target_path in ("app://browser", "browser"):
            # Locate installed real web browser with sandbox-safe flags for VPS environments
            browser_bin = None
            for b in ("firefox-esr", "firefox", "chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "epiphany-browser", "epiphany", "x-www-browser"):
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
                # Open terminal with easy one-liner to install Firefox / Chromium
                cmd = [
                    sys.executable,
                    "-m",
                    "desktop.terminal.app",
                    os.path.expanduser("~"),
                ]
        elif target_path in ("app://editor", "editor"):
            cmd = [sys.executable, "-m", "file_manager.app", os.path.expanduser("~")]
        else:
            cmd = [sys.executable, "-m", "file_manager.app", target_path]

        try:
            p = subprocess.Popen(
                cmd,
                cwd=ROOT,
                env=dict(os.environ, PYTHONPATH=ROOT + os.pathsep + os.environ.get("PYTHONPATH", "")),
            )
            self.children.append(p.pid)
        except OSError:
            pass

    def _tick_clock(self) -> bool:
        import time
        self.clock_label.set_text(time.strftime("%H:%M"))
        return True

    def _refresh_info(self) -> bool:
        # Check if external processes (like File Manager) updated desktop_config.json
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

    import time
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
