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

from shared.utilities.wallpaper import hex_to_rgb
from shared.utilities.apps import AppDefinition

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf

# ── Optional: gtk-layer-shell ─────────────────────────────────────────────────
LAYER_SHELL = False
try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell
    LAYER_SHELL = True
except (ValueError, ImportError):
    pass

def _img(name: str, size: int = 24) -> Gtk.Image:
    try:
        from shared.utilities.icons import get_icon_pixbuf as _gpb
        pb = _gpb(name, size=size)
        if pb:
            return Gtk.Image.new_from_pixbuf(pb)
    except Exception:
        pass
    
    # Fallback if icons.py fails (e.g. missing python3-cairo)
    theme = Gtk.IconTheme.get_default()
    if theme:
        # Try finding the icon in standard names first
        for lookup_name in [name, name.replace('_', '-'), "text-x-generic"]:
            if theme.has_icon(lookup_name):
                try:
                    pb = theme.load_icon(lookup_name, size, Gtk.IconLookupFlags.FORCE_SIZE)
                    if pb:
                        return Gtk.Image.new_from_pixbuf(pb)
                except Exception:
                    continue
                    
    # Ultimate fallback, forces size via css or default scaling
    img = Gtk.Image.new_from_icon_name(name, Gtk.IconSize.DIALOG)
    img.set_pixel_size(size)
    return img

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


def _ensure_gtk_initialized() -> None:
    try:
        if hasattr(Gtk, "get_initialized") and Gtk.get_initialized():
            return
    except Exception:
        pass
    try:
        Gtk.init_check()
    except Exception:
        pass
    try:
        Gtk.init()
    except Exception:
        pass


