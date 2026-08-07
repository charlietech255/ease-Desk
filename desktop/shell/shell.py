"""ease-Desk Shell — the minimal desktop shown after `desktop` starts.

Renders the background, top bar (server name, clock, Exit Desktop),
draggable and customizable desktop icons with grid snapping and drag-to-arrange/swap,
and a compact VPS info panel.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from shared.utilities import animate, sysinfo  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_DIR = os.path.expanduser("~/.config/ease-desk")
CONFIG_FILE = os.path.join(CONFIG_DIR, "desktop_config.json")

# Desktop Grid Constants (Matching Windows / GNOME desktop spacing)
GRID_START_X = 30
GRID_START_Y = 68
GRID_CELL_W = 120
GRID_CELL_H = 110

ICON_PRESETS = [
    ("📁", "Folder"),
    ("🖥️", "Server"),
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
    background-image: linear-gradient(180deg, #161b29, #0e121c);
}
.topbar {
    background-color: rgba(14, 18, 28, 0.85);
    border-bottom: 1px solid rgba(255,255,255,0.08);
}
.brand { color: #dce3f0; font-weight: 700; font-size: 15px; }
.server { color: #8a97ad; font-size: 12px; }
.clock { color: #7aa2f7; font-size: 14px; font-weight: 700; margin-right: 18px; }
.exitbtn {
    background: rgba(255, 255, 255, 0.05); color: #cbd5e1; border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px; font-weight: 600; padding: 4px 14px;
}
.exitbtn:hover { background-color: rgba(239, 68, 68, 0.2); color: #fca5a5; border-color: #ef4444; }
.icon-box {
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid transparent;
    transition: background-color 150ms ease, border-color 150ms ease;
    min-width: 90px;
}
.icon-box:hover {
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
}
.icon-box.selected {
    background-color: rgba(122, 162, 247, 0.22);
    border: 1px solid rgba(122, 162, 247, 0.50);
}
.icon-box.dragging {
    background-color: rgba(122, 162, 247, 0.35);
    border: 2px dashed #7aa2f7;
    opacity: 0.92;
}
.icon-name {
    color: #f1f5f9;
    font-weight: 600;
    font-size: 12px;
    text-shadow: 0 1px 3px rgba(0,0,0,0.85);
}
.vps-frame {
    background-color: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
}
.vps-title { color: #7aa2f7; font-weight: 700; font-size: 12px; }
.vps-key { color: #64748b; font-size: 12px; font-weight: 600; }
.vps-val { color: #cbd5e1; font-size: 12px; }
.hint { color: #64748b; font-size: 12px; }
"""


