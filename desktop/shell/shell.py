"""ease-Desk Shell — the minimal desktop shown after `desktop` starts.

Renders the background, top bar (server name, clock, Exit Desktop),
draggable and customizable desktop icons, and a compact VPS info panel.
Desktop icons can be dragged freely to any position just like Windows/GNOME.
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
    padding: 10px 14px;
    border-radius: 8px;
    border: 1px solid transparent;
    transition: background-color 150ms ease, border-color 150ms ease;
}
.icon-box:hover {
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
}
.icon-box.selected {
    background-color: rgba(122, 162, 247, 0.18);
    border: 1px solid rgba(122, 162, 247, 0.45);
}
.icon-box.dragging {
    background-color: rgba(122, 162, 247, 0.25);
    border: 1px dashed #7aa2f7;
    opacity: 0.90;
}
.icon-name {
    color: #f1f5f9;
    font-weight: 600;
    font-size: 13px;
    text-shadow: 0 1px 3px rgba(0,0,0,0.8);
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
        self.active_drag: dict | None = None
        self.selected_item_id: str | None = None

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
        )
        self.window.connect("delete-event", self._on_delete_event)
        self.window.connect("key-press-event", self._on_key_press)
        self.window.connect("motion-notify-event", self._on_window_motion)
        self.window.connect("button-release-event", self._on_window_button_release)

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
                "x": None,
                "y": None,
            }
        ]
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.desktop_items = data.get("items", default_items)
                    return
            except Exception:
                pass
        self.desktop_items = default_items

    def _save_config(self) -> None:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"items": self.desktop_items}, f, indent=2)
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

        # Background event box to catch right-clicks on empty desktop
        bg_event = Gtk.EventBox()
        bg_event.set_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        bg_event.connect("button-press-event", self._on_bg_click)

        fixed = Gtk.Fixed()
        bg_event.add(fixed)
        outer.pack_start(bg_event, True, True, 0)
        self.fixed = fixed

        # Build desktop items
        self._render_desktop_items()

        self.info_panel = self._build_info_panel()
        fixed.put(self.info_panel, 0, 0)

        self.hint = Gtk.Label(label="Double-click to open · Drag to arrange · Right-click to customize")
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
        # Clear existing widgets if any
        for w in list(self.item_widgets.values()):
            self.fixed.remove(w)
        self.item_widgets.clear()

        for item in self.desktop_items:
            widget = self._create_icon_widget(item)
            self.item_widgets[item["id"]] = widget
            self.fixed.put(widget, item.get("x") or 0, item.get("y") or 0)

    def _create_icon_widget(self, item: dict) -> Gtk.Widget:
        event = Gtk.EventBox()
        event.set_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.ENTER_NOTIFY_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
        )

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.get_style_context().add_class("icon-box")
        box.set_halign(Gtk.Align.CENTER)

        icon_label = Gtk.Label()
        icon_label.set_markup(f"<span font='64'>{item.get('icon', '📁')}</span>")

        name_label = Gtk.Label(label=item.get("name", "Item"))
        name_label.get_style_context().add_class("icon-name")

        box.pack_start(icon_label, False, False, 0)
        box.pack_start(name_label, False, False, 0)
        event.add(box)
        event.set_tooltip_text(f"{item.get('name')} — double-click to open, drag to move")

        def on_press(w: Gtk.Widget, event_gdk: Gdk.EventButton) -> bool:
            if event_gdk.type == Gdk.EventType._2BUTTON_PRESS and event_gdk.button == 1:
                self._launch_path(item.get("path", os.path.expanduser("~")))
                return True

            if event_gdk.button == 1:
                # Select item
                self._select_item(item["id"])
                alloc = w.get_allocation()
                # Start drag tracking
                self.active_drag = {
                    "item": item,
                    "widget": w,
                    "box": box,
                    "start_root_x": event_gdk.x_root,
                    "start_root_y": event_gdk.y_root,
                    "start_widget_x": alloc.x,
                    "start_widget_y": alloc.y,
                    "moved": False,
                }
                box.get_style_context().add_class("dragging")
                return True

            if event_gdk.button == 3:  # Right-click context menu
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

    def _on_window_motion(self, window: Gtk.Window, event_gdk: Gdk.EventMotion) -> bool:
        if not self.active_drag:
            return False

        dx = event_gdk.x_root - self.active_drag["start_root_x"]
        dy = event_gdk.y_root - self.active_drag["start_root_y"]

        if abs(dx) > 3 or abs(dy) > 3 or self.active_drag["moved"]:
            self.active_drag["moved"] = True
            win_w, win_h = self.window.get_size()
            w = self.active_drag["widget"]
            alloc = w.get_allocation()

            new_x = int(self.active_drag["start_widget_x"] + dx)
            new_y = int(self.active_drag["start_widget_y"] + dy)

            # Constrain within bounds
            new_x = max(10, min(win_w - alloc.width - 10, new_x))
            new_y = max(10, min(win_h - alloc.height - 70, new_y))

            self.fixed.move(w, new_x, new_y)
        return True

    def _on_window_button_release(self, window: Gtk.Window, event_gdk: Gdk.EventButton) -> bool:
        if event_gdk.button == 1 and self.active_drag:
            drag = self.active_drag
            self.active_drag = None
            drag["box"].get_style_context().remove_class("dragging")

            if drag["moved"]:
                alloc = drag["widget"].get_allocation()
                drag["item"]["x"] = alloc.x
                drag["item"]["y"] = alloc.y
                self._save_config()
                return True
        return False

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

            add_sc = Gtk.MenuItem.new_with_label("Add Shortcut to Folder…")
            add_sc.connect("activate", lambda *_: self._dialog_add_shortcut())
            menu.append(add_sc)

            arrange_item = Gtk.MenuItem.new_with_label("Auto-Arrange Icons")
            arrange_item.connect("activate", lambda *_: self._auto_arrange_icons())
            menu.append(arrange_item)

            menu.append(Gtk.SeparatorMenuItem())

            ref_item = Gtk.MenuItem.new_with_label("Refresh Server Info")
            ref_item.connect("activate", lambda *_: self._refresh_info())
            menu.append(ref_item)

            menu.show_all()
            menu.popup(None, None, None, None, event.button, event.time)
            return True
        return False

    def _dialog_change_icon(self, item: dict) -> None:
        dialog = Gtk.Dialog(
            title=f"Change Icon — {item.get('name')}",
            parent=self.window,
            flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
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
            parent=self.window,
            flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
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
            parent=self.window,
            flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
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
            self._render_desktop_items()
            self._auto_arrange_icons()
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
        self._apply_layout()

    def _auto_arrange_icons(self) -> None:
        start_x = 40
        start_y = 70
        spacing_y = 110
        spacing_x = 130
        max_rows = 5

        for idx, item in enumerate(self.desktop_items):
            col = idx // max_rows
            row = idx % max_rows
            item["x"] = start_x + (col * spacing_x)
            item["y"] = start_y + (row * spacing_y)

        self._save_config()
        self._apply_layout()

    # --------------------------------------------------------------- LAYOUT
    def _apply_layout(self) -> None:
        win_w, win_h = self.window.get_size()
        if win_w <= 1 or win_h <= 1:
            return

        for idx, item in enumerate(self.desktop_items):
            widget = self.item_widgets.get(item["id"])
            if not widget:
                continue
            x, y = item.get("x"), item.get("y")
            if x is None or y is None:
                # Default position
                if item.get("id") == "file_manager":
                    icon_w = widget.get_preferred_width()[1] or 100
                    x = (win_w - icon_w) // 2
                    y = max(110, int(win_h * 0.25))
                else:
                    x = 40 + (idx * 130)
                    y = 70
                item["x"] = x
                item["y"] = y
            self.fixed.move(widget, int(x), int(y))

        # Position hint cleanly below primary file manager
        fm_widget = self.item_widgets.get("file_manager")
        if fm_widget:
            fm_y = self.desktop_items[0].get("y") or max(110, int(win_h * 0.25))
            hint_w = self.hint.get_preferred_width()[1] or 400
            self.fixed.move(self.hint, max(20, (win_w - hint_w) // 2), int(fm_y + 140))

        # Position server status panel
        panel_h = self.info_panel.get_preferred_height()[1] or 160
        self.fixed.move(self.info_panel, 20, max(20, win_h - panel_h - 75))

    def _on_resize(self, window: Gtk.Window, allocation: Gdk.Rectangle) -> None:
        self._apply_layout()

    def _on_key_press(self, window: Gtk.Window, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self._exit()
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