class ShellApp:
    """Orchestrates all shell surfaces."""

    def __init__(self):
        _ensure_gtk_initialized()
        self.spotlight: SpotlightWindow | None = None
        self.dashboard: DashboardPanel | None = None
        self.start_btn = None
        self.desktop_items = []
        self.window = None
        self.wallpaper_path = None
        self.wallpaper_mode = "fill"
        self.solid_color = "#0b0e14"
        self.wallpaper_pixbuf = None
        self._cached_scaled_pixbuf = None
        self._cached_draw_params = None
        self._cached_offsets = (0, 0)
        self._cached_bg_rgb = hex_to_rgb(self.solid_color)
        self._config_mtime = 0.0
        self.pinned_buttons = {}
        self.pinned_indicators = {}
        self.tracked_processes = {}
        self.running_tasks_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.current_workspace = 1
        self.workspace_buttons = {}
        self._cal_window = None

        self._build_top_bar()
        self._build_left_dock()
        self._build_desktop_bg()

        if HAS_GAME_CHANGER:
            # Pass a lightweight proxy so panels can call back into us
            self.spotlight = SpotlightWindow(self)
            self.dashboard = DashboardPanel(self)

    def _compute_scaled_wallpaper(self, screen_w: int, screen_h: int):
        """Compatibility helper used by tests and wallpaper-related code."""
        self._cached_bg_rgb = hex_to_rgb(self.solid_color)

        if self.wallpaper_mode == "solid":
            self._cached_scaled_pixbuf = None
            self._cached_offsets = (0, 0)
            return

        pixbuf = self.wallpaper_pixbuf
        if pixbuf is None:
            self._cached_scaled_pixbuf = None
            self._cached_offsets = (0, 0)
            return

        src_w, src_h = pixbuf.get_width(), pixbuf.get_height()
        if src_w <= 0 or src_h <= 0:
            self._cached_scaled_pixbuf = None
            self._cached_offsets = (0, 0)
            return

        mode = self.wallpaper_mode
        if mode == "stretch":
            self._cached_scaled_pixbuf = pixbuf.scale_simple(screen_w, screen_h, GdkPixbuf.InterpType.BILINEAR)
            self._cached_offsets = (0, 0)
            return

        if mode == "center":
            self._cached_scaled_pixbuf = pixbuf.scale_simple(src_w, src_h, GdkPixbuf.InterpType.BILINEAR)
            self._cached_offsets = ((screen_w - src_w) // 2, (screen_h - src_h) // 2)
            return

        if mode == "fit":
            scale = min(screen_w / src_w, screen_h / src_h)
            dest_w = max(1, int(src_w * scale))
            dest_h = max(1, int(src_h * scale))
            self._cached_scaled_pixbuf = pixbuf.scale_simple(dest_w, dest_h, GdkPixbuf.InterpType.BILINEAR)
            self._cached_offsets = ((screen_w - dest_w) // 2, (screen_h - dest_h) // 2)
            return

        # default fill mode
        scale = max(screen_w / src_w, screen_h / src_h)
        dest_w = max(1, int(src_w * scale))
        dest_h = max(1, int(src_h * scale))
        self._cached_scaled_pixbuf = pixbuf.scale_simple(dest_w, dest_h, GdkPixbuf.InterpType.BILINEAR)
        self._cached_offsets = ((screen_w - dest_w) // 2, (screen_h - dest_h) // 2)

    def _set_wallpaper(self, path: str | None, mode: str = "fill", solid_color: str | None = None):
        self.wallpaper_path = path
        self.wallpaper_mode = mode
        if solid_color:
            self.solid_color = solid_color
        self._cached_bg_rgb = hex_to_rgb(self.solid_color)

    # ── Top bar ───────────────────────────────────────────────────────────────
    def _build_top_bar(self):
        self.top_win = Gtk.Window()
        self.top_win.set_title("easedesk-top-bar")
        self.top_win.set_decorated(False)
        self.top_win.set_resizable(False)
        self.top_win.set_type_hint(Gdk.WindowTypeHint.DOCK)
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
        self.start_btn = menu_btn
        left.pack_start(menu_btn, False, False, 0)
        bar.pack_start(left, False, False, 0)

        # Right side — tray icons + clock
        right = Gtk.Box(spacing=10)
        right.set_margin_end(14)

        self.pinned_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        right.pack_start(self.pinned_box, False, False, 0)
        self._build_pinned_apps()
        right.pack_start(self.running_tasks_box, False, False, 0)

        workspace_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        workspace_box.get_style_context().add_class("workspace-switcher")
        for workspace_id in range(1, 5):
            button = Gtk.Button.new_with_label(str(workspace_id))
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.set_tooltip_text(f"Workspace {workspace_id}")
            button.connect("clicked", self._switch_workspace, workspace_id)
            workspace_box.pack_start(button, False, False, 0)
            self.workspace_buttons[workspace_id] = button
        right.pack_start(workspace_box, False, False, 4)
        self._set_active_workspace(1)

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
        self.top_win.connect("key-press-event", self._on_key_press)

        self._update_clock()
        GLib.timeout_add_seconds(1, self._update_clock)

    def _build_pinned_apps(self):
        apps = (
            ("files", "Files", lambda: _launch(["python3", "-m", "file_manager.app"])),
            ("terminal", "Terminal", self._open_terminal),
            ("browser", "Web Browser", lambda: _launch(["epiphany"])),
            ("task_manager", "Task Manager", lambda: _launch(["python3", "-m", "desktop.task_manager.task_manager"])),
        )
        for app_id, tooltip, callback in apps:
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(_img(app_id, 18))
            button.set_tooltip_text(tooltip)
            button.connect("clicked", lambda *_args, cb=callback: cb())
            indicator = Gtk.Box()
            indicator.set_size_request(3, 3)
            indicator.get_style_context().add_class("pinned-indicator")
            self.pinned_box.pack_start(button, False, False, 0)
            self.pinned_buttons[app_id] = button
            self.pinned_indicators[app_id] = indicator

    def _update_running_tasks_ui(self):
        for child in self.running_tasks_box.get_children():
            self.running_tasks_box.remove(child)
        active_ids = {task.get("app_id") for task in self.tracked_processes.values()}
        for app_id, indicator in self.pinned_indicators.items():
            context = indicator.get_style_context()
            if app_id in active_ids:
                context.add_class("active")
            else:
                context.remove_class("active")
        for task in self.tracked_processes.values():
            label = Gtk.Label(label=task.get("title") or str(task.get("pid", "")))
            label.set_tooltip_text(task.get("title") or "Running task")
            self.running_tasks_box.pack_start(label, False, False, 0)
        self.running_tasks_box.show_all()

    def _toggle_calendar(self):
        if self._cal_window is not None:
            self._cal_window.destroy()
            self._cal_window = None
            return
        window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        window.set_title("Calendar")
        window.set_default_size(280, 240)
        window.set_position(Gtk.WindowPosition.CENTER)
        calendar = Gtk.Calendar()
        window.add(calendar)
        window.connect("destroy", self._calendar_closed)
        self._cal_window = window
        window.show_all()

    def _calendar_closed(self, _window):
        self._cal_window = None

    def _update_clock(self):
        now = datetime.datetime.now()
        self.clock_lbl.set_text(now.strftime("  %H:%M    %a %d %b  "))
        return True

    def _on_key_press(self, _widget, event):
        key = event.keyval
        if key == Gdk.KEY_Escape:
            if self.spotlight and self.spotlight.is_visible():
                self.spotlight.hide()
                return True
            if self.dashboard and self.dashboard.get_reveal_child():
                self.dashboard.set_reveal_child(False)
                return True
        if key in (Gdk.KEY_Super_L, Gdk.KEY_Super_R):
            self._toggle_spotlight()
            return True
        return False

    def _switch_workspace(self, _button, workspace_id: int):
        """Ask the compositor to change workspace; the shell remains stateless."""
        _launch(["swaymsg", "workspace", str(workspace_id)])
        self._set_active_workspace(workspace_id)

    def _set_active_workspace(self, workspace_id: int):
        if workspace_id not in self.workspace_buttons:
            return
        self.current_workspace = workspace_id
        for button_id, button in self.workspace_buttons.items():
            context = button.get_style_context()
            if button_id == workspace_id:
                context.add_class("active")
            else:
                context.remove_class("active")

    # ── Left dock ─────────────────────────────────────────────────────────────
    def _build_left_dock(self):
        self.dock_win = Gtk.Window()
        self.dock_win.set_title("easedesk-left-dock")
        self.dock_win.set_decorated(False)
        self.dock_win.set_resizable(False)
        self.dock_win.set_type_hint(Gdk.WindowTypeHint.DOCK)
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
        self.bg_win.set_title("easedesk-desktop-bg")
        self.bg_win.set_decorated(False)
        self.bg_win.set_resizable(False)
        self.bg_win.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
        # Solid dark background — no transparency needed
        self.bg_win.override_background_color(
            Gtk.StateFlags.NORMAL,
            Gdk.RGBA(0.02, 0.02, 0.07, 1.0),  # #050512
        )

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
            ("system-file-manager", "Files", 0, 0, "files",
             lambda: _launch(["python3", "-m", "file_manager.app"])),
            ("utilities-terminal", "Terminal", 0, 100, "terminal",
             lambda: self._open_terminal()),
            ("epiphany", "Browser", 0, 200, "browser",
             lambda: _launch(["epiphany"])),
            ("utilities-system-monitor", "Task Manager", 0, 300, "task_manager",
             lambda: _launch(["python3", "-m", "desktop.task_manager.task_manager"])),
        ]

        self.desktop_items = [{"id": item_id, "label": label, "icon": icon_name, "x": x, "y": y}
                              for icon_name, label, x, y, item_id, _ in icons]

        for icon_name, label, x, y, _item_id, cb in icons:
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
            elif app == "settings":
                _launch(["python3", "-m", "desktop.settings.app"])
            elif app == "wallpaper":
                self._dialog_change_wallpaper()
            elif app == "files":
                _launch(["python3", "-m", "file_manager.app"])
        elif path.startswith("thispc://"):
            _launch(["python3", "-m", "file_manager.app"])
        elif os.path.exists(path):
            _launch(["xdg-open", path])

    def _launch_application(self, application: AppDefinition):
        """Launch a registry entry without passing it through a shell."""
        _launch(list(application.exec_command))

    def _dialog_change_wallpaper(self):
        dialog = Gtk.MessageDialog(
            transient_for=self.bg_win,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Wallpaper settings",
        )
        dialog.format_secondary_text("Wallpaper selection will be available in Settings.")
        dialog.run()
        dialog.destroy()

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


class DesktopShell(ShellApp):
    """Backward-compatible shell entry point for older call sites and tests."""

    def __init__(self):
        super().__init__()
        self.window = self.bg_win


# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    settings = Gtk.Settings.get_default()
    if settings:
        settings.set_property("gtk-icon-theme-name", "Adwaita")
        settings.set_property("gtk-theme-name", "Adwaita")

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

    app = ShellApp()
    app.show_all()

    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
