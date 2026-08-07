"""Charlie Desktop Shell — the minimal desktop shown after `desktop` starts.

Renders the background, top bar (server name, clock, Exit Desktop), the
File Manager launcher icon and a compact VPS info panel.  Window management
is delegated to the lightweight window manager (openbox) started by the
session manager.
"""

from __future__ import annotations

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

COLORS = {
    "bg_top": "#161b29",
    "bg_bottom": "#0e121c",
    "fg": "#dce3f0",
    "dim": "#8a97ad",
    "accent": "#7aa2f7",
}

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
.icon-name { color: #f1f5f9; font-weight: 600; font-size: 14px; text-shadow: 0 1px 3px rgba(0,0,0,0.8); }
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
        self.current_font = 64

        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.window.get_style_context().add_class("shell")
        self.window.set_title("ease-Desk")
        self.window.set_decorated(False)
        self.window.set_default_size(1280, 800)
        self.window.fullscreen()
        self.window.connect("delete-event", self._on_delete_event)
        self.window.connect("key-press-event", self._on_key_press)

        self._load_css()
        self._build_ui()
        self._tick_clock()
        self._refresh_info()

        self.window.show_all()

        GLib.timeout_add_seconds(1, self._tick_clock)
        GLib.timeout_add_seconds(5, self._refresh_info)
        animate.fade_in(self.window, duration_ms=300)

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
        outer.pack_start(fixed, True, True, 0)
        self.fixed = fixed

        self.icon = self._build_icon()
        fixed.put(self.icon, 0, 0)

        self.info_panel = self._build_info_panel()
        fixed.put(self.info_panel, 0, 0)

        self.hint = Gtk.Label(label="Double-click the icon to open the File Manager")
        self.hint.get_style_context().add_class("hint")
        fixed.put(self.hint, 0, 0)

        self.window.add(outer)

        # Position children once the window has its final fullscreen size.
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

    def _build_icon(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_halign(Gtk.Align.CENTER)

        event = Gtk.EventBox()
        event.add(box)
        event.set_halign(Gtk.Align.CENTER)
        event.set_valign(Gtk.Align.CENTER)
        event.set_tooltip_text("File Manager — double-click to open")

        self.icon_label = Gtk.Label()
        self.icon_label.set_markup(f"<span font='{self.current_font}'>📁</span>")

        name = Gtk.Label(label="File Manager")
        name.get_style_context().add_class("icon-name")

        box.pack_start(self.icon_label, False, False, 0)
        box.pack_start(name, False, False, 0)

        event.connect("button-press-event", self._on_icon_click)
        event.connect("enter-notify-event", lambda *_: self._animate_hover(True))
        event.connect("leave-notify-event", lambda *_: self._animate_hover(False))
        return event

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

    # --------------------------------------------------------------- events
    def _on_resize(self, window, allocation) -> None:
        w, h = allocation.width, allocation.height
        icon_w = self.icon.get_preferred_width()[1]
        icon_h = self.icon.get_preferred_height()[1]
        icon_y = max(120, int(h * 0.25))
        self.fixed.move(self.icon, (w - icon_w) // 2, icon_y)

        hint_w = self.hint.get_preferred_width()[1]
        self.fixed.move(self.hint, (w - hint_w) // 2, icon_y + icon_h + 16)

        panel_h = self.info_panel.get_preferred_height()[1]
        self.fixed.move(self.info_panel, 20, max(20, h - panel_h - 75))

    def _on_icon_click(self, widget, event) -> bool:
        if event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 1:
            self._launch_file_manager()
            return True
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 1:
            self._animate_hover(True)
        return False

    def _on_key_press(self, window, event) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self._exit()
            return True
        return False

    def _on_delete_event(self, window, event) -> bool:
        self._exit()
        return True

    # -------------------------------------------------------------- actions
    def _launch_file_manager(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "file_manager", os.path.expanduser("~")],
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

    # --------------------------------------------------------------- timers
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

    def _animate_hover(self, growing: bool) -> None:
        target = 76 if growing else 64
        steps = 10
        start = self.current_font
        state = {"n": 0}

        def tick() -> bool:
            state["n"] += 1
            t = min(1.0, state["n"] / steps)
            size = int(start + (target - start) * (1 - (1 - t) ** 2))
            self.icon_label.set_markup(f"<span font='{size}'>📁</span>")
            if state["n"] >= steps:
                self.current_font = size
                return False
            return True

        GLib.timeout_add(12, tick)


def main() -> int:
    shell = DesktopShell()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
