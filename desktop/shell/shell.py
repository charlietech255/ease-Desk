"""ease-Desk Desktop Shell — Premium Dark UI Edition.

Full compositor shell with:
- Slim top bar with clock + system tray area + dashboard trigger
- Slim left icon dock with tooltips + separator
- Spotlight search (Super key)
- Quick-settings dashboard slide-in panel
- Desktop icon grid
- GtkLayerShell optional — graceful fallback on plain Wayland/X11
"""

import datetime
import os
import subprocess
import sys
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

# ── Optional: gtk-layer-shell ─────────────────────────────────────────────────
LAYER_SHELL = False
try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell
    LAYER_SHELL = True
except (ValueError, ImportError):
    pass

# ── Optional: icon helper ─────────────────────────────────────────────────────
try:
    from shared.utilities.icons import get_icon_pixbuf as _gpb

    def _img(name: str, size: int = 24) -> Gtk.Image:
        try:
            return Gtk.Image.new_from_pixbuf(_gpb(name, size=size))
        except Exception:
            return Gtk.Image.new_from_icon_name(name, Gtk.IconSize.LARGE_TOOLBAR)
except Exception:
    def _img(name: str, size: int = 24) -> Gtk.Image:
        return Gtk.Image.new_from_icon_name(name, Gtk.IconSize.LARGE_TOOLBAR)

# ── Optional: game_changer panels ─────────────────────────────────────────────
try:
    from desktop.shell.game_changer import SpotlightWindow, DashboardPanel
    HAS_GAME_CHANGER = True
except Exception:
    HAS_GAME_CHANGER = False


# ─────────────────────────────────────────────────────────────────────────────
def _layer(win, layer_name: str, edges: list[str], exclusive: bool = False):
    """Apply gtk-layer-shell anchors if available."""
    if not LAYER_SHELL:
        return
    layer_map = {
        "TOP": GtkLayerShell.Layer.TOP,
        "BOTTOM": GtkLayerShell.Layer.BOTTOM,
        "BACKGROUND": GtkLayerShell.Layer.BACKGROUND,
    }
    edge_map = {
        "TOP": GtkLayerShell.Edge.TOP,
        "BOTTOM": GtkLayerShell.Edge.BOTTOM,
        "LEFT": GtkLayerShell.Edge.LEFT,
        "RIGHT": GtkLayerShell.Edge.RIGHT,
    }
    GtkLayerShell.init_for_window(win)
    GtkLayerShell.set_layer(win, layer_map[layer_name])
    if exclusive:
        GtkLayerShell.auto_exclusive_zone_enable(win)
    for e in edges:
        GtkLayerShell.set_anchor(win, edge_map[e], True)


def _screen_size():
    screen = Gdk.Screen.get_default()
    if screen:
        return screen.get_width(), screen.get_height()
    return 1920, 1080


