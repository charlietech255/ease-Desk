"""ease-Desk Shell — the minimal desktop shown after `desktop` starts.

Renders the background, top bar (server name, clock, Exit Desktop),
draggable and customizable desktop icons with grid snapping / drag-to-arrange,
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

# Desktop Grid Constants
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
    opacity: 0.90;
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
        # Maps item id → (box_widget, icon_label, name_label)
        self.item_boxes: dict[str, tuple[Gtk.Widget, Gtk.Widget, Gtk.Widget]] = {}
        self.drag_ctx: dict | None = None
        self.selected_item_id: str | None = None
        self.snap_to_grid: bool = True

        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.window.get_style_context().add_class("shell")
        self.window.set_title("ease-Desk")
        self.window.set_decorated(False)
        self.window.set_default_size(1280, 800)
        self.window.fullscreen()
        self.window.connect("delete-event", self._on_delete_event)
        self.window.connect("key-press-event", self._on_key_press)

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

        # ---- Single EventBox as the entire desktop surface -----------------
        # Gtk.Fixed has no GDK window so events placed on it are ignored.
        # By wrapping Fixed in an EventBox we get ONE real X11/Wayland window
        # that receives ALL pointer events (press, motion, release) reliably.
        desk = Gtk.EventBox()
        desk.set_visible_window(True)   # creates a real GDK sub-window
        desk.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.BUTTON1_MOTION_MASK
        )
        desk.connect("button-press-event", self._on_desk_press)
        desk.connect("motion-notify-event", self._on_desk_motion)
        desk.connect("button-release-event", self._on_desk_release)
        outer.pack_start(desk, True, True, 0)
        self.desk = desk

        fixed = Gtk.Fixed()
        desk.add(fixed)
        self.fixed = fixed

        # Build icon boxes (plain non-interactive widgets — events go to desk)
        self._render_desktop_items()

        self.info_panel = self._build_info_panel()
        fixed.put(self.info_panel, 0, 0)

        self.hint = Gtk.Label(
            label="Double-click to open  ·  Hold & drag to arrange  ·  Right-click for options"
        )
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

    # ---------------------------------------------------------------- ICONS
    def _render_desktop_items(self) -> None:
        """Remove all existing icon widgets and recreate them."""
        for box, _, _ in self.item_boxes.values():
            self.fixed.remove(box)
        self.item_boxes.clear()

        for item in self.desktop_items:
            box, ilbl, nlbl = self._make_icon_box(item)
            self.item_boxes[item["id"]] = (box, ilbl, nlbl)
            x = item.get("x") if item.get("x") is not None else GRID_START_X
            y = item.get("y") if item.get("y") is not None else GRID_START_Y
            self.fixed.put(box, int(x), int(y))

    def _make_icon_box(self, item: dict) -> tuple[Gtk.Widget, Gtk.Widget, Gtk.Widget]:
        """Create a purely visual (non-interactive) icon widget."""
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

        # Disable event propagation from labels so all events reach the desk EventBox
        icon_label.set_can_focus(False)
        name_label.set_can_focus(False)

        return box, icon_label, name_label

    # -------------------------------------------------------- HIT TESTING
    def _item_at(self, x: float, y: float) -> dict | None:
        """Return the desktop item whose box covers coordinates (x, y)."""
        for item in self.desktop_items:
            box, _, _ = self.item_boxes.get(item["id"], (None, None, None))
            if box is None:
                continue
            a = box.get_allocation()
            if a.x <= x <= a.x + a.width and a.y <= y <= a.y + a.height:
                return item
        return None

    # ----------------------------------------------- DESKTOP EVENT HANDLERS
    def _on_desk_press(self, desk: Gtk.Widget, event: Gdk.EventButton) -> bool:
        """Single surface that handles ALL desktop pointer presses."""
        item = self._item_at(event.x, event.y)

        # Double-click → open
        if event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 1:
            if item:
                self.drag_ctx = None
                self._launch_path(item.get("path", os.path.expanduser("~")))
            return True

        # Left-click — start potential drag
        if event.button == 1:
            if item:
                self._select_item(item["id"])
                box, _, _ = self.item_boxes[item["id"]]
                alloc = box.get_allocation()
                self.drag_ctx = {
                    "item": item,
                    "box": box,
                    "start_root_x": event.x_root,
                    "start_root_y": event.y_root,
                    "start_x": alloc.x,
                    "start_y": alloc.y,
                    "current_x": alloc.x,
                    "current_y": alloc.y,
                    "moved": False,
                }
            else:
                self._select_item(None)
                self.drag_ctx = None
            return True

        # Right-click
        if event.button == 3:
            if item:
                self._select_item(item["id"])
                self._show_icon_menu(item, event)
            else:
                self._select_item(None)
                self._show_desktop_menu(event)
            return True

        return False

    def _on_desk_motion(self, desk: Gtk.Widget, event: Gdk.EventMotion) -> bool:
        """Pointer motion — move the dragged icon if a drag is in progress."""
        if not self.drag_ctx:
            return False

        dx = event.x_root - self.drag_ctx["start_root_x"]
        dy = event.y_root - self.drag_ctx["start_root_y"]

        # 4-pixel threshold before we commit to a drag (avoids jitter on click)
        if abs(dx) > 4 or abs(dy) > 4 or self.drag_ctx["moved"]:
            if not self.drag_ctx["moved"]:
                self.drag_ctx["moved"] = True
                self.drag_ctx["box"].get_style_context().add_class("dragging")

            win_w, win_h = self.window.get_size()
            b = self.drag_ctx["box"]
            a = b.get_allocation()

            new_x = int(self.drag_ctx["start_x"] + dx)
            new_y = int(self.drag_ctx["start_y"] + dy)
            new_x = max(10, min(win_w - a.width - 10, new_x))
            new_y = max(10, min(win_h - a.height - 10, new_y))

            self.drag_ctx["current_x"] = new_x
            self.drag_ctx["current_y"] = new_y
            self.fixed.move(b, new_x, new_y)
        return True

    def _on_desk_release(self, desk: Gtk.Widget, event: Gdk.EventButton) -> bool:
        """Mouse button released — finalise drag position or treat as single click."""
        if event.button != 1 or not self.drag_ctx:
            return False

        ctx = self.drag_ctx
        self.drag_ctx = None
        ctx["box"].get_style_context().remove_class("dragging")

        if not ctx["moved"]:
            return True  # Was a plain click, already handled in press

        dragged_item = ctx["item"]
        raw_x, raw_y = ctx["current_x"], ctx["current_y"]

        if self.snap_to_grid:
            snap_x, snap_y, tc, tr = self._calc_grid_slot(raw_x, raw_y)
            # Swap with occupant if another icon is at the target slot
            occupant = self._find_item_at_slot(tc, tr, dragged_item["id"])
            if occupant:
                obox, _, _ = self.item_boxes[occupant["id"]]
                occupant["x"] = ctx["start_x"]
                occupant["y"] = ctx["start_y"]
                self.fixed.move(obox, ctx["start_x"], ctx["start_y"])
            dragged_item["x"] = snap_x
            dragged_item["y"] = snap_y
            self.fixed.move(ctx["box"], snap_x, snap_y)
        else:
            dragged_item["x"] = raw_x
            dragged_item["y"] = raw_y

        self._save_config()
        return True

    # ---------------------------------------------------------- GRID HELPERS
    def _calc_grid_slot(self, x: int, y: int) -> tuple[int, int, int, int]:
        win_w, win_h = self.window.get_size()
        max_cols = max(1, (win_w - GRID_START_X) // GRID_CELL_W)
        max_rows = max(1, (win_h - GRID_START_Y - 80) // GRID_CELL_H)
        col = max(0, min(max_cols - 1, round((x - GRID_START_X) / GRID_CELL_W)))
        row = max(0, min(max_rows - 1, round((y - GRID_START_Y) / GRID_CELL_H)))
        return GRID_START_X + col * GRID_CELL_W, GRID_START_Y + row * GRID_CELL_H, col, row

    def _find_item_at_slot(self, col: int, row: int, exclude_id: str) -> dict | None:
        for item in self.desktop_items:
            if item.get("id") == exclude_id:
                continue
            _, _, c, r = self._calc_grid_slot(
                item.get("x", GRID_START_X), item.get("y", GRID_START_Y)
            )
            if c == col and r == row:
                return item
        return None

    # -------------------------------------------------------- SELECTION STYLE
    def _select_item(self, item_id: str | None) -> None:
        self.selected_item_id = item_id
        for iid, (box, _, _) in self.item_boxes.items():
            ctx = box.get_style_context()
            if iid == item_id:
                ctx.add_class("selected")
            else:
                ctx.remove_class("selected")

    # ------------------------------------------------------ STATUS INFO PANEL
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

    # ------------------------------------------------------- CONTEXT MENUS
    def _show_icon_menu(self, item: dict, event: Gdk.EventButton) -> None:
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

    def _show_desktop_menu(self, event: Gdk.EventButton) -> None:
        menu = Gtk.Menu()

        fm_item = Gtk.MenuItem.new_with_label("Open File Manager")
        fm_item.connect("activate", lambda *_: self._launch_path(os.path.expanduser("~")))
        menu.append(fm_item)

        menu.append(Gtk.SeparatorMenuItem())

        arrange_item = Gtk.MenuItem.new_with_label("Auto-Arrange Icons")
        arrange_item.connect("activate", lambda *_: self._auto_arrange_icons())
        menu.append(arrange_item)

        sort_menu_item = Gtk.MenuItem.new_with_label("Sort Icons By")
        sort_submenu = Gtk.Menu()
        for label, key in [("Name (A → Z)", "name_asc"), ("Name (Z → A)", "name_desc"), ("Path", "type")]:
            si = Gtk.MenuItem.new_with_label(label)
            si.connect("activate", lambda *_, k=key: self._sort_icons(k))
            sort_submenu.append(si)
        sort_menu_item.set_submenu(sort_submenu)
        menu.append(sort_menu_item)

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

    # --------------------------------------------------------- ICON ACTIONS
    def _toggle_snap_to_grid(self, check_item: Gtk.CheckMenuItem) -> None:
        self.snap_to_grid = check_item.get_active()
        if self.snap_to_grid:
            for item in self.desktop_items:
                sx, sy, _, _ = self._calc_grid_slot(item.get("x", GRID_START_X), item.get("y", GRID_START_Y))
                item["x"] = sx
                item["y"] = sy
                box, _, _ = self.item_boxes.get(item["id"], (None, None, None))
                if box:
                    self.fixed.move(box, sx, sy)
        self._save_config()

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
            item["icon"] = custom_entry.get_text().strip() or selected_icon[0]
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
            import uuid
            new_item = {
                "id": str(uuid.uuid4())[:8],
                "name": name_entry.get_text().strip() or "Shortcut",
                "icon": icon_entry.get_text().strip() or "📁",
                "path": path_entry.get_text().strip() or os.path.expanduser("~"),
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
        win_w, win_h = self.window.get_size()
        max_rows = max(3, (win_h - GRID_START_Y - 90) // GRID_CELL_H)
        for idx, item in enumerate(self.desktop_items):
            col = idx // max_rows
            row = idx % max_rows
            item["x"] = GRID_START_X + col * GRID_CELL_W
            item["y"] = GRID_START_Y + row * GRID_CELL_H
        self._save_config()
        self._apply_layout()

    # --------------------------------------------------------------- LAYOUT
    def _apply_layout(self) -> None:
        win_w, win_h = self.window.get_size()
        if win_w <= 1 or win_h <= 1:
            return

        max_rows = max(3, (win_h - GRID_START_Y - 90) // GRID_CELL_H)
        for idx, item in enumerate(self.desktop_items):
            # Don't override position of icon currently being dragged
            if self.drag_ctx and self.drag_ctx["item"].get("id") == item.get("id"):
                continue
            box, _, _ = self.item_boxes.get(item["id"], (None, None, None))
            if box is None:
                continue
            x, y = item.get("x"), item.get("y")
            if x is None or y is None:
                col = idx // max_rows
                row = idx % max_rows
                x = GRID_START_X + col * GRID_CELL_W
                y = GRID_START_Y + row * GRID_CELL_H
                item["x"] = x
                item["y"] = y
            self.fixed.move(box, int(x), int(y))

        # Hint label — centered at bottom
        hint_w = self.hint.get_preferred_width()[1] or 400
        self.fixed.move(self.hint, max(20, (win_w - hint_w) // 2), win_h - 45)

        # Server status panel — bottom right
        panel_w = self.info_panel.get_preferred_width()[1] or 240
        panel_h = self.info_panel.get_preferred_height()[1] or 160
        self.fixed.move(self.info_panel, max(20, win_w - panel_w - 24), max(20, win_h - panel_h - 60))

    def _on_resize(self, window: Gtk.Window, allocation: Gdk.Rectangle) -> None:
        self._apply_layout()

    def _on_key_press(self, window: Gtk.Window, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self._exit()
            return True
        if event.keyval in (Gdk.KEY_F5, Gdk.KEY_r, Gdk.KEY_R):
            self._refresh_info()
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
