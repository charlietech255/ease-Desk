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
import time
import logging
from pathlib import Path

LOG_DIR = Path.home() / ".cache" / "easedesk" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOG_DIR / "shell.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("DesktopShell")

import gi

from shared.utilities.wallpaper import hex_to_rgb
from desktop.shell.notify import NotificationManager
from desktop.shell.widgets import WidgetEngine
from shared.utilities.apps import AppDefinition, launcher_applications
from shared.config import preferences

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
    from desktop.shell.launcher import LauncherPanel
    from desktop.shell.lockscreen import LockScreen
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
        subprocess.Popen(
            cmd,
            start_new_session=True,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.error(f"[shell] launch error: {e}")
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
        self.locker: LockScreen | None = None
        self.start_btn = None
        self.desktop_items = []
        self.window = None
        self.wallpaper_path = preferences.get("Personalization", "wallpaper_path", "")
        if not self.wallpaper_path:
            # Fallback to our new premium default wallpaper
            default_wp = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "shared", "assets", "wallpapers", "default.jpg")
            if os.path.exists(default_wp):
                self.wallpaper_path = default_wp
        self.wallpaper_mode = preferences.get("Personalization", "wallpaper_mode", "fill")
        self.solid_color = preferences.get("Personalization", "solid_color", "#0b0e14")
        self.dock_position = preferences.get("Personalization", "dock_position", "left")
        self.wallpaper_pixbuf = None
        self.widget_engine = None
        
        # 1. Start notification daemon
        self.notify_manager = NotificationManager()

        # 2. Start game changer dashboard first so we can bind global hotkeys
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
        self.start_time = time.time()
        logger.info("Initializing DesktopShell UI components")

        self._build_top_bar()
        self._build_dock()
        self._build_desktop_bg()

        if HAS_GAME_CHANGER:
            # Pass a lightweight proxy so panels can call back into us
            self.spotlight = SpotlightWindow(self)
            self.dashboard = DashboardPanel(self)
            self.locker = LockScreen(self)
            
        self.widget_engine = WidgetEngine(self.bg_win)

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

        # Transparent background for floating pill effect
        screen = self.top_win.get_screen()
        visual = screen.get_rgba_visual()
        if visual and self.top_win.is_composited():
            self.top_win.set_visual(visual)
        self.top_win.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 0))

        panel_pos = preferences.get("Personalization", "panel_position", "top")

        if LAYER_SHELL:
            if panel_pos == "bottom":
                _layer(self.top_win, "TOP", ["BOTTOM", "LEFT", "RIGHT"], exclusive=True)
            else:
                _layer(self.top_win, "TOP", ["TOP", "LEFT", "RIGHT"], exclusive=True)
        else:
            w, h = _screen_size()
            self.top_win.set_size_request(w, TOP_BAR_H)
            if panel_pos == "bottom":
                self.top_win.move(0, h - TOP_BAR_H)
            else:
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
        pinned = preferences.get_pinned_apps()
        available_apps = {app.app_id: app for app in launcher_applications()}

        for app_id in pinned:
            if app_id not in available_apps:
                continue
            app = available_apps[app_id]
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(_img(app.icon, 18))
            button.set_tooltip_text(app.name)
            button.connect("clicked", lambda *_args, a=app: self._launch_application(a))
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
        fmt = "  %H:%M    %a %d %b  " if preferences.get("Personalization", "clock_format", "24h") == "24h" else "  %I:%M %p    %a %d %b  "
        self.clock_lbl.set_text(now.strftime(fmt))
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

    # ── Centered Bottom Dock ─────────────────────────────────────────────────────────────
    def _build_dock(self):
        self.dock_win = Gtk.Window()
        self.dock_win.set_title("easedesk-dock")
        self.dock_win.set_decorated(False)
        self.dock_win.set_resizable(False)
        self.dock_win.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.dock_win.set_keep_above(True)

        # Transparent background for the window so we can have floating margins
        screen = self.dock_win.get_screen()
        visual = screen.get_rgba_visual()
        if visual and self.dock_win.is_composited():
            self.dock_win.set_visual(visual)
        self.dock_win.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 0))

        if LAYER_SHELL:
            _layer(self.dock_win, "TOP", ["BOTTOM"], exclusive=False)
            GtkLayerShell.set_margin(self.dock_win, GtkLayerShell.Edge.BOTTOM, 16)
        else:
            w, h = _screen_size()
            self.dock_win.set_size_request(-1, -1)
            # Rough manual centering for Broadway testing (using an estimated dock width of 400px)
            self.dock_win.move(w // 2 - 200, h - 90)

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        outer.get_style_context().add_class("bottom-dock")
        self.dock_win.add(outer)

        dock = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        dock.set_margin_start(16)
        dock.set_margin_end(16)
        dock.set_margin_top(8)
        dock.set_margin_bottom(8)
        dock.set_valign(Gtk.Align.CENTER)
        dock.set_halign(Gtk.Align.CENTER)

        # App icons
        pinned = preferences.get_pinned_apps()
        available_apps = {app.app_id: app for app in launcher_applications()}

        for app_id in pinned:
            if app_id not in available_apps:
                continue
            app = available_apps[app_id]
            btn = Gtk.Button()
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.get_style_context().add_class("dock-btn")
            btn.add(_img(app.icon, 52)) # Larger icon size for the new premium dock
            btn.set_tooltip_text(app.name)
            btn.connect("clicked", lambda *_, a=app: self._launch_application(a))
            dock.pack_start(btn, False, False, 0)

        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.get_style_context().add_class("dock-sep")
        dock.pack_start(sep, False, False, 12)

        # Power button at right edge
        power_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        power_box.set_valign(Gtk.Align.CENTER)
        power_box.set_margin_end(16)

        pwr = Gtk.Button()
        pwr.set_relief(Gtk.ReliefStyle.NONE)
        pwr.get_style_context().add_class("dock-btn")
        pwr.add(_img("system-shutdown", 28))
        pwr.connect("clicked", lambda *_: self._launch(["systemctl", "poweroff"]))
        pwr.set_tooltip_text("Power Off")

        power_box.pack_start(pwr, False, False, 0)

        outer.pack_start(dock, True, True, 0)
        outer.pack_end(power_box, False, False, 0)

    # ── Desktop background ────────────────────────────────────────────────────
    def _build_desktop_bg(self):
        self.bg_win = Gtk.Window()
        self.bg_win.set_title("easedesk-desktop-bg")
        self.bg_win.set_decorated(False)
        self.bg_win.set_resizable(False)
        self.bg_win.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
        self.bg_win.set_app_paintable(True)
        
        # Connect the draw signal to render wallpaper
        self.bg_win.connect("draw", self._draw_bg)

        try:
            self.wallpaper_pixbuf = GdkPixbuf.Pixbuf.new_from_file(self.wallpaper_path) if self.wallpaper_path else None
        except Exception as e:
            logger.error(f"Failed to load wallpaper: {e}")
            self.wallpaper_pixbuf = None

        self._compute_scaled_wallpaper(*_screen_size())

        if LAYER_SHELL:
            _layer(self.bg_win, "BACKGROUND", ["TOP", "BOTTOM", "LEFT", "RIGHT"])
        else:
            self.bg_win.set_keep_below(True)
            w, h = _screen_size()
            self.bg_win.set_size_request(w, h)
            self.bg_win.move(0, 0)

        # Removed the desktop icon grid to provide a clean, modern desktop experience 
        # that highlights the premium wallpaper. Applications are launched via the dock.

    def _draw_bg(self, widget, cr):
        # Draw solid color first
        if hasattr(self, '_cached_bg_rgb'):
            r, g, b = self._cached_bg_rgb
            cr.set_source_rgb(r, g, b)
            cr.paint()
            
        # Draw wallpaper if it exists
        if hasattr(self, '_cached_scaled_pixbuf') and self._cached_scaled_pixbuf:
            ox, oy = getattr(self, '_cached_offsets', (0, 0))
            Gdk.cairo_set_source_pixbuf(cr, self._cached_scaled_pixbuf, ox, oy)
            cr.paint()
        return False

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
                _launch(["python3", "-m", "desktop.task_manager.app"])
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

    def _launch_application(self, app: AppDefinition):
        logger.info(f"Launching application: {app.name} ({app.app_id})")
        cmd = list(app.exec_command)
        
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
            logger.info(f"Successfully spawned {app.app_id} (PID {proc.pid})")
            
            self.tracked_processes[proc.pid] = {
                "pid": proc.pid,
                "app_id": app.app_id,
                "title": app.name,
                "icon_key": app.icon,
                "popen": proc
            }
            self._update_running_tasks_ui()
            
        except Exception as e:
            logger.error(f"Failed to launch {app.name}: {e}")
            print(f"Failed to launch {app.name}: {e}")

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
        """Invoke external screenshot utility."""
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "capture_screenshots.py")
        if os.path.exists(script_path):
            subprocess.Popen(["python3", script_path])
            
    def _lock_screen(self):
        """Lock the desktop session."""
        if self.dashboard and self.dashboard.get_reveal_child():
            self.dashboard.toggle()
        if self.locker:
            self.locker.lock()

    def _exit(self):
        logger.info("Exiting session...")
        try:
            subprocess.Popen(["swaymsg", "exit"])
        except Exception as e:
            logger.error(f"Error during exit: {e}")
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
                subprocess.Popen(
                    cmd,
                    cwd=root,
                    start_new_session=True,
                    close_fds=True,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except (FileNotFoundError, OSError):
                continue

    def show_all(self):
        self.bg_win.show_all()
        self.top_win.show_all()
        self.dock_win.show_all()


class DesktopShell(ShellApp):
    """Backward-compatible shell entry point for older call sites and tests."""

    def __init__(self):
        super().__init__()
        self.window = self.bg_win
        if not LAYER_SHELL:
            self.window.connect("configure-event", self._on_configure_event)

    def _on_configure_event(self, widget, event):
        w, h = _screen_size()
        self.top_win.set_size_request(w, TOP_BAR_H)
        self.dock_win.set_size_request(DOCK_W, h - TOP_BAR_H)
        self.dock_win.move(0, TOP_BAR_H)
        self.bg_win.set_size_request(w - DOCK_W, h - TOP_BAR_H)
        self.bg_win.move(DOCK_W, TOP_BAR_H)
        return False


# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    logger.info("Starting ease-Desk Shell")
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

    app = DesktopShell()
    app.show_all()

    Gtk.main()
    logger.info("ease-Desk Shell exited gracefully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