def _launch(cmd: list[str]):
    try:
        subprocess.Popen(cmd, start_new_session=True)
    except Exception as e:
        print(f"[shell] launch error: {e}", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────────────────
TOP_BAR_H = 36
DOCK_W = 60


class ShellApp:
    """Orchestrates all shell surfaces."""

    def __init__(self):
        self.spotlight: SpotlightWindow | None = None
        self.dashboard: DashboardPanel | None = None

        self._build_top_bar()
        self._build_left_dock()
        self._build_desktop_bg()

        if HAS_GAME_CHANGER:
            # Pass a lightweight proxy so panels can call back into us
            self.spotlight = SpotlightWindow(self)
            self.dashboard = DashboardPanel(self)

    # ── Top bar ───────────────────────────────────────────────────────────────
    def _build_top_bar(self):
        self.top_win = Gtk.Window()
        self.top_win.set_decorated(False)
        self.top_win.set_resizable(False)
        self.top_win.set_keep_above(True)

        if LAYER_SHELL:
            _layer(self.top_win, "TOP", ["TOP", "LEFT", "RIGHT"], exclusive=True)
        else:
            w, _ = _screen_size()
            self.top_win.set_size_request(w, TOP_BAR_H)
            self.top_win.move(0, 0)

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        bar.get_style_context().add_class("top-bar")
        bar.set_size_request(-1, TOP_BAR_H)

        # Left side — app menu hint
        left = Gtk.Box(spacing=8)
        left.set_margin_start(12)
        menu_btn = Gtk.Button()
        menu_btn.set_relief(Gtk.ReliefStyle.NONE)
        menu_btn.add(_img("application-x-executable", 16))
        menu_btn.get_style_context().add_class("left-dock-btn")
        menu_btn.set_tooltip_text("Applications (Super)")
        menu_btn.connect("clicked", lambda *_: self._toggle_spotlight())
        left.pack_start(menu_btn, False, False, 0)
        bar.pack_start(left, False, False, 0)

        # Right side — tray icons + clock
        right = Gtk.Box(spacing=10)
        right.set_margin_end(14)

        # Network icon
        net_img = _img("network-wireless", 16)
        net_img.get_style_context().add_class("topbar-icon")
        right.pack_start(net_img, False, False, 0)

        # Clock — clicking opens dashboard
        self.clock_lbl = Gtk.Label()
        self.clock_lbl.get_style_context().add_class("topbar-clock")
        self.clock_lbl.set_tooltip_text("Quick Settings")

        clock_btn = Gtk.Button()
        clock_btn.set_relief(Gtk.ReliefStyle.NONE)
        clock_btn.get_style_context().add_class("left-dock-btn")
        clock_btn.add(self.clock_lbl)
        clock_btn.connect("clicked", lambda *_: self._toggle_dashboard())
        right.pack_start(clock_btn, False, False, 0)

        bar.pack_end(right, False, False, 0)
        self.top_win.add(bar)

        self._update_clock()
        GLib.timeout_add_seconds(1, self._update_clock)

    def _update_clock(self):
        now = datetime.datetime.now()
        self.clock_lbl.set_text(now.strftime("  %H:%M    %a %d %b  "))
        return True

    # ── Left dock ─────────────────────────────────────────────────────────────
    def _build_left_dock(self):
        self.dock_win = Gtk.Window()
        self.dock_win.set_decorated(False)
        self.dock_win.set_resizable(False)
        self.dock_win.set_keep_above(True)

        if LAYER_SHELL:
            _layer(self.dock_win, "TOP", ["LEFT", "TOP", "BOTTOM"], exclusive=True)
        else:
            _, h = _screen_size()
            self.dock_win.set_size_request(DOCK_W, h - TOP_BAR_H)
            self.dock_win.move(0, TOP_BAR_H)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.get_style_context().add_class("left-dock")

        dock = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        dock.set_margin_top(10)
        dock.set_margin_bottom(10)
        dock.set_vexpand(True)
        dock.set_valign(Gtk.Align.START)

        # App icons
        apps = [
            ("system-file-manager", "File Manager",
             lambda: _launch(["python3", "-m", "file_manager.app"])),
            ("utilities-terminal", "Terminal",
             lambda: self._open_terminal()),
            ("epiphany", "Web Browser",
             lambda: _launch(["epiphany"])),
            ("system-run", "Task Manager",
             lambda: _launch(["python3", "-m", "desktop.task_manager.task_manager"])),
        ]

        for icon_name, tooltip, cb in apps:
            btn = Gtk.Button()
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.get_style_context().add_class("left-dock-btn")
            btn.add(_img(icon_name, 22))
            btn.set_tooltip_text(tooltip)
            btn.connect("clicked", lambda *_, c=cb: c())
            dock.pack_start(btn, False, False, 0)

        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.get_style_context().add_class("dock-sep")
        dock.pack_start(sep, False, False, 6)

        # Power button at bottom
        power_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        power_box.set_vexpand(True)
        power_box.set_valign(Gtk.Align.END)
        power_box.set_margin_bottom(10)

        pwr = Gtk.Button()
        pwr.set_relief(Gtk.ReliefStyle.NONE)
        pwr.get_style_context().add_class("left-dock-btn-power")
        pwr.add(_img("system-shutdown", 20))
        pwr.set_tooltip_text("End Session")
        pwr.connect("clicked", lambda *_: self._exit())
        power_box.pack_end(pwr, False, False, 0)

        outer.pack_start(dock, True, True, 0)
        outer.pack_end(power_box, False, False, 0)
        self.dock_win.add(outer)

    # ── Desktop background ────────────────────────────────────────────────────
    def _build_desktop_bg(self):
        self.bg_win = Gtk.Window()
        self.bg_win.set_decorated(False)
        self.bg_win.set_resizable(False)

        if LAYER_SHELL:
            _layer(self.bg_win, "BACKGROUND", ["TOP", "BOTTOM", "LEFT", "RIGHT"])
        else:
            self.bg_win.set_keep_below(True)
            w, h = _screen_size()
            self.bg_win.set_size_request(w - DOCK_W, h - TOP_BAR_H)
            self.bg_win.move(DOCK_W, TOP_BAR_H)

        fixed = Gtk.Fixed()
        fixed.set_margin_start(20)
        fixed.set_margin_top(20)

        icons = [
            ("system-file-manager", "Files", 0, 0,
             lambda: _launch(["python3", "-m", "file_manager.app"])),
            ("utilities-terminal", "Terminal", 0, 100,
             lambda: self._open_terminal()),
            ("epiphany", "Browser", 0, 200,
             lambda: _launch(["epiphany"])),
        ]

        for icon_name, label, x, y, cb in icons:
            btn = Gtk.Button()
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.get_style_context().add_class("icon-btn")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            box.set_halign(Gtk.Align.CENTER)

            img = _img(icon_name, 48)
            img.set_halign(Gtk.Align.CENTER)

            lbl = Gtk.Label(label=label)
            lbl.get_style_context().add_class("icon-name")
            lbl.set_halign(Gtk.Align.CENTER)

            box.pack_start(img, False, False, 0)
            box.pack_start(lbl, False, False, 0)
            btn.add(box)
            btn.connect("clicked", lambda *_, c=cb: c())
            fixed.put(btn, x, y)

        self.bg_win.add(fixed)

    # ── Actions ───────────────────────────────────────────────────────────────
    def _toggle_spotlight(self):
        if self.spotlight:
            self.spotlight.toggle()

    def _toggle_dashboard(self):
        if self.dashboard:
            self.dashboard.toggle()

    def _launch_path(self, path: str):
        """Called by SpotlightWindow to open things."""
        if path.startswith("app://"):
            app = path[6:]
            if app == "terminal":
                self._open_terminal()
            elif app == "browser":
                _launch(["epiphany"])
            elif app == "task_manager":
                _launch(["python3", "-m", "desktop.task_manager.task_manager"])
            elif app == "files":
                _launch(["python3", "-m", "file_manager.app"])
        elif path.startswith("thispc://"):
            _launch(["python3", "-m", "file_manager.app"])
        elif os.path.exists(path):
            _launch(["xdg-open", path])

    def _dialog_change_wallpaper(self):
        pass  # Future

    def _dialog_add_shortcut(self):
        pass  # Future

    def _take_screenshot(self):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.expanduser(f"~/screenshot_{ts}.png")
        for cmd in (["grim", path], ["scrot", path]):
            try:
                subprocess.Popen(cmd)
                return
            except FileNotFoundError:
                continue

    def _exit(self):
        Gtk.main_quit()
        sys.exit(0)

    @staticmethod
    def _open_terminal():
        root = os.environ.get("PYTHONPATH", "/opt/ease-desk").split(":")[0]
        for cmd in (
            ["python3", "-m", "desktop.terminal.app"],
            ["xterm"],
            ["xfce4-terminal"],
            ["bash", "-c", "xterm || true"],
        ):
            try:
                subprocess.Popen(cmd, cwd=root, start_new_session=True)
                return
            except (FileNotFoundError, OSError):
                continue

    def show_all(self):
        self.top_win.show_all()
        self.dock_win.show_all()
        self.bg_win.show_all()


# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    # ── Load CSS theme ────────────────────────────────────────────────────────
    provider = Gtk.CssProvider()
    css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "theme.css")
    if os.path.exists(css_path):
        provider.load_from_path(css_path)
        screen = Gdk.Screen.get_default()
        if screen:
            Gtk.StyleContext.add_provider_for_screen(
                screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    # ── Enable compositor transparency ────────────────────────────────────────
    screen = Gdk.Screen.get_default()
    if screen and screen.get_rgba_visual():
        Gtk.Widget.set_default_visual(screen.get_rgba_visual())

    app = ShellApp()
    app.show_all()

    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
