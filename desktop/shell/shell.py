"""ease-Desk Desktop Shell — Resilient Wayland/X11 Edition.

Tries to use gtk-layer-shell for a proper Wayland compositor overlay.
If the library is not available, falls back to plain Gtk.Window which
will still work inside a Wayland session (XWayland or native).
"""

import os
import sys
import subprocess
import datetime
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

# ── Optional: gtk-layer-shell (Wayland layer surface protocol) ────────────────
LAYER_SHELL_AVAILABLE = False
try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell as _GLS  # noqa: F401
    LAYER_SHELL_AVAILABLE = True
except (ValueError, ImportError):
    pass

# ── Optional: icon helper ─────────────────────────────────────────────────────
try:
    from shared.utilities.icons import get_icon_pixbuf as _get_icon_pixbuf
    def _icon(name: str, size: int = 24):
        try:
            return Gtk.Image.new_from_pixbuf(_get_icon_pixbuf(name, size=size))
        except Exception:
            return Gtk.Image.new_from_icon_name(name, Gtk.IconSize.LARGE_TOOLBAR)
except Exception:
    def _icon(name: str, size: int = 24):
        return Gtk.Image.new_from_icon_name(name, Gtk.IconSize.LARGE_TOOLBAR)


def _init_layer(win, layer, anchors: list[str], exclusive: bool = False):
    """Attach a Gtk.Window to a Wayland layer if GtkLayerShell is available."""
    if not LAYER_SHELL_AVAILABLE:
        return
    from gi.repository import GtkLayerShell
    GtkLayerShell.init_for_window(win)
    GtkLayerShell.set_layer(win, layer)
    if exclusive:
        GtkLayerShell.auto_exclusive_zone_enable(win)
    for edge_name in anchors:
        edge = getattr(GtkLayerShell.Edge, edge_name)
        GtkLayerShell.set_anchor(win, edge, True)


# ─────────────────────────────────────────────────────────────────────────────
class TopBar(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)

        if LAYER_SHELL_AVAILABLE:
            from gi.repository import GtkLayerShell
            _init_layer(self, GtkLayerShell.Layer.TOP,
                        ["TOP", "LEFT", "RIGHT"], exclusive=True)
        else:
            # Plain window — position at top of screen
            self.move(0, 0)
            screen = Gdk.Screen.get_default()
            self.set_size_request(screen.get_width() if screen else 1920, 32)

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bar.get_style_context().add_class("top-bar")
        bar.set_size_request(-1, 32)

        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        right_box.set_margin_end(16)

        right_box.pack_start(_icon("network-wireless", 16), False, False, 0)
        right_box.pack_start(_icon("battery-good", 16), False, False, 0)

        self.clock_label = Gtk.Label(label="")
        right_box.pack_start(self.clock_label, False, False, 0)

        bar.pack_end(right_box, False, False, 0)
        self.add(bar)

        # Start clock tick
        self._update_clock()
        GLib.timeout_add_seconds(1, self._update_clock)

    def _update_clock(self):
        now = datetime.datetime.now()
        self.clock_label.set_text(now.strftime("%H:%M  %d %b"))
        return True  # keep repeating