class DesktopShell:
    def __init__(self) -> None:
        self.children: list[int] = []
        self.desktop_items: list[dict] = []
        self.item_widgets: dict[str, Gtk.Widget] = {}
        self.drag_ctx: dict | None = None
        self.selected_item_id: str | None = None
        self.snap_to_grid: bool = True

        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.window.get_style_context().add_class("shell")
        self.window.set_title("ease-Desk")
        self.window.set_decorated(False)
        self.window.set_default_size(1280, 800)
        self.window.fullscreen()
        self.window.add_events(
            Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.BUTTON1_MOTION_MASK
        )
        self.window.connect("delete-event", self._on_delete_event)
        self.window.connect("key-press-event", self._on_key_press)
        # Window-level handlers receive ALL events during an active seat grab
        self.window.connect("motion-notify-event", self._on_window_motion)
        self.window.connect("button-release-event", self._on_window_release)
        self._seat: Gdk.Seat | None = None

        self._load_config()
        self._load_css()
        self._build_ui()
        self._tick_clock()
        self._refresh_info()

        self.window.show_all()

        GLib.timeout_add_seconds(1, self._tick_clock)
        GLib.timeout_add_seconds(5, self._refresh_info)
        animate.fade_in(self.window, duration_ms=300)

    # --------------------------------------------------------------- CONFIG
    def _load_config(self) -> None:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        default_items = [
            {
                "id": "file_manager",
                "name": "File Manager",
                "icon": "📁",
                "path": os.path.expanduser("~"),
                "x": GRID_START_X,
                "y": GRID_START_Y,
            }
        ]
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.desktop_items = data.get("items", default_items)
                    self.snap_to_grid = data.get("snap_to_grid", True)
                    return
            except Exception:
                pass
        self.desktop_items = default_items

    def _save_config(self) -> None:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {"items": self.desktop_items, "snap_to_grid": self.snap_to_grid},
                    f,
                    indent=2,
                )
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

        fixed = Gtk.Fixed()
        fixed.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.BUTTON1_MOTION_MASK
        )
        outer.pack_start(fixed, True, True, 0)
        self.fixed = fixed

        # Background click event box for empty desktop right clicks
        bg_event = Gtk.EventBox()
        bg_event.set_visible_window(False)
        bg_event.set_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        bg_event.connect("button-press-event", self._on_bg_click)
        fixed.put(bg_event, 0, 0)
        self.bg_event = bg_event

        # Build desktop items
        self._render_desktop_items()

        self.info_panel = self._build_info_panel()
        fixed.put(self.info_panel, 0, 0)

        self.hint = Gtk.Label(label="Double-click to open · Drag to arrange & swap · Right-click for options")
        self.hint.get_style_context().add_class("hint")
        fixed.put(self.hint, 0, 0)

        self.window.add(outer)
        self.window.connect("size-allocate", self._on_resize)

    def _build_topbar(self) -> Gtk.Widget:
        bar = Gtk.Box(spacing=12)
        bar.get_style_context().add_class("topbar")
        bar.set_margin_start(18)
        bar.set_margin_end(18)
        bar.set_size_request(-1, 48)

        brand = Gtk.Label(label="ease-Desk")
        brand.get_style_context().add_class("brand")
        bar.pack_start(brand, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        bar.pack_start(sep, False, False, 0)

        self.server_label = Gtk.Label()
        self.server_label.get_style_context().add_class("server")
        bar.pack_start(self.server_label, False, False, 0)

        bar.pack_start(Gtk.Box(), True, True, 0)  # spacer

        exit_btn = Gtk.Button.new_with_label("Exit Desktop")
        exit_btn.get_style_context().add_class("exitbtn")
        exit_btn.connect("clicked", lambda *_: self._exit())
        bar.pack_end(exit_btn, False, False, 0)

        self.clock_label = Gtk.Label()
        self.clock_label.get_style_context().add_class("clock")
        bar.pack_end(self.clock_label, False, False, 16)

        return bar

    def _render_desktop_items(self) -> None:
        # Clear existing widgets
        for w in list(self.item_widgets.values()):
            self.fixed.remove(w)
        self.item_widgets.clear()

        for item in self.desktop_items:
            widget = self._create_icon_widget(item)
            self.item_widgets[item["id"]] = widget
            self.fixed.put(widget, item.get("x") or GRID_START_X, item.get("y") or GRID_START_Y)

    def _create_icon_widget(self, item: dict) -> Gtk.Widget:
        event = Gtk.EventBox()
        event.set_visible_window(True)
        event.set_above_child(True)
        # Only need press events on the widget itself; motion/release are handled
        # at window level via seat grab once dragging starts.
        event.set_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
        )

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.get_style_context().add_class("icon-box")
        box.set_halign(Gtk.Align.CENTER)

        icon_label = Gtk.Label()
        icon_label.set_markup(f"<span font='54'>{item.get('icon', '📁')}</span>")

        name_label = Gtk.Label(label=item.get("name", "Item"))
        name_label.get_style_context().add_class("icon-name")
        name_label.set_max_width_chars(14)
        name_label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END

        box.pack_start(icon_label, False, False, 0)
        box.pack_start(name_label, False, False, 0)
        event.add(box)
        event.set_tooltip_text(f"{item.get('name')}\nDouble-click to open · Drag to arrange")

        def on_press(w: Gtk.Widget, event_gdk: Gdk.EventButton) -> bool:
            # Double-click → open, cancel any pending drag
            if event_gdk.type == Gdk.EventType._2BUTTON_PRESS and event_gdk.button == 1:
                self._cancel_drag()
                self._launch_path(item.get("path", os.path.expanduser("~")))
                return True

            if event_gdk.button == 1:
                self._select_item(item["id"])
                alloc = w.get_allocation()
                current_x = item.get("x") if item.get("x") is not None else alloc.x
                current_y = item.get("y") if item.get("y") is not None else alloc.y

                self.drag_ctx = {
                    "item": item,
                    "widget": w,
                    "box": box,
                    "start_root_x": event_gdk.x_root,
                    "start_root_y": event_gdk.y_root,
                    "start_x": current_x,
                    "start_y": current_y,
                    "current_x": current_x,
                    "current_y": current_y,
                    "moved": False,
                }

                # Grab the seat so that ALL pointer events (motion, release)
                # are routed to our window even when the mouse leaves the icon.
                self._begin_seat_grab(event_gdk.time)
                return True

            if event_gdk.button == 3:
                self._select_item(item["id"])
                self._show_icon_context_menu(item, event_gdk)
                return True
            return False

        event.connect("button-press-event", on_press)
        return event

    def _select_item(self, item_id: str | None) -> None:
        self.selected_item_id = item_id
        for i_id, w in self.item_widgets.items():
            child_box = w.get_child()
            if child_box:
                ctx = child_box.get_style_context()
                if i_id == item_id:
                    ctx.add_class("selected")
                else:
                    ctx.remove_class("selected")

    # --------------------------------------------------------------- DRAG & ARRANGE LOGIC
    def _begin_seat_grab(self, event_time: int) -> None:
        """Grab the pointer seat on the main window so motion/release events are
        always delivered to our window during dragging, regardless of where the
        mouse cursor is on screen."""
        if not self.drag_ctx:
            return
        gdk_window = self.window.get_window()
        if gdk_window is None:
            return
        display = Gdk.Display.get_default()
        if display is None:
            return
        seat = display.get_default_seat()
        if seat is None:
            return

        status = seat.grab(
            gdk_window,
            Gdk.SeatCapabilities.ALL_POINTING,
            False,   # owner_events=False → all events go to gdk_window
            None,
            None,
            None,
        )
        if status == Gdk.GrabStatus.SUCCESS:
            self._seat = seat
            # Now that we have the grab, show the dragging style
            self.drag_ctx["box"].get_style_context().add_class("dragging")
        else:
            # Grab failed (e.g. running headless); fall back to ungrabbed mode
            self._seat = None
            self.drag_ctx["box"].get_style_context().add_class("dragging")

    def _end_seat_grab(self) -> None:
        """Release the seat grab acquired in _begin_seat_grab."""
        if self._seat is not None:
            self._seat.ungrab()
            self._seat = None

    def _cancel_drag(self) -> None:
        """Abort an in-progress drag without saving."""
        if self.drag_ctx:
            self.drag_ctx["box"].get_style_context().remove_class("dragging")
            self.drag_ctx = None
        self._end_seat_grab()

    def _calc_grid_slot(self, x: int, y: int) -> tuple[int, int, int, int]:
        """Calculates snapped (x, y) and (col, row) for given coordinates."""
        win_w, win_h = self.window.get_size()
        max_cols = max(1, (win_w - GRID_START_X) // GRID_CELL_W)
        max_rows = max(1, (win_h - GRID_START_Y - 80) // GRID_CELL_H)

        col = max(0, min(max_cols - 1, round((x - GRID_START_X) / GRID_CELL_W)))
        row = max(0, min(max_rows - 1, round((y - GRID_START_Y) / GRID_CELL_H)))

        snap_x = GRID_START_X + (col * GRID_CELL_W)
        snap_y = GRID_START_Y + (row * GRID_CELL_H)
        return snap_x, snap_y, col, row

    def _find_item_at_grid_slot(self, target_col: int, target_row: int, exclude_id: str) -> dict | None:
        for item in self.desktop_items:
            if item.get("id") == exclude_id:
                continue
            ix = item.get("x", GRID_START_X)
            iy = item.get("y", GRID_START_Y)
            _, _, col, row = self._calc_grid_slot(ix, iy)
            if col == target_col and row == target_row:
                return item
        return None

    def _on_window_motion(self, window: Gtk.Window, event_gdk: Gdk.EventMotion) -> bool:
        """Called for every pointer motion event while the seat grab is active."""
        if not self.drag_ctx:
            return False

        dx = event_gdk.x_root - self.drag_ctx["start_root_x"]
        dy = event_gdk.y_root - self.drag_ctx["start_root_y"]

        # Start moving after a 3-pixel threshold to distinguish from a normal click
        if abs(dx) > 3 or abs(dy) > 3 or self.drag_ctx["moved"]:
            self.drag_ctx["moved"] = True
            win_w, win_h = self.window.get_size()
            w = self.drag_ctx["widget"]
            alloc = w.get_allocation()

            new_x = int(self.drag_ctx["start_x"] + dx)
            new_y = int(self.drag_ctx["start_y"] + dy)

            # Constrain within desktop bounds (stay clear of topbar + bottom edge)
            new_x = max(10, min(win_w - alloc.width - 10, new_x))
            new_y = max(10, min(win_h - alloc.height - 10, new_y))

            self.drag_ctx["current_x"] = new_x
            self.drag_ctx["current_y"] = new_y
            self.fixed.move(w, new_x, new_y)
        return True

    def _on_window_release(self, window: Gtk.Window, event_gdk: Gdk.EventButton) -> bool:
        """Called when the mouse button is released; finalises the drag."""
        if event_gdk.button != 1 or not self.drag_ctx:
            return False

        ctx = self.drag_ctx
        self.drag_ctx = None
        self._end_seat_grab()
        ctx["box"].get_style_context().remove_class("dragging")

        if ctx["moved"]:
            dragged_item = ctx["item"]
            raw_x = ctx["current_x"]
            raw_y = ctx["current_y"]

            if self.snap_to_grid:
                snap_x, snap_y, target_col, target_row = self._calc_grid_slot(raw_x, raw_y)
                # If target slot is occupied → swap positions
                occupant = self._find_item_at_grid_slot(target_col, target_row, dragged_item["id"])
                if occupant:
                    occupant_widget = self.item_widgets.get(occupant["id"])
                    occupant["x"] = ctx["start_x"]
                    occupant["y"] = ctx["start_y"]
                    if occupant_widget:
                        self.fixed.move(occupant_widget, ctx["start_x"], ctx["start_y"])

                dragged_item["x"] = snap_x
                dragged_item["y"] = snap_y
                self.fixed.move(ctx["widget"], snap_x, snap_y)
            else:
                dragged_item["x"] = raw_x
                dragged_item["y"] = raw_y
                self.fixed.move(ctx["widget"], raw_x, raw_y)

            self._save_config()
        return True

    def _build_info_panel(self) -> Gtk.Widget:
        frame = Gtk.Frame()
        frame.get_style_context().add_class("vps-frame")
        grid = Gtk.Grid(column_spacing=16, row_spacing=5)
        grid.set_margin_start(16)
        grid.set_margin_end(16)
        grid.set_margin_top(12)
        grid.set_margin_bottom(12)

        title = Gtk.Label(label="Server Status")
        title.get_style_context().add_class("vps-title")
        title.set_halign(Gtk.Align.START)
        grid.attach(title, 0, 0, 2, 1)

        self.vps_rows: list[tuple[Gtk.Label, Gtk.Label]] = []
        for i, key in enumerate(("Server", "OS", "CPU", "RAM", "Disk")):
            k = Gtk.Label(label=key)
            k.get_style_context().add_class("vps-key")
            k.set_halign(Gtk.Align.START)
            v = Gtk.Label()
            v.get_style_context().add_class("vps-val")
            v.set_halign(Gtk.Align.START)
            v.set_selectable(True)
            grid.attach(k, 0, i + 1, 1, 1)
            grid.attach(v, 1, i + 1, 1, 1)
            self.vps_rows.append((k, v))

        frame.add(grid)
        return frame

    # --------------------------------------------------------------- CONTEXT MENUS & ACTIONS
    def _show_icon_context_menu(self, item: dict, event: Gdk.EventButton) -> None:
        menu = Gtk.Menu()

        open_item = Gtk.MenuItem.new_with_label(f"Open {item.get('name')}")
        open_item.connect("activate", lambda *_: self._launch_path(item.get("path", "~")))
        menu.append(open_item)

        menu.append(Gtk.SeparatorMenuItem())

        change_icon = Gtk.MenuItem.new_with_label("Change Icon / Symbol…")
        change_icon.connect("activate", lambda *_: self._dialog_change_icon(item))
        menu.append(change_icon)

        rename_item = Gtk.MenuItem.new_with_label("Rename Shortcut…")
        rename_item.connect("activate", lambda *_: self._dialog_rename_item(item))
        menu.append(rename_item)

        reset_pos = Gtk.MenuItem.new_with_label("Reset Position")
        reset_pos.connect("activate", lambda *_: self._reset_item_position(item))
        menu.append(reset_pos)

        if item.get("id") != "file_manager":
            menu.append(Gtk.SeparatorMenuItem())
            del_item = Gtk.MenuItem.new_with_label("Remove Shortcut")
            del_item.connect("activate", lambda *_: self._remove_shortcut(item))
            menu.append(del_item)

        menu.show_all()
        menu.popup(None, None, None, None, event.button, event.time)

    def _on_bg_click(self, widget: Gtk.Widget, event: Gdk.EventButton) -> bool:
        self._select_item(None)
        if event.button == 3:  # Right-click on empty desktop
            menu = Gtk.Menu()

            fm_item = Gtk.MenuItem.new_with_label("Open File Manager")
            fm_item.connect("activate", lambda *_: self._launch_path(os.path.expanduser("~")))
            menu.append(fm_item)

            menu.append(Gtk.SeparatorMenuItem())

            # Auto Arrange
            arrange_item = Gtk.MenuItem.new_with_label("Auto-Arrange Icons")
            arrange_item.connect("activate", lambda *_: self._auto_arrange_icons())
            menu.append(arrange_item)

            # Sort Submenu
            sort_menu_item = Gtk.MenuItem.new_with_label("Sort Icons By")
            sort_submenu = Gtk.Menu()

            s_name_asc = Gtk.MenuItem.new_with_label("Name (A → Z)")
            s_name_asc.connect("activate", lambda *_: self._sort_icons("name_asc"))
            sort_submenu.append(s_name_asc)

            s_name_desc = Gtk.MenuItem.new_with_label("Name (Z → A)")
            s_name_desc.connect("activate", lambda *_: self._sort_icons("name_desc"))
            sort_submenu.append(s_name_desc)

            s_type = Gtk.MenuItem.new_with_label("Type / Path")
            s_type.connect("activate", lambda *_: self._sort_icons("type"))
            sort_submenu.append(s_type)

            sort_menu_item.set_submenu(sort_submenu)
            menu.append(sort_menu_item)

            # Snap to grid toggle
            snap_item = Gtk.CheckMenuItem.new_with_label("Snap to Grid")
            snap_item.set_active(self.snap_to_grid)
            snap_item.connect("toggled", self._toggle_snap_to_grid)
            menu.append(snap_item)

            menu.append(Gtk.SeparatorMenuItem())

            add_sc = Gtk.MenuItem.new_with_label("Add Desktop Shortcut…")
            add_sc.connect("activate", lambda *_: self._dialog_add_shortcut())
            menu.append(add_sc)

            menu.append(Gtk.SeparatorMenuItem())

            ref_item = Gtk.MenuItem.new_with_label("Refresh Server Info")
            ref_item.connect("activate", lambda *_: self._refresh_info())
            menu.append(ref_item)

            menu.show_all()
            menu.popup(None, None, None, None, event.button, event.time)
            return True
        return False

    def _toggle_snap_to_grid(self, check_item: Gtk.CheckMenuItem) -> None:
        self.snap_to_grid = check_item.get_active()
        if self.snap_to_grid:
            self._snap_all_to_grid()
        self._save_config()

    def _snap_all_to_grid(self) -> None:
        for item in self.desktop_items:
            x = item.get("x", GRID_START_X)
            y = item.get("y", GRID_START_Y)
            sx, sy, _, _ = self._calc_grid_slot(x, y)
            item["x"] = sx
            item["y"] = sy
            w = self.item_widgets.get(item["id"])
            if w:
                self.fixed.move(w, sx, sy)

    def _sort_icons(self, sort_type: str) -> None:
        if sort_type == "name_asc":
            self.desktop_items.sort(key=lambda i: (i.get("id") != "file_manager", i.get("name", "").lower()))
        elif sort_type == "name_desc":
            self.desktop_items.sort(key=lambda i: (i.get("id") != "file_manager", i.get("name", "").lower()), reverse=True)
        elif sort_type == "type":
            self.desktop_items.sort(key=lambda i: (i.get("id") != "file_manager", i.get("path", "")))

        self._auto_arrange_icons()

    def _dialog_change_icon(self, item: dict) -> None:
        dialog = Gtk.Dialog(
            title=f"Change Icon — {item.get('name')}",
            transient_for=self.window,
            modal=True,
            destroy_with_parent=True,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Apply", Gtk.ResponseType.OK)
        dialog.set_default_size(360, 260)

        content = dialog.get_content_area()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(14)
        box.set_margin_bottom(14)

        lbl = Gtk.Label(label="Select a new icon or symbol:")
        lbl.set_halign(Gtk.Align.START)
        box.pack_start(lbl, False, False, 0)

        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        selected_icon = [item.get("icon", "📁")]

        custom_entry = Gtk.Entry()
        custom_entry.set_text(item.get("icon", "📁"))
        custom_entry.set_placeholder_text("Or enter custom symbol/emoji…")

        def select(symbol: str) -> None:
            selected_icon[0] = symbol
            custom_entry.set_text(symbol)

        for i, (sym, label_text) in enumerate(ICON_PRESETS):
            btn = Gtk.Button.new_with_label(f"{sym} {label_text}")
            btn.connect("clicked", lambda *_, s=sym: select(s))
            grid.attach(btn, i % 2, i // 2, 1, 1)

        box.pack_start(grid, True, True, 0)
        box.pack_start(Gtk.Label(label="Custom Symbol / Text:"), False, False, 0)
        box.pack_start(custom_entry, False, False, 0)

        content.add(box)
        dialog.show_all()

        if dialog.run() == Gtk.ResponseType.OK:
            choice = custom_entry.get_text().strip() or selected_icon[0]
            item["icon"] = choice
            self._save_config()
            self._render_desktop_items()
            self._apply_layout()
            self.fixed.show_all()
        dialog.destroy()

    def _dialog_rename_item(self, item: dict) -> None:
        dialog = Gtk.Dialog(
            title="Rename Shortcut",
            transient_for=self.window,
            modal=True,
            destroy_with_parent=True,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Save", Gtk.ResponseType.OK)
        dialog.set_default_size(320, 140)

        content = dialog.get_content_area()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(14)
        box.set_margin_bottom(14)

        box.pack_start(Gtk.Label(label="New name:"), False, False, 0)
        entry = Gtk.Entry()
        entry.set_text(item.get("name", ""))
        entry.set_activates_default(True)
        box.pack_start(entry, False, False, 0)

        content.add(box)
        dialog.show_all()

        if dialog.run() == Gtk.ResponseType.OK:
            new_name = entry.get_text().strip()
            if new_name:
                item["name"] = new_name
                self._save_config()
                self._render_desktop_items()
                self._apply_layout()
                self.fixed.show_all()
        dialog.destroy()

    def _dialog_add_shortcut(self) -> None:
        dialog = Gtk.Dialog(
            title="Add Desktop Shortcut",
            transient_for=self.window,
            modal=True,
            destroy_with_parent=True,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Add Shortcut", Gtk.ResponseType.OK)
        dialog.set_default_size(380, 220)

        content = dialog.get_content_area()
        grid = Gtk.Grid(column_spacing=10, row_spacing=10)
        grid.set_margin_start(16)
        grid.set_margin_end(16)
        grid.set_margin_top(14)
        grid.set_margin_bottom(14)

        grid.attach(Gtk.Label(label="Shortcut Name:"), 0, 0, 1, 1)
        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text("e.g. Web Root or Server Logs")
        grid.attach(name_entry, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label="Folder / File Path:"), 0, 1, 1, 1)
        path_entry = Gtk.Entry()
        path_entry.set_placeholder_text("e.g. /var/www or /etc")
        grid.attach(path_entry, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label="Icon Symbol:"), 0, 2, 1, 1)
        icon_entry = Gtk.Entry()
        icon_entry.set_text("🌐")
        grid.attach(icon_entry, 1, 2, 1, 1)

        content.add(grid)
        dialog.show_all()

        if dialog.run() == Gtk.ResponseType.OK:
            name = name_entry.get_text().strip() or "Folder Shortcut"
            path = path_entry.get_text().strip() or os.path.expanduser("~")
            icon = icon_entry.get_text().strip() or "📁"
            import uuid

            new_item = {
                "id": str(uuid.uuid4())[:8],
                "name": name,
                "icon": icon,
                "path": path,
                "x": None,
                "y": None,
            }
            self.desktop_items.append(new_item)
            self._save_config()
            self._auto_arrange_icons()
            self._render_desktop_items()
            self._apply_layout()
            self.fixed.show_all()
        dialog.destroy()

    def _remove_shortcut(self, item: dict) -> None:
        self.desktop_items = [i for i in self.desktop_items if i.get("id") != item.get("id")]
        self._save_config()
        self._render_desktop_items()
        self._apply_layout()
        self.fixed.show_all()

    def _reset_item_position(self, item: dict) -> None:
        item["x"] = None
        item["y"] = None
        self._save_config()
        self._auto_arrange_icons()

    def _auto_arrange_icons(self) -> None:
        """Arranges all icons into clean sequential grid columns (Top-to-Bottom, Left-to-Right)."""
        win_w, win_h = self.window.get_size()
        max_rows = max(3, (win_h - GRID_START_Y - 90) // GRID_CELL_H)

        for idx, item in enumerate(self.desktop_items):
            col = idx // max_rows
            row = idx % max_rows
            item["x"] = GRID_START_X + (col * GRID_CELL_W)
            item["y"] = GRID_START_Y + (row * GRID_CELL_H)

        self._save_config()
        self._apply_layout()

    # --------------------------------------------------------------- LAYOUT
    def _apply_layout(self) -> None:
        win_w, win_h = self.window.get_size()
        if win_w <= 1 or win_h <= 1:
            return

        # Update background event box size to cover whole fixed container
        self.bg_event.set_size_request(win_w, win_h)

        max_rows = max(3, (win_h - GRID_START_Y - 90) // GRID_CELL_H)

        for idx, item in enumerate(self.desktop_items):
            if self.drag_ctx and item.get("id") == self.drag_ctx["item"].get("id"):
                continue
            widget = self.item_widgets.get(item["id"])
            if not widget:
                continue
            x, y = item.get("x"), item.get("y")
            if x is None or y is None:
                # Default position on grid
                col = idx // max_rows
                row = idx % max_rows
                x = GRID_START_X + (col * GRID_CELL_W)
                y = GRID_START_Y + (row * GRID_CELL_H)
                item["x"] = x
                item["y"] = y
            self.fixed.move(widget, int(x), int(y))

        # Position hint cleanly below desktop items or center bottom
        hint_w = self.hint.get_preferred_width()[1] or 400
        self.fixed.move(self.hint, max(20, (win_w - hint_w) // 2), win_h - 45)

        # Position server status panel at bottom right
        panel_w = self.info_panel.get_preferred_width()[1] or 240
        panel_h = self.info_panel.get_preferred_height()[1] or 160
        self.fixed.move(self.info_panel, max(20, win_w - panel_w - 24), max(20, win_h - panel_h - 60))

    def _on_resize(self, window: Gtk.Window, allocation: Gdk.Rectangle) -> None:
        self._apply_layout()

    def _on_key_press(self, window: Gtk.Window, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self._exit()
            return True
        if event.keyval == Gdk.KEY_F5 or (
            event.keyval in (Gdk.KEY_r, Gdk.KEY_R) and (event.state & Gdk.ModifierType.CONTROL_MASK)
        ):
            self._refresh_info()
            self._apply_layout()
            return True
        if event.keyval == Gdk.KEY_Delete and self.selected_item_id:
            for item in self.desktop_items:
                if item.get("id") == self.selected_item_id and item.get("id") != "file_manager":
                    self._remove_shortcut(item)
                    return True
        return False

    def _on_delete_event(self, window: Gtk.Window, event: Gdk.Event) -> bool:
        self._exit()
        return True

    # -------------------------------------------------------------- ACTIONS
    def _launch_path(self, path: str) -> None:
        target = os.path.expanduser(path)
        env = dict(os.environ)
        env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "file_manager", target],
                env=env,
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.children.append(proc.pid)
        except OSError:
            pass

    def _exit(self) -> None:
        for pid in self.children:
            try:
                os.kill(pid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                pass
        self.children.clear()
        animate.fade_out(self.window, duration_ms=260, on_done=self._quit)

    def _quit(self) -> None:
        self.window.destroy()
        Gtk.main_quit()

    # --------------------------------------------------------------- TIMERS
    def _tick_clock(self) -> bool:
        import datetime

        self.clock_label.set_text(datetime.datetime.now().strftime("%H:%M"))
        return True

    def _refresh_info(self) -> bool:
        info = sysinfo.summary()
        self.server_label.set_text(f"Server: {info['hostname']}")
        values = [
            info["hostname"],
            info["os"],
            f"{info['cpu']} cores",
            f"{info['mem_used']} / {info['mem_total']}",
            f"{info['disk_used']} / {info['disk_total']}",
        ]
        for (k_label, v_label), value in zip(self.vps_rows, values):
            v_label.set_text(value)
        return True


def main() -> int:
    shell = DesktopShell()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
