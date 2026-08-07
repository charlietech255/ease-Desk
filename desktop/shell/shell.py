"""ease-Desk Shell — minimal desktop environment shell.

Renders the background, top bar (server name, clock, Exit Desktop),
desktop icons in a clean left-column grid, and a compact VPS status panel.
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
    background-color: rgba(14, 18, 28, 0.88);
    border-bottom: 1px solid rgba(255,255,255,0.08);
}
.brand { color: #dce3f0; font-weight: 700; font-size: 15px; }
.server { color: #8a97ad; font-size: 12px; }
.clock { color: #7aa2f7; font-size: 14px; font-weight: 700; margin-right: 18px; }
.exitbtn {
    background: rgba(255, 255, 255, 0.05); color: #cbd5e1;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 6px; font-weight: 600; padding: 4px 14px;
}
.exitbtn:hover { background-color: rgba(239, 68, 68, 0.2); color: #fca5a5; border-color: #ef4444; }

/* Desktop icon button */
.icon-btn {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 10px 8px;
    min-width: 96px;
    min-height: 96px;
}
.icon-btn:hover {
    background-color: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.15);
}
.icon-btn:active {
    background-color: rgba(122, 162, 247, 0.22);
    border-color: rgba(122, 162, 247, 0.50);
}
.icon-btn.selected {
    background-color: rgba(122, 162, 247, 0.22);
    border-color: rgba(122, 162, 247, 0.50);
}
.icon-name {
    color: #f1f5f9;
    font-weight: 600;
    font-size: 12px;
    text-shadow: 0 1px 4px rgba(0,0,0,0.9);
}
.vps-frame {
    background-color: rgba(15, 23, 42, 0.88);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
}
.vps-title { color: #7aa2f7; font-weight: 700; font-size: 12px; }
.vps-key { color: #64748b; font-size: 12px; font-weight: 600; }
.vps-val { color: #cbd5e1; font-size: 12px; }
.hint { color: #475569; font-size: 11px; }
"""