# ─────────────────────────────────────────────────────────────────────────────
class LeftDock(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)

        if LAYER_SHELL_AVAILABLE:
            from gi.repository import GtkLayerShell
            _init_layer(self, GtkLayerShell.Layer.TOP,
                        ["LEFT", "TOP", "BOTTOM"], exclusive=True)
        else:
            self.move(0, 32)
            screen = Gdk.Screen.get_default()
            h = (screen.get_height() - 32) if screen else 1048
            self.set_size_request(56, h)

        dock = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        dock.get_style_context().add_class("left-dock")
        dock.set_margin_start(8)
        dock.set_margin_top(16)
        dock.set_valign(Gtk.Align.START)

        file_btn = Gtk.Button()
        file_btn.add(_icon("system-file-manager", 24))
        file_btn.get_style_context().add_class("left-dock-btn")
        file_btn.connect(
            "clicked",
            lambda *_: subprocess.Popen(
                ["python3", "-m", "file_manager.app"],
                cwd=os.environ.get("PYTHONPATH", "/opt/ease-desk"),
            ),
        )
        file_btn.set_tooltip_text("File Manager")

        term_btn = Gtk.Button()
        term_btn.add(_icon("utilities-terminal", 24))
        term_btn.get_style_context().add_class("left-dock-btn")
        term_btn.connect(
            "clicked",
            lambda *_: self._open_terminal(),
        )
        term_btn.set_tooltip_text("Terminal")

        pwr_btn = Gtk.Button()
        pwr_btn.add(_icon("system-shutdown", 24))
        pwr_btn.get_style_context().add_class("left-dock-btn")
        pwr_btn.connect("clicked", lambda *_: sys.exit(0))
        pwr_btn.set_tooltip_text("Shutdown Session")

        dock.pack_start(file_btn, False, False, 0)
        dock.pack_start(term_btn, False, False, 0)
        dock.pack_end(pwr_btn, False, False, 0)
        self.add(dock)

    @staticmethod
    def _open_terminal():
        """Try several terminal emulators in order of preference."""
        for term in ("python3 -m desktop.terminal.app", "xterm", "xfce4-terminal", "gnome-terminal"):
            cmd = term.split()
            if cmd[0] == "python3" or subprocess.run(
                ["which", cmd[0]], capture_output=True
            ).returncode == 0:
                try:
                    subprocess.Popen(cmd)
                    return
                except OSError:
                    continue


# ─────────────────────────────────────────────────────────────────────────────
class DesktopBackground(Gtk.Window):
    """A borderless full-screen background window with desktop icons."""

    def __init__(self):
        super().__init__()
        self.set_decorated(False)
        self.set_resizable(False)

        if LAYER_SHELL_AVAILABLE:
            from gi.repository import GtkLayerShell
            _init_layer(self, GtkLayerShell.Layer.BACKGROUND,
                        ["TOP", "BOTTOM", "LEFT", "RIGHT"])
        else:
            self.move(56, 32)          # leave room for dock + topbar
            screen = Gdk.Screen.get_default()
            w = (screen.get_width() - 56) if screen else 1864
            h = (screen.get_height() - 32) if screen else 1048
            self.set_size_request(w, h)
            self.set_keep_below(True)

        self.fixed = Gtk.Fixed()
        self.fixed.set_margin_start(16)
        self.fixed.set_margin_top(16)

        self._add_icon(
            "Files", "system-file-manager", 0, 0,
            lambda: subprocess.Popen(["python3", "-m", "file_manager.app"])
        )
        self._add_icon(
            "Terminal", "utilities-terminal", 0, 100,
            LeftDock._open_terminal,
        )

        self.add(self.fixed)

    def _add_icon(self, name: str, icon_name: str, x: int, y: int, callback):
        btn = Gtk.Button()
        btn.get_style_context().add_class("icon-btn")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        img = _icon(icon_name, 48)
        lbl = Gtk.Label(label=name)
        box.pack_start(img, False, False, 0)
        box.pack_start(lbl, False, False, 0)
        btn.add(box)
        btn.connect("clicked", lambda *_: callback())
        self.fixed.put(btn, x, y)


# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    # ── CSS theme ─────────────────────────────────────────────────────────────
    provider = Gtk.CssProvider()
    css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "theme.css")
    if os.path.exists(css_path):
        provider.load_from_path(css_path)
        screen = Gdk.Screen.get_default()
        if screen:
            Gtk.StyleContext.add_provider_for_screen(
                screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    top = TopBar()
    dock = LeftDock()
    bg = DesktopBackground()

    top.show_all()
    dock.show_all()
    bg.show_all()

    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