class DesktopShell:
    def __init__(self) -> None:
        self.children: list[int] = []
        self.desktop_items: list[dict] = []
        self.icon_buttons: dict[str, Gtk.Button] = {}
        self.selected_id: str | None = None

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
            }
        ]
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    items = data.get("items", default_items)
                    # Strip old x/y — layout is now purely grid-driven
                    for it in items:
                        it.pop("x", None)
                        it.pop("y", None)
                    self.desktop_items = items
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

        # Bottom status + hint overlay inside a fixed at the window level
        overlay = Gtk.Overlay()
        right.pack_start(overlay, False, False, 0)

        # Hint text
        self.hint_label = Gtk.Label(
            label="Double-click icon to open  ·  Right-click for options"
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
        bar = Gtk.Box(spacing=12)
        bar.get_style_context().add_class("topbar")
        bar.set_margin_start(18)
        bar.set_margin_end(18)
        bar.set_size_request(-1, 48)

        brand = Gtk.Label(label="ease-Desk")
        brand.get_style_context().add_class("brand")
        bar.pack_start(brand, False, False, 0)

        bar.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 0)

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

    def _build_icon_column(self) -> None:
        """Rebuild all icon buttons in the left column."""
        # Remove existing children
        for child in self.icons_col.get_children():
            self.icons_col.remove(child)
        self.icon_buttons.clear()

        for item in self.desktop_items:
            btn = self._make_icon_button(item)
            self.icon_buttons[item["id"]] = btn
            self.icons_col.pack_start(btn, False, False, 4)

        self.icons_col.show_all()

    def _make_icon_button(self, item: dict) -> Gtk.Button:
        """Create one desktop icon as a styled Gtk.Button."""
        btn = Gtk.Button()
        btn.get_style_context().add_class("icon-btn")
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.set_focus_on_click(False)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        inner.set_halign(Gtk.Align.CENTER)

        icon_lbl = Gtk.Label()
        icon_lbl.set_markup(f"<span font='48'>{item.get('icon', '📁')}</span>")

        name_lbl = Gtk.Label(label=item.get("name", "Item"))
        name_lbl.get_style_context().add_class("icon-name")
        name_lbl.set_max_width_chars(12)
        name_lbl.set_ellipsize(3)

        inner.pack_start(icon_lbl, False, False, 0)
        inner.pack_start(name_lbl, False, False, 0)
        btn.add(inner)

        # Single click → select
        btn.connect(
            "clicked",
            lambda *_, b=btn, i=item: self._on_icon_click(b, i),
        )
        # Double click via button-press-event
        btn.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        btn.connect(
            "button-press-event",
            lambda w, ev, i=item: self._on_icon_press(w, ev, i),
        )
        # Right-click
        btn.connect(
            "button-release-event",
            lambda w, ev, i=item: self._on_icon_right(w, ev, i),
        )

        btn.set_tooltip_text(f"{item.get('name')}  —  {item.get('path', '')}")
        return btn

    # ---------------------------------------------------------- ICON EVENTS
    def _on_icon_press(self, widget: Gtk.Widget, event: Gdk.EventButton, item: dict) -> bool:
        if event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 1:
            self._launch_path(item.get("path", os.path.expanduser("~")))
            return True
        return False

    def _on_icon_click(self, btn: Gtk.Button, item: dict) -> None:
        """Single-click → select the icon."""
        self._select(item["id"])

    def _on_icon_right(self, widget: Gtk.Widget, event: Gdk.EventButton, item: dict) -> bool:
        if event.button == 3:
            self._show_icon_menu(item, event)
            return True
        return False

    def _select(self, item_id: str | None) -> None:
        self.selected_id = item_id
        for iid, btn in self.icon_buttons.items():
            ctx = btn.get_style_context()
            if iid == item_id:
                ctx.add_class("selected")
            else:
                ctx.remove_class("selected")

    def _on_desktop_click(self, widget: Gtk.Widget, event: Gdk.EventButton) -> bool:
        """Right-click on empty desktop area → context menu."""
        self._select(None)
        if event.button == 3:
            self._show_desktop_menu(event)
            return True
        return False

    # ------------------------------------------------------ CONTEXT MENUS
    def _show_icon_menu(self, item: dict, event: Gdk.EventButton) -> None:
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

        if item.get("id") != "file_manager":
            menu.append(Gtk.SeparatorMenuItem())
            rem = Gtk.MenuItem.new_with_label("Remove Shortcut")
            rem.connect("activate", lambda *_: self._remove_shortcut(item))
            menu.append(rem)

        menu.show_all()
        menu.popup(None, None, None, None, event.button, event.time)

    def _show_desktop_menu(self, event: Gdk.EventButton) -> None:
        menu = Gtk.Menu()

        fm_mi = Gtk.MenuItem.new_with_label("Open File Manager")
        fm_mi.connect("activate", lambda *_: self._launch_path(os.path.expanduser("~")))
        menu.append(fm_mi)

        menu.append(Gtk.SeparatorMenuItem())

        add_mi = Gtk.MenuItem.new_with_label("Add Desktop Shortcut…")
        add_mi.connect("activate", lambda *_: self._dialog_add_shortcut())
        menu.append(add_mi)

        menu.append(Gtk.SeparatorMenuItem())

        ref_mi = Gtk.MenuItem.new_with_label("Refresh Server Info")
        ref_mi.connect("activate", lambda *_: self._refresh_info())
        menu.append(ref_mi)

        menu.show_all()
        menu.popup(None, None, None, None, event.button, event.time)

    # --------------------------------------------------------- DIALOGS
    def _dialog_change_icon(self, item: dict) -> None:
        dialog = Gtk.Dialog(
            title=f"Change Icon — {item.get('name')}",
            transient_for=self.window,
            modal=True,
            destroy_with_parent=True,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Apply", Gtk.ResponseType.OK)
        dialog.set_default_size(360, 280)

        content = dialog.get_content_area()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_start(16); vbox.set_margin_end(16)
        vbox.set_margin_top(14); vbox.set_margin_bottom(14)

        lbl = Gtk.Label(label="Pick a preset or enter a custom emoji:")
        lbl.set_halign(Gtk.Align.START)
        vbox.pack_start(lbl, False, False, 0)

        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        selected = [item.get("icon", "📁")]
        custom = Gtk.Entry()
        custom.set_text(item.get("icon", "📁"))
        custom.set_placeholder_text("Custom emoji or text…")

        def pick(sym: str) -> None:
            selected[0] = sym
            custom.set_text(sym)

        for i, (sym, txt) in enumerate(ICON_PRESETS):
            b = Gtk.Button.new_with_label(f"{sym} {txt}")
            b.connect("clicked", lambda *_, s=sym: pick(s))
            grid.attach(b, i % 2, i // 2, 1, 1)

        vbox.pack_start(grid, True, True, 0)
        vbox.pack_start(Gtk.Label(label="Custom:"), False, False, 0)
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
        vbox.set_margin_start(16); vbox.set_margin_end(16)
        vbox.set_margin_top(14); vbox.set_margin_bottom(14)
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
        grid.set_margin_start(16); grid.set_margin_end(16)
        grid.set_margin_top(14); grid.set_margin_bottom(14)

        grid.attach(Gtk.Label(label="Name:"), 0, 0, 1, 1)
        name_e = Gtk.Entry(); name_e.set_placeholder_text("e.g. Web Root")
        grid.attach(name_e, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label="Path:"), 0, 1, 1, 1)
        path_e = Gtk.Entry(); path_e.set_placeholder_text("e.g. /var/www")
        grid.attach(path_e, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label="Icon:"), 0, 2, 1, 1)
        icon_e = Gtk.Entry(); icon_e.set_text("🌐")
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
        g.set_margin_start(16); g.set_margin_end(16)
        g.set_margin_top(12); g.set_margin_bottom(12)

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

    # ---------------------------------------------------------- KEY / EVENTS
    def _on_key_press(self, window: Gtk.Window, event: Gdk.EventKey) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self._exit()
            return True
        if event.keyval == Gdk.KEY_F5:
            self._refresh_info()
            return True
        if event.keyval == Gdk.KEY_Delete and self.selected_id:
            for item in self.desktop_items:
                if item.get("id") == self.selected_id and item.get("id") != "file_manager":
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
                env=env, cwd=ROOT,
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
            info["hostname"], info["os"],
            f"{info['cpu']} cores",
            f"{info['mem_used']} / {info['mem_total']}",
            f"{info['disk_used']} / {info['disk_total']}",
        ]
        for (_, v_label), value in zip(self.vps_rows, values):
            v_label.set_text(value)
        return True


def main() -> int:
    shell = DesktopShell()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
